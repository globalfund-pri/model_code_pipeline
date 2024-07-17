import re
import warnings
from pathlib import Path
from typing import Tuple

import pandas as pd
import regex

from tgftools.filehandler import (
    # FixedGp,
    # Gp,
    ModelResults,
    # Parameters,
    # PartnerData,
    PFInputData,
    # RegionInformation,
)
from tgftools.utils import (
    get_data_path,
    get_files_with_extension,
)

""" START HERE FOR TB: This file sets up everything needed to run TB related code, including reading in the 
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
 1) The TB model results shared by Carel
 2) The PF input data. These were prepared by TGF and shared with modellers as input data to the model
 3) The WHO partner data as prepared by the TGF. These contain variables including e.g., year, iso3, deaths 
 population, cases (number of new TB cases infections for a given year). The partner data should contain data
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
 2) List of GF eligible countries: In file parameters.toml provide the full list of 
    iso3 codes of GF eligible countries for this disease that should be accounted for in this analysis. Adding or 
    removing iso3 codes from this list will automatically be reflected in the rest of the code (i.e. if Russia is not 
    eligible for GF funding, removing Russia from this list, means that the model results will not be extrapolated to 
    Russia when extrapolating to non-modelled counties). The list is used:
    a) to generate GP by using the population estimates for all eligible countries
    b) to filter out the partner data to only countries listed here
    b) to extrapolate to non-modelled countries
 3) List of indicators: The file parameter file provides a full list of variables needed for TB, 
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
 5) Parameters defining the GP: In file "shared/fixed_gps/tb_gp.csv" provide for each year the fixes reduction in 
    cases/incidence and deaths/mortality. 
    CAUTION: For each disease he indicator will vary (reduction for number of deaths OR mortality rate) but the column 
     headers should not be changed as this will result in errors. The correct indicators are set in the class GpTB(Gp). 
     These parameter are used to generate the time-series for new infections, incidence, deaths and mortality rate for
     each year. 
 6) Central parameters: In file "parameters.toml" update the years. Those are the first year of the model results, the 
    last year of model (models may run up to 2050, but we need results up to 2030 only), years of the replenishment, 
    years that should be used in the objector funding for the optimizer (first year of replenishment to 2030), the 
    first year of the GP for TB and the funding fractions fo reach disease. These parameters are used e.g., to generate 
    the GP time series and in the checks.  

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


class TBMixin:
    """Base class used as a `mix-in` that allows any inheriting class to have a property `disease_name` that returns
    the disease name."""
    @property
    def disease_name(self):
        return 'TB'


# Load the model result file(s)
class ModelResultsTb(TBMixin, ModelResults):
    """This is the File Handler for the TB modelling output."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame with multi-index (scenario, funding_fraction, country, year,
        indicator) and columns containing model output (low, central, high)."""

        # Read in each file and concatenate the results
        all_csv_file_at_the_path = get_files_with_extension(path, "xlsx")
        list_of_df = [
            self._turn_workbook_into_df(file) for file in all_csv_file_at_the_path
        ]

        concatenated_dfs = pd.concat(list_of_df, axis=0)

        # Remove NAN's (drop every row where this is an NaN)
        concatenated_dfs = concatenated_dfs.dropna()

        # Filter out countries and scenarios we do not need
        expected_countries = self.parameters.get(self.disease_name).get('MODELLED_COUNTRIES')
        scenario_names = (self.parameters.get_scenarios().index.to_list() +
                          self.parameters.get_counterfactuals().index.to_list() +
                          self.parameters.get_historiccounterfactuals().index.to_list())
        concatenated_dfs = concatenated_dfs.loc[
            (scenario_names, slice(None), expected_countries, slice(None), slice(None))
        ]

        # Make funding numbers into fractions
        concatenated_dfs = concatenated_dfs.reset_index()
        concatenated_dfs['new_column'] = concatenated_dfs.groupby(['scenario_descriptor', 'country'])['funding_fraction'].transform('max')
        concatenated_dfs['funding_fraction'] = concatenated_dfs['funding_fraction'] / concatenated_dfs['new_column']
        concatenated_dfs = concatenated_dfs.round({'funding_fraction': 2})
        concatenated_dfs = concatenated_dfs.drop('new_column', axis=1)

        # Re-pack the df
        concatenated_dfs = concatenated_dfs.set_index(
            ["scenario_descriptor", "funding_fraction", "country", "year", "indicator"]
        )

        return concatenated_dfs

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Returns formatted pd.DataFrame from the csv file provided. The returned dataframe is specific to one
        scenario, and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load 'Sheet1' from the Excel workbook
        xlsx_df = self._load_sheet(file)

        # TODO: remove later
        if file.name == "tb_ic_reference_BGD.xlsx":
            xlsx_df['iso3'] = 'BGD'

        # Compare columns to template
        template_csv = pd.read_excel(
            "/Users/mc1405/TGF_data/IC8/template/tb/tb_ic_modelling_reference 2024_06_21.xlsx", sheet_name="Template")
        model_column_names = list(xlsx_df.columns)
        template_column_names = list(template_csv.columns)
        filtered_list_in = [string for string in model_column_names if string not in template_column_names]
        filtered_list_out = [string for string in template_column_names if string not in model_column_names]

        print("Are there any missing or mis-names columns?")
        print(filtered_list_in)
        print(filtered_list_out)

        # Compare rows
        filtered_csv = xlsx_df[['iso3', 'Scenario', 'year']]
        filtered_template = template_csv[template_csv['iso3'].str.contains("IND")]
        filtered_template = filtered_template[['iso3', 'scenario', 'year']]
        filtered_template = filtered_template.rename(
            columns={'scenario': 'Scenario'})

        diff_df = pd.concat([filtered_csv, filtered_template])
        diff_df = diff_df.reset_index(drop=True)
        df_gpby = diff_df.groupby(list(diff_df.columns))
        idx = [x[0] for x in df_gpby.groups.values() if len(x) == 1]
        a = diff_df.reindex(idx)

        print("Here are the differences in rows")
        print(a)

        # Only keep columns of immediate interest:
        xlsx_df = xlsx_df[
            [
                "iso3",
                "year",
                "Scenario",
                "NewCases",
                "NewCases_LB",
                "NewCases_UB",
                "TBDeaths",
                "TBDeaths_LB",
                "TBDeaths_UB",
                "TBDeaths_HIVneg",
                "TBDeaths_HIVneg_LB",
                "TBDeaths_HIVneg_UB",
                "TBDeaths_HIVneg_NoTx",
                "TBDeaths_HIVneg_NoTx_LB",
                "TBDeaths_HIVneg_NoTx_UB",
                "Population",
                "Notified_n",
                "Notified_n_LB",
                "Notified_n_UB",
                "Notified_p",
                "Notified_p_LB",
                "Notified_p_UB",
                "TxSR",
                "mdr_notified_n",
                "mdr_notified_n_LB",
                "mdr_notified_n_UB",
                "mdr_notified_p",
                "mdr_notified_p_LB",
                "mdr_notified_p_UB",
                "TxSR_MDR",
                "mdr_estnew_n",
                "mdr_estretx_n",
                "mdr_Tx",
                "mdr_Tx_LB",
                "mdr_Tx_UB",
                "tb_art_n",
                "tb_art_n_LB",
                "tb_art_n_UB",
                "tb_art_p",
                "hiv_pos",
                "Costs",
            ]
        ]

        # Do some re-naming to make things easier
        xlsx_df = xlsx_df.rename(
            columns={
                "iso3": "country",
                "Scenario": "scenario_descriptor",
                "NewCases": "cases_central",
                "NewCases_LB": "cases_low",
                "NewCases_UB": "cases_high",
                "TBDeaths": "deaths_central",
                "TBDeaths_LB": "deaths_low",
                "TBDeaths_UB": "deaths_high",
                "TBDeaths_HIVneg": "deathshivneg_central",
                "TBDeaths_HIVneg_LB": "deathshivneg_low",
                "TBDeaths_HIVneg_UB": "deathshivneg_high",
                "TBDeaths_HIVneg_NoTx": "deathsnotxhivneg_central",
                "TBDeaths_HIVneg_NoTx_LB": "deathsnotxhivneg_low",
                "TBDeaths_HIVneg_NoTx_UB": "deathsnotxhivneg_high",
                "Notified_n": "notified_central",
                "Notified_n_LB": "notified_low",
                "Notified_n_UB": "notified_high",
                "Notified_p": "txcoverage_central",
                "Notified_p_LB": "txcoverage_low",
                "Notified_p_UB": "txcoverage_high",
                "mdr_notified_n": "mdrnotified_central",
                "mdr_notified_n_LB": "mdrnotified_low",
                "mdr_notified_n_UB": "mdrnotified_high",
                "mdr_notified_p": "mdrtxcoverage_central",
                "mdr_notified_p_LB": "mdrtxcoverage_low",
                "mdr_notified_p_UB": "mdrtxcoverage_high",
                "mdr_estnew_n": "mdrestimatesnew_central",
                "mdr_estretx_n": "mdrestimatedretx_central",
                "mdr_Tx": "mdrTx_central",
                "mdr_Tx_LB": "mdrTx_low",
                "mdr_Tx_UB": "mdrTx_high",
                "tb_art_n": "tbart_central",
                "tb_art_n_LB": "tbart_low",
                "tb_art_n_UB": "tbart_high",
                "tb_art_p": "tbartcoverage_central",
                "hiv_pos": "plhiv_central",
                "Costs": "cost_central",
            }
        )

        # Clean up funding fraction and PF scenario
        xlsx_df['funding_fraction'] = xlsx_df['scenario_descriptor'].str.extract('PF_(\d+)$').fillna('')
        xlsx_df['funding_fraction'] = xlsx_df['funding_fraction'].replace('', 1)
        xlsx_df.loc[xlsx_df['scenario_descriptor'].str.contains('PF'), 'scenario_descriptor'] = 'PF'

        # Duplicate indicators that do not have LB and UB to give low and high columns and remove duplicates
        xlsx_df["population_low"] = xlsx_df["Population"]
        xlsx_df["population_central"] = xlsx_df["Population"]
        xlsx_df["population_high"] = xlsx_df["Population"]
        xlsx_df = xlsx_df.drop(columns=["Population"])

        xlsx_df["TxSR_low"] = xlsx_df["TxSR"]
        xlsx_df["TxSR_central"] = xlsx_df["TxSR"]
        xlsx_df["TxSR_high"] = xlsx_df["TxSR"]
        xlsx_df = xlsx_df.drop(columns=["TxSR"])

        xlsx_df["mdrTxSR_low"] = xlsx_df["TxSR_MDR"]
        xlsx_df["mdrTxSR_central"] = xlsx_df["TxSR_MDR"]
        xlsx_df["mdrTxSR_high"] = xlsx_df["TxSR_MDR"]
        xlsx_df = xlsx_df.drop(columns=["TxSR_MDR"])

        xlsx_df["mdrestimatesnew_low"] = xlsx_df["mdrestimatesnew_central"]
        xlsx_df["mdrestimatesnew_high"] = xlsx_df["mdrestimatesnew_central"]

        xlsx_df["mdrestimatedretx_low"] = xlsx_df["mdrestimatedretx_central"]
        xlsx_df["mdrestimatedretx_high"] = xlsx_df["mdrestimatedretx_central"]

        xlsx_df["tbartcoverage_low"] = xlsx_df["tbartcoverage_central"]
        xlsx_df["tbartcoverage_high"] = xlsx_df["tbartcoverage_central"]

        xlsx_df["plhiv_low"] = xlsx_df["plhiv_central"]
        xlsx_df["plhiv_high"] = xlsx_df["plhiv_central"]

        xlsx_df["cost_low"] = xlsx_df["cost_central"]
        xlsx_df["cost_high"] = xlsx_df["cost_central"]

        # Generate incidence and mortality
        xlsx_df["incidence_low"] = xlsx_df["cases_low"] / xlsx_df["population_low"]
        xlsx_df["incidence_central"] = (
                xlsx_df["cases_central"] / xlsx_df["population_central"]
        )
        xlsx_df["incidence_high"] = xlsx_df["cases_high"] / xlsx_df["population_high"]

        xlsx_df["mortality_low"] = xlsx_df["deaths_low"] / xlsx_df["population_low"]
        xlsx_df["mortality_central"] = (
                xlsx_df["deaths_central"] / xlsx_df["population_central"]
        )
        xlsx_df["mortality_high"] = xlsx_df["deaths_high"] / xlsx_df["population_high"]

        # Pivot to long format
        melted = xlsx_df.melt(
            id_vars=["year", "country", "scenario_descriptor", "funding_fraction"]
        )

        # Remove the large TB file from memory
        del xlsx_df

        # Label the upper and lower bounds as variants and drop the original 'variable' term
        melted["indicator"] = melted["variable"].apply(lambda s: s.split("_")[0])
        melted["variant"] = melted["variable"].apply(lambda s: s.split("_")[1])
        melted = melted.drop(columns=["variable"])

        # Remove any rows with Nas
        melted = melted.dropna()

        # Convert funding_fraction to float
        melted["funding_fraction"] = melted["funding_fraction"].astype(float)

        # TODO: any NANs or NAs should be replaced. By zero? Do that for all diseases
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
        return pd.read_excel(file, sheet_name="ResultTemplate", engine="openpyxl")


class PFInputDataTb(TBMixin, PFInputData):
    """This is the File Handler for the Tb input data containing pf targets."""

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
        # WARNING: For Strategic target setting ensure that these names match the names in indicator list
        tb_indicators = self.parameters.get_indicators_for(self.disease_name).index.to_list()
        f = concatenated_dfs.reset_index()
        f = f.loc[f["indicator"].isin(tb_indicators)]

        # Drop any countries that are not listed with relevant `*_iso_model.csv`
        tb_modelled_countries = self.parameters.get_modelled_countries_for(self.disease_name)
        tb_modelled_countries = ['IND', 'BGD'] # TODO: update later
        f = f.loc[f["country"].isin(tb_modelled_countries)]

        # Re-concatenate
        concatenated_dfs = f.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        # Make a new version for the other scenarios
        f["scenario_descriptor"] = f["scenario_descriptor"].str.replace("PF", "CC_2022")
        concatenated_dfs2 = f.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        f["scenario_descriptor"] = f["scenario_descriptor"].str.replace("CC_2022", "NULL_2022")
        concatenated_dfs3 = f.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        # Make the final df with one set for each scenario
        all_dfs = [concatenated_dfs, concatenated_dfs2, concatenated_dfs3]
        concatenated_dfs = pd.concat(all_dfs, axis=0)

        # Check all scenarios are in there
        scenarios = (self.parameters.get_scenarios().index.to_list() +
                     self.parameters.get_counterfactuals().index.to_list() +
                     self.parameters.get_historiccounterfactuals().index.to_list())
        scenarios = [e for e in scenarios if e not in ("NULL_2000", "NULL_FIRSTYEARGF", "CC_2000", "CC_FIRSTYEARGF", "GP", "HH")]

        assert all(
            y in concatenated_dfs.index.get_level_values("scenario_descriptor")
            for y in scenarios
        )

        return concatenated_dfs

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Return formatted pd.DataFrame from the Excel file provided. The return dataframe is specific to one country,
        and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load 'Sheet1' from the Excel workbook
        xlsx_df = self._load_sheet(file)

        # Do some renaming to make things easier
        xlsx_df = xlsx_df.rename(
            columns={
                "iso3": "country",
                "y": "year",
            }
        )

        # Pivot to long format
        xlsx_df = xlsx_df.drop('data_type', axis=1)
        melted = xlsx_df.melt(id_vars=["country", "year"])
        melted = melted.rename(columns={'variable': 'indicator'})

        # Do some cleaning to variable names and formatting
        melted['indicator'] = melted['indicator'].str.replace('_n$', '', regex=True)

        melted.loc[melted["indicator"].str.endswith("_p"), "value"] = (
                melted["value"] / 100
        )
        melted['indicator'] = melted['indicator'].str.replace('tb_', '')
        melted['indicator'] = melted['indicator'].str.replace('_', '')

        # Set the index and unpivot
        unpivoted = melted.set_index(
            ["country", "year", "indicator"]
        ).unstack("indicator")
        unpivoted.columns = unpivoted.columns.droplevel(0)

        # Do some renaming to make things easier
        # WARNING: For Strategic target setting ensure that these names match the names in indicator list
        unpivoted = unpivoted.rename(
            columns={
                "notifiedp": "txcoverage",
                "successp": "TxSR",
                "mdrsuccessp": 'mdrTxSR',
                "tbhivart": "tbart",
            }
        )

        print(f"done")
        return unpivoted

    @staticmethod
    def _load_sheet(file: Path):
        """Load sheet1 from the specified file, while suppressing warnings which sometimes come from `openpyxl` to do
        with the stylesheet (see https://stackoverflow.com/questions/66214951/how-to-deal-with-warning-workbook-contains-no-default-style-apply-openpyxls).
        """
        return pd.read_excel(file)


# # Load the partner data file(s)
# class PartnerDataTb(TBMixin, PartnerData):
#     """This is the File Handler for the HIV partner data."""
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
#         tb_countries = RegionInformation().tb_countries
#         f = concatenated_dfs.reset_index()
#         f = f.loc[f["country"].isin(tb_countries)]
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
#         # Remove postfix substring from column headers
#         xlsx_df.columns = xlsx_df.columns.str.replace("_who", "")
#
#         # Do some renaming to make things easier
#         xlsx_df = xlsx_df.rename(
#             columns={
#                 "iso3": "country",
#                 "death": "deaths",
#                 "death_hivneg": "deathshivneg",
#                 "infection": "cases",
#             }
#         )
#
#         # Generate incidence and mortality
#         xlsx_df["incidence"] = xlsx_df["cases"] / xlsx_df["population"]
#         xlsx_df["mortality"] = xlsx_df["deaths"] / xlsx_df["population"]
#
#         # Pivot to long format
#         melted = xlsx_df.melt(id_vars=["country", "year"])
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
#
# # Define the checks
#
#
# class GpTb(TBMixin, Gp):
#     """Hold the GP for TB. It has to construct it from a file (fixed_gp) that shows the trend over time and
#     the partner data and some model results."""
#
#     def _build_df(
#         self,
#         fixed_gp: FixedGp,
#         model_results: ModelResults,
#         partner_data: PartnerData,
#         parameters: Parameters,
#     ) -> pd.DataFrame:
#
#         # Gather the parameters for this function
#         gp_start_year = parameters.get(self.disease_name).get("GP_START_YEAR")
#         first_year = parameters.get("START_YEAR")
#         last_year = parameters.get("END_YEAR")
#
#         tb_countries = RegionInformation().tb_countries
#         tb_m_countries = parameters.get_modelled_countries_for(self.disease_name)
#
#         # Extract relevant partner and model data
#         pop_model = (
#             model_results.df.loc[
#                 ("GP_GP", slice(None), tb_m_countries, slice(None), "population")
#             ]["central"]
#             .groupby(axis=0, level=3)
#             .sum()
#         )
#         pop_partner = (
#             partner_data.df.loc[("CD_GP", tb_countries, slice(None), "population")][
#                 "central"
#             ]
#             .groupby(axis=0, level=2)
#             .sum()
#         )
#
#         # Get population estimates from first model year to generate ratio
#         pop_m_firstyear = (
#             model_results.df.loc[
#                 ("GP_GP", slice(None), tb_m_countries, first_year, "population")
#             ]["central"]
#             .groupby(axis=0, level=3)
#             .sum()
#         )
#         pop_firstyear = partner_data.df.loc[
#             ("CD_GP", tb_countries, first_year, "population")
#         ].sum()["central"]
#         ratio = pop_m_firstyear / pop_firstyear
#
#         # Use GP baseline year partner data to get the cases/deaths/incidence/mortality estimates at baseline
#         cases_baseyear = partner_data.df.loc[
#             ("CD_GP", tb_countries, gp_start_year, "cases")
#         ].sum()["central"]
#         deaths_baseyear = partner_data.df.loc[
#             ("CD_GP", tb_countries, gp_start_year, "deaths")
#         ].sum()["central"]
#         deathshivneg_baseyear = partner_data.df.loc[
#             ("CD_GP", tb_countries, gp_start_year, "deathshivneg")
#         ].sum()["central"]
#         pop_baseyear = partner_data.df.loc[
#             ("CD_GP", tb_countries, gp_start_year, "population")
#         ].sum()["central"]
#         incidence_baseyear = cases_baseyear / pop_baseyear
#         mortality_rate_2015 = deaths_baseyear / pop_baseyear
#
#         # Make a time series of population estimates
#         pop_glued = pd.concat(
#             [
#                 pop_partner.loc[
#                     pop_partner.index.isin(
#                         [
#                             gp_start_year,
#                             gp_start_year + 1,
#                             gp_start_year + 2,
#                             gp_start_year + 3,
#                             gp_start_year + 4,
#                         ]
#                     )
#                 ],
#                 pop_model.loc[pop_model.index.isin(range(first_year, last_year + 1))]
#                 / ratio.values,
#             ]
#         )
#
#         # Convert reduction and get gp time series
#         relative_incidence = 1.0 - fixed_gp.df["incidence_reduction"]
#         gp_incidence = relative_incidence * incidence_baseyear
#         gp_cases = gp_incidence * pop_glued
#         relative_deaths = 1.0 - fixed_gp.df["death_rate_reduction"]
#         gp_deaths = relative_deaths * deaths_baseyear
#         gp_deathshivneg = relative_deaths * deathshivneg_baseyear
#         gp_mortality_rate = gp_deaths / pop_glued
#         gp_mortality_rate_hivneg = gp_deathshivneg / pop_glued
#
#         # Put it all together into a df
#         df = pd.DataFrame(
#             {
#                 "incidence": gp_incidence,
#                 "mortality": gp_mortality_rate,
#                 "mortalityhivneg": gp_mortality_rate_hivneg,
#                 "cases": gp_cases,
#                 "deaths": gp_deaths,
#                 "deathshivneg": gp_deathshivneg,
#             }
#         )
#
#         # Return in expected format
#         df.columns.name = "indicator"
#         df.index.name = "year"
#         return pd.DataFrame({"central": df.stack()})
