from typing import Dict, Any, NamedTuple

import openpyxl
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import Reference, LineChart

from tgftools.analysis import PortfolioProjection
from tgftools.filehandler import Parameters
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
    Each member function returns a Dict of the form {<label>: <stat>} which are assembled into an output Excel file.

    This is where we can access all data from all the scenarios we have defined, including the IC scenario and produce
    the data for the key graphs and key stats.

    CAUTION: the years and details of what is being extracted for the final report needs to be reviewed and done with
    care. The years and specific variables (e.g. tb deaths including or excluding hiv positive individuals).
    """

    def __init__(
            self,
            hiv: SetOfPortfolioProjections,
            tb: SetOfPortfolioProjections,
            malaria: SetOfPortfolioProjections,
            parameters: Parameters
    ):
        # Save arguments
        self.parameters = parameters
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
        """Generate the incidence reduction between 2029 and 2023, per disease"""

        # Generate output relating cases
        hiv_cases_2023 = self.hiv.IC.portfolio_results["cases"].at[2023, "model_central"]
        hiv_cases_2029 = self.hiv.IC.portfolio_results["cases"].at[2029, "model_central"]
        hiv_case_reduction = (hiv_cases_2029 / hiv_cases_2023 - 1) * 100

        # Generate output relating to incidence
        hiv_incidence_2023 = self.hiv.IC.portfolio_results["cases"].at[2023, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2023, "model_central"]
        hiv_incidence_2029 = self.hiv.IC.portfolio_results["cases"].at[2029, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2029, "model_central"]
        hiv_incidence_reduction = (hiv_incidence_2029 / hiv_incidence_2023 - 1) * 100

        hiv_incidence_2021 = self.hiv.PARTNER["cases"].at[2021] / \
                             self.hiv.PARTNER["hivneg"].at[2021]
        hiv_incidence_2028 = self.hiv.IC.portfolio_results["cases"].at[2028, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2028, "model_central"]
        hiv_incidence_reduction_st = (hiv_incidence_2028 / hiv_incidence_2021 - 1) * 100

        # Generate output relating deaths
        hiv_deaths_2023 = self.hiv.IC.portfolio_results["deaths"].at[2023, "model_central"]
        hiv_deaths_2029 = self.hiv.IC.portfolio_results["deaths"].at[2029, "model_central"]
        hiv_death_reduction = (hiv_deaths_2029 / hiv_deaths_2023 - 1) * 100

        # Generate output relating to mortality
        hiv_mortality_2023 = self.hiv.IC.portfolio_results["deaths"].at[2023, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2023, "model_central"]
        hiv_mortality_2029 = self.hiv.IC.portfolio_results["deaths"].at[2029, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2029, "model_central"]
        hiv_mortality_reduction = (hiv_mortality_2029 / hiv_mortality_2023 - 1) * 100

        hiv_mortality_2021 = self.hiv.PARTNER["deaths"].at[2021] / \
                             self.hiv.PARTNER["population"].at[2021]
        hiv_mortality_2028 = self.hiv.IC.portfolio_results["deaths"].at[2028, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2028, "model_central"]
        hiv_mortality_reduction_st = (hiv_mortality_2028 / hiv_mortality_2021 - 1) * 100

        # Generate incidence reduction amongst AGYW in high burden countries

        # Need to filter by countries below
        country_list = ['BWA', 'CMR', 'KEN', 'LSO', 'MOZ', 'MWI', 'NAM', 'SWZ', 'TZA', 'UGA', 'ZAF', 'ZMB', 'ZWE']

        list_of_dfs = list()  # list of mini dataframes for each indicator for each country

        for country in country_list:
            y = self.hiv.IC.country_results[country].model_projection
            indicators = ['agywni', 'agywpop', 'agywplhiv']
            years = range(2022, 2031)
            for indicator in indicators:
                df = y[indicator][['model_central', 'model_high', 'model_low']].loc[years].reset_index()
                df['indicator'] = indicator
                df['country'] = country
                list_of_dfs.append(df)

        # build whole df
        df = pd.concat(list_of_dfs, axis=0)

        # Now use this df to get agyw incidence in 2023 and 2029
        # First compute the required sums in 2023
        cases_sum_2023 = df[(df['year'] == 2023) &
                            (df['indicator'].isin(['agywni']))]['model_central'].sum()

        population_sum_2022 = df[(df['year'] == 2022) &
                                 (df['indicator'].isin(['agywpop']))][
            'model_central'].sum()

        plhiv_sum_2022 = df[(df['year'] == 2022) &
                            (df['indicator'].isin(['agywplhiv']))]['model_central'].sum()

        # Calculate incidence in 2023
        incidence_2023 = cases_sum_2023 / (population_sum_2022 - plhiv_sum_2022)

        # Then compute the required sums for 2029
        cases_sum_2029 = df[(df['year'] == 2029) &
                            (df['indicator'].isin(['agywni']))]['model_central'].sum()

        population_sum_2028 = df[(df['year'] == 2028) &
                                 (df['indicator'].isin(['agywpop']))][
            'model_central'].sum()

        plhiv_sum_2028 = df[(df['year'] == 2028) &
                            (df['indicator'].isin(['agywplhiv']))]['model_central'].sum()

        # Calculate incidence for 2029
        incidence_2029 = cases_sum_2029 / (population_sum_2028 - plhiv_sum_2028)

        # reduction in agyw incidence
        relative_reduction = ((incidence_2023 - incidence_2029) / incidence_2023) * 100

        # Generate output relating to service coverage
        art_coverage_2023 = self.hiv.IC.portfolio_results["art"].at[2023, "model_central"] / \
                            self.hiv.IC.portfolio_results["plhiv"].at[2023, "model_central"] * 100
        art_coverage_2029 = self.hiv.IC.portfolio_results["art"].at[2029, "model_central"] / \
                            self.hiv.IC.portfolio_results["plhiv"].at[2029, "model_central"] * 100
        art_number_2029 = self.hiv.IC.portfolio_results["art"].at[2029, "model_central"]
        pmtct_number_2027_2029 = self.hiv.IC.portfolio_results["pmtct"].loc[
            slice(2027, 2029), "model_central"].sum()
        hst_2027_2029 = self.hiv.IC.portfolio_results['hst'].loc[
            slice(2027, 2029), "model_central"].sum()
        kp_reached_2027_2029 = self.hiv.IC.portfolio_results['fswreached'].loc[
            slice(2027, 2029), "model_central"].sum() + self.hiv.IC.portfolio_results['msmreached'].loc[
            slice(2027, 2029), "model_central"].sum() + self.hiv.IC.portfolio_results['pwidreached'].loc[
            slice(2027, 2029), "model_central"].sum()


        return {
            "Number of new hiv infections in the year 2023": hiv_cases_2023,
            "Number of new hiv infections  in the year 2029": hiv_cases_2029,
            "Reduction in new hiv infections  between the year 2029 compared to 2023": hiv_case_reduction,

            "HIV incidence in the year 2023": hiv_incidence_2023,
            "HIV incidence in the year 2029": hiv_incidence_2029,
            "Reduction in hiv incidence between the year 2029 compared to 2023": hiv_incidence_reduction,

            "HIV incidence in the year 2021": hiv_incidence_2021,
            "HIV incidence in the year 2028": hiv_incidence_2028,
            "Reduction in hiv incidence between the year 2028 compared to 2021": hiv_incidence_reduction_st,

            "Number of hiv deaths in the year 2023": hiv_deaths_2023,
            "Number of  hiv deaths  in the year 2029": hiv_deaths_2029,
            "Reduction in of hiv deaths  between the year 2029 compared to 2023": hiv_death_reduction,

            "HIV mortality rate in the year 2023": hiv_mortality_2023,
            "HIV mortality rate in the year 2029": hiv_mortality_2029,
            "Reduction in hiv mortality rate between the year 2029 compared to 2023": hiv_mortality_reduction,

            "HIV mortality rate in the year 2021": hiv_mortality_2021,
            "HIV mortality rate in the year 2028": hiv_mortality_2028,
            "Reduction in hiv mortality rate between the year 2028 compared to 2021": hiv_mortality_reduction_st,

            "Incidence reduction in AGYW in most affected countries from 2023 to 2029": incidence_2029,

            "ART coverage in the year 2023": art_coverage_2023,
            "ART coverage in the year 2029": art_coverage_2029,
            "Number of people on ART in the year 2029": art_number_2029,
            "Number of pregnant women receiving ART between 2027 and 2029:": pmtct_number_2027_2029,
            "Number pf people receiving HIV testing and councelling 2027 to 2029": hst_2027_2029,
            "Number of KP reached with prevention programmes between 2027 and 2029": kp_reached_2027_2029,
        }

    def get_key_stats_tb(self) -> Dict[str, float]:
        """ Get the key stats for tb.  """

        # Generate output relating to cases
        tb_cases_2023 = self.tb.IC.portfolio_results["cases"].at[2023, "model_central"]
        tb_cases_2029 = self.tb.IC.portfolio_results["cases"].at[2029, "model_central"]
        tb_case_reduction = (tb_cases_2029 / tb_cases_2023 - 1) * 100

        # Generate output relating to incidence
        tb_incidence_2023 = self.tb.IC.portfolio_results["cases"].at[2023, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2023, "model_central"]
        tb_incidence_2029 = self.tb.IC.portfolio_results["cases"].at[2029, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2029, "model_central"]
        tb_incidence_reduction = (tb_incidence_2029 / tb_incidence_2023 - 1) * 100

        tb_incidence_2021 = self.tb.PARTNER["cases"].at[2021] / \
                            self.tb.PARTNER["population"].at[2021]
        tb_incidence_2028 = self.tb.IC.portfolio_results["cases"].at[2028, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2028, "model_central"]
        tb_incidence_reduction_st = (tb_incidence_2029 / tb_incidence_2023 - 1) * 100

        # Generate output relating to cases
        tb_deaths_2023 = self.tb.IC.portfolio_results["deaths"].at[2023, "model_central"]
        tb_deaths_2029 = self.tb.IC.portfolio_results["deaths"].at[2029, "model_central"]
        tb_deaths_reduction = (tb_deaths_2029 / tb_deaths_2023 - 1) * 100

        tb_deaths_hivneg_2023 = self.tb.IC.portfolio_results["deathshivneg"].at[2023, "model_central"]
        tb_deaths_hivneg_2029 = self.tb.IC.portfolio_results["deathshivneg"].at[2029, "model_central"]
        tb_deaths_hivneg_reduction = (tb_deaths_hivneg_2029 / tb_deaths_hivneg_2023 - 1) * 100

        # Generate output relating to mortality related
        tb_mortality_2023 = self.tb.IC.portfolio_results["deaths"].at[2023, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2023, "model_central"]
        tb_mortality_2029 = self.tb.IC.portfolio_results["deaths"].at[2029, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2029, "model_central"]
        tb_mortality_reduction = (tb_mortality_2029 / tb_mortality_2023 - 1) * 100

        tb_mortality_hivneg_2023 = self.tb.IC.portfolio_results["deathshivneg"].at[2023, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2023, "model_central"]
        tb_mortality_hivneg_2029 = self.tb.IC.portfolio_results["deathshivneg"].at[2029, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2029, "model_central"]
        tb_mortality_hivneg_reduction = (tb_mortality_hivneg_2029 / tb_mortality_hivneg_2023 - 1) * 100

        tb_mortality_2021 = self.tb.PARTNER["deaths"].at[2021] / \
                            self.tb.PARTNER["population"].at[2021]
        tb_mortality_2028 = self.tb.IC.portfolio_results["deaths"].at[2028, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2028, "model_central"]
        tb_mortality_reduction_st = (tb_mortality_2028 / tb_mortality_2021 - 1) * 100

        tb_mortality_hivneg_2021 = self.tb.PARTNER["deathshivneg"].at[2021] / \
                                   self.tb.PARTNER["population"].at[2021]
        tb_mortality_hivneg_2028 = self.tb.IC.portfolio_results["deathshivneg"].at[2028, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2028, "model_central"]
        tb_mortality_hivneg_reduction_st = (tb_mortality_hivneg_2028 / tb_mortality_hivneg_2021 - 1) * 100

        # Generate output relating to service coverage
        notified_2027_2029 = self.tb.IC.portfolio_results["notified"].loc[
            slice(2027, 2029), "model_central"].sum()
        notified_2024_2029 = self.tb.IC.portfolio_results["notified"].loc[
            slice(2024, 2029), "model_central"].sum()
        # TODO; correct this
        mdrnotified_2027_2029 = self.tb.IC.portfolio_results["mdrnotified"].loc[
            slice(2027, 2029), "model_central"].sum()
        mdrnotified_2024_2029 = self.tb.IC.portfolio_results["mdrnotified"].loc[
            slice(2024, 2029), "model_central"].sum()
        tb_txcoverage_2023 = self.tb.IC.portfolio_results["notified"].at[2023, "model_central"] / \
                             self.tb.IC.portfolio_results["cases"].at[2023, "model_central"] * 100
        tb_txcoverage_2029 = self.tb.IC.portfolio_results["notified"].at[2029, "model_central"] / \
                             self.tb.IC.portfolio_results["cases"].at[2029, "model_central"] * 100
        tb_art_2027_2029 = self.tb.IC.portfolio_results["tbart"].loc[
            slice(2027, 2029), "model_central"].sum()
        tb_screened_2027_2029 = self.tb.IC.portfolio_results["notified"].loc[
            slice(2027, 2029), "model_central"].sum()*22.9
        mdrtx_2027_2029 = self.tb.IC.portfolio_results["mdrTx"].loc[
            slice(2027, 2029), "model_central"].sum()

        return {
            "Number of TB cases in the year 2023": tb_cases_2023,
            "Number of TB cases in the year 2029": tb_cases_2029,
            "Reduction in TB cases  between the year 2029 compared to 2023": tb_case_reduction,

            "TB incidence in the year 2023": tb_incidence_2023,
            "TB incidence in the year 2029": tb_incidence_2029,
            "Reduction in TB incidence between the year 2029 compared to 2023": tb_incidence_reduction,

            "TB incidence in the year 2021": tb_incidence_2021,
            "TB incidence in the year 2028": tb_incidence_2028,
            "Reduction in TB incidence between the year 2028 compared to 2021": tb_incidence_reduction_st,

            "Number of TB deaths in the year 2023": tb_deaths_2023,
            "Number of TB deaths in the year 2029": tb_deaths_2029,
            "Reduction in TB deaths between the year 2029 compared to 2023": tb_deaths_reduction,

            "Number of TB deaths amongst hiv-negative individuals in the year 2023": tb_deaths_hivneg_2023,
            "Number of TB deaths amongst hiv-negative individuals in the year 2029": tb_deaths_hivneg_2029,
            "Reduction in TB deaths amongst hiv-negative individuals between the year 2029 compared to 2023": tb_deaths_hivneg_reduction,

            "TB mortality rate in the year 2023": tb_mortality_2023,
            "TB mortality rate in the year 2029": tb_mortality_2029,
            "Reduction in TB mortality rate between the year 2029 compared to 2023": tb_mortality_reduction,

            "TB mortality rate amongst hiv-negative individuals in the year 2023": tb_mortality_hivneg_2023,
            "TB mortality rate amongst hiv-negative individuals in the year 2029": tb_mortality_hivneg_2029,
            "Reduction in TB mortality rate amongst hiv-negative individuals between the year 2029 compared to 2023": tb_mortality_hivneg_reduction,

            "TB mortality rate in the year 2021": tb_mortality_2021,
            "TB mortality rate in the year 2028": tb_mortality_2028,
            "Reduction in TB mortality rate between the year 2028 compared to 2021": tb_mortality_reduction_st,

            "TB mortality rate amongst hiv-negative individuals in the year 2021": tb_mortality_hivneg_2021,
            "TB mortality rate amongst hiv-negative individuals in the year 2028": tb_mortality_hivneg_2028,
            "Reduction in TB mortality rate amongst hiv-negative individuals between the year 2028 compared to 2021": tb_mortality_hivneg_reduction_st,

            "Number of TB notifications between 2027 and 2029": notified_2027_2029,
            "Number of TB notifications between 2024 and 2029": notified_2024_2029,

            "Number of MDRTB notifications between 2027 and 2029": mdrnotified_2027_2029,
            "Number of MDRTB notifications between 2024 and 2029": mdrnotified_2024_2029,

            "TB treatment coverage in 2023": tb_txcoverage_2023,
            "TB treatment coverage in 2029": tb_txcoverage_2029,

            "Number of people treated for mdr between 2027 and 2029": mdrtx_2027_2029,

            "Number of HIV-positive TB patients receiving ART between 2027 to 2029": tb_art_2027_2029,
            "Number of people screened between 2027 and 2029": tb_screened_2027_2029,
        }

    def get_key_stats_malaria(self) -> Dict[str, float]:
        """ Get the key stats for malaria.  """

        # Generate output relating to cases
        malaria_cases_2023 = self.malaria.IC.portfolio_results["cases"].at[2023, "model_central"]
        malaria_cases_2029 = self.malaria.IC.portfolio_results["cases"].at[2029, "model_central"]
        malaria_case_reduction = (malaria_cases_2029 / malaria_cases_2023 - 1) * 100

        # Generate output relating to incidence
        malaria_incidence_2023 = self.malaria.IC.portfolio_results["cases"].at[2023, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2023, "model_central"]
        malaria_incidence_2029 = self.malaria.IC.portfolio_results["cases"].at[2029, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2029, "model_central"]
        malaria_incidence_reduction = (malaria_incidence_2029 / malaria_incidence_2023 - 1) * 100

        malaria_incidence_2021 = self.malaria.PARTNER["cases"].at[2021] / \
                                 self.malaria.PARTNER["par"].at[2021]
        malaria_incidence_2028 = self.malaria.IC.portfolio_results["cases"].at[2028, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2028, "model_central"]
        malaria_incidence_reduction_st = (malaria_incidence_2028 / malaria_incidence_2021 - 1) * 100

        # Generate output relating to mortality
        malaria_deaths_2023 = self.malaria.IC.portfolio_results["deaths"].at[2023, "model_central"]
        malaria_deaths_2029 = self.malaria.IC.portfolio_results["deaths"].at[2029, "model_central"]
        malaria_death_reduction = (malaria_deaths_2029 / malaria_deaths_2023 - 1) * 100

        # Generate output relating to mortality
        malaria_mortality_2023 = self.malaria.IC.portfolio_results["deaths"].at[2023, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2023, "model_central"]
        malaria_mortality_2029 = self.malaria.IC.portfolio_results["deaths"].at[2029, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2029, "model_central"]
        malaria_mortality_reduction = (malaria_mortality_2029 / malaria_mortality_2023 - 1) * 100

        malaria_mortality_2021 = self.malaria.PARTNER["deaths"].at[2021] / \
                                 self.malaria.PARTNER["par"].at[2021]
        malaria_mortality_2028 = self.malaria.IC.portfolio_results["deaths"].at[2028, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2028, "model_central"]
        malaria_mortality_reduction_st = (malaria_mortality_2028 / malaria_mortality_2021 - 1) * 100

        # Generate output to service coverage
        malaria_llins_2027_2029 = self.malaria.IC.portfolio_results["llins"].loc[
            slice(2027, 2029), "model_central"].sum()

        # Get llin use in 2023 limited to SSA only
        # Need to filter by countries below
        country_list = ['AGO', 'BDI', 'BEN', 'BFA', 'CAF', 'CIV', 'CMR', 'COD', 'COG', 'COM', 'ERI', 'ETH', 'GHA', 'GIN', 'GMB', 'GNB', 'KEN', 'LBR', 'MDG', 'MLI', 'MOZ', 'MRT', 'MWI', 'NAM', 'NER', 'NGA', 'RWA', 'SDN', 'SEN', 'SLE', 'SOM', 'SSD', 'TCD', 'TGO', 'TZA', 'UGA', 'ZMB', 'ZWE']

        list_of_dfs = list()  # list of mini dataframes for each indicator for each country

        for country in country_list:
            y = self.malaria.IC.country_results[country].model_projection
            indicators = ['llinsuse', 'par']
            years = range(2022, 2031)
            for indicator in indicators:
                df = y[indicator][['model_central', 'model_high', 'model_low']].loc[years].reset_index()
                df['indicator'] = indicator
                df['country'] = country
                list_of_dfs.append(df)

        # build whole df
        df = pd.concat(list_of_dfs, axis=0)

        # Compute llinuse for 2023
        llinuse_n_2023 = df[(df['year'] == 2023) & (df['indicator'] == 'llinsuse')]['model_central'].sum()
        par_2023 = df[(df['year'] == 2023) & (df['indicator'] == 'par')]['model_central'].sum()
        llinuse_2023 = llinuse_n_2023 / par_2023 * 100

        # Compute llinuse for 2029
        llinuse_n_2029 = df[(df['year'] == 2029) & (df['indicator'] == 'llinsuse')]['model_central'].sum()
        par_2029 = df[(df['year'] == 2029) & (df['indicator'] == 'par')]['model_central'].sum()
        llinuse_2029 = llinuse_n_2029 / par_2029 * 100

        malaria_llins_2024_2029 = self.malaria.IC.portfolio_results["llins"].loc[
            slice(2024, 2029), "model_central"].sum()

        smc_2027_2029 = self.malaria.IC.portfolio_results['smc'].loc[
            slice(2024, 2029), "model_central"].sum()

        tx_publicsector_2024_2029 = self.malaria.IC.portfolio_results["txpublic"].loc[
            slice(2024, 2029), "model_central"].sum()

        tx_publicsector_2027_2029 = self.malaria.IC.portfolio_results["txpublic"].loc[
            slice(2027, 2029), "model_central"].sum()

        number_tx = self.malaria.IC.portfolio_results["nrtx"].loc[
            slice(2027, 2029), "model_central"].sum()

        vaccines_2024_2029 = self.malaria.IC.portfolio_results["vaccine"].loc[
            slice(2024, 2029), "model_central"].sum()

        vaccines_doses_2024_2029 = self.malaria.IC.portfolio_results["vaccinedoses"].loc[
            slice(2024, 2029), "model_central"].sum()

        par_vaccines_2024_2029 = self.malaria.IC.portfolio_results["parvx"].loc[
            slice(2024, 2029), "model_central"].sum()

        vaccines_cost_2024_2029 = self.malaria.IC.portfolio_results["costvx"].loc[
            slice(2024, 2029), "model_central"].sum()

        vaccines_2027_2029 = self.malaria.IC.portfolio_results["vaccine"].loc[
            slice(2027, 2029), "model_central"].sum()

        vaccines_doses_2027_2029 = self.malaria.IC.portfolio_results["vaccinedoses"].loc[
            slice(2027, 2029), "model_central"].sum()

        par_vaccines_2027_2029 = self.malaria.IC.portfolio_results["parvx"].loc[
            slice(2027, 2029), "model_central"].sum()

        vaccines_cost_2027_2029 = self.malaria.IC.portfolio_results["costvx"].loc[
            slice(2027, 2029), "model_central"].sum()


        return {
            "Number of malaria cases in the year 2023": malaria_cases_2023,
            "Number of malaria cases in the year 2029": malaria_cases_2029,
            "Reduction in malaria cases between the year 2029 compared to 2023 ": malaria_case_reduction,

            "Malaria incidence in the year 2023": malaria_incidence_2023,
            "Malaria incidence in the year 2029": malaria_incidence_2029,
            "Reduction in malaria incidence between the year 2029 compared to 2023": malaria_incidence_reduction,

            "Malaria incidence in the year 2021": malaria_incidence_2021,
            "Malaria incidence in the year 2028": malaria_incidence_2028,
            "Reduction in malaria incidence between the year 2028 compared to 2021": malaria_incidence_reduction_st,

            "Number of malaria deaths in the year 2023": malaria_deaths_2023,
            "Number of malaria deaths  in the year 2029": malaria_deaths_2029,
            "Reduction in malaria deaths between the year 2029 compared to 2023": malaria_death_reduction,

            "Malaria mortality rate in the year 2023": malaria_mortality_2023,
            "Malaria mortality rate in the year 2029": malaria_mortality_2029,
            "Reduction in malaria mortality rate between the year 2029 compared to 2023": malaria_mortality_reduction,

            "Malaria mortality rate in the year 2021": malaria_mortality_2021,
            "Malaria mortality rate in the year 2028": malaria_mortality_2028,
            "Reduction in malaria mortality rate between the year 2028 compared to 2021": malaria_mortality_reduction_st,

            "Number of bed nets distributed between 2027 and 2029": malaria_llins_2027_2029,
            "Number of bed nets distributed between 2024 and 2029": malaria_llins_2024_2029,
            "LLIN use in 2023 in SSA": llinuse_2023,
            "LLIN use in 2029 in SSA": llinuse_2029,

            "Number of children receiving SMC": smc_2027_2029,

            "Number of people treated in the public sector between 2024 and 2029": tx_publicsector_2024_2029,
            "Number of people treated in the public sector between 2027 and 2029": tx_publicsector_2027_2029,
            "Number of people treated for malaria between 2027 and 2029": number_tx,

            "Number of people vaccinated between 2024 and 2029": vaccines_2024_2029,
            "Number of vaccine doses distributed between 2024 and 2029": vaccines_doses_2024_2029,
            "Vaccine coverage between 2024 and 2029": vaccines_2024_2029/par_vaccines_2024_2029,
            "Vaccine cost between 2024 and 2029": vaccines_cost_2024_2029,

            "Number of people vaccinated between 2027 and 2029": vaccines_2027_2029,
            "Number of vaccine doses distributed between 2027 and 2029": vaccines_doses_2027_2029,
            "Vaccine coverage between 2027 and 2029": vaccines_2027_2029/par_vaccines_2027_2029,
            "Vaccine cost between 2027 and 2029": vaccines_cost_2027_2029,
        }

    def get_lives_saved(self) -> Dict[str, float]:
        """Save a graph to the outputs directory"""

        # Get lives saved for HIV
        hiv_deaths_2024_2029_ic = self.hiv.IC.portfolio_results["deaths"].loc[slice(2024, 2029), "model_central"].sum()
        hiv_deaths_2024_2029_cf = self.hiv.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2024, 2029), "model_central"].sum()
        lives_saved_hiv_2024_2029 = hiv_deaths_2024_2029_cf - hiv_deaths_2024_2029_ic

        hiv_deaths_2027_2029_ic = self.hiv.IC.portfolio_results["deaths"].loc[slice(2027, 2029), "model_central"].sum()
        hiv_deaths_2027_2029_cf = self.hiv.CF_LivesSaved.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()
        lives_saved_hiv_2027_2029 = hiv_deaths_2027_2029_cf - hiv_deaths_2027_2029_ic

        # Get lives saved for TB
        # First obtain ratio for tbdeaths no tx amongst hivneg between IC and Partner because we have only 29 modelled
        # countries. We do not need to do this for malaria and hiv as we have a lot of modelled countries.
        indicator = "deathshivneg"
        year = 2022
        partner_2022 = self.tb.PARTNER[indicator].at[year]

        list_of_dfs = list()  # list of mini dataframes for each indicator for each country

        for country in self.tb.IC.country_results.keys():
            y = self.tb.IC.country_results[country].model_projection
            df = y[indicator][['model_central']].loc[year].reset_index()
            df['indicator'] = indicator
            df['country'] = country
            list_of_dfs.append(df)

        # build whole df
        df = pd.concat(list_of_dfs, axis=0)
        model_2022 = df[year].sum()
        ratio = partner_2022 / model_2022
        adj_tb_cf = (self.tb.IC.portfolio_results["deathshivneg"])*ratio
        adj_tb_cf = (self.tb.CF_InfAve.portfolio_results["deathshivneg"]) * ratio
        adj_tb_cf = (self.tb.CF_LivesSaved.portfolio_results["deathshivneg"]) * ratio


        tb_deaths_hivneg_2024_2029_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2024, 2029), "model_central"].sum()
        tb_deaths_hivneg_2024_2029_cf = adj_tb_cf.loc[slice(2024, 2029), "model_central"].sum()
        lives_saved_tb_hivneg_2024_2029 = tb_deaths_hivneg_2024_2029_cf - tb_deaths_hivneg_2024_2029_ic

        tb_deaths_hivneg_2027_2029_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2027, 2029), "model_central"].sum()
        tb_deaths_hivneg_2027_2029_cf = adj_tb_cf.loc[slice(2027, 2029), "model_central"].sum()
        lives_saved_tb_hivneg_2027_2029 = tb_deaths_hivneg_2027_2029_cf - tb_deaths_hivneg_2027_2029_ic

        # Get lives saved for malaria
        malaria_deaths_2024_2029_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2024, 2029), "model_central"].sum()
        malaria_deaths_2024_2029_cf = self.malaria.CF_LivesSaved_Malaria.loc[2024:2029].sum()
        lives_saved_malaria_2024_2029 = malaria_deaths_2024_2029_cf - malaria_deaths_2024_2029_ic

        malaria_deaths_2027_2029_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()
        malaria_deaths_2027_2029_cf = self.malaria.CF_LivesSaved_Malaria.loc[2027:2029].sum()
        lives_saved_malaria_2027_2029 = malaria_deaths_2027_2029_cf - malaria_deaths_2027_2029_ic

        # Get lives saved 2027 to 2029 as one stat
        total_ls_2027_2029 = lives_saved_hiv_2027_2029 + lives_saved_tb_hivneg_2027_2029 + lives_saved_malaria_2027_2029

        return {
            "Number of lives saved relating to hiv from 2024 to 2029": lives_saved_hiv_2024_2029,
            "Number of lives saved relating to hiv from 2027 to 2029": lives_saved_hiv_2027_2029,
            "Number of lives saved relating to tb  amongst hivneg from 2024 to 2029": lives_saved_tb_hivneg_2024_2029,
            "Number of lives saved relating to tb  amongst hivneg from 2027 to 2029": lives_saved_tb_hivneg_2027_2029,
            "Number of lives saved relating to malaria from 2024 to 2029": lives_saved_malaria_2024_2029,
            "Number of lives saved relating to malaria 2027 to 2029": lives_saved_malaria_2027_2029,
            "Number of lives saved across diseases 2027 to 2029": total_ls_2027_2029,
        }

    def get_infections_averted(self) -> dict[str, Any]:
        """ Generate infections averted """

        # Get infections averted for HIV
        hiv_cases_2027_2029_ic = self.hiv.IC.portfolio_results["cases"].loc[slice(2027, 2029), "model_central"].sum()
        hiv_cases_2027_2029_cf = self.hiv.CF_InfAve.portfolio_results["cases"].loc[
            slice(2027, 2029), "model_central"].sum()
        infections_averted_2027_2029_hiv = hiv_cases_2027_2029_cf - hiv_cases_2027_2029_ic

        # Get infections averted for TB
        tb_cases_2027_2029_ic = self.tb.IC.portfolio_results["cases"].loc[slice(2027, 2029), "model_central"].sum()
        tb_cases_2027_2029_cf = self.tb.CF_InfAve.portfolio_results["cases"].loc[
            slice(2027, 2029), "model_central"].sum()
        infections_averted_2027_2029_tb = tb_cases_2027_2029_cf - tb_cases_2027_2029_ic

        # Get infections averted for malaria
        malaria_cases_2027_2029_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2027, 2029), "model_central"].sum()
        malaria_cases_2027_2029_cf = self.malaria.CF_InfectionsAverted_Malaria.loc[2027:2029].sum()
        infections_averted_2027_2029_malaria = malaria_cases_2027_2029_cf - malaria_cases_2027_2029_ic

        # Get infections averted across diseases
        infections_averted_2027_2029_portfolio = infections_averted_2027_2029_hiv + infections_averted_2027_2029_tb + infections_averted_2027_2029_malaria

        return {
            "Infections averted relating to HIV from 2027 to 2029": infections_averted_2027_2029_hiv,
            "Infections averted relating to TB from 2027 to 2029": infections_averted_2027_2029_tb,
            "Infections averted relating to malaria from 2027 to 2029": infections_averted_2027_2029_malaria,
            "Infections averted across three diseases from 2027 to 2029": infections_averted_2027_2029_portfolio,
        }

    def hiv_cases(self) -> pd.DataFrame:
        """Produce graph for HIV cases"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.hiv.PARTNER['cases'],
                'GP': self.hiv.CF_forgraphs['cases'],
                'Counterfactual': self.hiv.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': self.hiv.IC.portfolio_results['cases']['model_central'],
                'IC_LB': self.hiv.IC.portfolio_results['cases']['model_low'],
                'IC_UB': self.hiv.IC.portfolio_results['cases']['model_high'],
                'hivneg_actual': self.hiv.PARTNER['hivneg'],
                'hivneg_gp': self.hiv.CF_forgraphs['hivneg'],
                'hivneg_cf': self.hiv.CF_InfAve.portfolio_results['hivneg']['model_central'],
                'hivneg_ic': self.hiv.IC.portfolio_results['hivneg']['model_central'],
                'Actual_inc': self.hiv.PARTNER['cases']/self.hiv.PARTNER["hivneg"],
                'GP_inc': self.hiv.CF_forgraphs['cases']/self.hiv.CF_forgraphs['hivneg'],
                'CF_inc': self.hiv.CF_InfAve.portfolio_results['cases']['model_central']/self.hiv.CF_InfAve.portfolio_results['hivneg']['model_central'],
                'IC_inc': self.hiv.IC.portfolio_results['cases']['model_central']/self.hiv.IC.portfolio_results['hivneg']['model_central'],
                'IC_LB_inc': self.hiv.IC.portfolio_results['cases']['model_low']/self.hiv.IC.portfolio_results['hivneg']['model_central'],
                'IC_UB_inc': self.hiv.IC.portfolio_results['cases']['model_high']/self.hiv.IC.portfolio_results['hivneg']['model_central'],
            }
        )

    def hiv_deaths(self) -> pd.DataFrame:
        """Produce graph for HIV deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.hiv.PARTNER['deaths'],
                'GP': self.hiv.CF_forgraphs['deaths'],
                'Counterfactual': self.hiv.CF_InfAve.portfolio_results['deaths']['model_central'],
                'IC': self.hiv.IC.portfolio_results['deaths']['model_central'],
                'IC_LB': self.hiv.IC.portfolio_results['deaths']['model_low'],
                'IC_UB': self.hiv.IC.portfolio_results['deaths']['model_high'],
                'pop_actual': self.hiv.PARTNER['population'],
                'pop_gp': self.hiv.CF_forgraphs['population'],
                'pop_cf': self.hiv.CF_InfAve.portfolio_results['population']['model_central'],
                'pop_ic': self.hiv.IC.portfolio_results['population']['model_central'],
                'Actual_inc': self.hiv.PARTNER['deaths'] / self.hiv.PARTNER["population"],
                'GP_inc': self.hiv.CF_forgraphs['deaths'] / self.hiv.CF_forgraphs['population'],
                'CF_inc': self.hiv.CF_InfAve.portfolio_results['deaths']['model_central'] /
                          self.hiv.CF_InfAve.portfolio_results['population']['model_central'],
                'IC_inc': self.hiv.IC.portfolio_results['deaths']['model_central'] /
                          self.hiv.IC.portfolio_results['population']['model_central'],
                'IC_LB_inc': self.hiv.IC.portfolio_results['deaths']['model_low'] /
                             self.hiv.IC.portfolio_results['population']['model_central'],
                'IC_UB_inc': self.hiv.IC.portfolio_results['deaths']['model_high'] /
                             self.hiv.IC.portfolio_results['population']['model_central'],
            }
        )

    def tb_cases(self) -> pd.DataFrame:
        """Produce graph for TB cases"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.tb.PARTNER['cases'],
                'GP': self.tb.CF_forgraphs['cases'],
                'Counterfactual': self.tb.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': self.tb.IC.portfolio_results['cases']['model_central'],
                'IC_LB': self.tb.IC.portfolio_results['cases']['model_low'],
                'IC_UB': self.tb.IC.portfolio_results['cases']['model_high'],
                'pop_actual': self.tb.PARTNER['population'],
                'pop_cf': self.tb.CF_InfAve.portfolio_results['population']['model_central'],
                'pop_ic': self.tb.IC.portfolio_results['population']['model_central'],
                'Actual_inc': self.tb.PARTNER['cases'] / self.tb.PARTNER["population"],
                'GP_inc': self.tb.CF_forgraphs['incidence'],
                'CF_inc': self.tb.CF_InfAve.portfolio_results['cases']['model_central'] /
                          self.tb.CF_InfAve.portfolio_results['population']['model_central'],
                'IC_inc': self.tb.IC.portfolio_results['cases']['model_central'] /
                          self.tb.IC.portfolio_results['population']['model_central'],
                'IC_LB_inc': self.tb.IC.portfolio_results['cases']['model_low'] /
                             self.tb.IC.portfolio_results['population']['model_central'],
                'IC_UB_inc': self.tb.IC.portfolio_results['cases']['model_high'] /
                             self.tb.IC.portfolio_results['population']['model_central'],
                'IC_LB_adj': (self.tb.IC.portfolio_results['cases']['model_low'])*0.9,
                'IC_UB_adj': (self.tb.IC.portfolio_results['cases']['model_high'])*1.1,

            }
        )

    def tbh_deaths(self) -> pd.DataFrame:
        """Produce graph for TB deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.tb.PARTNER['deaths'],
                'GP': self.tb.CF_forgraphs['deaths'],
                'Counterfactual': self.tb.CF_InfAve.portfolio_results['deaths']['model_central'],
                'IC': self.tb.IC.portfolio_results['deaths']['model_central'],
                'IC_LB': self.tb.IC.portfolio_results['deaths']['model_low'],
                'IC_UB': self.tb.IC.portfolio_results['deaths']['model_high'],
                'pop_actual': self.tb.PARTNER['population'],
                'pop_cf': self.tb.CF_InfAve.portfolio_results['population']['model_central'],
                'pop_ic': self.tb.IC.portfolio_results['population']['model_central'],
                'Actual_mort': self.tb.PARTNER['deaths'] / self.tb.PARTNER["population"],
                'GP_mort': self.tb.CF_forgraphs['mortality'],
                'CF_mort': self.tb.CF_InfAve.portfolio_results['deaths']['model_central'] /
                          self.tb.CF_InfAve.portfolio_results['population']['model_central'],
                'IC_mort': self.tb.IC.portfolio_results['deaths']['model_central'] /
                          self.tb.IC.portfolio_results['population']['model_central'],
                'IC_LB_mort': self.tb.IC.portfolio_results['deaths']['model_low'] /
                             self.tb.IC.portfolio_results['population']['model_central'],
                'IC_UB_mort': self.tb.IC.portfolio_results['deaths']['model_high'] /
                             self.tb.IC.portfolio_results['population']['model_central'],
                'IC_LB_adj': (self.tb.IC.portfolio_results['deaths']['model_low'])*0.9,
                'IC_UB_adj': (self.tb.IC.portfolio_results['deaths']['model_high'])*1.1,
            }
        )

    def tb_deaths(self) -> pd.DataFrame:
        """Produce graph for TB deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.tb.PARTNER['deathshivneg'],
                'GP': self.tb.CF_forgraphs['deathshivneg'],
                'Counterfactual': self.tb.CF_InfAve.portfolio_results['deathshivneg']['model_central'],
                'IC': self.tb.IC.portfolio_results['deathshivneg']['model_central'],
                'IC_LB': self.tb.IC.portfolio_results['deathshivneg']['model_low'],
                'IC_UB': self.tb.IC.portfolio_results['deathshivneg']['model_high'],
                'pop_actual': self.tb.PARTNER['population'],
                'pop_cf': self.tb.CF_InfAve.portfolio_results['population']['model_central'],
                'pop_ic': self.tb.IC.portfolio_results['population']['model_central'],
                'Actual_mort': self.tb.PARTNER['deathshivneg'] / self.tb.PARTNER["population"],
                'GP_mort': self.tb.CF_forgraphs['mortalityhivneg'],
                'CF_mort': self.tb.CF_InfAve.portfolio_results['deathshivneg']['model_central'] /
                          self.tb.CF_InfAve.portfolio_results['population']['model_central'],
                'IC_mort': self.tb.IC.portfolio_results['deathshivneg']['model_central'] /
                          self.tb.IC.portfolio_results['population']['model_central'],
                'IC_LB_mort': self.tb.IC.portfolio_results['deathshivneg']['model_low'] /
                             self.tb.IC.portfolio_results['population']['model_central'],
                'IC_UB_mort': self.tb.IC.portfolio_results['deathshivneg']['model_high'] /
                             self.tb.IC.portfolio_results['population']['model_central'],
                'IC_LB_adj': (self.tb.IC.portfolio_results['deathshivneg']['model_low'])*0.9,
                'IC_UB_adj': (self.tb.IC.portfolio_results['deathshivneg']['model_high'])*1.1,
            }
        )

    def mal_cases(self) -> pd.DataFrame:
        """Produce graph for malaria cases"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.malaria.PARTNER['cases'],
                'GP': self.malaria.CF_forgraphs['cases'],
                'Counterfactual': self.malaria.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': self.malaria.IC.portfolio_results['cases']['model_central'],
                'IC_LB': self.malaria.IC.portfolio_results['cases']['model_low'],
                'IC_UB': self.malaria.IC.portfolio_results['cases']['model_high'],
                'par_actual': self.malaria.PARTNER['par'],
                'par_cf': self.malaria.CF_InfAve.portfolio_results['par']['model_central'],
                'par_ic': self.malaria.IC.portfolio_results['par']['model_central'],
                'Actual_inc': self.malaria.PARTNER['cases'] / self.malaria.PARTNER["par"],
                'GP_inc': self.malaria.CF_forgraphs["incidence"],
                'CF_inc': self.malaria.CF_InfAve.portfolio_results['cases']['model_central'] /
                          self.malaria.CF_InfAve.portfolio_results['par']['model_central'],
                'IC_inc': self.malaria.IC.portfolio_results['cases']['model_central'] /
                          self.malaria.IC.portfolio_results['par']['model_central'],
                'IC_LB_inc': self.malaria.IC.portfolio_results['cases']['model_low'] /
                             self.malaria.IC.portfolio_results['par']['model_central'],
                'IC_UB_inc': self.malaria.IC.portfolio_results['cases']['model_high'] /
                             self.malaria.IC.portfolio_results['par']['model_central'],
            }
        )

    def mal_deaths(self) -> pd.DataFrame:
        """Produce graph for malaria deaths"""
        return pd.DataFrame(
            index=pd.Index(list(range(2005, 2031)), name='Year'),
            data={
                'Actual': self.malaria.PARTNER['deaths'],
                'GP': self.malaria.CF_forgraphs['deaths'],
                'Counterfactual': self.malaria.CF_InfAve.portfolio_results['deaths']['model_central'],
                'IC': self.malaria.IC.portfolio_results['deaths']['model_central'],
                'IC_LB': self.malaria.IC.portfolio_results['deaths']['model_low'],
                'IC_UB': self.malaria.IC.portfolio_results['deaths']['model_high'],
                'par_actual': self.malaria.PARTNER['par'],
                'par_cf': self.malaria.CF_InfAve.portfolio_results['par']['model_central'],
                'par_ic': self.malaria.IC.portfolio_results['par']['model_central'],
                'Actual_mort': self.malaria.PARTNER['deaths'] / self.malaria.PARTNER["par"],
                'GP_mort': self.malaria.CF_forgraphs["mortality"],
                'CF_mort': self.malaria.CF_InfAve.portfolio_results['deaths']['model_central'] /
                          self.malaria.CF_InfAve.portfolio_results['par']['model_central'],
                'IC_mort': self.malaria.IC.portfolio_results['deaths']['model_central'] /
                          self.malaria.IC.portfolio_results['par']['model_central'],
                'IC_LB_mort': self.malaria.IC.portfolio_results['deaths']['model_low'] /
                             self.malaria.IC.portfolio_results['par']['model_central'],
                'IC_UB_mort': self.malaria.IC.portfolio_results['deaths']['model_high'] /
                             self.malaria.IC.portfolio_results['par']['model_central'],
            }
        )

    def get_combined_stats(self) -> dict[str, Any]:
        """ Generate combined stats """

        # Get deaths in 2023 for each disease
        hiv_deaths_2005 = self.hiv.PARTNER["deaths"].at[2005]
        tb_deathshivneg_2005 = self.tb.PARTNER["deathshivneg"].at[2005]
        malaria_deaths_2005 = self.malaria.PARTNER["deaths"].at[2005]
        total_deaths_2005 = hiv_deaths_2005 + tb_deathshivneg_2005 + malaria_deaths_2005

        # Get deaths in 2023 for each disease
        hiv_deaths_2020 = self.hiv.PARTNER["deaths"].at[2020]
        tb_deathshivneg_2020 = self.tb.PARTNER["deathshivneg"].at[2020]
        malaria_deaths_2020 = self.malaria.PARTNER["deaths"].at[2020]
        total_deaths_2020 = hiv_deaths_2020 + tb_deathshivneg_2020 + malaria_deaths_2020

        # Get deaths in 2023 for each disease
        hiv_deaths_2023 = self.hiv.IC.portfolio_results["deaths"].at[2023, "model_central"]
        tb_deaths_2023 = self.tb.IC.portfolio_results["deaths"].at[2023, "model_central"]
        malaria_deaths_2023 = self.malaria.IC.portfolio_results["deaths"].at[2023, "model_central"]
        total_deaths_2023 = hiv_deaths_2023 + tb_deaths_2023 + malaria_deaths_2023

        # Get deaths in 2029 for each disease
        hiv_deaths_2029 = self.hiv.IC.portfolio_results["deaths"].at[2029, "model_central"]
        tb_deaths_2029 = self.tb.IC.portfolio_results["deaths"].at[2029, "model_central"]
        malaria_deaths_2029 = self.malaria.IC.portfolio_results["deaths"].at[2029, "model_central"]
        total_deaths_2029 = hiv_deaths_2029 + tb_deaths_2029 + malaria_deaths_2029

        # Get sum of deaths from IC for 2027 to 2029
        hiv_deaths_2027_2029_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()
        tb_deaths_2027_2029_ic = self.tb.IC.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()
        malaria_deaths_2027_2029_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()

        # Generate mortality reduction from 2023 to 2029 for hiv
        hiv_mortality_2023 = self.hiv.IC.portfolio_results["deaths"].at[2023, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2023, "model_central"]
        hiv_mortality_2029 = self.hiv.IC.portfolio_results["deaths"].at[2029, "model_central"] / \
                             self.hiv.IC.portfolio_results["population"].at[2029, "model_central"]
        hiv_mortality_reduction = (hiv_mortality_2029 / hiv_mortality_2023 - 1) * 100

        # Generate mortality reduction amongst hiv negatives from 2023 to 2029 for tb
        tb_mortality_hivneg_2023 = self.tb.IC.portfolio_results["deathshivneg"].at[2023, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2023, "model_central"]
        tb_mortality_hivneg_2029 = self.tb.IC.portfolio_results["deathshivneg"].at[2029, "model_central"] / \
                                   self.tb.IC.portfolio_results["population"].at[2029, "model_central"]
        tb_mortality_hivneg_reduction = (tb_mortality_hivneg_2029 / tb_mortality_hivneg_2023 - 1) * 100

        # Generate mortality reduction from 2023 to 2029 for malaria
        malaria_mortality_2023 = self.malaria.IC.portfolio_results["deaths"].at[2023, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2023, "model_central"]
        malaria_mortality_2029 = self.malaria.IC.portfolio_results["deaths"].at[2029, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2029, "model_central"]
        malaria_mortality_reduction = (malaria_mortality_2029 / malaria_mortality_2023 - 1) * 100

        # Compute mortality reductiona cross three diseases from 2023 to 2029
        mortality_reduction_portfolio_2023_2029 = (hiv_mortality_reduction + tb_mortality_hivneg_reduction + malaria_mortality_reduction) / 3

        # Generate incidence reduction from 2023 to 2029 for hiv
        hiv_incidence_2023 = self.hiv.IC.portfolio_results["cases"].at[2023, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2023, "model_central"]
        hiv_incidence_2029 = self.hiv.IC.portfolio_results["cases"].at[2029, "model_central"] / \
                             self.hiv.IC.portfolio_results["hivneg"].at[2029, "model_central"]
        hiv_incidence_reduction = (hiv_incidence_2029 / hiv_incidence_2023 - 1) * 100

        # Generate incidence reduction from 2023 to 2029 for tb
        tb_incidence_2023 = self.tb.IC.portfolio_results["cases"].at[2023, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2023, "model_central"]
        tb_incidence_2029 = self.tb.IC.portfolio_results["cases"].at[2029, "model_central"] / \
                            self.tb.IC.portfolio_results["population"].at[2029, "model_central"]
        tb_incidence_reduction = (tb_incidence_2029 / tb_incidence_2023 - 1) * 100

        # Generate incidence reduction from 2023 to 2029 for malaria
        malaria_incidence_2023 = self.malaria.IC.portfolio_results["cases"].at[2023, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2023, "model_central"]
        malaria_incidence_2029 = self.malaria.IC.portfolio_results["cases"].at[2029, "model_central"] / \
                                 self.malaria.IC.portfolio_results["par"].at[2029, "model_central"]
        malaria_incidence_reduction = (malaria_incidence_2029 / malaria_incidence_2023 - 1) * 100

        # Compute mortality reductiona cross three diseases from 2023 to 2029
        incidence_reduction_portfolio_2023_2029 = (hiv_incidence_reduction + tb_incidence_reduction + malaria_incidence_reduction) / 3

        # Get deaths averted from CFs for 2027 to 2029
        hiv_deaths_2027_2029_cf = self.hiv.CF_InfAve.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()
        tb_deaths_2027_2029_cf = self.tb.CF_InfAve.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()
        malaria_deaths_2027_2029_cf = self.malaria.CF_InfAve.portfolio_results["deaths"].loc[
            slice(2027, 2029), "model_central"].sum()

        # Compute deaths averted
        hiv_deaths_averted_2027_2029 = hiv_deaths_2027_2029_cf - hiv_deaths_2027_2029_ic
        tb_deaths_averted_2027_2029 = tb_deaths_2027_2029_cf - tb_deaths_2027_2029_ic
        malaria_deaths_averted_2027_2029 = malaria_deaths_2027_2029_cf - malaria_deaths_2027_2029_ic
        total_deaths_averted = hiv_deaths_averted_2027_2029 + tb_deaths_averted_2027_2029 + malaria_deaths_averted_2027_2029

        return {
            "Total number of deaths from 3 diseases in 2005 (from partner)": total_deaths_2005,
            "Total number of deaths from 3 diseases in 2020 (from partner)": total_deaths_2020,
            "Total number of deaths from 3 diseases in 2023 ": total_deaths_2023,
            "Total number of deaths from 3 diseases in 2029 ": total_deaths_2029,
            "Deaths averted (constant coverage) for HIV 2027 to 2029": hiv_deaths_averted_2027_2029,
            "Deaths averted (constant coverage) for TB 2027 to 2029": tb_deaths_averted_2027_2029,
            "Deaths averted (constant coverage) for malaria 2027 to 2029": malaria_deaths_averted_2027_2029,
            "Total Deaths averted (constant coverage) for 2027 to 2029": total_deaths_averted,
            "Reduction in mortality across three diseases from 2023 to 2029": mortality_reduction_portfolio_2023_2029,
            "Reduction in incidence across three diseases from 2023 to 2029": incidence_reduction_portfolio_2023_2029,
        }

    def comb_mort(self) -> pd.DataFrame:
        """Generate graphs for the combined mortality. """

        return self._calculate_combined_mortality_stats()['Combined mortality df']

    def comb_inc(self) -> pd.DataFrame:
        """Generate graphs for the combined incidence. """

        return self._calculate_combined_incidence_stats()['Combined incidence df']

    def comb_reduc(self) -> pd.DataFrame:
        """Get reductions in mortality for IC and CF. """

        # Keep only the reductions in mortality and incidence and turn into a df
        df_mort = self._calculate_combined_mortality_stats()
        keys = ["Reduction in mortality in IC", "Reduction in mortality in CF"]
        df_mort = dict((k, df_mort[k]) for k in keys if k in df_mort)
        df_mort = pd.DataFrame.from_dict(df_mort, orient='index')

        df_inc = self._calculate_combined_incidence_stats()
        keys = ["Reduction in incidence in IC", "Reduction in incidence in CF"]
        df_inc = dict((k, df_inc[k]) for k in keys if k in df_inc)
        df_inc = pd.DataFrame.from_dict(df_inc, orient='index')

        list = [df_mort, df_inc]
        result = pd.concat(list, axis=0)
        result.columns = ['Value']
        result.index.name = 'Indicator'

        return result

    def _post_processing_on_workbook(self, workbook: Workbook):
        """Create a simple version of the killer graph."""

        def _make_simple_graph(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
            """On the worksheet provided, make a simple graph to illustrate the killer graph.
            From: https://realpython.com/openpyxl-excel-spreadsheets-python/#adding-pretty-charts
            """
            # References to the data
            data = Reference(ws, min_col=2, min_row=1, max_col=7, max_row=27)
            categories = Reference(ws, min_col=1, min_row=2, max_row=27)

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
            'tbh_deaths',
            'tb_deaths',
            'mal_cases',
            'mal_deaths',
            'comb_mort',
            'comb_inc',
        ]

        for sheet in sheets_for_graphs:
            _make_simple_graph(workbook[sheet])

    def _calculate_combined_mortality_stats(self) -> dict[str, Any]:
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
            slice(2024, 2030), "model_central"]
        hiv_deaths_lb_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2024, 2030), "model_low"]
        hiv_deaths_ub_ic = self.hiv.IC.portfolio_results["deaths"].loc[
            slice(2024, 2030), "model_high"]

        tb_deaths_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2024, 2030), "model_central"]
        tb_deaths_lb_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2024, 2030), "model_low"]
        tb_deaths_ub_ic = self.tb.IC.portfolio_results["deathshivneg"].loc[
            slice(2024, 2030), "model_high"]

        malaria_deaths_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2024, 2030), "model_central"]
        malaria_deaths_lb_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2024, 2030), "model_low"]
        malaria_deaths_ub_ic = self.malaria.IC.portfolio_results["deaths"].loc[
            slice(2024, 2030), "model_high"]

        hiv_pop_ic = self.hiv.IC.portfolio_results["population"].loc[
            slice(2024, 2030), "model_central"]
        tb_pop_ic = self.tb.IC.portfolio_results["population"].loc[
            slice(2024, 2030), "model_central"]
        malaria_pop_ic = self.malaria.IC.portfolio_results["par"].loc[
            slice(2024, 2030), "model_central"]

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
            slice(2024, 2030), "model_central"]
        tb_deaths_cf = self.tb.CF_InfAve.portfolio_results["deathshivneg"].loc[
            slice(2024, 2030), "model_central"]
        malaria_deaths_cf = self.malaria.CF_InfAve.portfolio_results["deaths"].loc[
            slice(2024, 2030), "model_central"]

        hiv_pop_cf = self.hiv.CF_InfAve.portfolio_results["population"].loc[
            slice(2024, 2030), "model_central"]
        tb_pop_cf = self.tb.CF_InfAve.portfolio_results["population"].loc[
            slice(2024, 2030), "model_central"]
        malaria_pop_cf = self.malaria.CF_InfAve.portfolio_results["par"].loc[
            slice(2024, 2030), "model_central"]

        hiv_mortality_cf = hiv_deaths_cf / hiv_pop_cf
        tb_mortality_cf = tb_deaths_cf / tb_pop_cf
        malaria_mortality_cf = malaria_deaths_cf / malaria_pop_cf

        # Step 2.3 Get incidence for each disease from GP
        hiv_deaths_gp = self.hiv.CF_forgraphs["deaths"]
        hiv_pop_gp = self.hiv.CF_forgraphs["population"]
        hiv_mortality_gp = hiv_deaths_gp / hiv_pop_gp
        hiv_mortality_gp = pd.DataFrame(hiv_mortality_gp)
        hiv_mortality_gp = hiv_mortality_gp[hiv_mortality_gp.index > 2019]

        tb_mortality_gp = self.tb.CF_forgraphs["mortalityhivneg"]
        tb_mortality_gp = pd.DataFrame(tb_mortality_gp)
        tb_mortality_gp = tb_mortality_gp[tb_mortality_gp.index >2014]

        malaria_mortality_gp = self.malaria.CF_forgraphs["mortality"]
        malaria_mortality_gp = pd.DataFrame(malaria_mortality_gp)
        malaria_mortality_gp = malaria_mortality_gp[malaria_mortality_gp.index > 2014]

        # Step 3.1 Normalise each disease to 100 in 2023 for partner and IC
        combined_hiv_mortality = pd.concat([hiv_mortality_partner,hiv_mortality_ic])
        combined_hiv_mortality = pd.DataFrame(combined_hiv_mortality)
        combined_hiv_mortality = 100*(combined_hiv_mortality / combined_hiv_mortality.iloc[15,:])

        combined_tb_mortality = pd.concat([tb_mortality_partner, tb_mortality_ic])
        combined_tb_mortality = pd.DataFrame(combined_tb_mortality)
        combined_tb_mortality = 100 * (combined_tb_mortality / combined_tb_mortality.iloc[15, :])

        combined_malaria_mortality = pd.concat([malaria_mortality_partner, malaria_mortality_ic])
        combined_malaria_mortality = pd.DataFrame(combined_malaria_mortality)
        combined_malaria_mortality = 100 * (combined_malaria_mortality / combined_malaria_mortality.iloc[15, :])

        # Step 3.2. Normalise the LB and UB for the IC
        combined_hiv_mortality_lb = pd.concat([hiv_mortality_partner, hiv_mortality_lb_ic])
        combined_hiv_mortality_lb = pd.DataFrame(combined_hiv_mortality_lb)
        combined_hiv_mortality_lb = 100 * (combined_hiv_mortality_lb / combined_hiv_mortality_lb.iloc[15, :])
        combined_hiv_mortality_ub = pd.concat([hiv_mortality_partner, hiv_mortality_ub_ic])
        combined_hiv_mortality_ub = pd.DataFrame(combined_hiv_mortality_ub)
        combined_hiv_mortality_ub = 100 * (combined_hiv_mortality_ub / combined_hiv_mortality_ub.iloc[15, :])

        combined_tb_mortality_ub = pd.concat([tb_mortality_partner, tb_mortality_lb_ic])
        combined_tb_mortality_lb = pd.DataFrame(combined_tb_mortality_ub)
        combined_tb_mortality_lb = 100 * (combined_tb_mortality_lb / combined_tb_mortality_lb.iloc[15, :])
        combined_tb_mortality_ub = pd.concat([tb_mortality_partner, tb_mortality_ub_ic])
        combined_tb_mortality_ub = pd.DataFrame(combined_tb_mortality_ub)
        combined_tb_mortality_ub = 100 * (combined_tb_mortality_ub / combined_tb_mortality_ub.iloc[15, :])

        combined_malaria_mortality_lb = pd.concat([malaria_mortality_partner, malaria_mortality_lb_ic])
        combined_malaria_mortality_lb = pd.DataFrame(combined_malaria_mortality_lb)
        combined_malaria_mortality_lb = 100 * (combined_malaria_mortality_lb / combined_malaria_mortality_lb.iloc[15, :])
        combined_malaria_mortality_ub = pd.concat([malaria_mortality_partner, malaria_mortality_ub_ic])
        combined_malaria_mortality_ub = pd.DataFrame(combined_malaria_mortality_ub)
        combined_malaria_mortality_ub = 100 * (combined_malaria_mortality_ub / combined_malaria_mortality_ub.iloc[15, :])

        # Back calculate SD at
        hiv_sd = (hiv_mortality_ub_ic - hiv_mortality_ic)/1.96
        tb_sd = (tb_mortality_ub_ic - tb_mortality_ic) / 1.96
        malaria_sd = (malaria_mortality_ub_ic - malaria_mortality_ic) / 1.96
        sds = pd.DataFrame({"hiv":hiv_sd, "tb":tb_sd, "malaria":malaria_sd})

        # Prepare to generate CIs
        # rho_btw_diseases = 1 # TODO: update
        rho_btw_diseases = self.parameters.get("RHO_BETWEEN_DISEASES")
        years = list(range(2024, 2031))
        combined_temp = (hiv_mortality_ic + tb_mortality_ic + malaria_mortality_ic) / 3

        # Make an empty dataframe
        ic_bounds = pd.DataFrame(index = years, columns=["low", "high"])

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
        combined_lb = 100 * (combined_lb / combined_lb.iloc[15, :])

        combined_ub = pd.concat([combined_partner, high])
        combined_ub = pd.DataFrame(combined_ub)
        combined_ub = 100 * (combined_ub / combined_ub.iloc[15, :])

        # Step 3.2 Normalise each disease to 100 in 2020 for Covid disruption
        combined_hiv_mortality_cf = pd.concat([hiv_mortality_partner, hiv_mortality_cf])
        combined_hiv_mortality_cf = pd.DataFrame(combined_hiv_mortality_cf)
        combined_hiv_mortality_cf = 100 * (combined_hiv_mortality_cf / combined_hiv_mortality_cf.iloc[15, :])

        combined_tb_mortality_cf = pd.concat([tb_mortality_partner, tb_mortality_cf])
        combined_tb_mortality_cf = pd.DataFrame(combined_tb_mortality_cf)
        combined_tb_mortality_cf = 100 * (combined_tb_mortality_cf / combined_tb_mortality_cf.iloc[15, :])

        combined_malaria_mortality_cf = pd.concat([malaria_mortality_partner, malaria_mortality_cf])
        combined_malaria_mortality_cf = pd.DataFrame(combined_malaria_mortality_cf)
        combined_malaria_mortality_cf = 100 * (combined_malaria_mortality_cf / combined_malaria_mortality_cf.iloc[15, :])

        # Step 3.3 Normalise each disease to 100 in 2020 for GP
        hiv_mortality_partner_gp = hiv_mortality_partner[(hiv_mortality_partner.index < 2020)]
        hiv_mortality_partner_gp = hiv_mortality_partner_gp[(hiv_mortality_partner_gp.index > 2014)]
        combined_hiv_mortality_gp = pd.concat([hiv_mortality_partner_gp, hiv_mortality_gp])
        combined_hiv_mortality_gp = pd.DataFrame(combined_hiv_mortality_gp)
        combined_hiv_mortality_gp = 100 * (combined_hiv_mortality_gp / combined_hiv_mortality_gp.iloc[5, :])
        combined_hiv_mortality_gp.columns = ['mortality']

        combined_tb_mortality_gp = tb_mortality_gp
        combined_tb_mortality_gp = pd.DataFrame(combined_tb_mortality_gp)
        combined_tb_mortality_gp = 100 * (combined_tb_mortality_gp / combined_tb_mortality_gp.iloc[0, :])
        combined_tb_mortality_gp.columns = ['mortality']

        combined_malaria_mortality_gp = malaria_mortality_gp
        combined_malaria_mortality_gp = pd.DataFrame(combined_malaria_mortality_gp)
        combined_malaria_mortality_gp = 100 * (combined_malaria_mortality_gp / combined_malaria_mortality_gp.iloc[0, :])
        combined_malaria_mortality_gp.columns = ['mortality']

        # Step 4. Combine the three normalised incidence rates by doing simple average
        combined_mortality = (combined_hiv_mortality + combined_tb_mortality + combined_malaria_mortality)/3
        combined_mortality_cf = (combined_hiv_mortality_cf + combined_tb_mortality_cf + combined_malaria_mortality_cf) / 3
        combined_mortality_gp = (combined_hiv_mortality_gp + combined_tb_mortality_gp + combined_malaria_mortality_gp) / 3

        # Compute the needed reductions
        reduction_ic = combined_mortality.loc[2029, 0] - 100
        reduction_cf = combined_mortality_cf.loc[2029, 0] - 100

        # Clean up so we can output the graphs
        actual = combined_mortality.loc[combined_mortality.index <2024].iloc[:,0]
        gp = combined_mortality_gp.loc[combined_mortality_gp.index > 2019].iloc[:,0]
        cf = combined_mortality_cf.loc[combined_mortality_cf.index >2022].iloc[:,0]
        ic = combined_mortality.loc[combined_mortality.index > 2022].iloc[:,0]
        ic_lb = combined_lb.loc[combined_lb.index > 2022].iloc[:,0]
        ic_ub = combined_ub.loc[combined_ub.index > 2022].iloc[:,0]

        comb_mort_df = pd.DataFrame(
            index=pd.Index(list(range(2010, 2031)), name='Year'),
            data={
                'Actual': actual,
                'GP': gp,
                'Counterfactual': cf,
                'IC': ic,
                'IC_LB': ic_lb,
                'IC_UB': ic_ub,
            }
        )

        return {
            "Combined mortality df": comb_mort_df,
            "Reduction in mortality in IC": reduction_ic,
            "Reduction in mortality in CF": reduction_cf,
        }


    def _calculate_combined_incidence_stats(self) -> dict[str, Any]:
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
            slice(2024, 2030), "model_central"]
        hiv_cases_lb_ic = self.hiv.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_low"]
        hiv_cases_ub_ic = self.hiv.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_high"]

        tb_cases_ic = self.tb.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_central"]
        tb_cases_lb_ic = self.tb.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_low"]
        tb_cases_ub_ic = self.tb.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_high"]

        malaria_cases_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_central"]
        malaria_cases_lb_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_low"]
        malaria_cases_ub_ic = self.malaria.IC.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_high"]

        hiv_pop_ic = self.hiv.IC.portfolio_results["hivneg"].loc[
            slice(2024, 2030), "model_central"]
        tb_pop_ic = self.tb.IC.portfolio_results["population"].loc[
            slice(2024, 2030), "model_central"]
        malaria_pop_ic = self.malaria.IC.portfolio_results["par"].loc[
            slice(2024, 2030), "model_central"]

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
            slice(2024, 2030), "model_central"]
        tb_cases_cf = self.tb.CF_InfAve.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_central"]
        malaria_cases_cf = self.malaria.CF_InfAve.portfolio_results["cases"].loc[
            slice(2024, 2030), "model_central"]

        hiv_pop_cf = self.hiv.CF_InfAve.portfolio_results["hivneg"].loc[
            slice(2024, 2030), "model_central"]
        tb_pop_cf = self.tb.CF_InfAve.portfolio_results["population"].loc[
            slice(2024, 2030), "model_central"]
        malaria_pop_cf = self.malaria.CF_InfAve.portfolio_results["par"].loc[
            slice(2024, 2030), "model_central"]

        hiv_incidence_cf = hiv_cases_cf / hiv_pop_cf
        tb_incidence_cf = tb_cases_cf / tb_pop_cf
        malaria_incidence_cf = malaria_cases_cf / malaria_pop_cf

        # Step 2.3 Get incidence for each disease from GP
        hiv_cases_gp = self.hiv.CF_forgraphs["cases"]
        hiv_pop_gp = self.hiv.CF_forgraphs["hivneg"]
        hiv_incidence_gp = hiv_cases_gp / hiv_pop_gp
        hiv_incidence_gp = pd.DataFrame(hiv_incidence_gp)
        hiv_incidence_gp = hiv_incidence_gp[hiv_incidence_gp.index > 2019]

        tb_incidence_gp = self.tb.CF_forgraphs["incidence"]
        tb_incidence_gp = pd.DataFrame(tb_incidence_gp)
        tb_incidence_gp = tb_incidence_gp[tb_incidence_gp.index >2014]

        malaria_incidence_gp = self.malaria.CF_forgraphs["incidence"]
        malaria_incidence_gp = pd.DataFrame(malaria_incidence_gp)
        malaria_incidence_gp = malaria_incidence_gp[malaria_incidence_gp.index > 2014]

        # Step 3.1 Normalise each disease to 100 in 2020 for partner and IC
        combined_hiv_incidence = pd.concat([hiv_incidence_partner,hiv_incidence_ic])
        combined_hiv_incidence = pd.DataFrame(combined_hiv_incidence)
        combined_hiv_incidence = 100*(combined_hiv_incidence / combined_hiv_incidence.iloc[15,:])

        combined_tb_incidence = pd.concat([tb_incidence_partner, tb_incidence_ic])
        combined_tb_incidence = pd.DataFrame(combined_tb_incidence)
        combined_tb_incidence = 100 * (combined_tb_incidence / combined_tb_incidence.iloc[15, :])

        combined_malaria_incidence = pd.concat([malaria_incidence_partner, malaria_incidence_ic])
        combined_malaria_incidence = pd.DataFrame(combined_malaria_incidence)
        combined_malaria_incidence = 100 * (combined_malaria_incidence / combined_malaria_incidence.iloc[15, :])

        # Step 3.2. Normalise the LB and UB for the IC
        combined_hiv_incidence_lb = pd.concat([hiv_incidence_partner, hiv_incidence_lb_ic])
        combined_hiv_incidence_lb = pd.DataFrame(combined_hiv_incidence_lb)
        combined_hiv_incidence_lb = 100 * (combined_hiv_incidence_lb / combined_hiv_incidence_lb.iloc[15, :])
        combined_hiv_incidence_ub = pd.concat([hiv_incidence_partner, hiv_incidence_ub_ic])
        combined_hiv_incidence_ub = pd.DataFrame(combined_hiv_incidence_ub)
        combined_hiv_incidence_ub = 100 * (combined_hiv_incidence_ub / combined_hiv_incidence_ub.iloc[15, :])

        combined_tb_incidence_ub = pd.concat([tb_incidence_partner, tb_incidence_lb_ic])
        combined_tb_incidence_lb = pd.DataFrame(combined_tb_incidence_ub)
        combined_tb_incidence_lb = 100 * (combined_tb_incidence_lb / combined_tb_incidence_lb.iloc[15, :])
        combined_tb_incidence_ub = pd.concat([tb_incidence_partner, tb_incidence_ub_ic])
        combined_tb_incidence_ub = pd.DataFrame(combined_tb_incidence_ub)
        combined_tb_incidence_ub = 100 * (combined_tb_incidence_ub / combined_tb_incidence_ub.iloc[15, :])

        combined_malaria_incidence_lb = pd.concat([malaria_incidence_partner, malaria_incidence_lb_ic])
        combined_malaria_incidence_lb = pd.DataFrame(combined_malaria_incidence_lb)
        combined_malaria_incidence_lb = 100 * (combined_malaria_incidence_lb / combined_malaria_incidence_lb.iloc[15, :])
        combined_malaria_incidence_ub = pd.concat([malaria_incidence_partner, malaria_incidence_ub_ic])
        combined_malaria_incidence_ub = pd.DataFrame(combined_malaria_incidence_ub)
        combined_malaria_incidence_ub = 100 * (combined_malaria_incidence_ub / combined_malaria_incidence_ub.iloc[15, :])

        # Back calculate SD at
        hiv_sd = (hiv_incidence_ub_ic - hiv_incidence_ic) / 1.96
        tb_sd = (tb_incidence_ub_ic - tb_incidence_ic) / 1.96
        malaria_sd = (malaria_incidence_ub_ic - malaria_incidence_ic) / 1.96
        sds = pd.DataFrame({"hiv": hiv_sd, "tb": tb_sd, "malaria": malaria_sd})

        # Prepare to generate CIs
        rho_btw_diseases = self.parameters.get("RHO_BETWEEN_DISEASES")
        years = list(range(2024, 2031))
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
        combined_hiv_incidence_cf = 100 * (combined_hiv_incidence_cf / combined_hiv_incidence_cf.iloc[15, :])

        combined_tb_incidence_cf = pd.concat([tb_incidence_partner, tb_incidence_cf])
        combined_tb_incidence_cf = pd.DataFrame(combined_tb_incidence_cf)
        combined_tb_incidence_cf = 100 * (combined_tb_incidence_cf / combined_tb_incidence_cf.iloc[15, :])

        combined_malaria_incidence_cf = pd.concat([malaria_incidence_partner, malaria_incidence_cf])
        combined_malaria_incidence_cf = pd.DataFrame(combined_malaria_incidence_cf)
        combined_malaria_incidence_cf = 100 * (combined_malaria_incidence_cf / combined_malaria_incidence_cf.iloc[15, :])

        # Step 3.3 Normalise each disease to 100 in 2020 for GP
        hiv_incidence_partner_gp = hiv_incidence_partner[(hiv_incidence_partner.index < 2020)]
        hiv_incidence_partner_gp = hiv_incidence_partner_gp[(hiv_incidence_partner_gp.index > 2014)]
        combined_hiv_incidence_gp = pd.concat([hiv_incidence_partner_gp, hiv_incidence_gp])
        combined_hiv_incidence_gp = pd.DataFrame(combined_hiv_incidence_gp)
        combined_hiv_incidence_gp = 100 * (combined_hiv_incidence_gp / combined_hiv_incidence_gp.iloc[5, :])
        combined_hiv_incidence_gp.columns = ['incidence']

        combined_tb_incidence_gp = tb_incidence_gp
        combined_tb_incidence_gp = combined_tb_incidence_gp.bfill(axis=1).iloc[:, 0]
        combined_tb_incidence_gp = pd.DataFrame(combined_tb_incidence_gp)
        combined_tb_incidence_gp = 100 * (combined_tb_incidence_gp / combined_tb_incidence_gp.iloc[0, :])
        combined_tb_incidence_gp.columns = ['incidence']

        combined_malaria_incidence_gp = malaria_incidence_gp
        combined_malaria_incidence_gp = combined_malaria_incidence_gp.bfill(axis=1).iloc[:, 0]
        combined_malaria_incidence_gp = pd.DataFrame(combined_malaria_incidence_gp)
        combined_malaria_incidence_gp = 100 * (combined_malaria_incidence_gp / combined_malaria_incidence_gp.iloc[0, :])
        combined_malaria_incidence_gp.columns = ['incidence']

        # Step 4. Combine the three normalised incidence rates by doing simple average
        combined_incidence = (combined_hiv_incidence + combined_tb_incidence + combined_malaria_incidence)/3
        combined_incidence_lb = (combined_hiv_incidence_lb + combined_tb_incidence_lb + combined_malaria_incidence_lb) / 3
        combined_incidence_ub = (combined_hiv_incidence_ub + combined_tb_incidence_ub + combined_malaria_incidence_ub) / 3
        combined_incidence_cf = (combined_hiv_incidence_cf + combined_tb_incidence_cf + combined_malaria_incidence_cf) / 3
        combined_incidence_gp = (combined_hiv_incidence_gp + combined_tb_incidence_gp + combined_malaria_incidence_gp) / 3

        # Compute the needed reductions
        reduction_ic = combined_incidence.loc[2029, 0] - 100
        reduction_cf = combined_incidence_cf.loc[2029, 0] - 100

        # Clean up so we can output the graphs
        actual = combined_incidence.loc[combined_incidence.index < 2024].iloc[:, 0]
        gp = combined_incidence_gp.loc[combined_incidence_gp.index > 2019].iloc[:, 0]
        cf = combined_incidence_cf.loc[combined_incidence_cf.index > 2022].iloc[:, 0]
        ic = combined_incidence.loc[combined_incidence.index > 2022].iloc[:, 0]
        ic_lb = combined_incidence_lb.loc[combined_incidence_lb.index > 2022].iloc[:, 0]
        ic_ub = combined_incidence_ub.loc[combined_incidence_ub.index > 2022].iloc[:, 0]

        comb_inc_df = pd.DataFrame(
            index=pd.Index(list(range(2010, 2031)), name='Year'),
            data={
                'Actual': actual,
                'GP': gp,
                'Counterfactual': cf,
                'IC': ic,
                'IC_LB': ic_lb,
                'IC_UB': ic_ub,
            }
        )

        return {
            "Combined incidence df": comb_inc_df,
            "Reduction in incidence in IC": reduction_ic,
            "Reduction in incidence in CF": reduction_cf,
        }
