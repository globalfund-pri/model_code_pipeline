import math
from copy import copy
from typing import Dict, Iterable, NamedTuple, Optional, Union

import pandas as pd
from pathlib import Path

from scripts.ic8.shared.create_frontier import filter_for_frontier
from tgftools.approach_b import ApproachB
from tgftools.database import Database
from tgftools.dump_analysis_to_excel import DumpAnalysisToExcel
from tgftools.emulator import Emulator
from tgftools.filehandler import Gp, NonTgfFunding, Parameters, TgfFunding, RegionInformation
from tgftools.utils import matmul

"""This file holds everything needed for the Analysis class. The analysis class extracts the necessary output from the 
raw model OUTPUT, performs the necessary adjustments and holds the necessary data to generate the key stats and 
graphs in the report class. 


This file needs the following input: 
1. The db (database containing all the various data including model, partner, pf data and non-modelled Global Plan) 
   coming from the disease specific filehandler scripts
2. The scenario that should be analysed (set in the disease-specific analysis scripts when defining the analysis)
3. The tgf and non-tgf funding amounts. This includes an option to include or exclude unallocated amounts. This 
   information has to be computed outside the MCP (set in the disease-specific analysis scripts when loading the budget 
   assumptions)
4. Information on the years of replenishment period (set in the parameters.toml file)
5. How to handle out of bounds costs (set in the disease-specific scripts when defining the analysis)
6. Parameters to compute confidence intervals (CIs), including the z-value (whether we are computing e.g. 80%, 90%, 
   95% CIs), the rho-value (variation between countries within disease) (these are set in the parameters.toml file)


This class computes country and portfolio level results for the investment case scenario using two different approaches: 
1. It performs approach A. This approach is based on country-specific funding envelopes including domestic, non-TGF and 
   TGF funding and uses these amount to interpolate based on the cost impact curves the exact amount corresponding to 
   this funding envelope and the number of cases and deaths corresponding to this amount, 
2. It performs approach B, which optimizes i) GF or ii) GF and unallocated amounts (the option to include or exclude 
   unallocated amounts in the optimization can be set when defining the input) across countries within diseases. 
The option (A or B) to be performed are set in the disease specific analysis script AND in the HTM script. 
   
   
This class does the following processing, in the following order:   
1. Country-level projections given dollar amount/funding fraction: It emulates the country-specific projections for all 
   variables (epi and service) given the funding and scenario selected as an input to the analysis. This is only done 
   for the investment case scenario, not the counterfactuals. 
2. Baseline adjustment: Adjusts all the resulting country-level projections to baseline partner data, where 
   partner data is available. For example, if the partner data does not contain data on number of people on ART it will 
   keep the model projections, without doing any adjustments. It is therefore crucial to have partner data on all 
   variables generated in the model output. CAUTION: if population estimates are adjusted but e.g. number of people on
   treatment are not adjusted to baseline partner data, this will skew the coverage estimates.  CAUTION: HIV was not 
   adjusted for baseline partner data, only TB and malaria. 
3. Generate portfolio level results. It sums all variables across countries to generate portfolio level projections. 
   CAUTION: as it is not possible to sum fractions, the numerator and denominators are summed instead and the fractions 
   can be recalculated in the report class later. 
4. Generated CIs: as part of generating the portfolio level results, it takes the uncertainty at the country level to 
   generate portfolio level un certainty. The parameter for these are set in the parameter file. 
5. Adjusts for innovation: it computes a curve (e.g. sigmoidal) to adjust the final investment case scenario projections 
   to adjust for the missing impact within the partner GP that will be accounted for by innovation. CAUTION: the 
   original curve did not start at zero in 2020 and end at 1 in 2030. So the parameters for these two years have been 
   overwritten in the parameter file. NOTE: HIV was not adjusted for innovation, only TB and malaria. 


This class generated the following "SetOfPortfolioProjections" which contains the following data: 
1. The investment case related data. This undergoes all the aforementioned processing, unless specified
2. Various counterfactuals, including counterfactuals for lives saved, infections averted, each of them being disease
   specific. 
3. Data for the key graphs, including partner data and the disease-specific global plans


CAUTION: when running this script please note the following. 
1. Option to re-load and process the model output (load_data_from_raw_file at the bottom of the disease specific 
   analysis scripts and HTM script. Any updated to the filehandler relating to model output will not be reflected if 
   this option is set to "False"
2. Option to set approach A or B (set in "get_set_of_portfolio_projections" in HTM script AND in main switchboard of 
   disease specific analysis scripts (very bottom) will affect the resulting output
3. Option to set the scenario, funding amount and domestic scenario (in disease specific analysis scripts) will affect 
   resulting output.  
"""


class CountryProjection(NamedTuple):
    """NamedTuple for cases and death for a given program cost in a given country."""

    model_projection: Dict[
        str, pd.DataFrame
    ]  # dict of the form {<indicator>: <pd.DataFrame>}
    funding: float
    # model_projection_fully_funded: Dict[
    #     str, pd.DataFrame
    # ]  # dict of the form {<indicator>: <pd.DataFrame>} # TODO: remove if not needed


class PortfolioProjection(NamedTuple):
    """NamedTuple for the results of an Analysis."""

    tgf_funding_by_country: dict[str, float]

    non_tgf_funding_by_country: dict[str, float]

    country_results: dict[
        str, CountryProjection
    ]  # dict of the form {<country>: <CountryProjection>}

    portfolio_results: dict[
        str, pd.DataFrame
    ]  # dict of the form {<indicator>: <pd.DataFrame>}, where the pd.DataFrame has years in the row, and columns
    #                                                    (central/low/high for the value) across all the portfolio,
    #                                                    with adjustments.


class Analysis:
    """This is the Analysis class. It holds a Database object and requires an argument for the scenario_descriptor.
    It can then output ensemble results (or country-level results) that reflect decisions for the use of the funding -
    in particular, when the TGF funding is non-fungible (Approach A) and when it is fungible and its allocation
    between countries can be optimised (Approach B).
    :param years_for_funding: Defines the calendar years (integers) for which the budgets correspond, (i.e, the years
     to which the replenishment funding scenarios correspond).
    :param handle_out_of_bounds_costs: Determines whether an error is thrown when a result for country is needed
     for a cost that is not in the range of the model_results, or whether results are used for highest/lowest cost
     model_results instead. This is passed through to the `Emulator` class.
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

    def filter_funding_data_for_non_modelled_countries(
            self, funding_data_object: TgfFunding | NonTgfFunding
    ) -> TgfFunding | NonTgfFunding:
        """Returns a funding data object that has been filtered for countries that are not declared as the modelled
        countries for that disease."""
        list_of_modelled_countries = self.parameters.get_modelled_countries_for(self.disease_name)
        funding_data_object = copy(funding_data_object)
        funding_data_object.df = funding_data_object.df[funding_data_object.df.index.isin(list_of_modelled_countries)]
        return funding_data_object

    def portfolio_projection_approach_a(self) -> PortfolioProjection:
        """Returns the PortfolioProjection For Approach A: i.e., the projection for each country, given the funding
        to each country when the TGF funding allocated to a country CANNOT be changed.
        """

        country_results = self._get_country_projections_given_funding_dollar_amounts(
            total_funding_by_country=(
                self.tgf_funding.df["value"] + self.non_tgf_funding.df["value"]
            ).to_dict()
        )
        return PortfolioProjection(
            tgf_funding_by_country=self.tgf_funding.df["value"].to_dict(),
            non_tgf_funding_by_country=self.non_tgf_funding.df["value"].to_dict(),
            country_results=country_results,
            portfolio_results=self._make_portfolio_results(
                country_results=country_results,
                adjust_for_unmodelled_innovation=self.innovation_on,
                name='none',
            ),
        )

    def portfolio_projection_approach_b(
        self,
    ) -> PortfolioProjection:
        """Returns the PortfolioProjection For Approach B: i.e., the projection for each country, given the funding
        to each country when the TGF funding allocated to a country _CAN_ be changed. Multiple methods for optimisation
        may be tried, but only a single result is provided (that of the best solution found.)
        :param methods: List of methods to use in approach_b (For method see `do_approach_b`)
        :param optimisation_params: Dict of parameters specifying how to construct the optimisation.
        See `_get_data_frames_for_approach_b`
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
        return PortfolioProjection(
            tgf_funding_by_country=tgf_funding_under_approach_b,
            non_tgf_funding_by_country=self.non_tgf_funding.df["value"].to_dict(),
            country_results=country_results,
            portfolio_results=self._make_portfolio_results(
                country_results=country_results,
                adjust_for_unmodelled_innovation=self.innovation_on,
                name='none',
            )
        )


    def portfolio_projection_approach_c(self, funding_fraction: float) -> PortfolioProjection:
        """Returns the PortfolioProjection For Approach C: i.e., the funding fraction is the same in all countries
        """
        country_results = self._get_country_projection_given_funding_fraction(funding_fraction=funding_fraction)
        return PortfolioProjection(
            tgf_funding_by_country=None,  # In this scenario, we do not know the split between TGF and non-TGF sources
            non_tgf_funding_by_country=None,
            country_results=country_results,
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
        """Returns a PortfolioProjection for a chosen counterfactual scenario."""

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
            country_results=country_results,
            portfolio_results=self._make_portfolio_results(country_results, adjust_for_unmodelled_innovation=False, name=name),
        )

    def dump_everything_to_xlsx(
            self,
            filename: Path,
    ) -> None:
        """Dump everything into an Excel file."""
        DumpAnalysisToExcel(self, filename)

    def _approach_b(self) -> ApproachB:
        """Returns the object `ApproachB` so that other features of it can be accessed conveniently."""
        return ApproachB(**self.get_data_frames_for_approach_b())

    def get_data_frames_for_approach_b(
        self,
    ) -> Dict[str, pd.DataFrame]:
        """Returns dict of dataframes needed for using the `ApproachB` class. This is where the quantities are
        computed that summarises the performance of each country under each funding_fraction and the GP, which forms
        the basis of the optimisation."""

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
        """Returns a dict of CountryProjections given specified total funding dollar amounts to each country."""

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
        """Returns a dict of CountryProjections given a specified funding_fraction, which is the same in all countries"""
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
        """ This function generates portfolio level results. This included summing up variables across countries,
        scaling up for non-modelled countries, and doing the adjustment for GP-related innovation. """

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

    def _scale_up_for_non_modelled_countries(self, country_results: Dict[str, CountryProjection], name: str) -> Dict[str, pd.DataFrame]:
        """ This scales the modelled results to non-modelled countries for the epi indicators. """

        # @Mikaela -- Make this not do any scaling if self.parameters['SCALE_TO_NON_MODELLED_COUNTRIES'] is True.

        # Get the first year of the model and list of epi indicators
        first_year = self.parameters.get("START_YEAR")
        if name == ('GP'):
            first_year = self.parameters.get(self.disease_name).get("GP_START_YEAR")

        # Get the indicators that should be scaled
        indicator_list = self.parameters.get_indicators_for(self.disease_name).use_scaling
        indicator_list = pd.DataFrame(indicator_list).reset_index()
        indicator_list = indicator_list.loc[indicator_list['use_scaling'] == True]
        indicator_list = indicator_list['name'].tolist()

        # Filter partner data to the corresponding year and epi indicators, summed across countries and turned
        # into a dictionary
        df_partner = self.database.partner_data.df.loc[(self.scenario_descriptor, slice(None), first_year, indicator_list)].groupby(axis=0, level='indicator').sum()['central'].to_dict()

        # This loop scaled all epi indicators to non-modelled countries
        adj_results_portfolio = dict()
        for indicator, df in country_results.items():
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
        """ This will make the necessary adjustments for innovations assumed to come in within the partner GP. """


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
        """ This will sum up all the country results to get the portolfio-level results. This will use the adjusted
        country results and be used to generate uncertainty. """

        def _compute_mean_and_ci(_df_for_year: pd.DataFrame):
            """This helper function accepts a dataframe for one year of model results for each country, and returns a
            dict summarising the statistic across the countries, as a mean low/high range.
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
        first_year = p.get("START_YEAR")
        if name == ('GP'):
            first_year = self.parameters.get(self.disease_name).get("GP_START_YEAR")
        last_year = p.get("END_YEAR")
        z_value = p.get("Z_VALUE")
        rho_btw_countries = p.get("RHO_BETWEEN_COUNTRIES_WITHIN_DISEASE")

        portfolio_results = dict()

        # Defining the list of indicators and countries for the loop
        indicators = country_results[list(country_results.keys())[0]].model_projection.keys()
        types_lookup = self.indicators['type'].to_dict()

        # Define which countries to sum up...
        # Something like the following......
        country_subset = p.get('REGIONAL_SUBSET_OF_COUNTRIES_FOR_OUTPUTS_OF_ANALYSIS_CLASS')
        if country_subset == 'ALL':
            countries = country_results.keys()
        else:
            countries = list(
                set(
                    self.region_info.get_country_subset(country_subset)  # <-- or whatever you call the function in RegionalInformation
                ).intersection(country_results.keys())
            )

        # Extracting all values for each indicator across all countries, if we should do an aggregation
        for indicator in indicators:
            type_of_indicator_is_count = types_lookup[indicator] == 'count'

            if not type_of_indicator_is_count:
                # Do nothing if the indicator is not aggregating arithmetically (i.e., is a count).
                continue

            dfs = list()
            for country in countries:
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
        """Returns data-frame of the partner data that are needed for reporting."""

        if self.disease_name == 'HIV':
            indicator_partner = ['cases', 'deaths', 'hivneg', 'population']
        if self.disease_name == 'TB':
            indicator_partner = ['cases', 'deaths', 'deathshivneg', 'population']
        if self.disease_name == 'MALARIA':
            indicator_partner = ['cases', 'deaths', 'par']

        expected_first_year = self.parameters.get("GRAPH_FIRST_YEAR") - 5
        expected_last_year = self.parameters.get("START_YEAR") + 1

        partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, slice(None), range(expected_first_year, expected_last_year), indicator_partner)].groupby(axis=0, level=['year', 'indicator'])['central'].sum().unstack()

        return partner_data

    def get_gp(self) -> pd.DataFrame:
        """Returns data-frame of the GP elements that are needed for reporting."""

        if self.disease_name != 'HIV':
            gp_data = self.database.gp.df['central'].unstack()
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
        """ Return the CF time series to compute lives saved for malaria"""

        if self.disease_name != "MALARIA":
            return pd.DataFrame()

        # Get partner mortality data
        mortality_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, slice(None), 2000, "mortality"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])
        # 2000 is hard-coded as the year as that is intrinsic to the analysis.

        # TODO: make mean of funding fractions?
        # Set years of model output
        expected_first_year = self.parameters.get("START_YEAR")
        expected_last_year = self.parameters.get("END_YEAR")

        # First adjust model data to baseline partner data

        # Get the model estimates for par for IC scenario and generate mean across funding fractions
        par_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, slice(None), slice(None), range(expected_first_year, expected_last_year), "par"), "central"
        ].groupby(axis=0, level=['country', 'year']).mean().unstack()

        # Then get the estimates from baseline from model and partner data to compute adjustment ratio
        par_firstyear_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, slice(None), expected_first_year, "par"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])

        par_firstyear_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, 1, slice(None), expected_first_year, "par"), "central"
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
        """ Return the CF time series to compute infections averted for malaria"""

        if self.disease_name != "MALARIA":

            return pd.DataFrame()

        # Get partner mortality data
        # Set first year of model output
        expected_first_year = self.parameters.get("START_YEAR")
        expected_last_year = self.parameters.get("END_YEAR")

        incidence_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, slice(None), expected_first_year, "incidence"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])

        # TODO: make mean of funding fractions?
        # First adjust model data to baseline partner data
        # Get the model estimates for par for IC scenario and generate mean across funding fractions
        par_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, slice(None), slice(None), range(expected_first_year, expected_last_year), "par"), 'central'
        ].groupby(axis=0, level=['country', 'year']).mean().unstack()

        # Then get the estimates from baseline from model and partner data to compute adjustment ratio
        par_firstyear_partner_data = self.database.partner_data.df.loc[
            (self.scenario_descriptor, slice(None), expected_first_year, "par"), "central"
        ].droplevel(axis=0, level=["scenario_descriptor", "year", "indicator"])

        par_firstyear_model_data = self.database.model_results.df.loc[
            (self.scenario_descriptor, 1, slice(None), expected_first_year, "par"), "central"
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
        """
        Create a report that compares the results from Approach A and B (and alternative optimisation methods for
        Approach B if these are specified).
        :param plt_show: determines whether to show the plot
        :param filename: filename to save the report to
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
