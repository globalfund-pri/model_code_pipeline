import math
import warnings
from copy import copy
from typing import Dict, Iterable, NamedTuple, Optional, Union, List

import pandas as pd
from pathlib import Path

from scripts.ic8.shared.create_frontier import filter_for_frontier
from tgftools.approach_b import ApproachB
from tgftools.database import Database
from tgftools.dump_analysis_to_excel import DumpAnalysisToExcel
from tgftools.emulator import Emulator
from tgftools.filehandler import Gp, NonTgfFunding, Parameters, TgfFunding, RegionInformation
from tgftools.utils import matmul

"""Analysis module for investment case modeling.

This module provides the Analysis class, which extracts and processes model outputs,
performs necessary adjustments, and generates key statistics and graphs for reports.

Required Inputs
---------------
1. Database containing model data, partner data, partner framework data, and non-modeled
   Global Plan data (from disease-specific filehandler scripts)
2. Scenario to be analyzed (defined in disease-specific analysis scripts)
3. TGF and non-TGF funding amounts, with options to include or exclude unallocated amounts
   (computed outside the MCP in disease-specific analysis scripts)
4. Years of replenishment period (defined in parameters.toml)
5. How to handle out-of-bounds costs (defined in disease-specific scripts)
6. Parameters for computing confidence intervals, including z-value and rho-value
   (variation between countries within disease, defined in parameters.toml)

Funding Allocation Approaches
------------------------------
The class computes country and portfolio-level results using three approaches:

**Approach A**: Uses country-specific funding envelopes (domestic + non-TGF + TGF funding)
to interpolate exact amounts from cost-impact curves, along with corresponding cases and deaths.

**Approach B**: Optimizes allocation of (i) Global Fund or (ii) Global Fund and unallocated
amounts across countries within diseases. The option to include or exclude unallocated amounts
is configurable.

**Approach C**: Applies uniform funding fraction across all countries.

Processing Steps
----------------
The Analysis class performs the following operations in sequence:

1. **Country-level projections**: Emulates country-specific projections for all variables
   (epidemiological and service-related) given the funding and scenario inputs. Only applies
   to investment case scenarios, not counterfactuals.

2. **Baseline adjustment**: Adjusts country-level projections to baseline partner data where
   available. If partner data is missing for specific variables (e.g., number of people on ART),
   model projections are retained without adjustment.

   .. note::
      It is crucial to have partner data for all variables in the model output. If population
      estimates are adjusted but treatment numbers are not, coverage estimates will be skewed.
      HIV was not adjusted for baseline partner data, only TB and malaria.

3. **Portfolio-level aggregation**: Sums variables across countries to generate portfolio-level
   projections.

   .. note::
      Fractions cannot be summed directly; numerators and denominators are summed instead and
      fractions are recalculated in the report class.

4. **Confidence intervals**: Generates portfolio-level uncertainty from country-level uncertainty
   using parameters defined in the parameter file.

5. **Innovation adjustment**: Applies a curve (e.g., sigmoidal) to adjust investment case
   projections for missing impact within the partner Global Plan that will be accounted for
   by innovation.

   .. note::
      The original curve parameters were overwritten in the parameter file to ensure it starts
      at zero in 2020 and reaches one in 2030. HIV was not adjusted for innovation, only TB
      and malaria.

Output Structure
----------------
The class generates a SetOfPortfolioProjections containing:

1. Investment case data with all aforementioned processing applied
2. Various counterfactuals (disease-specific), including counterfactuals for lives saved
   and infections averted
3. Data for key graphs, including partner data and disease-specific global plans

Important Configuration Notes
------------------------------
* The `load_data_from_raw_file` option (in disease-specific and HTM scripts) controls whether
  model output is reloaded. If set to False, filehandler updates will not be reflected.
* The approach selection (A, B, or C) is set in both the HTM script and disease-specific
  analysis scripts and affects the resulting output.
* Scenario, funding amount, and domestic scenario settings (in disease-specific scripts)
  will affect the resulting output.
"""


class CountryProjection(NamedTuple):
    """Container for country-level projection results.

    Attributes:
        model_projection: Dictionary mapping indicator names to DataFrames containing
            model projections. Each DataFrame has years as the index and columns for
            central, low, and high estimates.
        funding: Total funding amount (in dollars) for the country.
    """

    model_projection: Dict[str, pd.DataFrame]
    funding: float


class PortfolioProjection(NamedTuple):
    """Container for portfolio-level analysis results.

    Attributes:
        tgf_funding_by_country: Dictionary mapping ISO3 country codes to TGF funding amounts.
        non_tgf_funding_by_country: Dictionary mapping ISO3 country codes to non-TGF
            funding amounts.
        country_results: Dictionary mapping ISO3 country codes to CountryProjection objects
            containing country-level results.
        portfolio_results: Dictionary mapping indicator names to DataFrames with portfolio-level
            results. Each DataFrame has years as rows and columns for central/low/high estimates
            across the entire portfolio, including all adjustments.
    """

    tgf_funding_by_country: dict[str, float]
    non_tgf_funding_by_country: dict[str, float]
    country_results: dict[str, CountryProjection]
    portfolio_results: dict[str, pd.DataFrame]


class Analysis:
    """Performs investment case analysis for disease modeling.

    This class holds a Database object and produces ensemble or country-level results
    that reflect funding allocation decisions. It supports multiple approaches for
    allocating TGF funding: when funding is non-fungible (Approach A), when it is
    fungible and can be optimized across countries (Approach B), or when a uniform
    funding fraction is applied (Approach C).

    Attributes:
        database: Database object containing all model and partner data.
        parameters: Parameters object with configuration settings.
        tgf_funding: TGF funding allocations by country.
        non_tgf_funding: Non-TGF funding allocations by country.
        gp: Global Plan data.
        countries: List of modeled countries.
        disease_name: Name of the disease being analyzed.
        indicators: DataFrame of indicators for this disease.
        scenario_descriptor: Scenario being analyzed for the investment case.
        handle_out_of_bounds_costs: Whether to handle costs outside model range by using
            boundary values (True) or raising an error (False).
        innovation_on: Whether to apply innovation adjustments.
        years_for_funding: Calendar years corresponding to the replenishment period.
        emulators: Dictionary mapping country codes to Emulator objects.
        region_info: RegionInformation object for country groupings.
        country_subset: List of country codes for the current analysis subset.

    Args:
        database: Database object containing model results, partner data, and Global Plan data.
        tgf_funding: TGF funding object with country-level allocations.
        non_tgf_funding: Non-TGF funding object with country-level allocations.
        parameters: Parameters object containing configuration settings from parameters.toml.
    """

    def __init__(
        self,
        database: Database,
        tgf_funding: TgfFunding,
        non_tgf_funding: NonTgfFunding,
        parameters: Parameters,
    ):
        # Save arguments (nb, funding data are updated again later in __init__)
        self.database = database
        self.parameters = parameters
        self.tgf_funding = tgf_funding
        self.non_tgf_funding = non_tgf_funding

        # Save short-cuts to elements of the database.
        self.gp: Gp = database.gp
        self.countries = database.model_results.countries

        # Store some parameters for easy access
        self.disease_name = self.database.disease_name
        self.indicators = self.parameters.get_indicators_for(self.disease_name)
        self.scenario_descriptor = parameters.get('SCENARIO_DESCRIPTOR_FOR_IC')
        self.handle_out_of_bounds_costs = parameters.get('HANDLE_OUT_OF_BOUNDS_COSTS')
        self.innovation_on = parameters.get('INNOVATION_ON')
        self.years_for_funding = self.parameters.get('YEARS_FOR_FUNDING')
        self.indicators_for_adj_for_innovations = self.parameters.get(self.disease_name).get(
            'INDICATORS_FOR_ADJ_FOR_INNOVATIONS')
        self.EXPECTED_GP_SCENARIO = self.parameters.get_gpscenario().index.to_list()

        # Filter funding assumptions for countries that are not modelled
        self.tgf_funding = self.filter_funding_data_for_non_modelled_countries(self.tgf_funding)
        self.non_tgf_funding = self.filter_funding_data_for_non_modelled_countries(self.non_tgf_funding)

        # If we should remove the dominated points, edit the model results accordingly:
        if self.parameters.get('REMOVE_DOMINATED_POINTS'):
            self.database.model_results = filter_for_frontier(
                model_results=self.database.model_results,
                scenario_descriptor=self.scenario_descriptor,
                years_for_obj_func=parameters.get("YEARS_FOR_OBJ_FUNC"),
                years_for_funding=parameters.get("YEARS_FOR_FUNDING"),
            )

        # Create emulators for each country so that results can be created for any cost (within the range of actual
        # results).
        self.emulators: dict = {
            c: Emulator(
                database=self.database,
                scenario_descriptor=self.scenario_descriptor,
                country=c,
                years_for_funding=self.years_for_funding,
                handle_out_of_bounds_costs=self.handle_out_of_bounds_costs,
            )
            for c in self.countries
        }

        # Load the helper class for Regional Information
        self.region_info = RegionInformation()

        # Store country subsets we are interested in for outputs
        self.country_subset = self.get_country_subset()

    def get_country_subset(self) -> List[str]:
        """Get the subset of countries for analysis outputs.

        Returns:
            List of ISO3 country codes corresponding to the subset of countries
            specified for outputs.
        """
        country_subset_param = self.parameters.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        whole_portfolio_countries = self.parameters.get_portfolio_countries_for(self.disease_name)

        if country_subset_param == 'ALL':
            return whole_portfolio_countries
        else:
            return list(
                set(
                    self.region_info.get_countries_by_regional_flag(country_subset_param)
                ).intersection(whole_portfolio_countries)
            )

    def filter_funding_data_for_non_modelled_countries(
            self, funding_data_object: TgfFunding | NonTgfFunding
    ) -> TgfFunding | NonTgfFunding:
        """Filter funding data to include only modeled countries.

        Args:
            funding_data_object: TGF or non-TGF funding object to be filtered.

        Returns:
            Filtered funding data object containing only countries that are declared
            as modeled countries for this disease.
        """
        list_of_modelled_countries = self.parameters.get_modelled_countries_for(self.disease_name)
        funding_data_object = copy(funding_data_object)
        funding_data_object.df = funding_data_object.df[funding_data_object.df.index.isin(list_of_modelled_countries)]
        return funding_data_object

    def portfolio_projection(self) -> PortfolioProjection:
        """Generate portfolio projection using the configured allocation method.

        The method is determined by the METHOD_FOR_ALLOCATION_IN_IC parameter,
        which can be 'A' (non-fungible funding), 'B' (optimized allocation),
        or 'C' (uniform funding fraction, requires explicit call).

        Returns:
            PortfolioProjection object containing funding allocations, country results,
            and portfolio-level aggregated results.

        Raises:
            ValueError: If Approach C is specified (requires explicit funding_fraction)
                or if an unrecognized method is specified.
        """
        approach = self.parameters.get('METHOD_FOR_ALLOCATION_IN_IC').upper()
        if approach == 'A':
            return self.portfolio_projection_approach_a()
        elif approach == 'B':
            return self.portfolio_projection_approach_b()
        elif approach == 'C':
            raise ValueError('Cannot do Approach C without a funding_fraction being specified. '
                             'Call `portfolio_projection_approach_c` instead.')
        else:
            raise ValueError(f'Do not recognise the method for allocation in IC: {approach=}')

    def portfolio_projection_approach_a(self) -> PortfolioProjection:
        """Generate portfolio projection using Approach A (non-fungible TGF funding).

        In Approach A, TGF funding allocated to each country is fixed and cannot be
        reallocated. Each country receives its predetermined funding envelope consisting
        of domestic, non-TGF, and TGF funding.

        Returns:
            PortfolioProjection object with results for each country based on their
            fixed funding allocations, filtered to the specified country subset.
        """

        country_results = self._get_country_projections_given_funding_dollar_amounts(
            total_funding_by_country=(
                self.tgf_funding.df["value"] + self.non_tgf_funding.df["value"]
            ).to_dict()
        )

        # Return portfolio result, ensuring that only results for countries that are within this region are included.
        return PortfolioProjection(
            tgf_funding_by_country={country: amt for country, amt in self.tgf_funding.df["value"].to_dict().items() if country in self.country_subset},
            non_tgf_funding_by_country={country: amt for country, amt in self.non_tgf_funding.df["value"].to_dict().items() if country in self.country_subset},
            country_results={country: country_projection for country, country_projection in country_results.items() if country in self.country_subset},
            portfolio_results=self._make_portfolio_results(
                country_results=country_results,
                adjust_for_unmodelled_innovation=self.innovation_on,
                name='none',
            )
        )


    def portfolio_projection_approach_b(
        self,
    ) -> PortfolioProjection:
        """Generate portfolio projection using Approach B (optimized TGF allocation).

        In Approach B, TGF funding can be reallocated across countries to optimize
        health impact. The optimization uses methods specified in the APPROACH_B_METHODS
        parameter. Multiple optimization methods may be tried, but only the best
        solution is returned.

        Returns:
            PortfolioProjection object with optimized TGF funding allocations and
            corresponding results for each country, filtered to the specified
            country subset.
        """
        # Use the `ApproachB` class to get the TGF funding allocations from the optimisation, getting only the best
        # result.

        methods = self.parameters.get('APPROACH_B_METHODS')

        results_from_approach_b = self._approach_b().do_approach_b(
            methods=methods, provide_best_only=True
        )
        tgf_funding_under_approach_b = results_from_approach_b.tgf_budget_by_country

        country_results = self._get_country_projections_given_funding_dollar_amounts(
            (
                pd.Series(tgf_funding_under_approach_b)
                + self.non_tgf_funding.df["value"]
            ).to_dict()
        )

        # Return portfolio result, ensuring that only results for countries that are within this region are included.
        return PortfolioProjection(
            tgf_funding_by_country={country: amt for country, amt in self.tgf_funding.df["value"].to_dict().items() if country in self.country_subset},
            non_tgf_funding_by_country={country: amt for country, amt in self.non_tgf_funding.df["value"].to_dict().items() if country in self.country_subset},
            country_results={country: country_projection for country, country_projection in country_results.items() if country in self.country_subset},
            portfolio_results=self._make_portfolio_results(
                country_results=country_results,
                adjust_for_unmodelled_innovation=self.innovation_on,
                name='none',
            )
        )


    def portfolio_projection_approach_c(self, funding_fraction: float) -> PortfolioProjection:
        """Generate portfolio projection using Approach C (uniform funding fraction).

        In Approach C, all countries receive the same funding fraction of their
        resource needs, without distinguishing between TGF and non-TGF sources.

        Args:
            funding_fraction: Funding fraction to apply uniformly across all countries
                (e.g., 0.8 for 80% funding).

        Returns:
            PortfolioProjection object with results for each country based on the
            uniform funding fraction. TGF and non-TGF funding breakdowns are not
            available (set to None).
        """
        country_results = self._get_country_projection_given_funding_fraction(funding_fraction=funding_fraction)

        return PortfolioProjection(
            tgf_funding_by_country=None,  # In this scenario, we do not know the split between TGF and non-TGF sources
            non_tgf_funding_by_country=None,
            country_results={country: country_projection for country, country_projection in country_results.items() if country in self.country_subset},
            portfolio_results=self._make_portfolio_results(
                country_results=country_results,
                adjust_for_unmodelled_innovation=self.innovation_on,
                name='none',
            ),
        )


    def portfolio_projection_counterfactual(
            self,
            name: str,
    ) -> PortfolioProjection:
        """Generate portfolio projection for a counterfactual scenario.

        Args:
            name: Scenario descriptor for the counterfactual (must exist in model results).

        Returns:
            PortfolioProjection object for the counterfactual scenario. Funding values
            are set to NaN as they are not applicable to counterfactuals.

        Raises:
            AssertionError: If the specified counterfactual name is not found in model results.
        """

        assert name in self.database.model_results.df.index.get_level_values('scenario_descriptor'),\
            f"Counterfactual {name} not found in model results."

        # Create dict of country_results corresponding to the counterfactual scenario
        country_results = dict()
        for country in self.countries:

            model_projection = {
                indicator:
                    self.database.model_results.df.loc[(name, slice(None), country, slice(None), indicator)]
                    .droplevel(axis=0, level='funding_fraction')
                    .rename(columns={'central': 'model_central', 'low': 'model_low', 'high': 'model_high'})
                for indicator in self.database.model_results.indicators
            }

            country_results[country] = CountryProjection(
                model_projection=model_projection,
                funding=float('nan'),
            )

        return PortfolioProjection(
            tgf_funding_by_country={k: float('nan') for k in self.countries},
            non_tgf_funding_by_country={k: float('nan') for k in self.countries},
            country_results={country: country_projection for country, country_projection in country_results.items() if country in self.country_subset},
            portfolio_results=self._make_portfolio_results(country_results, adjust_for_unmodelled_innovation=False, name=name),
        )

    def dump_everything_to_xlsx(
            self,
            filename: Path,
    ) -> None:
        """Export all analysis results to an Excel file.

        Args:
            filename: Path where the Excel file should be saved.
        """
        DumpAnalysisToExcel(self, filename)

    def _approach_b(self) -> ApproachB:
        """Create an ApproachB object for optimization.

        Returns:
            ApproachB object configured with data frames needed for optimization.
        """
        return ApproachB(**self.get_data_frames_for_approach_b())

    def get_data_frames_for_approach_b(
        self,
    ) -> Dict[str, pd.DataFrame]:
        """Prepare data frames for Approach B optimization.

        Computes summary quantities that characterize each country's performance
        under different funding fractions and the Global Plan. These form the basis
        for the optimization algorithm.

        Returns:
            Dictionary containing:
                - 'tgf_budgets': TGF budget allocations by country
                - 'non_tgf_budgets': Non-TGF budget allocations by country
                - 'model_results': Country-level cases, deaths, and costs for each
                  funding level, potentially with monotonic decreasing enforcement
                  and out-of-bounds handling applied
        """

        # ---------------
        # Get parameters:
        force_monotonic_decreasing = self.parameters.get("FORCE_MONOTONIC_DECREASING")
        years_for_obj_func = self.parameters.get("YEARS_FOR_OBJ_FUNC")
        # ---------------

        # get budgets as data-frames
        tgf_budgets = self.tgf_funding.df["value"].reset_index()
        non_tgf_budgets = self.non_tgf_funding.df["value"].reset_index()

        # Create Model Results df: country|cases|deaths|cost (multiple row per country, one for each costing value),
        # with...
        # * cost being the sums of cost within the years specified by `years_for_funding` (i.e. the years of the
        #   replenishment).
        # * cases and death being sums within the years specified by `years_for_obj_func` (i.e. the period over which
        #   we wish to "compete" the different funding allocations).

        # Summarise cases/death for each funding_fraction: sums within  `years_for_obj_func`
        cases_and_deaths = (
            self.database.model_results.df.loc[
                (
                    self.scenario_descriptor,
                    slice(None),
                    slice(None),
                    years_for_obj_func,
                    ["cases", "deaths"],
                )
            ]["central"]
            .groupby(axis=0, level=["funding_fraction", "country", "indicator"])
            .sum()
            .unstack("indicator")
        )

        # Summarise cost for each funding_fraction: sums within `self.years_for_funding`
        costs = (
            self.database.model_results.df.loc[
                (
                    self.scenario_descriptor,
                    slice(None),
                    slice(None),
                    self.years_for_funding,
                    ["cost"],
                )
            ]["central"]
            .groupby(axis=0, level=["funding_fraction", "country", "indicator"])
            .sum()
            .unstack("indicator")
        )

        # join these two dataframes:
        model_results = cases_and_deaths.join(costs).reset_index().sort_values(["country", "cost"]).reset_index(drop=True)

        # Handle_out_of_bounds_costs`: Insert a set of records for zero-funding with same results as for 10% funding
        # and a set of records with float('inf') costs for with the same results as the highest funding level
        if self.handle_out_of_bounds_costs:
            zero_funding_records = model_results.loc[model_results['funding_fraction'] == 0.1].copy()
            zero_funding_records['funding_fraction'] = 0.0
            zero_funding_records['cost'] = 0.0

            inf_funding_records = model_results.loc[model_results['funding_fraction'] == 1.0].copy()
            inf_funding_records['funding_fraction'] = float('inf')
            inf_funding_records['cost'] = float('inf')

            model_results = pd.concat([model_results, zero_funding_records, inf_funding_records], axis=0).sort_values(["country", "cost"]).reset_index(drop=True)

        # Force_monotonic_decreasing`: Within the results for each country, force that cases and deaths are
        #  monotonically decreasing with costs.
        if force_monotonic_decreasing:
            for country in model_results.country.unique():
                raw_sorted_on_cost = model_results.loc[model_results['country'] == country, ['cost', 'deaths', 'cases']].set_index('cost').sort_index(ascending=True)
                model_results.loc[model_results['country'] == country, 'cost'] = raw_sorted_on_cost.index.values
                model_results.loc[model_results['country'] == country, 'cases'] = raw_sorted_on_cost['cases'].cummin().values
                model_results.loc[model_results['country'] == country, 'deaths'] = raw_sorted_on_cost['deaths'].cummin().values

        # Tidy-up (sort and drop any duplicates)
        model_results = model_results.reset_index() \
                                     .drop(columns=["funding_fraction"]) \
                                     .drop_duplicates(subset=['country', 'cost']) \
                                     .sort_values(["country", "cost"])[["country", "cost", "cases", "deaths"]]

        return {
            "tgf_budgets": tgf_budgets,
            "non_tgf_budgets": non_tgf_budgets,
            "model_results": model_results,
        }

    def _get_country_projections_given_funding_dollar_amounts(
        self, total_funding_by_country: Dict[str, float]
    ) -> Dict[str, CountryProjection]:
        """Generate country projections for specified funding amounts.

        Args:
            total_funding_by_country: Dictionary mapping ISO3 country codes to total
                funding amounts in dollars.

        Returns:
            Dictionary mapping ISO3 country codes to CountryProjection objects containing
            model projections and funding amounts for each country.
        """

        # Collect results for each country
        country_results = dict()
        for country, total_dollar_funding in total_funding_by_country.items():

            if country not in self.countries:
                # Skip a country that is included in the funding data but not included in the model results
                continue

            model_projection = self.emulators[country].get(
                dollars=total_dollar_funding,
            )

            country_projection = CountryProjection(
                model_projection=model_projection,
                funding=total_dollar_funding,
            )
            country_results[country] = country_projection

        return country_results

    def _get_country_projection_given_funding_fraction(self, funding_fraction: float) -> Dict[str, CountryProjection]:
        """Generate country projections for a uniform funding fraction.

        Args:
            funding_fraction: Funding fraction to apply uniformly across all countries.

        Returns:
            Dictionary mapping ISO3 country codes to CountryProjection objects.
        """
        country_results = dict()
        for country in self.countries:
            model_projection = self.emulators[country].get(
                funding_fraction=funding_fraction,
            )
            country_projection = CountryProjection(
                model_projection=model_projection,
                funding=None,  # could find this from self.emulators[country]._lookup_dollars_to_funding_fraction[1.0]
            )
            country_results[country] = country_projection
        return country_results

    def _make_portfolio_results(
            self,
            country_results: Dict[str, CountryProjection],
            adjust_for_unmodelled_innovation: bool,
            name: str,
    ) -> Dict[str, pd.DataFrame]:
        """Generate portfolio-level results from country-level projections.

        Aggregates country results to portfolio level, including summing variables across
        countries, scaling up for non-modeled countries, and applying Global Plan-related
        innovation adjustments if specified.

        Args:
            country_results: Dictionary mapping country codes to CountryProjection objects.
            adjust_for_unmodelled_innovation: Whether to apply innovation adjustments for
                impact not captured in the model but expected in the Global Plan.
            name: Name identifier for the scenario.

        Returns:
            Dictionary mapping indicator names to DataFrames with portfolio-level results
            including central, low, and high estimates.
        """

        actual_without_innovation = (
            self._scale_up_for_non_modelled_countries(
                self._summing_up_countries(country_results, name), name
            )
        )

        if not adjust_for_unmodelled_innovation:
            return actual_without_innovation

        else:
            # Get the fully funded version of the model output
            scenario_that_represents_full_impact_including_innovation = self.parameters.get('SCENARIO_THAT_REPRESENTS_FULL_IMPACT_INCLUDING_INNOVATION')
            full_funding_without_innovation = self.portfolio_projection_counterfactual(scenario_that_represents_full_impact_including_innovation)

            return (
                self._adj_for_innovations(
                    actual_without_innovation=actual_without_innovation,
                    full_funding_without_innovation=full_funding_without_innovation,
                    gp=self.gp,
                )
            )

    def _scale_up_for_non_modelled_countries(self, portfolio_results: Dict[str, pd.DataFrame], name: str) -> Dict[str, pd.DataFrame]:
        """Scale modeled results to account for non-modeled countries.

        Applies scaling factors to epidemiological indicators to extrapolate from modeled
        countries to the full portfolio including non-modeled countries.

        Args:
            portfolio_results: Dictionary of portfolio-level results by indicator.
            name: Name identifier for the scenario (affects which start year is used).

        Returns:
            Dictionary of scaled portfolio results by indicator.
        """

        # Define years and parameters we need
        p = self.parameters

        # Get the first year of the model and list of epi indicators
        first_year = p.get("START_YEAR")
        if name == ('GP'):
            first_year = p.get(self.disease_name).get("GP_START_YEAR")
        if name == ('NULL_2022'):
            first_year = p.get("NULL_START_YEAR")

        # Get the indicators that should be scaled
        indicator_list = p.get_indicators_for(self.disease_name).use_scaling
        indicator_list = pd.DataFrame(indicator_list).reset_index()
        indicator_list = indicator_list.loc[indicator_list['use_scaling'] == True]
        indicator_list = indicator_list['name'].tolist()

        # Define which countries to sum up. This is the place where we would filter for regions if the run requests this
        country_subset_param = p.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        if country_subset_param == 'ALL':
            country_subset = slice(None)
        else:
            country_subset = list(
                set(
                    self.region_info.get_countries_by_regional_flag(country_subset_param)
                ).intersection(self.database.partner_data.countries)
            )

        # Filter partner data to the corresponding year and epi indicators, summed across countries and turned
        # into a dictionary
        df_partner = \
            self.database.partner_data.df.loc[
                (self.scenario_descriptor, country_subset, first_year, indicator_list)].groupby(
                axis=0, level='indicator').sum()['central'].to_dict()

        # This loop scaled all epi indicators to non-modelled countries
        adj_results_portfolio = dict()
        for indicator, df in portfolio_results.items():
            if indicator not in indicator_list:
                adj_results_portfolio[indicator] = df
            else:
                # do scaling:
                adj_results_portfolio[indicator] = df * (df_partner[indicator] / df.at[first_year, 'model_central'])

        return adj_results_portfolio

    def _adj_for_innovations(
            self,
            actual_without_innovation: Dict[str, CountryProjection],
            full_funding_without_innovation: Dict[str, CountryProjection],
            gp: Gp,
    ) -> Dict[str, pd.DataFrame]:
        """Apply innovation adjustments to project results.

        Adjusts projections to account for innovations expected to be introduced
        within the partner Global Plan using a sigmoidal scaling curve.

        Args:
            actual_without_innovation: Portfolio results before innovation adjustment.
            full_funding_without_innovation: Results under full funding without innovation,
                used as a reference point.
            gp: Global Plan data.

        Returns:
            Dictionary mapping indicator names to DataFrames with innovation-adjusted results.
        """

        sigmoid_scaling = pd.Series(
            dict(zip(
                range(self.parameters.get('START_YEAR'), self.parameters.get('END_YEAR') + 1),
                self.parameters.get(self.disease_name).get("NEW_INNOVATIONS_SCALING_FACTORS")
            ))
        )

        INDICATORS_FOR_ADJ_FOR_INNOVATIONS = self.indicators_for_adj_for_innovations

        adj_country_results = dict()

        for indicator, df in actual_without_innovation.items():

            if indicator not in INDICATORS_FOR_ADJ_FOR_INNOVATIONS:
                # Do not do any adjustment
                adj_country_results[indicator] = df.copy()

            else:
                # Do the adjustment for new innovations

                # Set first year of model output
                expected_first_year = self.parameters.get("START_YEAR")

                # Work out correction needed for non-modelled innovations:
                full_funding = full_funding_without_innovation.portfolio_results[indicator]
                _gp_df = gp.df.reset_index()
                _gp = _gp_df.loc[(_gp_df.indicator == indicator), ['year', 'central']].set_index('year')['central']
                _gp = _gp[_gp.index >= expected_first_year]  # Ensure all dfs have same length
                step_one = (df / full_funding).mul(_gp, axis=0)
                step_two = df - (df - step_one).mul(sigmoid_scaling, axis=0)

                # Over-write the lower and upper bounds so they are the same distance as the modelled distance before applying the sigmoidal adjustment
                # If not, the lower bounds and upper bounds can behave strangely

                # First capture the distance from central to LB and Ub from unadjusted
                distance_low  = df['model_central'] - df['model_low']
                distance_upper = df['model_high'] - df['model_central']

                step_two['model_low'] = step_two['model_central'] - distance_low
                step_two['model_high'] = step_two['model_central'] + distance_upper

                # Add adjusted time series to the dataframe
                adj_country_results[indicator] = step_two

        return adj_country_results

    def _summing_up_countries(self, country_results: Dict[str, CountryProjection], name: str) -> Dict[str, pd.DataFrame]:
        """Aggregate country results to portfolio level with uncertainty.

        Sums adjusted country results to generate portfolio-level projections,
        including propagation of uncertainty from country to portfolio level.

        Args:
            country_results: Dictionary mapping country codes to CountryProjection objects.
            name: Name identifier for the scenario (affects which start year is used).

        Returns:
            Dictionary mapping indicator names to DataFrames with aggregated portfolio
            results including central, low, and high estimates.
        """

        def _compute_mean_and_ci(_df_for_year: pd.DataFrame):
            """Compute portfolio-level statistics with confidence intervals.

            Args:
                _df_for_year: DataFrame containing model results for one year across
                    all countries, with columns for model_central, model_low, and model_high.

            Returns:
                Dictionary with keys 'model_central', 'model_low', and 'model_high'
                containing aggregated estimates.
            """
            model_central = _df_for_year["model_central"].sum()

            # Then we do the SDs. CAUTION for the first SD it has to be 1.96 as the assumptions that the model LB and UB
            # correspond to 95% confidence intervals
            _sds = ((_df_for_year.model_high - _df_for_year.model_low) / (2 * 1.96)).values
            sd_for_year = (
                                  matmul(_sds).sum() * rho_btw_countries
                                  + (_sds ** 2).sum() * (1 - rho_btw_countries)
                          ) ** 0.5
            model_low = max(0, (model_central - z_value * sd_for_year))
            model_high = model_central + z_value * sd_for_year
            return {
                'model_central': model_central,
                'model_low': model_low,
                'model_high': model_high
            }

        # Define years and parameters we need
        p = self.parameters

        # Define start year (over-riding for special cases)
        if name == ('GP'):
            first_year = self.parameters.get(self.disease_name).get("GP_START_YEAR")
        elif name == ('NULL_2022'):
            first_year = self.parameters.get("NULL_START_YEAR")
        else:
            first_year = p.get("START_YEAR")

        last_year = p.get("END_YEAR")
        z_value = p.get("Z_VALUE")
        rho_btw_countries = p.get("RHO_BETWEEN_COUNTRIES_WITHIN_DISEASE")

        portfolio_results = dict()

        # Defining the list of indicators and countries for the loop
        indicators = country_results[list(country_results.keys())[0]].model_projection.keys()
        types_lookup = self.indicators['type'].to_dict()

        # Define which countries to sum up. This is the place where we would filter for regions if the run requests this
        country_subset = p.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        if country_subset == 'ALL':
            countries = country_results.keys()
        else:
            countries = list(
                set(
                    self.region_info.get_countries_by_regional_flag(country_subset)
                ).intersection(country_results.keys())
            )

        # Filter country_results to match only countries in the selected subset
        country_results = {
            iso3: result for iso3, result in country_results.items()
            if iso3 in countries
        }

        if not countries:
            warnings.warn(
                f"No countries available for '{self.disease_name}' in region '{country_subset}'. Creating two dummy countries with zeros.")

            indicators = list(indicators)  # Just to be safe in case it's a dict_keys object

            country_results = {}

            for i in range(2):  # Create two dummy countries
                dummy_iso3 = f"DUMMY{i + 1}"
                dummy_projections = {}

                for indicator in indicators:
                    df = pd.DataFrame({
                        'model_central': [0] * (last_year - first_year + 1),
                        'model_low': [0] * (last_year - first_year + 1),
                        'model_high': [0] * (last_year - first_year + 1),
                    }, index=range(first_year, last_year + 1))

                    dummy_projections[indicator] = df

                country_results[dummy_iso3] = CountryProjection(model_projection=dummy_projections, funding=0.0)

        # Extracting all values for each indicator across all countries, if we should do an aggregation
        for indicator in indicators:
            type_of_indicator_is_count = types_lookup[indicator] == 'count'

            if not type_of_indicator_is_count:
                # Do nothing if the indicator is not aggregating arithmetically (i.e., is a count).
                continue

            dfs = list()
            for country in country_results:
                dfs.append(
                    country_results[country].model_projection[indicator].loc[
                        slice(first_year, last_year),
                        ['model_central', 'model_high', 'model_low']
                    ]
                )

            # Put all the values for a given indicator together into one df
            all_dfs = pd.concat(dfs)

            # Aggregate by year:
            _res = dict()
            for year in range(first_year, last_year + 1):
                _res[year] = all_dfs.loc[year].pipe(_compute_mean_and_ci)

            portfolio_results[indicator] = pd.DataFrame(_res).T

        return portfolio_results

    def get_partner(self) -> pd.DataFrame:
        """Get partner data for reporting.

        Retrieves and aggregates partner data for the indicators and time period
        needed for report generation.

        Returns:
            DataFrame with partner data aggregated across countries in the specified
            subset, with years as rows and indicators as columns.
        """

        if self.disease_name == 'HIV':
            indicator_partner = ['cases', 'deaths', 'hivneg', 'population']
        if self.disease_name == 'TB':
            indicator_partner = ['cases', 'deaths', 'deathshivneg', 'population']
        if self.disease_name == 'MALARIA':
            indicator_partner = ['cases', 'deaths', 'par']

        expected_first_year = self.parameters.get("GRAPH_FIRST_YEAR") - 5
        expected_last_year = self.parameters.get("START_YEAR") + 1

        # Define which countries to sum up. This is the place where we would filter for regions if the run requests this
        country_subset_param = self.parameters.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        if country_subset_param == 'ALL':
            partner_data = self.database.partner_data.df.loc[
                (self.scenario_descriptor, slice(None), range(expected_first_year, expected_last_year),
                 indicator_partner)].groupby(axis=0, level=['year', 'indicator'])['central'].sum().unstack()
        else:
            country_list = self.region_info.get_countries_by_regional_flag(country_subset_param)
            # Get the existing countries in the partner_data index
            existing_countries = set(self.database.partner_data.df.index.get_level_values('country').unique())
            # Filter country_list to only include countries present in partner_data
            filtered_countries = [country for country in country_list if country in existing_countries]
            partner_data = self.database.partner_data.df.loc[
                (self.scenario_descriptor, filtered_countries, range(expected_first_year, expected_last_year),
                 indicator_partner)].groupby(axis=0, level=['year', 'indicator'])['central'].sum().unstack()

        return partner_data

    def get_gp(self) -> pd.DataFrame:
        """Get Global Plan data for reporting.

        Retrieves Global Plan data aggregated appropriately for the disease and
        country subset being analyzed.

        Returns:
            DataFrame with Global Plan data, with years as rows and indicators as columns.
        """

        if self.disease_name != 'HIV':
            # Define which countries to sum up.
            country_subset_param = self.parameters.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
            if country_subset_param == 'ALL':
                gp_data = self.database.gp.df['central'].unstack()
            elif self.disease_name =="TB":
                from scripts.ic8.tb.tb_analysis import get_tb_database_subset
                gp_data = get_tb_database_subset(country_subset_param=country_subset_param).gp.df['central'].unstack()
            elif self.disease_name =="MALARIA":
                from scripts.ic8.malaria.malaria_analysis import get_malaria_database_subset
                gp_data = get_malaria_database_subset(load_data_from_raw_files=False, country_subset_param=country_subset_param).gp.df['central'].unstack()
        else:
            # Get GP for HIV
            gp_data = self.portfolio_projection_counterfactual(self.EXPECTED_GP_SCENARIO[0])

            # Convert to the same format as other diseases
            gp_data = gp_data.portfolio_results
            gp_data = pd.concat(gp_data, axis=0).reset_index(level=0).rename({'level_0': 'key'}, axis=1)
            gp_data = gp_data.drop(['model_low', 'model_high'], axis=1)
            gp_data = gp_data.pivot(columns='key', values='model_central')

        return gp_data

    def get_counterfactual_lives_saved_malaria(self) -> pd.DataFrame:
        """Get counterfactual time series for computing lives saved in malaria.

        Returns:
            DataFrame with counterfactual mortality time series adjusted to baseline
            partner data. Returns empty DataFrame if disease is not malaria.
        """

        if self.disease_name != "MALARIA":
            return pd.DataFrame()

        # Define which countries to sum up. This is the
        country_subset_param = self.parameters.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        if country_subset_param == 'ALL':
           country_list = slice(None)
        else:
            country_in_region = self.region_info.get_countries_by_regional_flag(country_subset_param)
            # Get the existing countries in the partner_data index
            existing_countries = set(self.database.model_results.df.index.get_level_values('country').unique())
            # Filter country_list to only include countries present in partner_data
            country_list = [country for country in country_in_region if country in existing_countries]

        # Get partner mortality data
        mortality_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, country_list, 2000, "mortality"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])
        # 2000 is hard-coded as the year as that is intrinsic to the analysis.

        # TODO: make mean of funding fractions?
        # Set years of model output
        expected_first_year = self.parameters.get("START_YEAR")
        expected_last_year = self.parameters.get("END_YEAR")

        # First adjust model data to baseline partner data

        # Get the model estimates for par for IC scenario and generate mean across funding fractions
        par_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, slice(None), country_list, range(expected_first_year, expected_last_year), "par"), "central"
        ].groupby(axis=0, level=['country', 'year']).mean().unstack()

        # Then get the estimates from baseline from model and partner data to compute adjustment ratio
        par_firstyear_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, country_list, expected_first_year, "par"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])

        par_firstyear_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, 1, country_list, expected_first_year, "par"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "funding_fraction", "year", "indicator"])

        ratio = par_firstyear_partner_data / par_firstyear_model_data

        # Compute modelled par that have been adjusted to baseline partner data
        adj_par_data_model = par_model_data.mul(ratio, axis=0)

        # Now compute deaths from the above as a CF time series for lives saved
        adjusted_mortality = adj_par_data_model.mul(mortality_partner_data, axis=0)
        adjusted_mortality_total = adjusted_mortality.sum(axis=0)
        adjusted_mortality_total.index = adjusted_mortality_total.index.astype(int)

        return adjusted_mortality_total

    def get_counterfactual_infections_averted_malaria(self) -> pd.DataFrame:
        """Get counterfactual time series for computing infections averted in malaria.

        Returns:
            DataFrame with counterfactual incidence time series adjusted to baseline
            partner data. Returns empty DataFrame if disease is not malaria.
        """

        if self.disease_name != "MALARIA":

            return pd.DataFrame()

        # Get partner mortality data
        # Define which countries to sum up.
        country_subset_param = self.parameters.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        if country_subset_param == 'ALL':
            country_list = slice(None)
        else:
            country_in_region = self.region_info.get_countries_by_regional_flag(country_subset_param)
            # Get the existing countries in the partner_data index
            existing_countries = set(self.database.model_results.df.index.get_level_values('country').unique())
            # Filter country_list to only include countries present in partner_data
            country_list = [country for country in country_in_region if country in existing_countries]

        # Set first year of model output
        expected_first_year = self.parameters.get("START_YEAR")
        expected_last_year = self.parameters.get("END_YEAR")

        incidence_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, country_list, expected_first_year, "incidence"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])

        # TODO: make mean of funding fractions?
        # First adjust model data to baseline partner data
        # Get the model estimates for par for IC scenario and generate mean across funding fractions
        par_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, slice(None), country_list, range(expected_first_year, expected_last_year), "par"), 'central'
        ].groupby(axis=0, level=['country', 'year']).mean().unstack()

        # Then get the estimates from baseline from model and partner data to compute adjustment ratio
        par_firstyear_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, country_list, expected_first_year, "par"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])

        par_firstyear_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, 1, country_list, expected_first_year, "par"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "funding_fraction", "year", "indicator"])

        ratio = par_firstyear_partner_data / par_firstyear_model_data

        # Compute modelled par that have been adjusted to baseline partner data
        adj_par_data_model = par_model_data.mul(ratio, axis=0)

        # Now compute deaths from the above as a CF time series for lives saved
        adjusted_incidence = adj_par_data_model.mul(incidence_partner_data, axis=0)
        adjusted_incidence_total = adjusted_incidence.sum(axis=0)
        adjusted_incidence_total.index = adjusted_incidence_total.index.astype(int)

        return adjusted_incidence_total

    def make_diagnostic_report(
            self,
            plt_show: Optional[bool] = False,
            filename: Optional[Path] = None,
    ):
        """Create a diagnostic report comparing Approach A and B results.

        Generates a report that compares results from Approach A and B, including
        alternative optimization methods for Approach B if specified in parameters.

        Args:
            plt_show: Whether to display plots interactively.
            filename: Path where the report should be saved. If None, no file is saved.
        """
        # Create the approach_b object
        approach_b_object = self._approach_b()

        # Run the report, specifying whether to plot graphs, the filename, and passing through any other kwargs
        # Suppress the returned results as the purpose of this function is generating the report.
        _ = approach_b_object.run(
            plt_show=plt_show,
            filename=filename,
            methods=self.parameters.get('APPROACH_B_METHODS'),
            provide_best_only=False,
        )
