import re
import warnings
from pathlib import Path
from typing import Tuple

import pandas as pd
import regex

from tgftools.filehandler import (
    FixedGp,
    Gp,
    ModelResults,
    Parameters,
    PFInputData,
    PartnerData,
)
from tgftools.utils import (
    get_data_path,
    get_files_with_extension,
)

""" START HERE FOR TB: This file sets up everything needed to run TB related code, including reading in the 
relevant files, cleans up the data in these files (harmonizing naming convention, generate needed variables, filters out 
variables that are not needed), puts them in the format defined for the database format. 

The database format is: 
1) scenario_descriptor: contains a shorthand for scenario names. The parameters.toml file maps the short-hand to definition
2) funding fraction: contains the funding fraction as expressed by the % of GP funding need. These need to be given as
   a proportion (0-1) NOT as a percentage (0-100)
3) country: holds iso3 code for a country
4) year: contains year information
5) indicator: contains the variable names (short-hand). The parameters.toml file maps the short-hand to definition
6) low, central and high: contains the value for the lower bound, central and upper bound of a given variable. Where 
   LB and UB are not available these should be set to be the same as the "central" value.  

 This following files are read in in this script: 
 1) The TB model results shared by Carel
 2) The PF input data. These were prepared by TGF and shared with modellers as input data to the model
 3) The WHO partner data as prepared by the TGF. These contain variables including e.g., year, iso3, cases, deaths (by
    hiv status) and population estimates (for a given year). The partner data should contain data for each of these 
    variable for each country eligible for GF funding for 2000 to latest year. 

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

        # Filter out countries and scenarios we do not need
        expected_countries = self.parameters.get(self.disease_name).get('MODELLED_COUNTRIES')
        scenario_names = (self.parameters.get_scenarios().index.to_list() +
                          self.parameters.get_counterfactuals().index.to_list())
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

        # Make IC scenario
        funding_fraction = 1
        ic_df = concatenated_dfs.loc[
            ("PF", funding_fraction, slice(None), slice(None), slice(None))
        ]
        ic_df = ic_df.reset_index()
        ic_df["scenario_descriptor"] = "FULL_FUNDING"
        ic_df["funding_fraction"] = funding_fraction
        ic_df = ic_df.set_index(
            ["scenario_descriptor", "funding_fraction", "country", "year", "indicator"]
        )  # repack the index

        # Sort the ic_df
        ic_df.sort_index(level="country")

        # Add ic_ic scenario to model output
        concatenated_dfs = pd.concat(([concatenated_dfs, ic_df]))

        return concatenated_dfs

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Returns formatted pd.DataFrame from the csv file provided. The returned dataframe is specific to one
        scenario, and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load 'Sheet1' from the Excel workbook
        xlsx_df = self._load_sheet(file)

        # If we are running checks set the below to 1
        check = 0

        # Get costs without vaccine
        xlsx_df['TotalCost'] = xlsx_df["Costs"]
        xlsx_df['Costs'] = xlsx_df["TotalCost"] - xlsx_df["vacc_costs"]

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
                "NewCases_0_4",
                "NewCases_5_9",
                "NewCases_10_14",
                "NewCases_15_19",
                "NewCases_20_24",
                "NewCases_25_29",
                "NewCases_30_34",
                "NewCases_35_39",
                "NewCases_40_44",
                "NewCases_45_49",
                "NewCases_50_54",
                "NewCases_55_59",
                "NewCases_60_64",
                "NewCases_65_69",
                "NewCases_70_74",
                "NewCases_75_79",
                "NewCases_80",
                "TBDeathsAll_0_4",
                "TBDeathsAll_5_9",
                "TBDeathsAll_10_14",
                "TBDeathsAll_15_19",
                "TBDeathsAll_20_24",
                "TBDeathsAll_25_29",
                "TBDeathsAll_30_34",
                "TBDeathsAll_35_39",
                "TBDeathsAll_40_44",
                "TBDeathsAll_45_49",
                "TBDeathsAll_50_54",
                "TBDeathsAll_55_59",
                "TBDeathsAll_60_64",
                "TBDeathsAll_65_69",
                "TBDeathsAll_70_74",
                "TBDeathsAll_75_79",
                "TBDeathsAll_80",
                "TBDeathsHIVneg_0_4",
                "TBDeathsHIVneg_5_9",
                "TBDeathsHIVneg_10_14",
                "TBDeathsHIVneg_15_19",
                "TBDeathsHIVneg_20_24",
                "TBDeathsHIVneg_25_29",
                "TBDeathsHIVneg_30_34",
                "TBDeathsHIVneg_35_39",
                "TBDeathsHIVneg_40_44",
                "TBDeathsHIVneg_45_49",
                "TBDeathsHIVneg_50_54",
                "TBDeathsHIVneg_55_59",
                "TBDeathsHIVneg_60_64",
                "TBDeathsHIVneg_65_69",
                "TBDeathsHIVneg_70_74",
                "TBDeathsHIVneg_75_79",
                "TBDeathsHIVneg_80",
                "Population_all_0_4",
                "Population_all_5_9",
                "Population_all_10_14",
                "Population_all_15_19",
                "Population_all_20_24",
                "Population_all_25_29",
                "Population_all_30_34",
                "Population_all_35_39",
                "Population_all_40_44",
                "Population_all_45_49",
                "Population_all_50_54",
                "Population_all_55_59",
                "Population_all_60_64",
                "Population_all_65_69",
                "Population_all_70_74",
                "Population_all_75_79",
                "Population_all_80",
                "YLDs",
                "YLDs_HIVn",
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
                "vacc_number",
                "vacc_costs",
            ]
        ]
        # Only keep columns of immediate interest:

        # Before going to the rest of the code need to do some cleaning to GP scenario, to prevent errors in this script
        df_gp = xlsx_df[xlsx_df.Scenario == "GP"]
        xlsx_df = xlsx_df[xlsx_df.Scenario != "GP"]

        # 1. Add copy central into lb and ub columns for needed variables
        df_gp['NewCases_LB'] = df_gp['NewCases']
        df_gp['NewCases_UB'] = df_gp['NewCases']
        df_gp['TBDeaths_LB'] = df_gp['TBDeaths']
        df_gp['TBDeaths_UB'] = df_gp['TBDeaths']
        df_gp['TBDeaths_HIVneg_LB'] = df_gp['TBDeaths_HIVneg']
        df_gp['TBDeaths_HIVneg_UB'] = df_gp['TBDeaths_HIVneg']

        # 2. Replace nan with zeros
        df_gp[[
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
            "vacc_number",
            "vacc_costs",
            "NewCases_0_4",
            "NewCases_5_9",
            "NewCases_10_14",
            "NewCases_15_19",
            "NewCases_20_24",
            "NewCases_25_29",
            "NewCases_30_34",
            "NewCases_35_39",
            "NewCases_40_44",
            "NewCases_45_49",
            "NewCases_50_54",
            "NewCases_55_59",
            "NewCases_60_64",
            "NewCases_65_69",
            "NewCases_70_74",
            "NewCases_75_79",
            "NewCases_80",
            "TBDeathsAll_0_4",
            "TBDeathsAll_5_9",
            "TBDeathsAll_10_14",
            "TBDeathsAll_15_19",
            "TBDeathsAll_20_24",
            "TBDeathsAll_25_29",
            "TBDeathsAll_30_34",
            "TBDeathsAll_35_39",
            "TBDeathsAll_40_44",
            "TBDeathsAll_45_49",
            "TBDeathsAll_50_54",
            "TBDeathsAll_55_59",
            "TBDeathsAll_60_64",
            "TBDeathsAll_65_69",
            "TBDeathsAll_70_74",
            "TBDeathsAll_75_79",
            "TBDeathsAll_80",
            "TBDeathsHIVneg_0_4",
            "TBDeathsHIVneg_5_9",
            "TBDeathsHIVneg_10_14",
            "TBDeathsHIVneg_15_19",
            "TBDeathsHIVneg_20_24",
            "TBDeathsHIVneg_25_29",
            "TBDeathsHIVneg_30_34",
            "TBDeathsHIVneg_35_39",
            "TBDeathsHIVneg_40_44",
            "TBDeathsHIVneg_45_49",
            "TBDeathsHIVneg_50_54",
            "TBDeathsHIVneg_55_59",
            "TBDeathsHIVneg_60_64",
            "TBDeathsHIVneg_65_69",
            "TBDeathsHIVneg_70_74",
            "TBDeathsHIVneg_75_79",
            "TBDeathsHIVneg_80",
            "Population_all_0_4",
            "Population_all_5_9",
            "Population_all_10_14",
            "Population_all_15_19",
            "Population_all_20_24",
            "Population_all_25_29",
            "Population_all_30_34",
            "Population_all_35_39",
            "Population_all_40_44",
            "Population_all_45_49",
            "Population_all_50_54",
            "Population_all_55_59",
            "Population_all_60_64",
            "Population_all_65_69",
            "Population_all_70_74",
            "Population_all_75_79",
            "Population_all_80",
            "YLDs",
            "YLDs_HIVn",
        ]] = df_gp[[
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
            "vacc_number",
            "vacc_costs",
            "NewCases_0_4",
            "NewCases_5_9",
            "NewCases_10_14",
            "NewCases_15_19",
            "NewCases_20_24",
            "NewCases_25_29",
            "NewCases_30_34",
            "NewCases_35_39",
            "NewCases_40_44",
            "NewCases_45_49",
            "NewCases_50_54",
            "NewCases_55_59",
            "NewCases_60_64",
            "NewCases_65_69",
            "NewCases_70_74",
            "NewCases_75_79",
            "NewCases_80",
            "TBDeathsAll_0_4",
            "TBDeathsAll_5_9",
            "TBDeathsAll_10_14",
            "TBDeathsAll_15_19",
            "TBDeathsAll_20_24",
            "TBDeathsAll_25_29",
            "TBDeathsAll_30_34",
            "TBDeathsAll_35_39",
            "TBDeathsAll_40_44",
            "TBDeathsAll_45_49",
            "TBDeathsAll_50_54",
            "TBDeathsAll_55_59",
            "TBDeathsAll_60_64",
            "TBDeathsAll_65_69",
            "TBDeathsAll_70_74",
            "TBDeathsAll_75_79",
            "TBDeathsAll_80",
            "TBDeathsHIVneg_0_4",
            "TBDeathsHIVneg_5_9",
            "TBDeathsHIVneg_10_14",
            "TBDeathsHIVneg_15_19",
            "TBDeathsHIVneg_20_24",
            "TBDeathsHIVneg_25_29",
            "TBDeathsHIVneg_30_34",
            "TBDeathsHIVneg_35_39",
            "TBDeathsHIVneg_40_44",
            "TBDeathsHIVneg_45_49",
            "TBDeathsHIVneg_50_54",
            "TBDeathsHIVneg_55_59",
            "TBDeathsHIVneg_60_64",
            "TBDeathsHIVneg_65_69",
            "TBDeathsHIVneg_70_74",
            "TBDeathsHIVneg_75_79",
            "TBDeathsHIVneg_80",
            "Population_all_0_4",
            "Population_all_5_9",
            "Population_all_10_14",
            "Population_all_15_19",
            "Population_all_20_24",
            "Population_all_25_29",
            "Population_all_30_34",
            "Population_all_35_39",
            "Population_all_40_44",
            "Population_all_45_49",
            "Population_all_50_54",
            "Population_all_55_59",
            "Population_all_60_64",
            "Population_all_65_69",
            "Population_all_70_74",
            "Population_all_75_79",
            "Population_all_80",
            "YLDs",
            "YLDs_HIVn",

        ]].fillna(0)

        # Then put GP back into df
        xlsx_df = pd.concat([xlsx_df, df_gp], axis=0)

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
                "vacc_number": "vaccine_central",
                "vacc_costs": "costvx_central",
                "Costs": "cost_central",
            }
        )

        # Remove rows with NAN for country
        xlsx_df = xlsx_df[xlsx_df['country'].notna()]

        # Remove PF_05a scenario
        xlsx_df = xlsx_df.drop(xlsx_df[xlsx_df.scenario_descriptor =="PF_05a"].index)

        # Clean up funding fraction and PF scenario
        if check==1:
            xlsx_df['funding_fraction'] = xlsx_df['scenario_descriptor'].str.extract('PF_(\d+)$').fillna(
                '')  # Puts the funding scenario number in a new column called funding fraction
            xlsx_df['funding_fraction'] = xlsx_df['funding_fraction'].replace('',
                                                                    1)  # Where there is no funding fraction, set it to 1
            xlsx_df.loc[xlsx_df['scenario_descriptor'].str.contains('PF'), 'scenario_descriptor'] = 'PF'  # removes "_"


        # First get the sum over 2027, 2028 and 2029 of cost by scenario
        if check ==0:
            xlsx_df['new_column'] = \
            xlsx_df[(xlsx_df['year'] < 2030) & (xlsx_df['year'] > 2026)].groupby(['scenario_descriptor', 'country'])[
                'cost_central'].transform('sum')
            xlsx_df['new_column'] = xlsx_df.groupby(['scenario_descriptor', 'country'])['new_column'].transform(
                lambda v: v.ffill()) # forwardfill
            xlsx_df['new_column'] = xlsx_df.groupby(['scenario_descriptor', 'country'])['new_column'].transform(
                lambda v: v.bfill()) # backfill

            # Clean up PF scenario
            xlsx_df['funding_fraction'] = xlsx_df['scenario_descriptor'].str.extract('PF_(\d+)$').fillna(
                '')  # Puts the funding scenario number in a new column called funding fraction
            xlsx_df['funding_fraction'] = xlsx_df['funding_fraction'].replace('',
                                                                    1)  # Where there is no funding fraction, set it to 1
            xlsx_df.loc[xlsx_df['scenario_descriptor'].str.contains('PF'), 'scenario_descriptor'] = 'PF'  # removes "_"

        # Remove cost for non-PF scenarios
        xlsx_df.loc[(xlsx_df['scenario_descriptor'] != 'PF'), 'new_column'] = 0

        # Get max from PF scenario
        xlsx_df['max_cost'] = xlsx_df.groupby(['scenario_descriptor', 'country'])[
            'new_column'].transform('max')
        xlsx_df['funding_fraction'] = xlsx_df['new_column'] / xlsx_df['max_cost']

        # Drop temporary columns
        xlsx_df = xlsx_df.drop(columns=['new_column', 'max_cost'])

        # Now replace missing funding fractions with 1
        xlsx_df['funding_fraction'] = xlsx_df['funding_fraction'].fillna(1)  # Where there is no funding fraction, set it to 1

        # Finally remove duplicates
        xlsx_df = xlsx_df.drop_duplicates()

        # Duplicate indicators that do not have LB and UB to give low and high columns and remove duplicates
        xlsx_df["population_low"] = xlsx_df["Population"]
        xlsx_df["population_central"] = xlsx_df["Population"]
        xlsx_df["population_high"] = xlsx_df["Population"]
        xlsx_df = xlsx_df.drop(columns=["Population"])

        xlsx_df["cases0to4_low"] = xlsx_df["NewCases_0_4"]
        xlsx_df["cases0to4_central"] = xlsx_df["NewCases_0_4"]
        xlsx_df["cases0to4_high"] = xlsx_df["NewCases_0_4"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_0_4"])

        xlsx_df["cases5to9_low"] = xlsx_df["NewCases_5_9"]
        xlsx_df["cases5to9_central"] = xlsx_df["NewCases_5_9"]
        xlsx_df["cases5to9_high"] = xlsx_df["NewCases_5_9"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_5_9"])

        xlsx_df["cases10to14_low"] = xlsx_df["NewCases_10_14"]
        xlsx_df["cases10to14_central"] = xlsx_df["NewCases_10_14"]
        xlsx_df["cases10to14_high"] = xlsx_df["NewCases_10_14"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_10_14"])

        xlsx_df["cases15to19_low"] = xlsx_df["NewCases_15_19"]
        xlsx_df["cases15to19_central"] = xlsx_df["NewCases_15_19"]
        xlsx_df["cases15to19_high"] = xlsx_df["NewCases_15_19"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_15_19"])

        xlsx_df["cases20to24_low"] = xlsx_df["NewCases_20_24"]
        xlsx_df["cases20to24_central"] = xlsx_df["NewCases_20_24"]
        xlsx_df["cases20to24_high"] = xlsx_df["NewCases_20_24"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_20_24"])

        xlsx_df["cases25to29_low"] = xlsx_df["NewCases_25_29"]
        xlsx_df["cases25to29_central"] = xlsx_df["NewCases_25_29"]
        xlsx_df["cases25to29_high"] = xlsx_df["NewCases_25_29"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_25_29"])

        xlsx_df["cases30to34_low"] = xlsx_df["NewCases_30_34"]
        xlsx_df["cases30to34_central"] = xlsx_df["NewCases_30_34"]
        xlsx_df["cases30to34_high"] = xlsx_df["NewCases_30_34"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_30_34"])

        xlsx_df["cases35to39_low"] = xlsx_df["NewCases_35_39"]
        xlsx_df["cases35to39_central"] = xlsx_df["NewCases_35_39"]
        xlsx_df["cases35to39_high"] = xlsx_df["NewCases_35_39"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_35_39"])

        xlsx_df["cases40to44_low"] = xlsx_df["NewCases_40_44"]
        xlsx_df["cases40to44_central"] = xlsx_df["NewCases_40_44"]
        xlsx_df["cases40to44_high"] = xlsx_df["NewCases_40_44"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_40_44"])

        xlsx_df["cases45to49_low"] = xlsx_df["NewCases_45_49"]
        xlsx_df["cases45to49_central"] = xlsx_df["NewCases_45_49"]
        xlsx_df["cases45to49_high"] = xlsx_df["NewCases_45_49"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_45_49"])

        xlsx_df["cases50to54_low"] = xlsx_df["NewCases_50_54"]
        xlsx_df["cases50to54_central"] = xlsx_df["NewCases_50_54"]
        xlsx_df["cases50to54_high"] = xlsx_df["NewCases_50_54"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_50_54"])

        xlsx_df["cases55to59_low"] = xlsx_df["NewCases_55_59"]
        xlsx_df["cases55to59_central"] = xlsx_df["NewCases_55_59"]
        xlsx_df["cases55to59_high"] = xlsx_df["NewCases_55_59"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_55_59"])

        xlsx_df["cases60to64_low"] = xlsx_df["NewCases_60_64"]
        xlsx_df["cases60to64_central"] = xlsx_df["NewCases_60_64"]
        xlsx_df["cases60to64_high"] = xlsx_df["NewCases_60_64"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_60_64"])

        xlsx_df["cases65to69_low"] = xlsx_df["NewCases_65_69"]
        xlsx_df["cases65to69_central"] = xlsx_df["NewCases_65_69"]
        xlsx_df["cases65to69_high"] = xlsx_df["NewCases_65_69"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_65_69"])

        xlsx_df["cases70to74_low"] = xlsx_df["NewCases_70_74"]
        xlsx_df["cases70to74_central"] = xlsx_df["NewCases_70_74"]
        xlsx_df["cases70to74_high"] = xlsx_df["NewCases_70_74"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_70_74"])

        xlsx_df["cases75to79_low"] = xlsx_df["NewCases_75_79"]
        xlsx_df["cases75to79_central"] = xlsx_df["NewCases_75_79"]
        xlsx_df["cases75to79_high"] = xlsx_df["NewCases_75_79"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_75_79"])

        xlsx_df["cases80_low"] = xlsx_df["NewCases_80"]
        xlsx_df["cases80_central"] = xlsx_df["NewCases_80"]
        xlsx_df["cases80_high"] = xlsx_df["NewCases_80"]
        xlsx_df = xlsx_df.drop(columns=["NewCases_80"])

        xlsx_df["deaths0to4_low"] = xlsx_df["TBDeathsAll_0_4"]
        xlsx_df["deaths0to4_central"] = xlsx_df["TBDeathsAll_0_4"]
        xlsx_df["deaths0to4_high"] = xlsx_df["TBDeathsAll_0_4"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_0_4"])

        xlsx_df["deaths5to9_low"] = xlsx_df["TBDeathsAll_5_9"]
        xlsx_df["deaths5to9_central"] = xlsx_df["TBDeathsAll_5_9"]
        xlsx_df["deaths5to9_high"] = xlsx_df["TBDeathsAll_5_9"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_5_9"])

        xlsx_df["deaths10to14_low"] = xlsx_df["TBDeathsAll_10_14"]
        xlsx_df["deaths10to14_central"] = xlsx_df["TBDeathsAll_10_14"]
        xlsx_df["deaths10to14_high"] = xlsx_df["TBDeathsAll_10_14"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_10_14"])

        xlsx_df["deaths15to19_low"] = xlsx_df["TBDeathsAll_15_19"]
        xlsx_df["deaths15to19_central"] = xlsx_df["TBDeathsAll_15_19"]
        xlsx_df["deaths15to19_high"] = xlsx_df["TBDeathsAll_15_19"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_15_19"])

        xlsx_df["deaths20to24_low"] = xlsx_df["TBDeathsAll_20_24"]
        xlsx_df["deaths20to24_central"] = xlsx_df["TBDeathsAll_20_24"]
        xlsx_df["deaths20to24_high"] = xlsx_df["TBDeathsAll_20_24"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_20_24"])

        xlsx_df["deaths25to29_low"] = xlsx_df["TBDeathsAll_25_29"]
        xlsx_df["deaths25to29_central"] = xlsx_df["TBDeathsAll_25_29"]
        xlsx_df["deaths25to29_high"] = xlsx_df["TBDeathsAll_25_29"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_25_29"])

        xlsx_df["deaths30to34_low"] = xlsx_df["TBDeathsAll_30_34"]
        xlsx_df["deaths30to34_central"] = xlsx_df["TBDeathsAll_30_34"]
        xlsx_df["deaths30to34_high"] = xlsx_df["TBDeathsAll_30_34"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_30_34"])

        xlsx_df["deaths35to39_low"] = xlsx_df["TBDeathsAll_35_39"]
        xlsx_df["deaths35to39_central"] = xlsx_df["TBDeathsAll_35_39"]
        xlsx_df["deaths35to39_high"] = xlsx_df["TBDeathsAll_35_39"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_35_39"])

        xlsx_df["deaths40to44_low"] = xlsx_df["TBDeathsAll_40_44"]
        xlsx_df["deaths40to44_central"] = xlsx_df["TBDeathsAll_40_44"]
        xlsx_df["deaths40to44_high"] = xlsx_df["TBDeathsAll_40_44"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_40_44"])

        xlsx_df["deaths45to49_low"] = xlsx_df["TBDeathsAll_45_49"]
        xlsx_df["deaths45to49_central"] = xlsx_df["TBDeathsAll_45_49"]
        xlsx_df["deaths45to49_high"] = xlsx_df["TBDeathsAll_45_49"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_45_49"])

        xlsx_df["deaths50to54_low"] = xlsx_df["TBDeathsAll_50_54"]
        xlsx_df["deaths50to54_central"] = xlsx_df["TBDeathsAll_50_54"]
        xlsx_df["deaths50to54_high"] = xlsx_df["TBDeathsAll_50_54"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_50_54"])

        xlsx_df["deaths55to59_low"] = xlsx_df["TBDeathsAll_55_59"]
        xlsx_df["deaths55to59_central"] = xlsx_df["TBDeathsAll_55_59"]
        xlsx_df["deaths55to59_high"] = xlsx_df["TBDeathsAll_55_59"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_55_59"])

        xlsx_df["deaths60to64_low"] = xlsx_df["TBDeathsAll_60_64"]
        xlsx_df["deaths60to64_central"] = xlsx_df["TBDeathsAll_60_64"]
        xlsx_df["deaths60to64_high"] = xlsx_df["TBDeathsAll_60_64"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_60_64"])

        xlsx_df["deaths65to69_low"] = xlsx_df["TBDeathsAll_65_69"]
        xlsx_df["deaths65to69_central"] = xlsx_df["TBDeathsAll_65_69"]
        xlsx_df["deaths65to69_high"] = xlsx_df["TBDeathsAll_65_69"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_65_69"])

        xlsx_df["deaths70to74_low"] = xlsx_df["TBDeathsAll_70_74"]
        xlsx_df["deaths70to74_central"] = xlsx_df["TBDeathsAll_70_74"]
        xlsx_df["deaths70to74_high"] = xlsx_df["TBDeathsAll_70_74"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_70_74"])

        xlsx_df["deaths75to79_low"] = xlsx_df["TBDeathsAll_75_79"]
        xlsx_df["deaths75to79_central"] = xlsx_df["TBDeathsAll_75_79"]
        xlsx_df["deaths75to79_high"] = xlsx_df["TBDeathsAll_75_79"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_75_79"])

        xlsx_df["deaths80_low"] = xlsx_df["TBDeathsAll_80"]
        xlsx_df["deaths80_central"] = xlsx_df["TBDeathsAll_80"]
        xlsx_df["deaths80_high"] = xlsx_df["TBDeathsAll_80"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsAll_80"])

        xlsx_df["deathshivneg0to4_low"] = xlsx_df["TBDeathsHIVneg_0_4"]
        xlsx_df["deathshivneg0to4_central"] = xlsx_df["TBDeathsHIVneg_0_4"]
        xlsx_df["deathshivneg0to4_high"] = xlsx_df["TBDeathsHIVneg_0_4"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_0_4"])

        xlsx_df["deathshivneg5to9_low"] = xlsx_df["TBDeathsHIVneg_5_9"]
        xlsx_df["deathshivneg5to9_central"] = xlsx_df["TBDeathsHIVneg_5_9"]
        xlsx_df["deathshivneg5to9_high"] = xlsx_df["TBDeathsHIVneg_5_9"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_5_9"])

        xlsx_df["deathshivneg10to14_low"] = xlsx_df["TBDeathsHIVneg_10_14"]
        xlsx_df["deathshivneg10to14_central"] = xlsx_df["TBDeathsHIVneg_10_14"]
        xlsx_df["deathshivneg10to14_high"] = xlsx_df["TBDeathsHIVneg_10_14"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_10_14"])

        xlsx_df["deathshivneg15to19_low"] = xlsx_df["TBDeathsHIVneg_15_19"]
        xlsx_df["deathshivneg15to19_central"] = xlsx_df["TBDeathsHIVneg_15_19"]
        xlsx_df["deathshivneg15to19_high"] = xlsx_df["TBDeathsHIVneg_15_19"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_15_19"])

        xlsx_df["deathshivneg20to24_low"] = xlsx_df["TBDeathsHIVneg_20_24"]
        xlsx_df["deathshivneg20to24_central"] = xlsx_df["TBDeathsHIVneg_20_24"]
        xlsx_df["deathshivneg20to24_high"] = xlsx_df["TBDeathsHIVneg_20_24"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_20_24"])

        xlsx_df["deathshivneg25to29_low"] = xlsx_df["TBDeathsHIVneg_25_29"]
        xlsx_df["deathshivneg25to29_central"] = xlsx_df["TBDeathsHIVneg_25_29"]
        xlsx_df["deathshivneg25to29_high"] = xlsx_df["TBDeathsHIVneg_25_29"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_25_29"])

        xlsx_df["deathshivneg30to34_low"] = xlsx_df["TBDeathsHIVneg_30_34"]
        xlsx_df["deathshivneg30to34_central"] = xlsx_df["TBDeathsHIVneg_30_34"]
        xlsx_df["deathshivneg30to34_high"] = xlsx_df["TBDeathsHIVneg_30_34"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_30_34"])

        xlsx_df["deathshivneg35to39_low"] = xlsx_df["TBDeathsHIVneg_35_39"]
        xlsx_df["deathshivneg35to39_central"] = xlsx_df["TBDeathsHIVneg_35_39"]
        xlsx_df["deathshivneg35to39_high"] = xlsx_df["TBDeathsHIVneg_35_39"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_35_39"])

        xlsx_df["deathshivneg40to44_low"] = xlsx_df["TBDeathsHIVneg_40_44"]
        xlsx_df["deathshivneg40to44_central"] = xlsx_df["TBDeathsHIVneg_40_44"]
        xlsx_df["deathshivneg40to44_high"] = xlsx_df["TBDeathsHIVneg_40_44"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_40_44"])

        xlsx_df["deathshivneg45to49_low"] = xlsx_df["TBDeathsHIVneg_45_49"]
        xlsx_df["deathshivneg45to49_central"] = xlsx_df["TBDeathsHIVneg_45_49"]
        xlsx_df["deathshivneg45to49_high"] = xlsx_df["TBDeathsHIVneg_45_49"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_45_49"])

        xlsx_df["deathshivneg50to54_low"] = xlsx_df["TBDeathsHIVneg_50_54"]
        xlsx_df["deathshivneg50to54_central"] = xlsx_df["TBDeathsHIVneg_50_54"]
        xlsx_df["deathshivneg50to54_high"] = xlsx_df["TBDeathsHIVneg_50_54"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_50_54"])

        xlsx_df["deathshivneg55to59_low"] = xlsx_df["TBDeathsHIVneg_55_59"]
        xlsx_df["deathshivneg55to59_central"] = xlsx_df["TBDeathsHIVneg_55_59"]
        xlsx_df["deathshivneg55to59_high"] = xlsx_df["TBDeathsHIVneg_55_59"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_55_59"])

        xlsx_df["deathshivneg60to64_low"] = xlsx_df["TBDeathsHIVneg_60_64"]
        xlsx_df["deathshivneg60to64_central"] = xlsx_df["TBDeathsHIVneg_60_64"]
        xlsx_df["deathshivneg60to64_high"] = xlsx_df["TBDeathsHIVneg_60_64"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_60_64"])

        xlsx_df["deathshivneg65to69_low"] = xlsx_df["TBDeathsHIVneg_65_69"]
        xlsx_df["deathshivneg65to69_central"] = xlsx_df["TBDeathsHIVneg_65_69"]
        xlsx_df["deathshivneg65to69_high"] = xlsx_df["TBDeathsHIVneg_65_69"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_65_69"])

        xlsx_df["deathshivneg70to74_low"] = xlsx_df["TBDeathsHIVneg_70_74"]
        xlsx_df["deathshivneg70to74_central"] = xlsx_df["TBDeathsHIVneg_70_74"]
        xlsx_df["deathshivneg70to74_high"] = xlsx_df["TBDeathsHIVneg_70_74"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_70_74"])

        xlsx_df["deathshivneg75to79_low"] = xlsx_df["TBDeathsHIVneg_75_79"]
        xlsx_df["deathshivneg75to79_central"] = xlsx_df["TBDeathsHIVneg_75_79"]
        xlsx_df["deathshivneg75to79_high"] = xlsx_df["TBDeathsHIVneg_75_79"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_75_79"])

        xlsx_df["deathshivneg80_low"] = xlsx_df["TBDeathsHIVneg_80"]
        xlsx_df["deathshivneg80_central"] = xlsx_df["TBDeathsHIVneg_80"]
        xlsx_df["deathshivneg80_high"] = xlsx_df["TBDeathsHIVneg_80"]
        xlsx_df = xlsx_df.drop(columns=["TBDeathsHIVneg_80"])

        xlsx_df["population0to4_low"] = xlsx_df["Population_all_0_4"]
        xlsx_df["population0to4_central"] = xlsx_df["Population_all_0_4"]
        xlsx_df["population0to4_high"] = xlsx_df["Population_all_0_4"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_0_4"])

        xlsx_df["population5to9_low"] = xlsx_df["Population_all_5_9"]
        xlsx_df["population5to9_central"] = xlsx_df["Population_all_5_9"]
        xlsx_df["population5to9_high"] = xlsx_df["Population_all_5_9"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_5_9"])

        xlsx_df["population10to14_low"] = xlsx_df["Population_all_10_14"]
        xlsx_df["population10to14_central"] = xlsx_df["Population_all_10_14"]
        xlsx_df["population10to14_high"] = xlsx_df["Population_all_10_14"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_10_14"])

        xlsx_df["population15to19_low"] = xlsx_df["Population_all_15_19"]
        xlsx_df["population15to19_central"] = xlsx_df["Population_all_15_19"]
        xlsx_df["population15to19_high"] = xlsx_df["Population_all_15_19"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_15_19"])

        xlsx_df["population20to24_low"] = xlsx_df["Population_all_20_24"]
        xlsx_df["population20to24_central"] = xlsx_df["Population_all_20_24"]
        xlsx_df["population20to24_high"] = xlsx_df["Population_all_20_24"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_20_24"])

        xlsx_df["population25to29_low"] = xlsx_df["Population_all_25_29"]
        xlsx_df["population25to29_central"] = xlsx_df["Population_all_25_29"]
        xlsx_df["population25to29_high"] = xlsx_df["Population_all_25_29"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_25_29"])

        xlsx_df["population30to34_low"] = xlsx_df["Population_all_30_34"]
        xlsx_df["population30to34_central"] = xlsx_df["Population_all_30_34"]
        xlsx_df["population30to34_high"] = xlsx_df["Population_all_30_34"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_30_34"])

        xlsx_df["population35to39_low"] = xlsx_df["Population_all_35_39"]
        xlsx_df["population35to39_central"] = xlsx_df["Population_all_35_39"]
        xlsx_df["population35to39_high"] = xlsx_df["Population_all_35_39"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_35_39"])

        xlsx_df["population40to44_low"] = xlsx_df["Population_all_40_44"]
        xlsx_df["population40to44_central"] = xlsx_df["Population_all_40_44"]
        xlsx_df["population40to44_high"] = xlsx_df["Population_all_40_44"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_40_44"])

        xlsx_df["population45to49_low"] = xlsx_df["Population_all_45_49"]
        xlsx_df["population45to49_central"] = xlsx_df["Population_all_45_49"]
        xlsx_df["population45to49_high"] = xlsx_df["Population_all_45_49"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_45_49"])

        xlsx_df["population50to54_low"] = xlsx_df["Population_all_50_54"]
        xlsx_df["population50to54_central"] = xlsx_df["Population_all_50_54"]
        xlsx_df["population50to54_high"] = xlsx_df["Population_all_50_54"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_50_54"])

        xlsx_df["population55to59_low"] = xlsx_df["Population_all_55_59"]
        xlsx_df["population55to59_central"] = xlsx_df["Population_all_55_59"]
        xlsx_df["population55to59_high"] = xlsx_df["Population_all_55_59"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_55_59"])

        xlsx_df["population60to64_low"] = xlsx_df["Population_all_60_64"]
        xlsx_df["population60to64_central"] = xlsx_df["Population_all_60_64"]
        xlsx_df["population60to64_high"] = xlsx_df["Population_all_60_64"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_60_64"])

        xlsx_df["population65to69_low"] = xlsx_df["Population_all_65_69"]
        xlsx_df["population65to69_central"] = xlsx_df["Population_all_65_69"]
        xlsx_df["population65to69_high"] = xlsx_df["Population_all_65_69"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_65_69"])

        xlsx_df["population70to74_low"] = xlsx_df["Population_all_70_74"]
        xlsx_df["population70to74_central"] = xlsx_df["Population_all_70_74"]
        xlsx_df["population70to74_high"] = xlsx_df["Population_all_70_74"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_70_74"])

        xlsx_df["population75to79_low"] = xlsx_df["Population_all_75_79"]
        xlsx_df["population75to79_central"] = xlsx_df["Population_all_75_79"]
        xlsx_df["population75to79_high"] = xlsx_df["Population_all_75_79"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_75_79"])

        xlsx_df["population80_low"] = xlsx_df["Population_all_80"]
        xlsx_df["population80_central"] = xlsx_df["Population_all_80"]
        xlsx_df["population80_high"] = xlsx_df["Population_all_80"]
        xlsx_df = xlsx_df.drop(columns=["Population_all_80"])

        xlsx_df["yld_low"] = xlsx_df["YLDs"]
        xlsx_df["yld_central"] = xlsx_df["YLDs"]
        xlsx_df["yld_high"] = xlsx_df["YLDs"]
        xlsx_df = xlsx_df.drop(columns=["YLDs"])

        xlsx_df["yldhivneg_low"] = xlsx_df["YLDs_HIVn"]
        xlsx_df["yldhivneg_central"] = xlsx_df["YLDs_HIVn"]
        xlsx_df["yldhivneg_high"] = xlsx_df["YLDs_HIVn"]
        xlsx_df = xlsx_df.drop(columns=["YLDs_HIVn"])

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

        xlsx_df["costvx_low"] = xlsx_df["costvx_central"]
        xlsx_df["costvx_high"] = xlsx_df["costvx_central"]

        xlsx_df["vaccine_low"] = xlsx_df["vaccine_central"]
        xlsx_df["vaccine_high"] = xlsx_df["vaccine_central"]

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
        melted = melted[melted['funding_fraction'].notnull()].copy()
        melted['funding_fraction'] = melted['funding_fraction'].astype(float)

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
class PartnerDataTb(TBMixin, PartnerData):
    """This is the File Handler for the HIV partner data."""

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
        start_year = self.parameters.get("HISTORIC_FIRST_YEAR")
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

        # Load 'Sheet1' from the Excel workbook
        csv_df = self._load_sheet(file)

        # Only keep columns of immediate interest.
        csv_df = csv_df[
            [
                "Year",
                "ISO3",
                "tb_cases_n_pip",
                "tb_deaths_n_pip",
                "tb_deathsnohiv_n_pip",
                "tb_pop_n_pip",
            ]
        ]

        # Do some renaming to make things easier
        csv_df = csv_df.rename(
            columns={
                "ISO3": "country",
                "Year": 'year',
                "tb_deaths_n_pip": "deaths",
                "tb_deathsnohiv_n_pip": "deathshivneg",
                "tb_cases_n_pip": "cases",
                "tb_pop_n_pip": "population",
            }
        )

        # Generate incidence and mortality
        csv_df["incidence"] = csv_df["cases"] / csv_df["population"]
        csv_df["mortality"] = csv_df["deaths"] / csv_df["population"]

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


class GpTb(TBMixin, Gp):
    """Hold the GP for TB. It has to construct it from a file (fixed_gp) that shows the trend over time and
    the partner data and some model results."""

    def _build_df(
        self,
        fixed_gp: FixedGp,
        model_results: ModelResults,
        partner_data: PartnerData,
        parameters: Parameters,
    ) -> pd.DataFrame:

        # Gather the parameters for this function
        gp_start_year = parameters.get(self.disease_name).get("GP_START_YEAR")
        first_year = parameters.get("START_YEAR")
        last_year = parameters.get("END_YEAR")

        tb_countries = parameters.get_portfolio_countries_for(self.disease_name)
        tb_m_countries = parameters.get_modelled_countries_for(self.disease_name)

        # Extract relevant partner and model data
        pop_model = (
            model_results.df.loc[
                ("GP", slice(None), tb_m_countries, slice(None), "population")
            ]["central"]
            .groupby(axis=0, level=3)
            .sum()
        )
        pop_partner = (
            partner_data.df.loc[("PF", tb_countries, slice(None), "population")][
                "central"
            ]
            .groupby(axis=0, level=2)
            .sum()
        )

        # Get population estimates from first model year to generate ratio
        pop_m_firstyear = (
            model_results.df.loc[
                ("GP", slice(None), tb_m_countries, first_year+1, "population")
            ]["central"]
            .groupby(axis=0, level=3)
            .sum()
        )
        pop_firstyear = partner_data.df.loc[
            ("PF", tb_countries, first_year, "population")
        ].sum()["central"]
        ratio = pop_m_firstyear / pop_firstyear

        # Use GP baseline year partner data to get the cases/deaths/incidence/mortality estimates at baseline
        cases_baseyear = partner_data.df.loc[
            ("PF", tb_countries, gp_start_year, "cases")
        ].sum()["central"]
        deaths_baseyear = partner_data.df.loc[
            ("PF", tb_countries, gp_start_year, "deaths")
        ].sum()["central"]
        deathshivneg_baseyear = partner_data.df.loc[
            ("PF", tb_countries, gp_start_year, "deathshivneg")
        ].sum()["central"]
        pop_baseyear = partner_data.df.loc[
            ("PF", tb_countries, gp_start_year, "population")
        ].sum()["central"]
        incidence_baseyear = cases_baseyear / pop_baseyear
        mortality_rate_2015 = deaths_baseyear / pop_baseyear

        # Make a time series of population estimates
        pop_glued = pd.concat(
            [
                pop_partner.loc[
                    pop_partner.index.isin(
                        [
                            gp_start_year,
                            gp_start_year + 1,
                            gp_start_year + 2,
                            gp_start_year + 3,
                            gp_start_year + 4,
                            gp_start_year + 5,
                            gp_start_year + 6,
                            gp_start_year + 7,
                        ]
                    )
                ],
                pop_model.loc[pop_model.index.isin(range(first_year, last_year + 1))]
                / ratio.values,
            ]
        )

        # Convert reduction and get gp time series
        relative_incidence = 1.0 - fixed_gp.df["incidence_reduction"]
        gp_incidence = relative_incidence * incidence_baseyear
        gp_cases = gp_incidence * pop_glued
        relative_deaths = 1.0 - fixed_gp.df["death_rate_reduction"]
        gp_deaths = relative_deaths * deaths_baseyear
        gp_deathshivneg = relative_deaths * deathshivneg_baseyear
        gp_mortality_rate = gp_deaths / pop_glued
        gp_mortality_rate_hivneg = gp_deathshivneg / pop_glued

        # Put it all together into a df
        df = pd.DataFrame(
            {
                "incidence": gp_incidence,
                "mortality": gp_mortality_rate,
                "mortalityhivneg": gp_mortality_rate_hivneg,
                "cases": gp_cases,
                "deaths": gp_deaths,
                "deathshivneg": gp_deathshivneg,
            }
        )

        # Return in expected format
        df.columns.name = "indicator"
        df.index.name = "year"
        return pd.DataFrame({"central": df.stack()})
