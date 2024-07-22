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
1) scenario_descriptor: contains a XX_XX shorthand for scenario names
2) funding fraction: contains the funding fraction as expressed by the % of GP funding need. These need to be given as
   a proportion (0-1) NOT as a percentage (0-100)
3) country: holds iso3 code for a country
4) year: contains year information
5) indicator: contains the variable names (short-hand)
6) low, central and high: contains the value for the lower bound, central and upper bound of a given variable. Where 
   LB and UB are not available these should be set to be the same as the "central" value.  

 This following files are read in in this script: 
 1) The malaria model results shared by Pete
 2) The PF input data. These were prepared by TGF and shared with modellers as input data to the model
 3) The WHO partner data as prepared by the TGF. These contain variables including e.g., year, iso3, deaths 
 population, cases (number of new malaria cases infections for a given year). The partner data should contain data
 for each of these variable for each country eligible for GF funding for 2000 to latest year. 

 The above files are saved in the file structure described below. 
 CAUTION: failing to follow the file structure may throw up errors. 
 File structure: 
 1) Main project folder: "IC7/TimEmulationTool"
 2) model results should be located in "/modelling_outputs"
 3) PF input daa should be saved under "/pf"
 4) WHO partner data should be saved under "/partner"

 The following additional information needs to be set and prepared in order to run the code: 
 1) List of modelled countries: In the parameter file  provide the full list of iso3 codes
    of modelled countries for this disease that should be analysed. The list is used:
     a) in the checks, for example, to ensure that we have results for each country, for each year, for each variable 
     defined in this set of lists
     b) for filtering when generating the output (i.e. if we have to remove model results for Russia from the analysis, 
     we can remove Russia from this list and model results for this country will be filtered out)
 2) List of GF eligible countries: In file parameters.toml provide the full list 
    of iso3 codes of GF eligible countries for this disease that should be accounted for in this analysis. Adding or 
    removing iso3 codes from this list will automatically be reflected in the rest of the code (i.e. if Russia is not 
    eligible for GF funding, removing Russia from this list, means that the model results will not be extrapolated to 
    Russia when extrapolating to non-modelled counties). The list is used:
    a) to generate GP by using the population estimates for all eligible countries
    b) to filter out the partner data to only countries listed here
    b) to extrapolate to non-modelled countries
 3) List of indicators: The file parameter file provides a full list of variables needed for malaria, 
    including epidemiological variables and service-related variables. The list should include the short-hand variable
    name, full variable definition, and the data type (e.g. count (integer), fraction (proportion), rate. 
    The list is used:
     a) to map the variable names to their full definitions
     b) in the checks to ensure, for example, that we have results for each country, for each year, for each variable 
     defined in this set of lists
     c) which ones should be scaled to non-modelled countries (CAUTION: this will need to updated in 8th Replenishment)
     d) which indicators should be scaled for innovation
 4) List of scenarios: The parameter file provides the mapping of the scenario descriptions to their short-hand. 
    This list is used to:
    a) to map the variable (short-hand) name to the full definition
    b) in the checks to ensure, for example, that we have results for each country, for each year, for each variable 
    defined in this set of lists 
    c) for filtering when generating the output (i.e., select the final investment case and necessary counterfactual 
    scenario)
 5) Parameters defining the GP: In file "shared/fixed_gps/malaria_gp.csv" provide for each year the fixes reduction in 
    cases/incidence and deaths/mortality. 
    CAUTION: For each disease he indicator will vary (reduction for number of deaths OR mortality rate) but the column 
     headers should not be changed as this will result in errors. The correct indicators are set in the class 
     GpMalaria(Gp). These parameter are used to generate the time-series for new infections, incidence, deaths and 
     mortality rate for each year. 
 6) Central parameters: In file "parameters.toml" update the years. Those are the first year of the model results, the 
    last year of model (models may run up to 2050, but we need results up to 2030 only), years of the replenishment, 
    years that should be used in the objector funding for the optimizer (first year of replenishment to 2030), the 
    first year of the GP for malaria and the funding fractions fo reach disease. These parameters are used e.g., to 
    generate the GP time series and in the checks.  

Running the script for the first time and options to improve speed: 
At the end of the script is a line of code stating "LOAD_DATA_FROM_RAW_FILES". The first time you run this code, this 
needs to be set to True to load the model output and save it locally. In subsequent runs, this can be set to False to 
speed up the runs. 
CAUTION: If any changes are made to the way the model output is handled (i.e. add or remove a ISO3 code in the 
parameter file, the above switch needs to be turned to True and model results re-loaded to reflect these changes! 

CAUTION: 
Adding or removing items from these list will automatically be reflected in the rest of the code.
Scenarios without funding fractions (GP_GP, NULL_NULL, CC_CC) should be given a funding fraction of 100% in order to be 
included in key checks. 

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
        indicator) and columns containing model output (low, central, high)."""

        # Read in each file and concatenate the results
        all_csv_file_at_the_path = get_files_with_extension(path, "csv")
        list_of_df = [
            self._turn_workbook_into_df(file) for file in all_csv_file_at_the_path
        ]
        concatenated_dfs = pd.concat(list_of_df, axis=0)

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
        csv_df = self._load_sheet(file)

        # Only keep columns of immediate interest:
        csv_df = csv_df[
            [
                "iso3",
                "year",
                "scenario",
                "cases_smooth",
                "cases_smooth_lb",
                "cases_smooth_ub",
                "deaths_smooth",
                "deaths_smooth_lb",
                "deaths_smooth_ub",
                "net_n",
                "irs_people_protected",
                "treatments_given_public",
                "treatment_coverage",
                "smc_children_protected",
                "smc_coverage",
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
        ]

        # Before going to the rest of the code need to do some cleaning to GP scenario, to prevent errors in this script
        df_gp = csv_df[csv_df.scenario == "GP"]
        csv_df = csv_df[csv_df.scenario != "GP"]

        # 1. Add copy central into lb and ub columns for needed variables
        df_gp['cases_smooth_lb'] = df_gp['cases_smooth']
        df_gp['cases_smooth_ub'] = df_gp['cases_smooth']
        df_gp['deaths_smooth_lb'] = df_gp['deaths_smooth']
        df_gp['deaths_smooth_ub'] = df_gp['deaths_smooth']

        # 2. Replace nan with zeros
        df_gp[[
            "net_n",
            "irs_people_protected",
            "treatments_given_public",
            "treatment_coverage",
            "smc_children_protected",
            "smc_coverage",
            "vaccine_n",
            "vaccine_doses_n",
            "vaccine_coverage",
            "par",
            "par_targeted_smc",
            "par_vx",
            "total_cost",
            "cost_private",
            "cost_vaccine",
        ]] = df_gp[[
            "net_n",
            "irs_people_protected",
            "treatments_given_public",
            "treatment_coverage",
            "smc_children_protected",
            "smc_coverage",
            "vaccine_n",
            "vaccine_doses_n",
            "vaccine_coverage",
            "par",
            "par_targeted_smc",
            "par_vx",
            "total_cost",
            "cost_private",
            "cost_vaccine",
        ]].fillna(0)

        # Then put GP back into df
        csv_df = pd.concat([csv_df, df_gp], axis=0)

        # Do some re-naming to make things easier
        csv_df = csv_df.rename(
            columns={
                "iso3": "country",
                "scenario": "scenario_descriptor",
                "cases_smooth": "cases_central",
                "cases_smooth_lb": "cases_low",
                "cases_smooth_ub": "cases_high",
                "deaths_smooth": "deaths_central",
                "deaths_smooth_lb": "deaths_low",
                "deaths_smooth_ub": "deaths_high",
            }
        )

        # Clean up funding fraction and PF scenario
        csv_df['funding_fraction'] = csv_df['scenario_descriptor'].str.extract('PF_(\d+)$').fillna(
            '')  # Puts the funding scenario number in a new column called funding fraction
        csv_df['funding_fraction'] = csv_df['funding_fraction'].replace('',
                                                                        1)  # Where there is no funding fraction, set it to 1
        csv_df.loc[csv_df['scenario_descriptor'].str.contains('PF'), 'scenario_descriptor'] = 'PF'  # removes "_"

        # Duplicate indicators that do not have LB and UB to give low and high columns and remove duplicates
        csv_df["par_low"] = csv_df["par"]
        csv_df["par_central"] = csv_df["par"]
        csv_df["par_high"] = csv_df["par"]
        csv_df = csv_df.drop(columns=["par"])

        csv_df["llins_low"] = csv_df["net_n"]
        csv_df["llins_central"] = csv_df["net_n"]
        csv_df["llins_high"] = csv_df["net_n"]
        csv_df = csv_df.drop(columns=["net_n"])

        csv_df["irsppl_low"] = csv_df["irs_people_protected"]
        csv_df["irsppl_central"] = csv_df["irs_people_protected"]
        csv_df["irsppl_high"] = csv_df["irs_people_protected"]
        csv_df = csv_df.drop(columns=["irs_people_protected"])

        csv_df["txpublic_low"] = csv_df["treatments_given_public"]
        csv_df["txpublic_central"] = csv_df["treatments_given_public"]
        csv_df["txpublic_high"] = csv_df["treatments_given_public"]
        csv_df = csv_df.drop(columns=["treatments_given_public"])

        csv_df["txcoverage_low"] = csv_df["treatment_coverage"]
        csv_df["txcoverage_central"] = csv_df["treatment_coverage"]
        csv_df["txcoverage_high"] = csv_df["treatment_coverage"]
        csv_df = csv_df.drop(columns=["treatment_coverage"])

        csv_df["smc_low"] = csv_df["smc_children_protected"]
        csv_df["smc_central"] = csv_df["smc_children_protected"]
        csv_df["smc_high"] = csv_df["smc_children_protected"]
        csv_df = csv_df.drop(columns=["smc_children_protected"])

        csv_df["smccoverage_low"] = csv_df["smc_coverage"]
        csv_df["smccoverage_central"] = csv_df["smc_coverage"]
        csv_df["smccoverage_high"] = csv_df["smc_coverage"]
        csv_df = csv_df.drop(columns=["smc_coverage"])

        csv_df["vaccine_low"] = csv_df["vaccine_n"]
        csv_df["vaccine_central"] = csv_df["vaccine_n"]
        csv_df["vaccine_high"] = csv_df["vaccine_n"]
        csv_df = csv_df.drop(columns=["vaccine_n"])

        csv_df["vaccinedoses_low"] = csv_df["vaccine_doses_n"]
        csv_df["vaccinedoses_central"] = csv_df["vaccine_doses_n"]
        csv_df["vaccinedoses_high"] = csv_df["vaccine_doses_n"]
        csv_df = csv_df.drop(columns=["vaccine_doses_n"])

        csv_df["vaccinecoverage_low"] = csv_df["vaccine_coverage"]
        csv_df["vaccinecoverage_central"] = csv_df["vaccine_coverage"]
        csv_df["vaccinecoverage_high"] = csv_df["vaccine_coverage"]
        csv_df = csv_df.drop(columns=["vaccine_coverage"])

        csv_df["partargetedsmc_low"] = csv_df["par_targeted_smc"]
        csv_df["partargetedsmc_central"] = csv_df["par_targeted_smc"]
        csv_df["partargetedsmc_high"] = csv_df["par_targeted_smc"]
        csv_df = csv_df.drop(columns=["par_targeted_smc"])

        csv_df["parvx_low"] = csv_df["par_vx"]
        csv_df["parvx_central"] = csv_df["par_vx"]
        csv_df["parvx_high"] = csv_df["par_vx"]
        csv_df = csv_df.drop(columns=["par_vx"])

        csv_df["cost_low"] = csv_df["total_cost"]
        csv_df["cost_central"] = csv_df["total_cost"]
        csv_df["cost_high"] = csv_df["total_cost"]
        csv_df = csv_df.drop(columns=["total_cost"])

        csv_df["costtxprivate_low"] = csv_df["cost_private"]
        csv_df["costtxprivate_central"] = csv_df["cost_private"]
        csv_df["costtxprivate_high"] = csv_df["cost_private"]
        csv_df = csv_df.drop(columns=["cost_private"])

        csv_df["costvx_low"] = csv_df["cost_vaccine"]
        csv_df["costvx_central"] = csv_df["cost_vaccine"]
        csv_df["costvx_high"] = csv_df["cost_vaccine"]
        csv_df = csv_df.drop(columns=["cost_vaccine"])

        # Generate incidence and mortality
        csv_df["incidence_low"] = csv_df["cases_low"] / csv_df["par_low"]
        csv_df["incidence_central"] = csv_df["cases_central"] / csv_df["par_central"]
        csv_df["incidence_high"] = csv_df["cases_high"] / csv_df["par_high"]

        csv_df["mortality_low"] = csv_df["deaths_low"] / csv_df["par_low"]
        csv_df["mortality_central"] = (
            csv_df["deaths_central"] / csv_df["par_central"]
        )
        csv_df["mortality_high"] = csv_df["deaths_high"] / csv_df["par_high"]

        # Pivot to long format
        melted = csv_df.melt(
            id_vars=["year", "country", "scenario_descriptor", "funding_fraction"]
        )

        # Label the upper and lower bounds as variants and drop the original 'variable' term
        melted["indicator"] = melted["variable"].apply(lambda s: s.split("_")[0])
        melted["variant"] = melted["variable"].apply(lambda s: s.split("_")[1])
        melted = melted.drop(columns=["variable"])

        # Remove any rows with Nas
        melted = melted.dropna()

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
        ).unstack("variant")
        unpivoted.columns = unpivoted.columns.droplevel(0)

        print(f"done")
        return unpivoted

    @staticmethod
    def _load_sheet(file: Path):
        """Load sheet1 from the specified file, while suppressing warnings which sometimes come from `openpyxl` to do
        with the stylesheet (see https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls).
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
        return pd.read_csv(file, encoding="ISO-8859-1")


# Load the pf input data file(s)
# class PFInputDataMalaria(MALARIAMixin, PFInputData):
#     """This is the File Handler for the malaria input data containing pf targets."""
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#     def _build_df(self, path: Path) -> pd.DataFrame:
#         """Reads in the data and returns a pd.DataFrame with multi-index (scenario_descriptor, country, year,
#         indicator)."""
#
#         # Read in each file and concatenate the results
#         all_xlsx_file_at_the_path = get_files_with_extension(path, "xls")
#         list_of_df = [
#             self._turn_workbook_into_df(file) for file in all_xlsx_file_at_the_path
#         ]
#         concatenated_dfs = pd.concat(list_of_df, axis=0)
#
#         # Organise multi-index to be '(scenario country, year, indicator)' and column ['central']
#         concatenated_dfs = (
#             concatenated_dfs.reset_index()
#             .set_index(["scenario_descriptor", "country", "year"])
#             .stack()
#         )
#         concatenated_dfs = pd.DataFrame({"central": concatenated_dfs})
#
#         # Only keep indicators of immediate interest:
#         # WARNING: For Strategic target setting ensure that these names match the names in indicator list
#         malaria_indicators = self.parameters.get_indicators_for(self.disease_name).index.to_list()
#         f = concatenated_dfs.reset_index()
#         f = f.loc[f["indicator"].isin(malaria_indicators)]
#         f["scenario_descriptor"] = f["scenario_descriptor"] + "_GP"
#
#         # Drop any countries that are not listed with relevant `*_iso_model.csv`
#         malaria_modelled_countries = self.parameters.get_modelled_countries_for(self.disease_name)
#         f = f.loc[f["country"].isin(malaria_modelled_countries)]
#
#         # Re-concatenate
#         concatenated_dfs = f.set_index(
#             ["scenario_descriptor", "country", "year", "indicator"]
#         )
#
#         # Make a new version for the other scenarios
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace("_GP", "_MC")
#         concatenated_dfs2 = f.set_index(
#             ["scenario_descriptor", "country", "year", "indicator"]
#         )
#
#         # Make the final df with one set for each scenario
#         all_dfs = [concatenated_dfs, concatenated_dfs2]
#         concatenated_dfs = pd.concat(all_dfs, axis=0)
#
#         # Add IC scenario by slicing for any of the CD scenarios as the data for the period to be compared will match
#         ic_ic = concatenated_dfs.loc[
#             ("CD_MC", slice(None), slice(None), slice(None))
#         ]
#         ic_ic = ic_ic.reset_index()
#         ic_ic["scenario_descriptor"] = "IC_IC"
#         ic_ic = ic_ic.set_index(
#             ["scenario_descriptor", "country", "year", "indicator"]
#         )
#         all_dfs = [concatenated_dfs, ic_ic]
#         concatenated_dfs = pd.concat(all_dfs, axis=0)
#
#         # Check all scenarios are in there
#         scenarios = self.parameters.get_scenarios().index.to_list()
#         scenarios = [e for e in scenarios if e not in ("NULL_NULL", "GP_GP", "CC_CC")]
#
#         # Filter out countries that we do not need
#         expected_countries = self.parameters.get_modelled_countries_for(self.disease_name)
#         concatenated_dfs = concatenated_dfs.drop(
#             concatenated_dfs.index[
#                 ~concatenated_dfs.index.get_level_values('country').isin(expected_countries)]
#         )
#
#         assert all(
#             y in concatenated_dfs.index.get_level_values("scenario_descriptor")
#             for y in scenarios
#         )
#
#         return concatenated_dfs
#
#     def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
#         """Return formatted pd.DataFrame from the Excel file provided. The return dataframe is specific to one country,
#         and has the required multi-index and column specifications."""
#         print(f"Reading: {file}  .....", end="")
#
#         # Load 'Sheet1' from the Excel workbook
#         xlsx_df = self._load_sheet(file)
#
#         # Do some renaming to make things easier
#         # WARNING: For Strategic target setting ensure that these names match the names in indicator list
#         xlsx_df = xlsx_df.rename(
#             columns={
#                 "iso3": "country",
#                 "y": "year",
#             }
#         )
#
#         # Pivot to long format
#         melted = xlsx_df.melt(id_vars=["country", "year"])
#
#         # Deconstruct the 'Scenario' column to give "variable" and "scenario description" separately.
#         def _deconstruct_scenario(s: str) -> Tuple[str, str]:
#             """For a given string, from the `Scenario` column of the malaria workbook, return a tuple that gives
#             (scenario_descriptor, variable name). This routine extracts the scenario that is labelled in the form:
#              "<Variable> <Scenario_Descriptor>"."""
#
#             split_char = ""
#             k = 2
#             temp = re.split(r"(_n_|_p_)", s)
#             res = split_char.join(temp[:k]), split_char.join(temp[k:])
#
#             if res[1] not in (
#                 "covid_target",
#                 "prf_adj_target",
#                 "target",
#             ):
#                 return res[0], str("nan")
#             else:
#                 return res[0], res[1]
#
#         scenario_deconstructed = pd.DataFrame(
#             melted["variable"].apply(_deconstruct_scenario).to_list(),
#             index=melted.index,
#             columns=["indicator", "scenario_descriptor"],
#         )
#
#         melted = melted.join(scenario_deconstructed).drop(columns=["variable"])
#
#         # Do some cleaning to variable names and formatting
#         melted["indicator"] = melted["indicator"].astype(str).str.replace("_n_", "")
#         melted.loc[melted["indicator"].str.contains("_p_"), "value"] = (
#             melted["value"] / 100
#         )
#         melted["indicator"] = (
#             melted["indicator"].astype(str).str.replace("_p_", "coverage")
#         )
#         melted["scenario_descriptor"] = melted["scenario_descriptor"].replace(
#             {"covid_target": "CD", "prf_adj_target": "PP", "target": "PF"}
#         )
#
#         # Set the index and unpivot
#         unpivoted = melted.set_index(
#             ["country", "year", "scenario_descriptor", "indicator"]
#         ).unstack("indicator")
#         unpivoted.columns = unpivoted.columns.droplevel(0)
#
#         # Do some renaming to make things easier
#         # WARNING: For Strategic target setting ensure that these names match the names in indicator list
#         unpivoted = unpivoted.rename(
#             columns={
#                 "irs": "irshh",
#                 "malaria_txcoverage": "txcoverage",
#             }
#         )
#
#         print(f"done")
#         return unpivoted
#
#     @staticmethod
#     def _load_sheet(file: Path):
#         """Load sheet1 from the specified file, while suppressing warnings which sometimes come from `openpyxl` to do
#         with the stylesheet (see https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls).
#         """
#         return pd.read_excel(file)
#

# class PartnerDataMalaria(MALARIAMixin, PartnerData):
#     """This is the File Handler for the malaria partner data."""
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#     def _build_df(self, path: Path) -> pd.DataFrame:
#         """Reads in the data and returns a pd.DataFrame with multi-index (country, year, indicator)."""
#
#         # Read in each file and concatenate the results
#         all_xlsx_file_at_the_path = get_files_with_extension(path, "csv")
#         list_of_df = [
#             self._turn_workbook_into_df(file) for file in all_xlsx_file_at_the_path
#         ]
#         concatenated_dfs = pd.concat(list_of_df, axis=0)
#
#         # Construct multi-index as (country, year, indicator) & drop rows with na's in the year
#         concatenated_dfs = concatenated_dfs.reset_index()
#         concatenated_dfs = concatenated_dfs.dropna(subset=["year"])
#         concatenated_dfs["year"] = concatenated_dfs["year"].astype(int)
#         concatenated_dfs = concatenated_dfs.set_index(["country", "year"])
#         concatenated_dfs.columns.name = "indicator"
#         concatenated_dfs = pd.DataFrame({"central": concatenated_dfs.stack()})
#
#         # Drop any countries that are not listed with relevant `*_iso.csv`
#         malaria_countries = self.parameters.get_portfolio_countries_for(self.disease_name)
#         f = concatenated_dfs.reset_index()
#         f = f.loc[f["country"].isin(malaria_countries)]
#
#         # Add scenario name
#         f["scenario_descriptor"] = "CD_GP"
#         concatenated_dfs = f.set_index(
#             ["scenario_descriptor", "country", "year", "indicator"]
#         )
#
#         # Make a new version for the other scenario
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace(
#             "CD_GP", "CD_MC"
#         )
#         dfs2 = f.set_index(["scenario_descriptor", "country", "year", "indicator"])
#
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace(
#             "CD_MC", "PP_GP"
#         )
#         dfs3 = f.set_index(["scenario_descriptor", "country", "year", "indicator"])
#
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace(
#             "PP_GP", "PP_MC"
#         )
#         dfs4 = f.set_index(["scenario_descriptor", "country", "year", "indicator"])
#
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace(
#             "PP_MC", "PF_GP"
#         )
#         dfs5 = f.set_index(["scenario_descriptor", "country", "year", "indicator"])
#
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace(
#             "PF_GP", "PF_MC"
#         )
#         dfs6 = f.set_index(["scenario_descriptor", "country", "year", "indicator"])
#
#         f["scenario_descriptor"] = f["scenario_descriptor"].str.replace(
#             "PF_MC", "IC_IC"
#         )
#         dfs7 = f.set_index(["scenario_descriptor", "country", "year", "indicator"])
#
#         # Make the final df with one set for each scenario
#         all_dfs = [concatenated_dfs, dfs2, dfs3, dfs4, dfs5, dfs6, dfs7]
#         concatenated_dfs = pd.concat(all_dfs, axis=0)
#
#         # Check all scenarios are in there
#         scenarios = self.parameters.get_scenarios().index.to_list()
#         scenarios = [e for e in scenarios if e not in ("NULL_NULL", "GP_GP", "CC_CC")]
#
#         assert all(
#             y in concatenated_dfs.index.get_level_values("scenario_descriptor")
#             for y in scenarios
#         )
#
#         return concatenated_dfs
#
#     def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
#         """Return formatted pd.DataFrame from the Excel file provided. The return dataframe is specific to one country,
#         and has the required multi-index and column specifications."""
#         print(f"Reading: {file}  .....", end="")
#
#         # Load 'Sheet1' from the Excel workbook
#         xlsx_df = self._load_sheet(file)
#
#         # Only keep columns of immediate interest:
#         xlsx_df = xlsx_df[["iso3", "year", "death_who", "infection_who", "par_who"]]
#
#         # Remove postfix substring from column headers
#         xlsx_df.columns = xlsx_df.columns.str.replace("_who", "")
#
#         # Do some renaming to make things easier
#         xlsx_df = xlsx_df.rename(
#             columns={
#                 "iso3": "country",
#                 "infection": "cases",
#                 "death": "deaths",
#             }
#         )
#
#         # Generate incidence and mortality
#         xlsx_df["incidence"] = xlsx_df["cases"] / xlsx_df["par"]
#         xlsx_df["mortality"] = xlsx_df["deaths"] / xlsx_df["par"]
#
#         # Pivot to long format
#         melted = xlsx_df.melt(id_vars=["country", "year"])
#
#         # Remove any rows with Nas
#         melted = melted.drop(melted.index[melted["country"] == "CIV"])
#         melted.loc[pd.isnull(melted.country), "country"] = "CIV"
#
#         # Set the index and unpivot
#         unpivoted = melted.set_index(["country", "year", "variable"]).unstack(
#             "variable"
#         )
#         unpivoted.columns = unpivoted.columns.droplevel(0)
#         print(f"done")
#         return unpivoted
#
#     @staticmethod
#     def _load_sheet(file: Path):
#         """Load sheet1 from the specified file, while suppressing warnings which sometimes come from `openpyxl` to do
#         with the stylesheet (see https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls).
#         """
#         return pd.read_csv(file, encoding="ISO-8859-1")
#

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
