from typing import Dict, Any, NamedTuple

import openpyxl
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import Reference, LineChart

from tgftools.analysis import PortfolioProjection
from tgftools.report import Report
from tgftools.utils import get_root_path, matmul


class SetOfPortfolioProjections(NamedTuple):
    IC: PortfolioProjection  # The main forward projection scenario for the investment case
    CF_InfAve: PortfolioProjection  # The counterfactual projection scenario to compute infections averted
    # (N.B., we may have multiple different ones for different diseases)
    CF_LivesSaved: PortfolioProjection  # The counterfactual projection scenario to compute lives saved
    # (N.B., we may have multiple different ones for different diseases)
    CF_LivesSaved_Malaria: pd.DataFrame  # The counterfactual for lives saved for malaria
    CF_InfectionsAverted_Malaria: pd.DataFrame  # The counterfactual for lives saved for malaria
    PARTNER: pd.DataFrame  # Dataframe containing partner data needed for reporting
    CF_forgraphs: pd.DataFrame  # Dataframe containing GP needed for reporting (N.B., may differ by disease)
    Info: Dict # Dictionary containing all the information on the ananlysis including files used and technical information


class HTMReport(Report):
    """This is the Report class. It accepts AnalysisResults for each disease and produces summary statistics.
    Each member function returns a Dict of the form {<label>: <stat>} which are assembled into an output Excel file."""

    def __init__(
            self,
            hiv: SetOfPortfolioProjections,
            tb: SetOfPortfolioProjections,
            malaria: SetOfPortfolioProjections,
    ):
        # Save arguments
        self.parameters = None
        self.hiv = hiv
        self.tb = tb
        self.malaria = malaria

    def info(self) -> pd.DataFrame:
        """Collate the information relating to the report, including which folders were being used and the details of
        the analysis (e.g., which approach was used (a or b), which funding envelope, how did we handle unalllocated
        amounts, did we adjust for innovation, etc). """
        return pd.DataFrame(
            data={
                'HIV': {**self.hiv.Info},
                'TB': {**self.tb.Info},
                'Malaria': {**self.malaria.Info}
            })

    def get_key_stats_hiv(self) -> Dict[str, float]:
        """Generate the incidence reduction between 2026 and 2020, per disease"""

        # Generate output relating cases
        hiv_cases_2020 = self.hiv.IC.portfolio_results["cases"].at[2020, "model_central"]
        hiv_cases_2026 = self.hiv.IC.portfolio_results["cases"].at[2026, "model_central"]
        hiv_case_reduction = (hiv_cases_2026 / hiv_cases_2020 - 1) * 100

        # Generate output relating to incidence
        hiv_incidence_2020 = self.hiv.IC.portfolio_results["cases"].at[2020, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2020, "model_central"]
        hiv_incidence_2026 = self.hiv.IC.portfolio_results["cases"].at[2026, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2026, "model_central"]
        hiv_incidence_reduction = (hiv_incidence_2026 / hiv_incidence_2020 - 1) * 100

        # Generate output relating deaths
        hiv_deaths_2020 = self.hiv.IC.portfolio_results["deaths"].at[2020, "model_central"]
        hiv_deaths_2026 = self.hiv.IC.portfolio_results["deaths"].at[2026, "model_central"]
        hiv_death_reduction = (hiv_deaths_2026 / hiv_deaths_2020 - 1) * 100

        # Generate output relating to mortality
        hiv_mortality_2020 = self.hiv.IC.portfolio_results["deaths"].at[2020, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2020, "model_central"]
        hiv_mortality_2026 = self.hiv.IC.portfolio_results["deaths"].at[2026, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2026, "model_central"]
        hiv_mortality_reduction = (hiv_mortality_2026 / hiv_mortality_2020 - 1) * 100

        # Generate output relating to service coverage
        art_coverage_2020 = self.hiv.IC.portfolio_results["art"].at[2020, "model_central"] / \
                            self.hiv.IC.portfolio_results["plhiv"].at[2020, "model_central"] * 100
        art_coverage_2026 = self.hiv.IC.portfolio_results["art"].at[2026, "model_central"] / \
                            self.hiv.IC.portfolio_results["plhiv"].at[2026, "model_central"] * 100
        art_number_2026 = self.hiv.IC.portfolio_results["art"].at[2026, "model_central"]

        return {
            "Number of new hiv infections in the year 2020": hiv_cases_2020,
            "Number of new hiv infections  in the year 2026": hiv_cases_2026,
            "Reduction in new hiv infections  between the year 2026 compared to 2020": hiv_case_reduction,

            "Hiv incidence in the year 2020": hiv_incidence_2020,
            "Hiv incidence in the year 2026": hiv_incidence_2026,
            "Reduction in hiv incidence between the year 2026 compared to 2020": hiv_incidence_reduction,

            "Number of hiv deaths in the year 2020": hiv_deaths_2020,
            "Number of  hiv deaths  in the year 2026": hiv_deaths_2026,
            "Reduction in of hiv deaths  between the year 2026 compared to 2020": hiv_death_reduction,

            "Hiv mortality rate in the year 2020": hiv_mortality_2020,
            "Hiv mortality rate in the year 2026": hiv_mortality_2026,
            "Reduction in hiv mortality rate between the year 2026 compared to 2020": hiv_mortality_reduction,

            "ART coverage in the year 2020": art_coverage_2020,
            "ART coverage in the year 2026": art_coverage_2026,
            "Number of people on ART in the year 2026": art_number_2026,
        }

    def get_key_stats_tb(self) -> Dict[str, float]:
        """ Get the key stats for tb.  """

        # Generate output relating to cases
        tb_cases_2020 = self.tb.IC.portfolio_results["cases"].at[2020, "model_central"]
        tb_cases_2026 = self.tb.IC.portfolio_results["cases"].at[2026, "model_central"]
        tb_case_reduction = (tb_cases_2026 / tb_cases_2020 - 1) * 100

        # Generate output relating to incidence
        tb_incidence_2020 = self.tb.IC.portfolio_results["cases"].at[2020, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2020, "model_central"]
        tb_incidence_2026 = self.tb.IC.portfolio_results["cases"].at[2026, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2026, "model_central"]
        tb_incidence_reduction = (tb_incidence_2026 / tb_incidence_2020 - 1) * 100

        # Generate output relating to cases
        tb_deaths_2020 = self.tb.IC.portfolio_results["deaths"].at[2020, "model_central"]
        tb_deaths_2026 = self.tb.IC.portfolio_results["deaths"].at[2026, "model_central"]
        tb_deaths_reduction = (tb_deaths_2026 / tb_deaths_2020 - 1) * 100

        tb_deaths_hivneg_2020 = self.tb.IC.portfolio_results["deathshivneg"].at[2020, "model_central"]
        tb_deaths_hivneg_2026 = self.tb.IC.portfolio_results["deathshivneg"].at[2026, "model_central"]
        tb_deaths_hivneg_reduction = (tb_deaths_hivneg_2026 / tb_deaths_hivneg_2020 - 1) * 100

        # Generate output relating to mortality related
        tb_mortality_2020 = self.tb.IC.portfolio_results["deaths"].at[2020, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2020, "model_central"]
        tb_mortality_2026 = self.tb.IC.portfolio_results["deaths"].at[2026, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2026, "model_central"]
        tb_mortality_reduction = (tb_mortality_2026 / tb_mortality_2020 - 1) * 100

        tb_mortality_hivneg_2020 = self.tb.IC.portfolio_results["deathshivneg"].at[2020, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2020, "model_central"]
        tb_mortality_hivneg_2026 = self.tb.IC.portfolio_results["deathshivneg"].at[2026, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2026, "model_central"]
        tb_mortality_hivneg_reduction = (tb_mortality_hivneg_2026 / tb_mortality_hivneg_2020 - 1) * 100

        # Generate output relating to service coverage
        notified_2024_2026 = self.tb.IC.portfolio_results["notified"].loc[
            slice(2024, 2026), "model_central"].sum()
        notified_2021_2026 = self.tb.IC.portfolio_results["notified"].loc[
            slice(2021, 2026), "model_central"].sum()
        mdr_tx_2024_2026 = self.tb.IC.portfolio_results["mdrtx"].loc[
            slice(2024, 2026), "model_central"].sum()
        mdr_tx_2021_2026 = self.tb.IC.portfolio_results["mdrtx"].loc[
            slice(2021, 2026), "model_central"].sum()
        tb_txcoverage_2020 = self.tb.IC.portfolio_results["notified"].at[2020, "model_central"] / \
                             self.tb.IC.portfolio_results["cases"].at[2020, "model_central"] * 100
        tb_txcoverage_2026 = self.tb.IC.portfolio_results["notified"].at[2026, "model_central"] / \
                             self.tb.IC.portfolio_results["cases"].at[2026, "model_central"] * 100

        return {
            "Number of TB cases in the year 2020": tb_cases_2020,
            "Number of TB cases in the year 2026": tb_cases_2026,
            "Reduction in TB cases  between the year 2026 compared to 2020 ": tb_case_reduction,

            "TB incidence in the year 2020 ": tb_incidence_2020,
            "TB incidence in the year 2026 ": tb_incidence_2026,
            "Reduction in TB incidence between the year 2026 compared to 2020 ": tb_incidence_reduction,

            "Number of TB deaths in the year 2020 ": tb_deaths_2020,
            "Number of TB deaths in the year 2026 ": tb_deaths_2026,
            "Reduction in TB deaths between the year 2026 compared to 2020": tb_deaths_reduction,

            "Number of TB deaths amongst hiv-negative individuals in the year 2020 ": tb_deaths_hivneg_2020,
            "Number of TB deaths amongst hiv-negative individuals in the year 2026 ": tb_deaths_hivneg_2026,
            "Reduction in TB deaths amongst hiv-negative individuals between the year 2026 compared to 2020": tb_deaths_hivneg_reduction,

            "TB mortality rate in the year 2020 ": tb_mortality_2020,
            "TB mortality rate in the year 2026 ": tb_mortality_2026,
            "Reduction in TB mortality rate between the year 2026 compared to 2020 ": tb_mortality_reduction,

            "TB mortality rate amongst hiv-negative individuals in the year 2020 ": tb_mortality_hivneg_2020,
            "TB mortality rate amongst hiv-negative individuals in the year 2026 ": tb_mortality_hivneg_2026,
            "Reduction in TB mortality rate amongst hiv-negative individuals between the year 2026 compared to 2020 ": tb_mortality_hivneg_reduction,

            "Number of TB notifications between 2024 and 2026 ": notified_2024_2026,
            "Number of TB notifications between 2021 and 2026 ": notified_2021_2026,
            "Number of MDR cases who received treatment between 2024 and 2026 ": mdr_tx_2024_2026,
            "Number of MDR cases who received treatment between 2021 and 2026 ": mdr_tx_2021_2026,
            "TB treatment coverage in 2020 ": tb_txcoverage_2020,
            "TB treatment coverage in 2026 ": tb_txcoverage_2026,
        }

    def get_key_stats_malaria(self) -> Dict[str, float]:
        """ Get the key stats for malaria.  """

        # Generate output relating to cases
        malaria_cases_2020 = self.malaria.IC.portfolio_results["cases"].at[2020, "model_central"]
        malaria_cases_2026 = self.malaria.IC.portfolio_results["cases"].at[2026, "model_central"]
        malaria_case_reduction = (malaria_cases_2026 / malaria_cases_2020 - 1) * 100

        # Generate output relating to incidence
        malaria_incidence_2020 = self.malaria.IC.portfolio_results["cases"].at[2020, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2020, "model_central"]
        malaria_incidence_2026 = self.malaria.IC.portfolio_results["cases"].at[2026, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2026, "model_central"]
        malaria_incidence_reduction = (malaria_incidence_2026 / malaria_incidence_2020 - 1) * 100

        # Generate output relating to mortality
        malaria_deaths_2020 = self.malaria.IC.portfolio_results["deaths"].at[2020, "model_central"]
        malaria_deaths_2026 = self.malaria.IC.portfolio_results["deaths"].at[2026, "model_central"]
        malaria_death_reduction = (malaria_deaths_2026 / malaria_deaths_2020 - 1) * 100

        # Generate output relating to mortality
        malaria_mortality_2020 = self.malaria.IC.portfolio_results["deaths"].at[2020, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2020, "model_central"]
        malaria_mortality_2026 = self.malaria.IC.portfolio_results["deaths"].at[2026, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2026, "model_central"]
        malaria_mortality_reduction = (malaria_mortality_2026 / malaria_mortality_2020 - 1) * 100

        # Generate output to service coverage
        malaria_llins_2024_2026 = self.malaria.IC.portfolio_results["llins"].loc[
            slice(2024, 2026), "model_central"].sum()

        malaria_llins_2021_2026 = self.malaria.IC.portfolio_results["llins"].loc[
            slice(2021, 2026), "model_central"].sum()

        tx_publicsector_2020_2026 = self.malaria.IC.portfolio_results["tx"].loc[
            slice(2021, 2026), "model_central"].sum()

        return {
            "Number of malaria cases in the year 2020": malaria_cases_2020,
            "Number of malaria cases in the year 2026": malaria_cases_2026,
            "Reduction in malaria cases between the year 2026 compared to 2020 ": malaria_case_reduction,

            "Malaria incidence in the year 2020": malaria_incidence_2020,
            "Malaria incidence in the year 2026": malaria_incidence_2026,
            "Reduction in malaria incidence between the year 2026 compared to 2020": malaria_incidence_reduction,

            "Number of malaria deaths in the year 2020": malaria_deaths_2020,
            "Number of malaria deaths  in the year 2026": malaria_deaths_2026,
            "Reduction in malaria deaths between the year 2026 compared to 2020": malaria_death_reduction,

            "Malaria mortality rate in the year 2020": malaria_mortality_2020,
            "Malaria mortality rate in the year 2026": malaria_mortality_2026,
            "Reduction in malaria mortality rate between the year 2026 compared to 2020": malaria_mortality_reduction,

            "Number of bed nets distributed between 2024 and 2026": malaria_llins_2024_2026,
            "Number of bed nets distributed between 2021 and 2026": malaria_llins_2021_2026,
            "Number of people treated in the public sector between 2020 and 2026": tx_publicsector_2020_2026,
        }

    def get_lives_saved(self) -> Dict[str, float]:
        """Save a graph to the outputs directory"""

        # Get lives saved for HIV
        hiv_deaths_2021_2026_ic = self.hiv.IC.portfolio_results["deaths"].loc[slice(2021, 2026), "model_central"].sum()
        hiv_deaths_2021_2026_cf = self.hiv.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()
        lives_saved_hiv_2021_2026 = hiv_deaths_2021_2026_cf - hiv_deaths_2021_2026_ic

        hiv_deaths_2024_2026_ic = self.hiv.IC.portfolio_results["deaths"].loc[slice(2024, 2026), "model_central"].sum()
        hiv_deaths_2024_2026_cf = self.hiv.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2024, 2026), "model_central"].sum()
        lives_saved_hiv_2024_2026 = hiv_deaths_2024_2026_cf - hiv_deaths_2024_2026_ic

        # Get lives saved for TB
        tb_deaths_hivneg_2021_2026_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2020, 2026), "model_central"].sum()
        tb_deaths_hivneg_2021_2026_cf = self.tb.IC.portfolio_results["deathsnotxhivneg"].loc[
            slice(2020, 2026), "model_central"].sum()
        lives_saved_tb_hivneg_2021_2026 = tb_deaths_hivneg_2021_2026_cf - tb_deaths_hivneg_2021_2026_ic

        tb_deaths_hivneg_2024_2026_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2024, 2026), "model_central"].sum()
        tb_deaths_hivneg_2024_2026_cf = self.tb.IC.portfolio_results["deathsnotxhivneg"].loc[
            slice(2024, 2026), "model_central"].sum()
        lives_saved_tb_hivneg_2024_2026 = tb_deaths_hivneg_2024_2026_cf - tb_deaths_hivneg_2024_2026_ic

        # Get lives saved for malaria
        malaria_deaths_2021_2026_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2020, 2026), "model_central"].sum()
        malaria_deaths_2021_2026_cf = self.malaria.CF_LivesSaved_Malaria.loc[2020:2026].sum()
        lives_saved_malaria_2021_2026 = malaria_deaths_2021_2026_cf - malaria_deaths_2021_2026_ic

        malaria_deaths_2024_2026_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2024, 2026), "model_central"].sum()
        malaria_deaths_2024_2026_cf = self.malaria.CF_LivesSaved_Malaria.loc[2024:2026].sum()
        lives_saved_malaria_2024_2026 = malaria_deaths_2024_2026_cf - malaria_deaths_2024_2026_ic

        return {
            "Number of lives saved relating to hiv from 2021 to 2026": lives_saved_hiv_2021_2026,
            "Number of lives saved relating to hiv from 2024 to 2026": lives_saved_hiv_2024_2026,
            "Number of lives saved relating to tb  amongst hivneg from 2021 to 2026": lives_saved_tb_hivneg_2021_2026,
            "Number of lives saved relating to tb  amongst hivneg from 2024 to 2026": lives_saved_tb_hivneg_2024_2026,
            "Number of lives saved relating to malaria from 2021 to 2026": lives_saved_malaria_2021_2026,
            "Number of lives saved relating to malaria 2024 to 2026": lives_saved_malaria_2024_2026,
        }

    def get_infections_averted(self) -> dict[str, Any]:
        """ Generate infections averted """

        # Get infections averted for HIV
        hiv_cases_2024_2026_ic = self.hiv.IC.portfolio_results["cases"].loc[slice(2024, 2026), "model_central"].sum()
        hiv_cases_2024_2026_cf = self.hiv.CF_InfAve.portfolio_results["cases"].loc[
            slice(2024, 2026), "model_central"].sum()
        infections_averted_2024_2026_hiv = hiv_cases_2024_2026_cf - hiv_cases_2024_2026_ic

        # Get infections averted for TB
        tb_cases_2024_2026_ic = self.tb.IC.portfolio_results["cases"].loc[slice(2024, 2026), "model_central"].sum()
        tb_cases_2024_2026_cf = self.tb.CF_InfAve.portfolio_results["cases"].loc[
            slice(2024, 2026), "model_central"].sum()
        infections_averted_2024_2026_tb = tb_cases_2024_2026_cf - tb_cases_2024_2026_ic

        # Get infections averted for malaria
        malaria_cases_2024_2026_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2024, 2026), "model_central"].sum()
        malaria_cases_2024_2026_cf = self.malaria.CF_InfectionsAverted_Malaria.loc[2024:2026].sum()
        infections_averted_2024_2026_malaria = malaria_cases_2024_2026_cf - malaria_cases_2024_2026_ic

        return {
            "Infections averted relating to HIV from 2024 to 2026": infections_averted_2024_2026_hiv,
            "Infections averted relating to TB from 2024 to 2026": infections_averted_2024_2026_tb,
            "Infections averted relating to malaria from 2024 to 2026": infections_averted_2024_2026_malaria,
        }

    def hiv_cases(self) -> pd.DataFrame:
        """Produce graph for HIV cases"""
        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': self.hiv.PARTNER['cases'],
                'GP': self.hiv.CF_forgraphs['cases'],
                'Counterfactual': self.hiv.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': self.hiv.IC.portfolio_results['cases']['model_central'],
                'IC_LB': self.hiv.IC.portfolio_results['cases']['model_low'],
                'IC_UB': self.hiv.IC.portfolio_results['cases']['model_high'],
            }
        )

    def hiv_deaths(self) -> pd.DataFrame:
        """Produce graph for HIV deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': self.hiv.PARTNER['deaths'],
                'GP': self.hiv.CF_forgraphs['deaths'],
                'Counterfactual': self.hiv.CF_InfAve.portfolio_results['deaths']['model_central'],
                'IC': self.hiv.IC.portfolio_results['deaths']['model_central'],
                'IC_LB': self.hiv.IC.portfolio_results['deaths']['model_low'],
                'IC_UB': self.hiv.IC.portfolio_results['deaths']['model_high'],
            }
        )

    def tb_cases(self) -> pd.DataFrame:
        """Produce graph for TB cases"""
        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': self.tb.PARTNER['cases'],
                'GP': self.tb.CF_forgraphs['cases'],
                'Counterfactual': self.tb.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': self.tb.IC.portfolio_results['cases']['model_central'],
                'IC_LB': self.tb.IC.portfolio_results['cases']['model_low'],
                'IC_UB': self.tb.IC.portfolio_results['cases']['model_high'],
            }
        )

    def tb_deaths(self) -> pd.DataFrame:
        """Produce graph for TB deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': self.tb.PARTNER['deaths'],
                'GP': self.tb.CF_forgraphs['deaths'],
                'Counterfactual': self.tb.CF_InfAve.portfolio_results['deaths']['model_central'],
                'IC': self.tb.IC.portfolio_results['deaths']['model_central'],
                'IC_LB': self.tb.IC.portfolio_results['deaths']['model_low'],
                'IC_UB': self.tb.IC.portfolio_results['deaths']['model_high'],
            }
        )

    def mal_cases(self) -> pd.DataFrame:
        """Produce graph for malaria cases"""
        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': self.malaria.PARTNER['cases'],
                'GP': self.malaria.CF_forgraphs['cases'],
                'Counterfactual': self.malaria.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': self.malaria.IC.portfolio_results['cases']['model_central'],
                'IC_LB': self.malaria.IC.portfolio_results['cases']['model_low'],
                'IC_UB': self.malaria.IC.portfolio_results['cases']['model_high'],
            }
        )

    def mal_deaths(self) -> pd.DataFrame:
        """Produce graph for malaria deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': self.malaria.PARTNER['deaths'],
                'GP': self.malaria.CF_forgraphs['deaths'],
                'Counterfactual': self.malaria.CF_InfAve.portfolio_results['deaths']['model_central'],
                'IC': self.malaria.IC.portfolio_results['deaths']['model_central'],
                'IC_LB': self.malaria.IC.portfolio_results['deaths']['model_low'],
                'IC_UB': self.malaria.IC.portfolio_results['deaths']['model_high'],
            }
        )

    def get_combined_stats(self) -> dict[str, Any]:
        """ Generate combined stats """

        # Get deaths in 2020 for each disease
        hiv_deaths_2020 = self.hiv.IC.portfolio_results["deaths"].at[2020, "model_central"]
        tb_deaths_2020 = self.tb.IC.portfolio_results["deaths"].at[2020, "model_central"]
        malaria_deaths_2020 = self.malaria.IC.portfolio_results["deaths"].at[2020, "model_central"]
        total_deaths_2020 = hiv_deaths_2020 + tb_deaths_2020 + malaria_deaths_2020

        # Get deaths in 2026 for each disease
        hiv_deaths_2026 = self.hiv.IC.portfolio_results["deaths"].at[2026, "model_central"]
        tb_deaths_2026 = self.tb.IC.portfolio_results["deaths"].at[2026, "model_central"]
        malaria_deaths_2026 = self.malaria.IC.portfolio_results["deaths"].at[2026, "model_central"]
        total_deaths_2026 = hiv_deaths_2026 + tb_deaths_2026 + malaria_deaths_2026

        # Get sum of deaths from IC for 2021 to 2026
        hiv_deaths_2021_2026_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()
        tb_deaths_2021_2026_ic = self.tb.IC.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()
        malaria_deaths_2021_2026_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()

        # Get deaths averted from CFs for 2021 to 2026
        hiv_deaths_2021_2026_cf = self.hiv.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()
        tb_deaths_2021_2026_cf = self.tb.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()
        malaria_deaths_2021_2026_cf = self.malaria.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2021, 2026), "model_central"].sum()

        # Compute deaths averted
        hiv_deaths_averted_2021_2026 = hiv_deaths_2021_2026_cf - hiv_deaths_2021_2026_ic
        tb_deaths_averted_2021_2026 = tb_deaths_2021_2026_cf - tb_deaths_2021_2026_ic
        malaria_deaths_averted_2021_2026 = malaria_deaths_2021_2026_cf - malaria_deaths_2021_2026_ic
        total_deaths_averted = hiv_deaths_averted_2021_2026 + tb_deaths_averted_2021_2026 + malaria_deaths_averted_2021_2026

        return {
            "Total number of deaths from 3 diseases in 2020 ": total_deaths_2020,
            "Total number of deaths from 3 diseases in 2026 ": total_deaths_2026,
            "Deaths averted (covid disruption) for HIV 2021 to 2026": hiv_deaths_averted_2021_2026,
            "Deaths averted (covid disruption) for TB 2021 to 2026": tb_deaths_averted_2021_2026,
            "Deaths averted (covid disruption) for malaria 2021 to 2026": malaria_deaths_averted_2021_2026,
            "Total Deaths averted (covid disruption) for hiv 2021 to 2026": total_deaths_averted,
        }

    def _post_processing_on_workbook(self, workbook: Workbook):
        """Create a simple version of the killer graph."""

        def _make_simple_graph(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
            """On the worksheet provided, make a simple graph to illustrate the killer graph.
            From: https://realpython.com/openpyxl-excel-spreadsheets-python/#adding-pretty-charts
            """
            # References to the data
            data = Reference(ws, min_col=2, min_row=1, max_col=7, max_row=13)
            categories = Reference(ws, min_col=1, min_row=2, max_row=13)

            # Plot standard chart
            c1 = LineChart()
            c1.title = ws.title
            c1.style = 13
            c1.y_axis.title = ''
            c1.x_axis.title = 'Year'

            c1.add_data(data, titles_from_data=True)
            c1.set_categories(categories)

            # Style the lines
            s1 = c1.series[0]
            s1.marker.symbol = "triangle"
            s1.marker.graphicalProperties.solidFill = "FF0000"  # Marker filling
            s1.marker.graphicalProperties.line.solidFill = "FF0000"  # Marker outline
            s1.graphicalProperties.line.noFill = True

            s2 = c1.series[1]
            s2.graphicalProperties.line.solidFill = "00AAAA"
            s2.graphicalProperties.line.dashStyle = "sysDot"
            s2.graphicalProperties.line.width = 100050  # width in EMUs

            ws.add_chart(c1, "K2")

        sheets_for_graphs = [
            'hiv_cases',
            'hiv_deaths',
            'tb_cases',
            'tb_deaths',
            'mal_cases',
            'mal_deaths',
            'comb_mort',
            'comb_inc',
        ]

        for sheet in sheets_for_graphs:
            _make_simple_graph(workbook[sheet])

    def comb_mort(self) -> dict[str, Any]:
        """ Generate combined mortality stats """

        # Step 1. Get data for each disease from partner
        hiv_deaths_partner = self.hiv.PARTNER["deaths"]
        tb_deaths_partner = self.tb.PARTNER["deathshivneg"]
        malaria_deaths_partner = self.malaria.PARTNER["deaths"]

        hiv_pop_partner = self.hiv.PARTNER["population"]
        tb_pop_partner = self.tb.PARTNER["population"]
        malaria_pop_partner = self.malaria.PARTNER["par"]

        hiv_mortality_partner = hiv_deaths_partner / hiv_pop_partner
        tb_mortality_partner = tb_deaths_partner / tb_pop_partner
        malaria_mortality_partner = malaria_deaths_partner / malaria_pop_partner

        # Step 2.1 Get mortality for each disease from IC including LB and UB
        hiv_deaths_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_central"]
        hiv_deaths_lb_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_low"]
        hiv_deaths_ub_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_high"]

        tb_deaths_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2021, 2030), "model_central"]
        tb_deaths_lb_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2021, 2030), "model_low"]
        tb_deaths_ub_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2021, 2030), "model_high"]

        malaria_deaths_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_central"]
        malaria_deaths_lb_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_low"]
        malaria_deaths_ub_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_high"]

        hiv_pop_ic = self.hiv.IC.portfolio_results["population"].loc[
            slice(2021, 2030), "model_central"]
        tb_pop_ic = self.tb.IC.portfolio_results["population"].loc[
            slice(2021, 2030), "model_central"]
        malaria_pop_ic = self.malaria.IC.portfolio_results["par"].loc[
            slice(2021, 2030), "model_central"]

        hiv_mortality_ic = hiv_deaths_ic / hiv_pop_ic
        tb_mortality_ic = tb_deaths_ic / tb_pop_ic
        malaria_mortality_ic = malaria_deaths_ic / malaria_pop_ic

        hiv_mortality_lb_ic = hiv_deaths_lb_ic / hiv_pop_ic
        tb_mortality_lb_ic = tb_deaths_lb_ic / tb_pop_ic
        malaria_mortality_lb_ic = malaria_deaths_lb_ic / malaria_pop_ic

        hiv_mortality_ub_ic = hiv_deaths_ub_ic / hiv_pop_ic
        tb_mortality_ub_ic = tb_deaths_ub_ic / tb_pop_ic
        malaria_mortality_ub_ic = malaria_deaths_ub_ic / malaria_pop_ic

        # Step 2.2 Get incidence for each disease from Covid disruption
        hiv_deaths_cf = self.hiv.CF_InfAve.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_central"]
        tb_deaths_cf = self.tb.CF_InfAve.portfolio_results["deathshivneg"].loc[
            slice(2021, 2030), "model_central"]
        malaria_deaths_cf = self.malaria.CF_InfAve.portfolio_results["deaths"].loc[
            slice(2021, 2030), "model_central"]

        hiv_pop_cf = self.hiv.CF_InfAve.portfolio_results["population"].loc[
            slice(2021, 2030), "model_central"]
        tb_pop_cf = self.tb.CF_InfAve.portfolio_results["population"].loc[
            slice(2021, 2030), "model_central"]
        malaria_pop_cf = self.malaria.CF_InfAve.portfolio_results["par"].loc[
            slice(2021, 2030), "model_central"]

        hiv_mortality_cf = hiv_deaths_cf / hiv_pop_cf
        tb_mortality_cf = tb_deaths_cf / tb_pop_cf
        malaria_mortality_cf = malaria_deaths_cf / malaria_pop_cf

        # Step 2.3 Get incidence for each disease from GP
        hiv_deaths_gp = self.hiv.CF_forgraphs["deaths"]
        hiv_pop_gp = self.hiv.CF_forgraphs["population"]
        hiv_mortality_gp = hiv_deaths_gp / hiv_pop_gp
        hiv_mortality_gp = pd.DataFrame(hiv_mortality_gp)
        hiv_mortality_gp = hiv_mortality_gp[hiv_mortality_gp.index > 2020]

        tb_mortality_gp = self.tb.CF_forgraphs["mortalityhivneg"]
        tb_mortality_gp = pd.DataFrame(tb_mortality_gp)
        tb_mortality_gp = tb_mortality_gp[tb_mortality_gp.index >2020]

        malaria_mortality_gp = self.malaria.CF_forgraphs["mortality"]
        malaria_mortality_gp = pd.DataFrame(malaria_mortality_gp)
        malaria_mortality_gp = malaria_mortality_gp[malaria_mortality_gp.index > 2020]

        # Step 3.1 Normalise each disease to 100 in 2020 for partner and IC
        combined_hiv_mortality = pd.concat([hiv_mortality_partner,hiv_mortality_ic])
        combined_hiv_mortality = pd.DataFrame(combined_hiv_mortality)
        combined_hiv_mortality = 100*(combined_hiv_mortality / combined_hiv_mortality.iloc[5,:])

        combined_tb_mortality = pd.concat([tb_mortality_partner, tb_mortality_ic])
        combined_tb_mortality = pd.DataFrame(combined_tb_mortality)
        combined_tb_mortality = 100 * (combined_tb_mortality / combined_tb_mortality.iloc[5, :])

        combined_malaria_mortality = pd.concat([malaria_mortality_partner, malaria_mortality_ic])
        combined_malaria_mortality = pd.DataFrame(combined_malaria_mortality)
        combined_malaria_mortality = 100 * (combined_malaria_mortality / combined_malaria_mortality.iloc[5, :])

        # Step 3.2. Normalise the LB and UB for the IC
        combined_hiv_mortality_lb = pd.concat([hiv_mortality_partner, hiv_mortality_lb_ic])
        combined_hiv_mortality_lb = pd.DataFrame(combined_hiv_mortality_lb)
        combined_hiv_mortality_lb = 100 * (combined_hiv_mortality_lb / combined_hiv_mortality_lb.iloc[5, :])
        combined_hiv_mortality_ub = pd.concat([hiv_mortality_partner, hiv_mortality_ub_ic])
        combined_hiv_mortality_ub = pd.DataFrame(combined_hiv_mortality_ub)
        combined_hiv_mortality_ub = 100 * (combined_hiv_mortality_ub / combined_hiv_mortality_ub.iloc[5, :])

        combined_tb_mortality_ub = pd.concat([tb_mortality_partner, tb_mortality_lb_ic])
        combined_tb_mortality_lb = pd.DataFrame(combined_tb_mortality_ub)
        combined_tb_mortality_lb = 100 * (combined_tb_mortality_lb / combined_tb_mortality_lb.iloc[5, :])
        combined_tb_mortality_ub = pd.concat([tb_mortality_partner, tb_mortality_ub_ic])
        combined_tb_mortality_ub = pd.DataFrame(combined_tb_mortality_ub)
        combined_tb_mortality_ub = 100 * (combined_tb_mortality_ub / combined_tb_mortality_ub.iloc[5, :])

        combined_malaria_mortality_lb = pd.concat([malaria_mortality_partner, malaria_mortality_lb_ic])
        combined_malaria_mortality_lb = pd.DataFrame(combined_malaria_mortality_lb)
        combined_malaria_mortality_lb = 100 * (combined_malaria_mortality_lb / combined_malaria_mortality_lb.iloc[5, :])
        combined_malaria_mortality_ub = pd.concat([malaria_mortality_partner, malaria_mortality_ub_ic])
        combined_malaria_mortality_ub = pd.DataFrame(combined_malaria_mortality_ub)
        combined_malaria_mortality_ub = 100 * (combined_malaria_mortality_ub / combined_malaria_mortality_ub.iloc[5, :])

        # Back calculate SD at
        hiv_sd = (hiv_mortality_ub_ic - hiv_mortality_ic)/1.96
        tb_sd = (tb_mortality_ub_ic - tb_mortality_ic) / 1.96
        malaria_sd = (malaria_mortality_ub_ic - malaria_mortality_ic) / 1.96
        sds = pd.DataFrame({"hiv":hiv_sd, "tb":tb_sd, "malaria":malaria_sd})

        # Prepare to generate CIs
        rho_btw_diseases = self.parameters.get("RHO_BETWEEN_DISEASES")
        years = list(range(2021, 2031))
        combined_temp = (hiv_mortality_ic + tb_mortality_ic + malaria_mortality_ic) / 3

        # Make an empty dataframe
        ic_bounds = pd.DataFrame(index = years, columns=["low", "high"])

        # Calculate combined sd across diseases
        for y in years:

            # Grab the sd for that year
            _sd =  sds.loc[sds.index == y]
            _sd = _sd.iloc[0].to_numpy()

            # Grab the model central (average across diseases) for that year
            _combined_temp = combined_temp[combined_temp.index == y]

            sd_for_year = ((
                                  matmul(_sd).sum() * rho_btw_diseases
                                  + (_sd ** 2).sum() * (1 - rho_btw_diseases)
                          ) ** 0.5)/3
            model_low = _combined_temp - 1.96 * sd_for_year
            model_high = _combined_temp + 1.96 * sd_for_year

            ic_bounds['low'][y] = model_low.iloc[0]
            ic_bounds['high'][y] = model_high.iloc[0]

        # Step 3.2 Normalise the LB and UB
        combined_partner = (hiv_mortality_partner + tb_mortality_partner + malaria_mortality_partner)/3
        low = ic_bounds['low']
        high = ic_bounds['high']

        combined_lb = pd.concat([combined_partner, low])
        combined_lb = pd.DataFrame(combined_lb)
        combined_lb = 100 * (combined_lb / combined_lb.iloc[5, :])

        combined_ub = pd.concat([combined_partner, high])
        combined_ub = pd.DataFrame(combined_ub)
        combined_ub = 100 * (combined_ub / combined_ub.iloc[5, :])

        # Step 3.2 Normalise each disease to 100 in 2020 for Covid disruption
        combined_hiv_mortality_cf = pd.concat([hiv_mortality_partner, hiv_mortality_cf])
        combined_hiv_mortality_cf = pd.DataFrame(combined_hiv_mortality_cf)
        combined_hiv_mortality_cf = 100 * (combined_hiv_mortality_cf / combined_hiv_mortality_cf.iloc[5, :])

        combined_tb_mortality_cf = pd.concat([tb_mortality_partner, tb_mortality_cf])
        combined_tb_mortality_cf = pd.DataFrame(combined_tb_mortality_cf)
        combined_tb_mortality_cf = 100 * (combined_tb_mortality_cf / combined_tb_mortality_cf.iloc[5, :])

        combined_malaria_mortality_cf = pd.concat([malaria_mortality_partner, malaria_mortality_cf])
        combined_malaria_mortality_cf = pd.DataFrame(combined_malaria_mortality_cf)
        combined_malaria_mortality_cf = 100 * (combined_malaria_mortality_cf / combined_malaria_mortality_cf.iloc[5, :])

        # Step 3.3 Normalise each disease to 100 in 2020 for GP
        combined_hiv_mortality_gp = pd.concat([hiv_mortality_partner, hiv_mortality_gp])
        combined_hiv_mortality_gp = pd.DataFrame(combined_hiv_mortality_gp)
        combined_hiv_mortality_gp = 100 * (combined_hiv_mortality_gp / combined_hiv_mortality_gp.iloc[5, :])

        combined_tb_mortality_gp = pd.concat([tb_mortality_partner, tb_mortality_gp])
        combined_tb_mortality_gp = combined_tb_mortality_gp.bfill(axis=1).iloc[:, 0]
        combined_tb_mortality_gp = pd.DataFrame(combined_tb_mortality_gp)
        combined_tb_mortality_gp = 100 * (combined_tb_mortality_gp / combined_tb_mortality_gp.iloc[5, :])

        combined_malaria_mortality_gp = pd.concat([malaria_mortality_partner, malaria_mortality_gp])
        combined_malaria_mortality_gp = combined_malaria_mortality_gp.bfill(axis=1).iloc[:, 0]
        combined_malaria_mortality_gp = pd.DataFrame(combined_malaria_mortality_gp)
        combined_malaria_mortality_gp = 100 * (combined_malaria_mortality_gp / combined_malaria_mortality_gp.iloc[5, :])

        # Step 4. Combine the three normalised incidence rates by doing simple average
        combined_mortality = (combined_hiv_mortality + combined_tb_mortality + combined_malaria_mortality)/3
        combined_mortality_cf = (combined_hiv_mortality_cf + combined_tb_mortality_cf + combined_malaria_mortality_cf) / 3
        combined_mortality_gp = (combined_hiv_mortality_gp + combined_tb_mortality_gp + combined_malaria_mortality_gp) / 3

        # Compute the needed reductions
        reduction_ic = combined_mortality.loc[2026, 0] - 100
        reduction_cf = combined_mortality_cf.loc[2026, 0] - 100

        # Clean up so we can output the graphs
        actual = combined_mortality.loc[combined_mortality.index <2021].iloc[:,0]
        gp = combined_mortality_gp.loc[combined_mortality_gp.index > 2020].iloc[:,0]
        cf = combined_mortality_cf.loc[combined_mortality_cf.index >2019 ].iloc[:,0]
        ic = combined_mortality.loc[combined_mortality.index > 2019].iloc[:,0]
        ic_lb = combined_lb.loc[combined_lb.index > 2020].iloc[:,0]
        ic_ub = combined_ub.loc[combined_ub.index > 2020].iloc[:,0]

        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': actual,
                'GP': gp,
                'Counterfactual': cf,
                'IC': ic,
                'IC_LB': ic_lb,
                'IC_UB': ic_ub,
            }
        )

    def comb_inc(self) -> dict[str, Any]:
        """ Generate combined incidence stats """

        # Step 1. Get data for each disease from partner
        hiv_cases_partner = self.hiv.PARTNER["cases"]
        tb_cases_partner = self.tb.PARTNER["cases"]
        malaria_cases_partner = self.malaria.PARTNER["cases"]

        hiv_pop_partner = self.hiv.PARTNER["hivneg"]
        tb_pop_partner = self.tb.PARTNER["population"]
        malaria_pop_partner = self.malaria.PARTNER["par"]

        hiv_incidence_partner = hiv_cases_partner / hiv_pop_partner
        tb_incidence_partner = tb_cases_partner / tb_pop_partner
        malaria_incidence_partner = malaria_cases_partner / malaria_pop_partner

        # Step 2.1 Get incidence for each disease from IC including LB and UB
        hiv_cases_ic = self.hiv.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_central"]
        hiv_cases_lb_ic = self.hiv.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_low"]
        hiv_cases_ub_ic = self.hiv.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_high"]

        tb_cases_ic = self.tb.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_central"]
        tb_cases_lb_ic = self.tb.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_low"]
        tb_cases_ub_ic = self.tb.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_high"]

        malaria_cases_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_central"]
        malaria_cases_lb_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_low"]
        malaria_cases_ub_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_high"]

        hiv_pop_ic = self.hiv.IC.portfolio_results["hivneg"].loc[
            slice(2021, 2030), "model_central"]
        tb_pop_ic = self.tb.IC.portfolio_results["population"].loc[
            slice(2021, 2030), "model_central"]
        malaria_pop_ic = self.malaria.IC.portfolio_results["par"].loc[
            slice(2021, 2030), "model_central"]

        hiv_incidence_ic = hiv_cases_ic / hiv_pop_ic
        tb_incidence_ic = tb_cases_ic / tb_pop_ic
        malaria_incidence_ic = malaria_cases_ic / malaria_pop_ic

        hiv_incidence_lb_ic = hiv_cases_lb_ic / hiv_pop_ic
        tb_incidence_lb_ic = tb_cases_lb_ic / tb_pop_ic
        malaria_incidence_lb_ic = malaria_cases_lb_ic / malaria_pop_ic

        hiv_incidence_ub_ic = hiv_cases_ub_ic / hiv_pop_ic
        tb_incidence_ub_ic = tb_cases_ub_ic / tb_pop_ic
        malaria_incidence_ub_ic = malaria_cases_ub_ic / malaria_pop_ic

        # Step 2.2 Get incidence for each disease from Covid disruption
        hiv_cases_cf = self.hiv.CF_InfAve.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_central"]
        tb_cases_cf = self.tb.CF_InfAve.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_central"]
        malaria_cases_cf = self.malaria.CF_InfAve.portfolio_results["cases"].loc[
            slice(2021, 2030), "model_central"]

        hiv_pop_cf = self.hiv.CF_InfAve.portfolio_results["hivneg"].loc[
            slice(2021, 2030), "model_central"]
        tb_pop_cf = self.tb.CF_InfAve.portfolio_results["population"].loc[
            slice(2021, 2030), "model_central"]
        malaria_pop_cf = self.malaria.CF_InfAve.portfolio_results["par"].loc[
            slice(2021, 2030), "model_central"]

        hiv_incidence_cf = hiv_cases_cf / hiv_pop_cf
        tb_incidence_cf = tb_cases_cf / tb_pop_cf
        malaria_incidence_cf = malaria_cases_cf / malaria_pop_cf

        # Step 2.3 Get incidence for each disease from GP
        hiv_cases_gp = self.hiv.CF_forgraphs["cases"]
        hiv_pop_gp = self.hiv.CF_forgraphs["hivneg"]
        hiv_incidence_gp = hiv_cases_gp / hiv_pop_gp
        hiv_incidence_gp = pd.DataFrame(hiv_incidence_gp)
        hiv_incidence_gp = hiv_incidence_gp[hiv_incidence_gp.index > 2020]

        tb_incidence_gp = self.tb.CF_forgraphs["incidence"]
        tb_incidence_gp = pd.DataFrame(tb_incidence_gp)
        tb_incidence_gp = tb_incidence_gp[tb_incidence_gp.index >2020]

        malaria_incidence_gp = self.malaria.CF_forgraphs["incidence"]
        malaria_incidence_gp = pd.DataFrame(malaria_incidence_gp)
        malaria_incidence_gp = malaria_incidence_gp[malaria_incidence_gp.index > 2020]

        # Step 3.1 Normalise each disease to 100 in 2020 for partner and IC
        combined_hiv_incidence = pd.concat([hiv_incidence_partner,hiv_incidence_ic])
        combined_hiv_incidence = pd.DataFrame(combined_hiv_incidence)
        combined_hiv_incidence = 100*(combined_hiv_incidence / combined_hiv_incidence.iloc[5,:])

        combined_tb_incidence = pd.concat([tb_incidence_partner, tb_incidence_ic])
        combined_tb_incidence = pd.DataFrame(combined_tb_incidence)
        combined_tb_incidence = 100 * (combined_tb_incidence / combined_tb_incidence.iloc[5, :])

        combined_malaria_incidence = pd.concat([malaria_incidence_partner, malaria_incidence_ic])
        combined_malaria_incidence = pd.DataFrame(combined_malaria_incidence)
        combined_malaria_incidence = 100 * (combined_malaria_incidence / combined_malaria_incidence.iloc[5, :])

        # Step 3.2. Normalise the LB and UB for the IC
        combined_hiv_incidence_lb = pd.concat([hiv_incidence_partner, hiv_incidence_lb_ic])
        combined_hiv_incidence_lb = pd.DataFrame(combined_hiv_incidence_lb)
        combined_hiv_incidence_lb = 100 * (combined_hiv_incidence_lb / combined_hiv_incidence_lb.iloc[5, :])
        combined_hiv_incidence_ub = pd.concat([hiv_incidence_partner, hiv_incidence_ub_ic])
        combined_hiv_incidence_ub = pd.DataFrame(combined_hiv_incidence_ub)
        combined_hiv_incidence_ub = 100 * (combined_hiv_incidence_ub / combined_hiv_incidence_ub.iloc[5, :])

        combined_tb_incidence_ub = pd.concat([tb_incidence_partner, tb_incidence_lb_ic])
        combined_tb_incidence_lb = pd.DataFrame(combined_tb_incidence_ub)
        combined_tb_incidence_lb = 100 * (combined_tb_incidence_lb / combined_tb_incidence_lb.iloc[5, :])
        combined_tb_incidence_ub = pd.concat([tb_incidence_partner, tb_incidence_ub_ic])
        combined_tb_incidence_ub = pd.DataFrame(combined_tb_incidence_ub)
        combined_tb_incidence_ub = 100 * (combined_tb_incidence_ub / combined_tb_incidence_ub.iloc[5, :])

        combined_malaria_incidence_lb = pd.concat([malaria_incidence_partner, malaria_incidence_lb_ic])
        combined_malaria_incidence_lb = pd.DataFrame(combined_malaria_incidence_lb)
        combined_malaria_incidence_lb = 100 * (combined_malaria_incidence_lb / combined_malaria_incidence_lb.iloc[5, :])
        combined_malaria_incidence_ub = pd.concat([malaria_incidence_partner, malaria_incidence_ub_ic])
        combined_malaria_incidence_ub = pd.DataFrame(combined_malaria_incidence_ub)
        combined_malaria_incidence_ub = 100 * (combined_malaria_incidence_ub / combined_malaria_incidence_ub.iloc[5, :])

        # Back calculate SD at
        hiv_sd = (hiv_incidence_ub_ic - hiv_incidence_ic) / 1.96
        tb_sd = (tb_incidence_ub_ic - tb_incidence_ic) / 1.96
        malaria_sd = (malaria_incidence_ub_ic - malaria_incidence_ic) / 1.96
        sds = pd.DataFrame({"hiv": hiv_sd, "tb": tb_sd, "malaria": malaria_sd})

        # Prepare to generate CIs
        rho_btw_diseases = self.parameters.get("RHO_BETWEEN_DISEASES")
        years = list(range(2021, 2031))
        combined_temp = (hiv_incidence_ic + tb_incidence_ic + malaria_incidence_ic) / 3

        # Make an empty dataframe
        ic_bounds = pd.DataFrame(index=years, columns=["low", "high"])

        # Calculate combined sd across diseases
        for y in years:
            # Grab the sd for that year
            _sd = sds.loc[sds.index == y]
            _sd = _sd.iloc[0].to_numpy()

            # Grab the model central (average across diseases) for that year
            _combined_temp = combined_temp[combined_temp.index == y]

            sd_for_year = ((
                                   matmul(_sd).sum() * rho_btw_diseases
                                   + (_sd ** 2).sum() * (1 - rho_btw_diseases)
                           ) ** 0.5) / 3
            model_low = _combined_temp - 1.96 * sd_for_year
            model_high = _combined_temp + 1.96 * sd_for_year

            ic_bounds['low'][y] = model_low.iloc[0]
            ic_bounds['high'][y] = model_high.iloc[0]

        # Step 3.2 Normalise the LB and UB
        combined_partner = (hiv_incidence_partner + tb_incidence_partner + malaria_incidence_partner) / 3
        low = ic_bounds['low']
        high = ic_bounds['high']

        combined_lb = pd.concat([combined_partner, low])
        combined_lb = pd.DataFrame(combined_lb)
        combined_lb = 100 * (combined_lb / combined_lb.iloc[5, :])

        combined_ub = pd.concat([combined_partner, high])
        combined_ub = pd.DataFrame(combined_ub)
        combined_ub = 100 * (combined_ub / combined_ub.iloc[5, :])

        # Step 3.2 Normalise each disease to 100 in 2020 for Covid disruption
        combined_hiv_incidence_cf = pd.concat([hiv_incidence_partner, hiv_incidence_cf])
        combined_hiv_incidence_cf = pd.DataFrame(combined_hiv_incidence_cf)
        combined_hiv_incidence_cf = 100 * (combined_hiv_incidence_cf / combined_hiv_incidence_cf.iloc[5, :])

        combined_tb_incidence_cf = pd.concat([tb_incidence_partner, tb_incidence_cf])
        combined_tb_incidence_cf = pd.DataFrame(combined_tb_incidence_cf)
        combined_tb_incidence_cf = 100 * (combined_tb_incidence_cf / combined_tb_incidence_cf.iloc[5, :])

        combined_malaria_incidence_cf = pd.concat([malaria_incidence_partner, malaria_incidence_cf])
        combined_malaria_incidence_cf = pd.DataFrame(combined_malaria_incidence_cf)
        combined_malaria_incidence_cf = 100 * (combined_malaria_incidence_cf / combined_malaria_incidence_cf.iloc[5, :])

        # Step 3.3 Normalise each disease to 100 in 2020 for GP
        combined_hiv_incidence_gp = pd.concat([hiv_incidence_partner, hiv_incidence_gp])
        combined_hiv_incidence_gp = pd.DataFrame(combined_hiv_incidence_gp)
        combined_hiv_incidence_gp = 100 * (combined_hiv_incidence_gp / combined_hiv_incidence_gp.iloc[5, :])

        combined_tb_incidence_gp = pd.concat([tb_incidence_partner, tb_incidence_gp])
        combined_tb_incidence_gp = combined_tb_incidence_gp.bfill(axis=1).iloc[:, 0]
        combined_tb_incidence_gp = pd.DataFrame(combined_tb_incidence_gp)
        combined_tb_incidence_gp = 100 * (combined_tb_incidence_gp / combined_tb_incidence_gp.iloc[5, :])

        combined_malaria_incidence_gp = pd.concat([malaria_incidence_partner, malaria_incidence_gp])
        combined_malaria_incidence_gp = combined_malaria_incidence_gp.bfill(axis=1).iloc[:, 0]
        combined_malaria_incidence_gp = pd.DataFrame(combined_malaria_incidence_gp)
        combined_malaria_incidence_gp = 100 * (combined_malaria_incidence_gp / combined_malaria_incidence_gp.iloc[5, :])

        # Step 4. Combine the three normalised incidence rates by doing simple average
        combined_incidence = (combined_hiv_incidence + combined_tb_incidence + combined_malaria_incidence)/3
        combined_incidence_lb = (combined_hiv_incidence_lb + combined_tb_incidence_lb + combined_malaria_incidence_lb) / 3
        combined_incidence_ub = (combined_hiv_incidence_ub + combined_tb_incidence_ub + combined_malaria_incidence_ub) / 3
        combined_incidence_cf = (combined_hiv_incidence_cf + combined_tb_incidence_cf + combined_malaria_incidence_cf) / 3
        combined_incidence_gp = (combined_hiv_incidence_gp + combined_tb_incidence_gp + combined_malaria_incidence_gp) / 3

        # Compute the needed reductions
        reduction_ic = combined_incidence.loc[2026, 0] - 100
        reduction_cf = combined_incidence_cf.loc[2026, 0] - 100

        # Clean up so we can output the graphs
        actual = combined_incidence.loc[combined_incidence.index <2021].iloc[:,0]
        gp = combined_incidence_gp.loc[combined_incidence_gp.index > 2020].iloc[:,0]
        cf = combined_incidence_cf.loc[combined_incidence_cf.index >2019 ].iloc[:,0]
        ic = combined_incidence.loc[combined_incidence.index > 2019].iloc[:,0]
        ic_lb = combined_incidence_lb.loc[combined_incidence_lb.index > 2020].iloc[:,0]
        ic_ub = combined_incidence_ub.loc[combined_incidence_ub.index > 2020].iloc[:,0]

        return pd.DataFrame(
            index=pd.Index(list(range(2015, 2027)), name='Year'),
            data={
                'Actual': actual,
                'GP': gp,
                'Counterfactual': cf,
                'IC': ic,
                'IC_LB': ic_lb,
                'IC_UB': ic_ub,
            }
        )
