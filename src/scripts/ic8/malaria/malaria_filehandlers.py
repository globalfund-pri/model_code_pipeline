import re
import warnings
from pathlib import Path
from typing import Tuple

import pandas as pd

from tgftools.filehandler import (
    FixedGp,
    Gp,
    ModelResults,
    Parameters,
    PartnerData,
    PFInputData,
)
from tgftools.utils import (
    get_files_with_extension,
)

""" START HERE FOR malaria: This file sets up everything needed to run malaria related code, including reading in the 
relevant files, cleans up the data in these files (harmonizing naming convention, generate needed variables, filters out 
variables that are not needed), puts them in the format defined for the database format. 

The database format is: 
1) scenario_descriptor: contains a shorthand for scenario names
2) funding fraction: contains the funding fraction as expressed by the % of GP funding need. These need to be given as
   a proportion (0-1) NOT as a percentage (0-100)
3) country: holds iso3 code for a country
4) year: contains year information
5) indicator: contains the variable names (short-hand). The parameters.toml file maps the short-hand to definition
6) low, central and high: contains the value for the lower bound, central and upper bound of a given variable. Where 
   LB and UB are not available these should be set to be the same as the "central" value.  

 This following files are read in in this script: 
 1) The malaria model results shared by Pete
 2) The PF input data. These were prepared by TGF and shared with modellers as input data to the model
 3) The WHO partner data as prepared by the TGF. These contain variables including e.g., year, iso3, cases, deaths, and
    population at risk (for a given year). The partner data should contain data for each of these variable for each 
    country eligible for GF funding for 2000 to latest year. 

 The above files are saved in the file structure described below. 
 CAUTION: failing to follow the file structure may throw up errors. 
 File structure: 
 1) Main project folder: "IC8"
 2) model results should be located in "/modelling_outputs"
 3) PF input daa should be saved under "/pf"
 4) WHO partner data should be saved under "/partner"

  The following additional information needs to be set and prepared in order to run the code: 
 1) List of modelled countries: In the parameters.toml file  provide the full list of iso3 codes
    of modelled countries for this disease that should be analysed. The list is used:
     a) in the checks, for example, to ensure that we have results for each country, for each year, for each variable 
     defined in this set of lists
     b) for filtering when generating the output (i.e. if we have to remove model results for Russia from the analysis, 
     we can remove Russia from this list and model results for this country will be filtered out)
 2) List of GF eligible countries: In the parameters.toml file provide the full list of 
    iso3 codes of GF eligible countries for this disease that should be accounted for in this analysis. Adding or 
    removing iso3 codes from this list will automatically be reflected in the rest of the code (i.e. if Russia is not 
    eligible for GF funding, removing Russia from this list, means that the model results will not be extrapolated to 
    Russia when extrapolating to non-modelled counties). The list is used:
    a) to filter out the partner data to only countries listed here
    b) to extrapolate to non-modelled countries
 3) List of indicators: The parameters.toml file provides a full list of variables needed for TB, 
    including epidemiological variables and service-related variables. The list should include the short-hand variable
    name, full variable definition, and the data type (e.g. count (integer), fraction (proportion), rate. 
    The list is used:
     a) to map the variable names to their full definitions
     b) in the checks to ensure, for example, that we have results for each country, for each year, for each variable 
     defined in this set of lists
     c) that the variables are in the right format, e.g. that coverage indicators are expressed as fractions between 
     0-1 and that coverage is not above 1.  
     d) which ones should be scaled to non-modelled countries
     e) which indicators should be scaled for innovation
 4) List of scenarios: The parameter file provides the mapping of the scenario descriptions to their short-hand. 
    This list is used to:
    a) to map the variable (short-hand) name to the full definition
    b) in the checks to ensure, for example, that we have results for each country, for each year, for each variable 
    defined in this set of lists 
    c) for filtering when generating the output (i.e., select the final investment case and necessary counterfactual 
    scenario)
 5) Central parameters: In file "parameters.toml" update the years. Those are the first year of the model results, the 
    last year of model (e.g. model output may be provided up to 2050, but we only need projections up to 2030), years of 
    the replenishment, years that should be used in the objector funding for the optimizer, etc.  

Running the script for the first time and options to improve speed: 
At the end of the script is a line of code stating "LOAD_DATA_FROM_RAW_FILES". The first time you run this code, this 
needs to be set to True to load the model output and save it locally. In subsequent runs, this can be set to False to 
speed up the runs. 
CAUTION: If any changes are made to the way the model output is handled (i.e. add or remove a ISO3 code in the 
parameter file, the above switch needs to be turned to True and model results re-loaded to reflect these changes! 

CAUTION: 
Adding or removing items from the aforementioned lists list will automatically be reflected in the rest of the code. If 
the code is running from local copies of the model data and analysis by e.g. setting LOAD_DATA_FROM_RAW_FILES to false
these may not be reflected. 

CAUTION: 
Scenarios without funding fractions (e.g GP, NULL, CC) should be given a funding fraction of 100% in this filehandler 
script in order to pass the database check and later will be used to run key checks.  

GOOD CODE PRACTICE:
Variable names: should be use small letter and be short but easy to understand
Hard-coding: to be avoided at all costs and if at all limited to these disease files and report class. 
"""


class MALARIAMixin:
    """Base class used as a `mix-in` that allows any inheriting class to have a property `disease_name` that returns
    the disease name."""
    @property
    def disease_name(self):
        return 'MALARIA'


# Load the model result file(s)
class ModelResultsMalaria(MALARIAMixin, ModelResults):
    """This is the File Handler for the malaria modelling output."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame with multi-index (scenario, funding_fraction, country, year,
        indicator) and columns containing model output (low, central, high).
        This uses only the first-found .xlsx file in the path provided.
        """

        # Read in each file and concatenate the results
        first_xlsx_file_at_the_path = get_files_with_extension(path, "xlsx")[0]
        concatenated_dfs = self._turn_workbook_into_df(first_xlsx_file_at_the_path)

        # TODO: @richard: when Pete sends NULL_FIRSTYEARGF AND PF scenarios adapt/uncomment the section below and remove part on "scenario_names
        # Filter out any countries that we do not need
        expected_countries = self.parameters.get_modelled_countries_for(self.disease_name)
        scenario_names = (self.parameters.get_counterfactuals().index.to_list()) # TODO @richard: if we have all remove this line
        scenario_names.remove("GP") # TODO @richard: if we have all remove this line, else if we just get NULL FIRST year, remove that from this line
        scenario_names.remove("NULL_FIRSTYEARGF") # TODO @richard: if we have all remove this line, else if we just get NULL FIRST year, remove that from this line
        # TODO @richard: uncomment the part below
        # scenario_names = (self.parameters.get_scenarios().index.to_list() +
        #                   self.parameters.get_counterfactuals().index.to_list())
        concatenated_dfs = concatenated_dfs.loc[
            (scenario_names, slice(None), expected_countries, slice(None), slice(None))
        ]

        # Make funding numbers into fractions
        concatenated_dfs = concatenated_dfs.reset_index()
        concatenated_dfs['new_column'] = concatenated_dfs.groupby(['scenario_descriptor', 'country'])[
            'funding_fraction'].transform('max')
        concatenated_dfs['funding_fraction'] = concatenated_dfs['funding_fraction'] / concatenated_dfs['new_column']
        concatenated_dfs = concatenated_dfs.round({'funding_fraction': 2})
        concatenated_dfs = concatenated_dfs.drop('new_column', axis=1)

        # Re-pack the df
        concatenated_dfs = concatenated_dfs.set_index(
            ["scenario_descriptor", "funding_fraction", "country", "year", "indicator"]
        )
        return concatenated_dfs

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Returns formatted pd.DataFrame from the csv file provided. The returned dataframe is specific to one country,
        and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load csv
        df = self._load_sheet(file)

        # Only keep columns of immediate interest:
        cols_needed = [
                "iso3",
                "year",
                "scenario",
                "budget_proportion",    # this is the 'funding_fraction'
                "cases",                # }
                "cases_lb",             # }
                "cases_ub",             # }
                "deaths",               # }
                "deaths_lb",            # }
                "deaths_ub",            # } these are needed are the GP scenarios do not have the "_smooth" versions
                "cases_smooth",
                "cases_smooth_lb",
                "cases_smooth_ub",
                "deaths_smooth",
                "deaths_smooth_lb",
                "deaths_smooth_ub",
                "net_n",
                "irs_people_protected",
                "irs_hh",
                "treatments_given_public",
                "treatment_coverage",
                "smc_children_protected",
                "smc_coverage",
                # "vector_control_n", # TODO: @richard to uncomment
                "vaccine_n",
                "vaccine_doses_n",
                "vaccine_coverage",
                "par",
                "par_targeted_smc",
                "par_vx",
                "total_cost",
                "cost_private",
                "cost_vaccine",
        ]
        df = df[cols_needed]

        # For GP scenario, we only have cases, deaths (not smoothed), but for other scenarios we update the values
        # for cases and deaths with the smoothed versions. We then drop the smoothed versions of the columns
        df.loc[df.scenario != "GP", 'cases'] = df.loc[df.scenario != "GP", 'cases_smooth']
        df.loc[df.scenario != "GP", 'cases_ub'] = df.loc[df.scenario != "GP", 'cases_smooth_ub']
        df.loc[df.scenario != "GP", 'cases_lb'] = df.loc[df.scenario != "GP", 'cases_smooth_lb']
        df.loc[df.scenario != "GP", 'deaths'] = df.loc[df.scenario != "GP", 'deaths_smooth']
        df.loc[df.scenario != "GP", 'deaths_ub'] = df.loc[df.scenario != "GP", 'deaths_smooth_ub']
        df.loc[df.scenario != "GP", 'deaths_lb'] = df.loc[df.scenario != "GP", 'deaths_smooth_lb']
        df = df.drop(
            columns=['cases_smooth', 'cases_smooth_lb', 'cases_smooth_ub',
                     'deaths_smooth', 'deaths_smooth_lb', 'deaths_smooth_ub']
        )

        # Before going to the rest of the code need to do some cleaning to GP scenario, to prevent errors in this script
        cols_to_zero_out_in_gp = [
            "net_n",
            "irs_people_protected",
            'irs_hh',
            "treatments_given_public",
            "treatment_coverage",
            "smc_children_protected",
            "smc_coverage",
            # "vector_control_n", # TODO: @richard to uncomment
            "vaccine_n",
            "vaccine_doses_n",
            "vaccine_coverage",
            "par",
            "par_targeted_smc",
            "par_vx",
            "total_cost",
            "cost_private",
            "cost_vaccine",
        ]
        df.loc[df.scenario == "GP", cols_to_zero_out_in_gp].fillna(0.0, inplace=True)

        # Do some re-naming to make things easier
        df = df.rename(
            columns={
                "iso3": "country",
                "scenario": "scenario_descriptor",
                'budget_proportion': 'funding_fraction',
                "cases": "cases_central",
                "cases_lb": "cases_low",
                "cases_ub": "cases_high",
                "deaths": "deaths_central",
                "deaths_lb": "deaths_low",
                "deaths_ub": "deaths_high",
            }
        )

        # Duplicate indicators that do not have LB and UB to give low and high columns and remove duplicates
        df["par_low"] = df["par"]
        df["par_central"] = df["par"]
        df["par_high"] = df["par"]
        df = df.drop(columns=["par"])

        df["llins_low"] = df["net_n"]
        df["llins_central"] = df["net_n"]
        df["llins_high"] = df["net_n"]
        df = df.drop(columns=["net_n"])

        df["irsppl_low"] = df["irs_people_protected"]
        df["irsppl_central"] = df["irs_people_protected"]
        df["irsppl_high"] = df["irs_people_protected"]
        df = df.drop(columns=["irs_people_protected"])

        df["irshh_low"] = df["irs_hh"]
        df["irshh_central"] = df["irs_hh"]
        df["irshh_high"] = df["irs_hh"]
        df = df.drop(columns=["irs_hh"])

        df["txpublic_low"] = df["treatments_given_public"]
        df["txpublic_central"] = df["treatments_given_public"]
        df["txpublic_high"] = df["treatments_given_public"]
        df = df.drop(columns=["treatments_given_public"])

        df["txcoverage_low"] = df["treatment_coverage"]
        df["txcoverage_central"] = df["treatment_coverage"]
        df["txcoverage_high"] = df["treatment_coverage"]
        df = df.drop(columns=["treatment_coverage"])

        df["smc_low"] = df["smc_children_protected"]
        df["smc_central"] = df["smc_children_protected"]
        df["smc_high"] = df["smc_children_protected"]
        df = df.drop(columns=["smc_children_protected"])

        df["smccoverage_low"] = df["smc_coverage"]
        df["smccoverage_central"] = df["smc_coverage"]
        df["smccoverage_high"] = df["smc_coverage"]
        df = df.drop(columns=["smc_coverage"])

        # TODO: @richard to uncomment
        # csv_df["vectorcontrol_low"] = csv_df["vector_control_n"]
        # csv_df["vectorcontrol_central"] = csv_df["vector_control_n"]
        # csv_df["vectorcontrol_high"] = csv_df["vector_control_n"]
        # csv_df = csv_df.drop(columns=["vector_control_n"])

        df["vaccine_low"] = df["vaccine_n"]
        df["vaccine_central"] = df["vaccine_n"]
        df["vaccine_high"] = df["vaccine_n"]
        df = df.drop(columns=["vaccine_n"])

        df["vaccinedoses_low"] = df["vaccine_doses_n"]
        df["vaccinedoses_central"] = df["vaccine_doses_n"]
        df["vaccinedoses_high"] = df["vaccine_doses_n"]
        df = df.drop(columns=["vaccine_doses_n"])

        df["vaccinecoverage_low"] = df["vaccine_coverage"]
        df["vaccinecoverage_central"] = df["vaccine_coverage"]
        df["vaccinecoverage_high"] = df["vaccine_coverage"]
        df = df.drop(columns=["vaccine_coverage"])

        df["partargetedsmc_low"] = df["par_targeted_smc"]
        df["partargetedsmc_central"] = df["par_targeted_smc"]
        df["partargetedsmc_high"] = df["par_targeted_smc"]
        df = df.drop(columns=["par_targeted_smc"])

        df["parvx_low"] = df["par_vx"]
        df["parvx_central"] = df["par_vx"]
        df["parvx_high"] = df["par_vx"]
        df = df.drop(columns=["par_vx"])

        df["cost_low"] = df["total_cost"]
        df["cost_central"] = df["total_cost"]
        df["cost_high"] = df["total_cost"]
        df = df.drop(columns=["total_cost"])

        df["costtxprivate_low"] = df["cost_private"]
        df["costtxprivate_central"] = df["cost_private"]
        df["costtxprivate_high"] = df["cost_private"]
        df = df.drop(columns=["cost_private"])

        df["costvx_low"] = df["cost_vaccine"]
        df["costvx_central"] = df["cost_vaccine"]
        df["costvx_high"] = df["cost_vaccine"]
        df = df.drop(columns=["cost_vaccine"])

        # Generate incidence and mortality
        df["incidence_low"] = df["cases_low"] / df["par_low"]
        df["incidence_central"] = df["cases_central"] / df["par_central"]
        df["incidence_high"] = df["cases_high"] / df["par_high"]

        df["mortality_low"] = df["deaths_low"] / df["par_low"]
        df["mortality_central"] = df["deaths_central"] / df["par_central"]

        df["mortality_high"] = df["deaths_high"] / df["par_high"]

        # Pivot to long format
        melted = df.melt(
            id_vars=["year", "country", "scenario_descriptor", "funding_fraction"]
        )

        # Label the upper and lower bounds as variants and drop the original 'variable' term
        def get_var_name_and_variant(s: str) -> Tuple[str, str]:
            split_at_last_underscore = s.rpartition("_")
            return split_at_last_underscore[0], split_at_last_underscore[-1]

        indicator_and_variant = pd.DataFrame(melted["variable"].apply(get_var_name_and_variant).to_list())
        melted["indicator"] = indicator_and_variant[0]
        melted["variant"] = indicator_and_variant[1]
        melted = melted.drop(columns=["variable"])

        # Set the index and unpivot variant (so that these are columns (low/central/high) are returned
        unpivoted = melted.set_index(
            [
                "scenario_descriptor",
                "funding_fraction",
                "country",
                "year",
                "indicator",
                "variant",
            ]
        )
        unpivoted = unpivoted.unstack("variant")
        unpivoted.columns = unpivoted.columns.droplevel(0)

        print(f"done")
        return unpivoted

    @staticmethod
    def _load_sheet(file: Path):
        """Load the sheet named 'Output'"""
        return pd.read_excel(file, sheet_name='Output')



# Load the pf input data file(s)
class PFInputDataMalaria(MALARIAMixin, PFInputData):
    """This is the File Handler for the malaria input data containing pf targets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and returns a pd.DataFrame with multi-index (scenario_descriptor, country, year,
        indicator)."""

        # Read in each file and concatenate the results
        all_xlsx_file_at_the_path = get_files_with_extension(path, "xlsx")
        list_of_df = [
            self._turn_workbook_into_df(file) for file in all_xlsx_file_at_the_path
        ]
        concatenated_dfs = pd.concat(list_of_df, axis=0)
        concatenated_dfs['scenario_descriptor'] = "PF"

        # Organise multi-index to be '(scenario country, year, indicator)' and column ['central']
        concatenated_dfs = (
            concatenated_dfs.reset_index()
            .set_index(["scenario_descriptor", "country", "year"])
            .stack()
        )
        concatenated_dfs = pd.DataFrame({"central": concatenated_dfs})

        # Only keep indicators of immediate interest:
        indicators = self.parameters.get_indicators_for(self.disease_name).index.to_list()
        countries = self.parameters.get_modelled_countries_for(self.disease_name)
        f = concatenated_dfs.reset_index()
        f = f.loc[f["indicator"].isin(indicators)]
        f = f.loc[f["country"].isin(countries)]

        # Re-concatenate
        concatenated_dfs = f.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        return concatenated_dfs

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Return formatted pd.DataFrame from the Excel file provided. The return dataframe is specific to one country,
        and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load workbook
        xlsx_df = self._load_sheet(file)

        # Do some renaming to make things easier
        xlsx_df = xlsx_df.rename(
            columns={
                "iso3": "country",
                'smc_child_n': 'smc',
                'pop_irs_n': 'irsppl_n',
                'irs_n': 'irshh_n',
            }
        )

        # Pivot to long format
        xlsx_df = xlsx_df.drop('data_type', axis=1)
        melted = xlsx_df.melt(id_vars=["country", "year"])
        melted = melted.rename(columns={'variable': 'indicator'})

        # Do some cleaning to variable names and formatting
        melted['indicator'] = melted['indicator'].str.replace('_n$', '', regex=True)
        melted.loc[melted["indicator"].str.contains("_p"), "value"] = (
            melted["value"] / 100
        )

        # Set the index and unpivot
        unpivoted = melted.set_index(
            ["country", "year", "indicator"]
        ).unstack("indicator")
        unpivoted.columns = unpivoted.columns.droplevel(0)

        print(f"done")
        return unpivoted

    @staticmethod
    def _load_sheet(file: Path):
        """Load sheet1 from the specified file, while suppressing warnings which sometimes come from `openpyxl` to do
        with the stylesheet (see https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls).
        """
        return pd.read_excel(file)


class PartnerDataMalaria(MALARIAMixin, PartnerData):
    """This is the File Handler for the malaria partner data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and returns a pd.DataFrame with multi-index (country, year, indicator)."""

        # Read in each file and concatenate the results
        all_xlsx_file_at_the_path = get_files_with_extension(path, "csv")
        list_of_df = [
            self._turn_workbook_into_df(file) for file in all_xlsx_file_at_the_path
        ]
        concatenated_dfs = pd.concat(list_of_df, axis=0)
        concatenated_dfs['scenario_descriptor'] = "PF"

        # Organise multi-index to be '(scenario country, year, indicator)' and column ['central']
        concatenated_dfs = (
            concatenated_dfs.reset_index()
            .set_index(["scenario_descriptor", "country", "year"])
            .stack()
        )
        concatenated_dfs = pd.DataFrame({"central": concatenated_dfs})

        # Only keep indicators and years of immediate interest:
        countries = self.parameters.get_portfolio_countries_for(self.disease_name)
        start_year = self.parameters.get("PARTNER_START_YEAR")
        f = concatenated_dfs.reset_index()
        f = f.loc[f["country"].isin(countries)]
        f = f.loc[f["year"] >= start_year]

        # Re-concatenate
        concatenated_dfs = f.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        return concatenated_dfs

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Return formatted pd.DataFrame from the Excel file provided. The return dataframe is specific to one country,
        and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load workbook
        csv_df = self._load_sheet(file)

        # Only keep columns of immediate interest:
        csv_df = csv_df[
            [
                "ISO3",
                "Year",
                "malaria_cases_n_pip",
                "malaria_deaths_n_pip",
                "malaria_par_n_pip"
            ]
        ]

        # Do some renaming to make things easier
        csv_df = csv_df.rename(
            columns={
                "ISO3": "country",
                "Year": 'year',
                "malaria_cases_n_pip": "cases",
                "malaria_deaths_n_pip": "deaths",
                "malaria_par_n_pip": "par",

            }
        )

        # Generate incidence and mortality
        csv_df["incidence"] = csv_df["cases"] / csv_df["par"]
        csv_df["mortality"] = csv_df["deaths"] / csv_df["par"]

        # Pivot to long format
        melted = csv_df.melt(id_vars=["country", "year"])
        melted = melted.rename(columns={'variable': 'indicator'})

        # Set the index and unpivot
        unpivoted = melted.set_index(["country", "year", "indicator"]).unstack(
            "indicator"
        )
        unpivoted.columns = unpivoted.columns.droplevel(0)

        print(f"done")
        return unpivoted

    @staticmethod
    def _load_sheet(file: Path):
        """Load sheet1 from the specified file, while suppressing warnings which sometimes come from `openpyxl` to do
        with the stylesheet (see https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls).
        """
        return pd.read_csv(file, encoding="ISO-8859-1")


# Define the checks


# class GpMalaria(MALARIAMixin, Gp):
#     """Hold the GP for malaria. It has to construct it from a file (fixed_gp) that shows the trend over time and
#     the partner data and some model results."""
#
#     def _build_df(
#         self,
#         fixed_gp: FixedGp,
#         model_results: ModelResults,
#         partner_data: PartnerData,
#         parameters: Parameters
#     ) -> pd.DataFrame:
#
#         # Gather the parameters for this function
#         gp_start_year = parameters.get(self.disease_name).get("GP_START_YEAR")
#         first_year = parameters.get("START_YEAR")
#         last_year = parameters.get("END_YEAR")
#
#         malaria_countries = parameters.get_portfolio_countries_for(self.disease_name)
#         malaria_m_countries = parameters.get_modelled_countries_for(self.disease_name)
#
#         # Extract relevant partner and model data
#         pop_model = (
#             model_results.df.loc[("GP_GP", 1, malaria_m_countries, slice(None), "par")][
#                 "central"
#             ]
#             .groupby(axis=0, level=3)
#             .sum()
#         )
#
#         # Get population estimates from first model year to generate ratio
#         pop_m_firstyear = (
#             model_results.df.loc[
#                 ("GP_GP", 1, malaria_m_countries, gp_start_year, "par")
#             ]["central"]
#             .groupby(axis=0, level=1)
#             .sum()
#         )
#         pop_firstyear = partner_data.df.loc[
#             ("CD_GP", malaria_countries, gp_start_year, "par")
#         ].sum()["central"]
#         ratio = pop_m_firstyear / pop_firstyear
#
#         # Use baseline partner data to get the cases/deaths/incidence/mortality estimates at baseline
#         cases_baseyear = partner_data.df.loc[
#             ("CD_GP", malaria_countries, gp_start_year, "cases")
#         ].sum()["central"]
#         pop_baseyear = partner_data.df.loc[
#             ("CD_GP", malaria_countries, gp_start_year, "par")
#         ].sum()["central"]
#         deaths_baseyear = partner_data.df.loc[
#             ("CD_GP", malaria_countries, gp_start_year, "deaths")
#         ].sum()["central"]
#         incidence_baseyear = cases_baseyear / pop_baseyear
#         mortality_rate_baseyear = deaths_baseyear / pop_baseyear
#
#         # Make a time series of population estimate
#         pop_glued = (
#             pop_model.loc[pop_model.index.isin(range(gp_start_year, last_year + 1))]
#             / ratio.values
#         )
#
#         # Convert reduction and get gp time series
#         relative_incidence = 1.0 - fixed_gp.df["incidence_reduction"]
#         gp_incidence = relative_incidence * incidence_baseyear
#         relative_mortality_rate = 1.0 - fixed_gp.df["death_rate_reduction"]
#         gp_mortality_rate = relative_mortality_rate * mortality_rate_baseyear
#         gp_cases = gp_incidence * pop_glued
#         gp_deaths = gp_mortality_rate * pop_glued
#
#         # Put it all together into a df
#         df = pd.DataFrame(
#             {
#                 "incidence": gp_incidence,
#                 "mortality": gp_mortality_rate,
#                 "cases": gp_cases,
#                 "deaths": gp_deaths,
#             }
#         )
#
#         # Return in expected format
#         df.columns.name = "indicator"
#         df.index.name = "year"
#         return pd.DataFrame({"central": df.stack()})
