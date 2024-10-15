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
    PFInputData,
    PartnerData,
)
from tgftools.utils import (
    get_files_with_extension,
)

""" START HERE FOR HIV: This file sets up everything needed to run HIV related code, including reading in the 
relevant files, cleans up the data in these files (harmonizing naming convention, generate needed extra variables 
e.g. HIV-negative population estimates, filters out variables that are not needed), puts them in the format defined for
the database format. 

The database format is: 
1) scenario_descriptor: contains a shorthand for scenario names. The parameters.toml file maps the short-hand to definition
2) funding fraction: contains the funding fraction as expressed by the numbers starting at "01". They do not refer to 
   % of GP funding need but as increments of increasing services/availability of services. 
3) country: holds iso3 code for a country
4) year: contains year information
5) indicator: contains the variable names (short-hand). The parameters.toml file maps the short-hand to definition
6) low, central and high: contains the value for the lower bound, central and upper bound of a given variable. Where 
   LB and UB are not available these should be set to be the same as the "central" value.  

 This following files are read in in this script: 
 1) The HIV model results shared by John
 2) The PF input data. These were prepared by TGF and shared with modellers as input data to the model
 3) The UNAIDS partner data as prepared by the TGF. These contain the following variables: year, iso3, new infections, 
    deaths, population estimates (by HIV status) (for a given year). The partner data should contain data for each of 
    these variable for each country eligible for GF funding for 2000 to latest year. 

 The above files are saved in the file structure described below. 
 CAUTION: failing to follow the file structure may throw up errors. 
 File structure: 
 1) Main project folder: "IC8"
 2) model results should be located in "/modelling_outputs"
 3) PF input daa should be saved under "/pf"
 4) UNAIDS partner data should be saved under "/partner"
 
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


class HIVMixin:
    """Base class used as a `mix-in` that allows any inheriting class to have a property `disease_name` that returns
    the disease name."""

    @property
    def disease_name(self):
        return 'HIV'


# Load the model result file(s)
class ModelResultsHiv(HIVMixin, ModelResults):
    """This is the File Handler for the HIV modelling output."""

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

        # Filter out any countries that we do not need
        expected_countries = self.parameters.get_modelled_countries_for(self.disease_name)

        scenario_names = (self.parameters.get_scenarios().index.to_list() +
                          self.parameters.get_counterfactuals().index.to_list()
                          )
        concatenated_dfs = concatenated_dfs.loc[
            (scenario_names, slice(None), expected_countries, slice(None), slice(None))
        ]

        # Make funding numbers into fractions
        concatenated_dfs = concatenated_dfs.reset_index()
        concatenated_dfs['funding_fraction'] = concatenated_dfs['funding_fraction']-2
        concatenated_dfs.loc[concatenated_dfs.funding_fraction == -1, 'funding_fraction'] = 1 # Because now 1s will be -1s

        concatenated_dfs['new_column'] = concatenated_dfs.groupby(['scenario_descriptor', 'country'])[
            'funding_fraction'].transform('max')
        concatenated_dfs['funding_fraction'] = concatenated_dfs['funding_fraction'] / concatenated_dfs['new_column']
        concatenated_dfs = concatenated_dfs.round({'funding_fraction': 3})
        concatenated_dfs.loc[
            concatenated_dfs.funding_fraction == 0.091, 'funding_fraction'] = 0.0  # otherwise we have duplicates of the 0.5 funding fraction
        concatenated_dfs.loc[
            concatenated_dfs.funding_fraction == 0.182, 'funding_fraction'] = 0.1  # otherwise we have duplicates of the 0.5 funding fraction
        concatenated_dfs.loc[
            concatenated_dfs.funding_fraction == 0.273, 'funding_fraction'] = 0.2  # otherwise we have duplicates of the 0.5 funding fraction
        concatenated_dfs.loc[
            concatenated_dfs.funding_fraction == 0.364, 'funding_fraction'] = 0.3  # otherwise we have duplicates of the 0.5 funding fraction
        concatenated_dfs.loc[concatenated_dfs.funding_fraction == 0.455, 'funding_fraction'] = 0.4  # otherwise we have duplicates of the 0.5 funding fraction
        concatenated_dfs = concatenated_dfs.round({'funding_fraction': 1})
        concatenated_dfs = concatenated_dfs.drop('new_column', axis=1)

        df_duplicates = concatenated_dfs[concatenated_dfs.duplicated()]

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
        """Returns formatted pd.DataFrame from the Excel file provided. The returned dataframe is specific to one
        country, and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load 'Sheet1' from the Excel workbook
        csv_df = self._load_sheet(file)

        # Only keep columns of immediate interest:
        csv_df = csv_df[
            [
                "iso3",
                "scenario",
                "year",
                "New_infections",
                "New_infections_LB",
                "New_infections_UB",
                "AIDS_deaths_total",
                "AIDS_deaths_total_LB",
                "AIDS_deaths_total_UB",
                "PLHIV",
                "PLHIV_LB",
                "PLHIV_UB",
                "Population",
                "Population_LB",
                "Population_UB",
                "ART_total",
                "ART_total_LB",
                "ART_total_UB",
                "ART_cov",
                'Deaths_0_4',
                'Deaths_5_9',
                'Deaths_10_14',
                'Deaths_15_19',
                'Deaths_20_24',
                'Deaths_25_29',
                'Deaths_30_34',
                'Deaths_35_39',
                'Deaths_40_44',
                'Deaths_45_49',
                'Deaths_50_54',
                'Deaths_55_59',
                'Deaths_60_64',
                'Deaths_65_69',
                'Deaths_70_74',
                'Deaths_75_79',
                'Deaths_80',
                "Adult_ART",
                'Ped_ART',
                'notx_15plus_more500',
                'notx_15plus_350_500',
                'notx_15plus_250_350',
                'notx_15plus_200_250',
                'notx_15plus_100_200',
                'notx_15plus_50_100',
                'notx_15plus_less50',
                'notx_5_14_more1000',
                'notx_5_14_750_999',
                'notx_5_14_500_749',
                'notx_5_14_350_499',
                'notx_5_14_200_349',
                'notx_5_14_less200',
                'notx_less5_more30',
                'notx_less5_26_30',
                'notx_less5_21_25',
                'notx_less5_16_20',
                'notx_less5_11_15',
                'notx_less5_5_10',
                'notx_less5_less5',
                "PMTCT_num",
                "PMTCT_num_LB",
                "PMTCT_num_UB",
                "PMTCT_need",
                "PMTCT_need_LB",
                "PMTCT_need_UB",
                "PMTCT_cov",
                "FSW_cov",
                "MSM_cov",
                "PWID_cov",
                "PrEP",
                "PrEP_LB",
                "PrEP_UB",
                "FSW_PrEP",
                "FSW_PrEP_LB",
                "FSW_PrEP_UB",
                "MSM_PrEP",
                "MSM_PrEP_LB",
                "MSM_PrEP_UB",
                "PWID_PrEP",
                "PWID_PrEP_LB",
                "PWID_PrEP_UB",
                "OST",
                "OST_LB",
                "OST_UB",
                "KOS",
                "KOS_LB",
                "KOS_UB",
                "VS",
                "VS_LB",
                "VS_UB",
                "VMMC_n",
                "VMMC_n_LB",
                "VMMC_n_UB",
                "Total_cost",
            ]
        ]

        # Before going to the rest of the code need to do some cleaning to GP scenario, to prevent errors in this script
        df_gp = csv_df[csv_df.scenario == "GP"]
        csv_df = csv_df[csv_df.scenario != "GP"]

        # 1. Add copy central into lb and ub columns for needed variables
        df_gp['New_infections_LB'] = df_gp['New_infections']
        df_gp['New_infections_UB'] = df_gp['New_infections']
        df_gp['AIDS_deaths_total_LB'] = df_gp['AIDS_deaths_total']
        df_gp['AIDS_deaths_total_UB'] = df_gp['AIDS_deaths_total']
        df_gp['PLHIV_LB'] = df_gp['PLHIV']
        df_gp['PLHIV_UB'] = df_gp['PLHIV']
        df_gp['Population_LB'] = df_gp['Population']
        df_gp['Population_UB'] = df_gp['Population']
        df_gp['ART_total_LB'] = df_gp['ART_total']
        df_gp['ART_total_UB'] = df_gp['ART_total']

        # 2. Replace nan with zeros
        df_gp[[
            "ART_cov",
            'Deaths_0_4',
            'Deaths_5_9',
            'Deaths_10_14',
            'Deaths_15_19',
            'Deaths_20_24',
            'Deaths_25_29',
            'Deaths_30_34',
            'Deaths_35_39',
            'Deaths_40_44',
            'Deaths_45_49',
            'Deaths_50_54',
            'Deaths_55_59',
            'Deaths_60_64',
            'Deaths_65_69',
            'Deaths_70_74',
            'Deaths_75_79',
            'Deaths_80',
            "Adult_ART",
            'Ped_ART',
            'notx_15plus_more500',
            'notx_15plus_350_500',
            'notx_15plus_250_350',
            'notx_15plus_200_250',
            'notx_15plus_100_200',
            'notx_15plus_50_100',
            'notx_15plus_less50',
            'notx_5_14_more1000',
            'notx_5_14_750_999',
            'notx_5_14_500_749',
            'notx_5_14_350_499',
            'notx_5_14_200_349',
            'notx_5_14_less200',
            'notx_less5_more30',
            'notx_less5_26_30',
            'notx_less5_21_25',
            'notx_less5_16_20',
            'notx_less5_11_15',
            'notx_less5_5_10',
            'notx_less5_less5',
                "PMTCT_num",
                "PMTCT_num_LB",
                "PMTCT_num_UB",
                "PMTCT_need",
                "PMTCT_need_LB",
                "PMTCT_need_UB",
                "PMTCT_cov",
                "FSW_cov",
                "MSM_cov",
                "PWID_cov",
                "PrEP",
                "PrEP_LB",
                "PrEP_UB",
                "FSW_PrEP",
                "FSW_PrEP_LB",
                "FSW_PrEP_UB",
                "MSM_PrEP",
                "MSM_PrEP_LB",
                "MSM_PrEP_UB",
                "PWID_PrEP",
                "PWID_PrEP_LB",
                "PWID_PrEP_UB",
                "OST",
                "OST_LB",
                "OST_UB",
                "KOS",
                "KOS_LB",
                "KOS_UB",
                "VS",
                "VS_LB",
                "VS_UB",
                "VMMC_n",
                "VMMC_n_LB",
                "VMMC_n_UB",
                "Total_cost",
        ]] = df_gp[[
            "ART_cov",
            'Deaths_0_4',
            'Deaths_5_9',
            'Deaths_10_14',
            'Deaths_15_19',
            'Deaths_20_24',
            'Deaths_25_29',
            'Deaths_30_34',
            'Deaths_35_39',
            'Deaths_40_44',
            'Deaths_45_49',
            'Deaths_50_54',
            'Deaths_55_59',
            'Deaths_60_64',
            'Deaths_65_69',
            'Deaths_70_74',
            'Deaths_75_79',
            'Deaths_80',
            "Adult_ART",
            'Ped_ART',
            'notx_15plus_more500',
            'notx_15plus_350_500',
            'notx_15plus_250_350',
            'notx_15plus_200_250',
            'notx_15plus_100_200',
            'notx_15plus_50_100',
            'notx_15plus_less50',
            'notx_5_14_more1000',
            'notx_5_14_750_999',
            'notx_5_14_500_749',
            'notx_5_14_350_499',
            'notx_5_14_200_349',
            'notx_5_14_less200',
            'notx_less5_more30',
            'notx_less5_26_30',
            'notx_less5_21_25',
            'notx_less5_16_20',
            'notx_less5_11_15',
            'notx_less5_5_10',
            'notx_less5_less5',
            "PMTCT_num",
            "PMTCT_num_LB",
            "PMTCT_num_UB",
            "PMTCT_need",
            "PMTCT_need_LB",
            "PMTCT_need_UB",
            "PMTCT_cov",
            "FSW_cov",
            "MSM_cov",
            "PWID_cov",
            "PrEP",
            "PrEP_LB",
            "PrEP_UB",
            "FSW_PrEP",
            "FSW_PrEP_LB",
            "FSW_PrEP_UB",
            "MSM_PrEP",
            "MSM_PrEP_LB",
            "MSM_PrEP_UB",
            "PWID_PrEP",
            "PWID_PrEP_LB",
            "PWID_PrEP_UB",
            "OST",
            "OST_LB",
            "OST_UB",
            "KOS",
            "KOS_LB",
            "KOS_UB",
            "VS",
            "VS_LB",
            "VS_UB",
            "VMMC_n",
            "VMMC_n_LB",
            "VMMC_n_UB",
            "Total_cost",
        ]].fillna(0)

        # Then put GP back into df
        csv_df = pd.concat([csv_df, df_gp], axis=0)

        # Do some renaming to make things easier
        csv_df = csv_df.rename(
            columns={
                "iso3": "country",
                "scenario": "scenario_descriptor",
                "New_infections": "cases_central",
                "New_infections_LB": "cases_low",
                "New_infections_UB": "cases_high",
                "AIDS_deaths_total": "deaths_central",
                "AIDS_deaths_total_LB": "deaths_low",
                "AIDS_deaths_total_UB": "deaths_high",
                "PLHIV": "plhiv_central",
                "PLHIV_LB": "plhiv_low",
                "PLHIV_UB": "plhiv_high",
                "Population": "population_central",
                "Population_LB": "population_low",
                "Population_UB": "population_high",
                "ART_total": "art_central",
                "ART_total_LB": "art_low",
                "ART_total_UB": "art_high",
                "PMTCT_num": "pmtct_central",
                "PMTCT_num_LB": "pmtct_low",
                "PMTCT_num_UB": "pmtct_high",
                "PMTCT_need": "pmtctneed_central",
                "PMTCT_need_LB": "pmtctneed_low",
                "PMTCT_need_UB": "pmtctneed_high",
                "PrEP": "prep_central",
                "PrEP_LB": "prep_low",
                "PrEP_UB": "prep_high",
                "FSW_PrEP": "fswprep_central",
                "FSW_PrEP_LB": "fswprep_low",
                "FSW_PrEP_UB": "fswprep_high",
                "MSM_PrEP": "msmprep_central",
                "MSM_PrEP_LB": "msmprep_low",
                "MSM_PrEP_UB": "msmprep_high",
                "PWID_PrEP": "pwidprep_central",
                "PWID_PrEP_LB": "pwidprep_low",
                "PWID_PrEP_UB": "pwidprep_high",
                "OST": "ost_central",
                "OST_LB": "ost_low",
                "OST_UB": "ost_high",
                "KOS": "status_central",
                "KOS_LB": "status_low",
                "KOS_UB": "status_high",
                "VS": "vls_central",
                "VS_LB": "vls_low",
                "VS_UB": "vls_high",
                "VMMC_n": "vmmc_central",
                "VMMC_n_LB": "vmmc_low",
                "VMMC_n_UB": "vmmc_high",
            }
        )

        # Clean up scenario names
        csv_df = csv_df.replace('Step1', 'NULL_2022')
        csv_df = csv_df.replace('Step2', 'CC_2022')



        # Clean up funding fraction and PF scenario
        csv_df['funding_fraction'] = csv_df['scenario_descriptor'].str.extract('Step(\d+)$').fillna('') # Puts the funding scenario number in a new column called funding fraction
        csv_df['funding_fraction'] = csv_df['funding_fraction'].replace('', 1) # Where there is no funding fraction, set it to 1
        csv_df.loc[csv_df['scenario_descriptor'].str.contains('Step'), 'scenario_descriptor'] = 'PF' # removes "_"

        # Remove rows without funding fraction results
        csv_df = csv_df[csv_df['plhiv_central'].notna()]

        # Convert funding fraction to number
        csv_df['funding_fraction'] = csv_df['funding_fraction'].astype('float')

        # Duplicate indicators that do not have LB and UB to give low and high columns and remove duplicates
        csv_df["artcoverage_low"] = csv_df["ART_cov"]
        csv_df["artcoverage_central"] = csv_df["ART_cov"]
        csv_df["artcoverage_high"] = csv_df["ART_cov"]
        csv_df = csv_df.drop(columns=["ART_cov"])

        csv_df["deaths0to4_low"] = csv_df["Deaths_0_4"]
        csv_df["deaths0to4_central"] = csv_df["Deaths_0_4"]
        csv_df["deaths0to4_high"] = csv_df["Deaths_0_4"]
        csv_df = csv_df.drop(columns=["Deaths_0_4"])

        csv_df["deaths5to9_low"] = csv_df["Deaths_5_9"]
        csv_df["deaths5to9_central"] = csv_df["Deaths_5_9"]
        csv_df["deaths5to9_high"] = csv_df["Deaths_5_9"]
        csv_df = csv_df.drop(columns=["Deaths_5_9"])

        csv_df["deaths10to14_low"] = csv_df["Deaths_10_14"]
        csv_df["deaths10to14_central"] = csv_df["Deaths_10_14"]
        csv_df["deaths10to14_high"] = csv_df["Deaths_10_14"]
        csv_df = csv_df.drop(columns=["Deaths_10_14"])

        csv_df["deaths15to19_low"] = csv_df["Deaths_15_19"]
        csv_df["deaths15to19_central"] = csv_df["Deaths_15_19"]
        csv_df["deaths15to19_high"] = csv_df["Deaths_15_19"]
        csv_df = csv_df.drop(columns=["Deaths_15_19"])

        csv_df["deaths20to24_low"] = csv_df["Deaths_20_24"]
        csv_df["deaths20to24_central"] = csv_df["Deaths_20_24"]
        csv_df["deaths20to24_high"] = csv_df["Deaths_20_24"]
        csv_df = csv_df.drop(columns=["Deaths_20_24"])

        csv_df["deaths25to29_low"] = csv_df["Deaths_25_29"]
        csv_df["deaths25to29_central"] = csv_df["Deaths_25_29"]
        csv_df["deaths25to29_high"] = csv_df["Deaths_25_29"]
        csv_df = csv_df.drop(columns=["Deaths_25_29"])

        csv_df["deaths30to34_low"] = csv_df["Deaths_30_34"]
        csv_df["deaths30to34_central"] = csv_df["Deaths_30_34"]
        csv_df["deaths30to34_high"] = csv_df["Deaths_30_34"]
        csv_df = csv_df.drop(columns=["Deaths_30_34"])

        csv_df["deaths35to39_low"] = csv_df["Deaths_35_39"]
        csv_df["deaths35to39_central"] = csv_df["Deaths_35_39"]
        csv_df["deaths35to39_high"] = csv_df["Deaths_35_39"]
        csv_df = csv_df.drop(columns=["Deaths_35_39"])

        csv_df["deaths40to44_low"] = csv_df["Deaths_40_44"]
        csv_df["deaths40to44_central"] = csv_df["Deaths_40_44"]
        csv_df["deaths40to44_high"] = csv_df["Deaths_40_44"]
        csv_df = csv_df.drop(columns=["Deaths_40_44"])

        csv_df["deaths45to49_low"] = csv_df["Deaths_45_49"]
        csv_df["deaths45to49_central"] = csv_df["Deaths_45_49"]
        csv_df["deaths45to49_high"] = csv_df["Deaths_45_49"]
        csv_df = csv_df.drop(columns=["Deaths_45_49"])

        csv_df["deaths50to54_low"] = csv_df["Deaths_50_54"]
        csv_df["deaths50to54_central"] = csv_df["Deaths_50_54"]
        csv_df["deaths50to54_high"] = csv_df["Deaths_50_54"]
        csv_df = csv_df.drop(columns=["Deaths_50_54"])

        csv_df["deaths55to59_low"] = csv_df["Deaths_55_59"]
        csv_df["deaths55to59_central"] = csv_df["Deaths_55_59"]
        csv_df["deaths55to59_high"] = csv_df["Deaths_55_59"]
        csv_df = csv_df.drop(columns=["Deaths_55_59"])

        csv_df["deaths60to64_low"] = csv_df["Deaths_60_64"]
        csv_df["deaths60to64_central"] = csv_df["Deaths_60_64"]
        csv_df["deaths60to64_high"] = csv_df["Deaths_60_64"]
        csv_df = csv_df.drop(columns=["Deaths_60_64"])

        csv_df["deaths65to69_low"] = csv_df["Deaths_65_69"]
        csv_df["deaths65to69_central"] = csv_df["Deaths_65_69"]
        csv_df["deaths65to69_high"] = csv_df["Deaths_65_69"]
        csv_df = csv_df.drop(columns=["Deaths_65_69"])

        csv_df["deaths70to74_low"] = csv_df["Deaths_70_74"]
        csv_df["deaths70to74_central"] = csv_df["Deaths_70_74"]
        csv_df["deaths70to74_high"] = csv_df["Deaths_70_74"]
        csv_df = csv_df.drop(columns=["Deaths_70_74"])

        csv_df["deaths75to79_low"] = csv_df["Deaths_75_79"]
        csv_df["deaths75to79_central"] = csv_df["Deaths_75_79"]
        csv_df["deaths75to79_high"] = csv_df["Deaths_75_79"]
        csv_df = csv_df.drop(columns=["Deaths_75_79"])

        csv_df["deaths80_low"] = csv_df["Deaths_80"]
        csv_df["deaths80_central"] = csv_df["Deaths_80"]
        csv_df["deaths80_high"] = csv_df["Deaths_80"]
        csv_df = csv_df.drop(columns=["Deaths_80"])

        csv_df["adultart_low"] = csv_df["Adult_ART"]
        csv_df["adultart_central"] = csv_df["Adult_ART"]
        csv_df["adultart_high"] = csv_df["Adult_ART"]
        csv_df = csv_df.drop(columns=["Adult_ART"])

        csv_df["pedart_low"] = csv_df["Ped_ART"]
        csv_df["pedart_central"] = csv_df["Ped_ART"]
        csv_df["pedart_high"] = csv_df["Ped_ART"]
        csv_df = csv_df.drop(columns=["Ped_ART"])

        csv_df["notx15plusmore500_low"] = csv_df["notx_15plus_more500"]
        csv_df["notx15plusmore500_central"] = csv_df["notx_15plus_more500"]
        csv_df["notx15plusmore500_high"] = csv_df["notx_15plus_more500"]
        csv_df = csv_df.drop(columns=["notx_15plus_more500"])

        csv_df["notx15plus350to500_low"] = csv_df["notx_15plus_350_500"]
        csv_df["notx15plus350to500_central"] = csv_df["notx_15plus_350_500"]
        csv_df["notx15plus350to500_high"] = csv_df["notx_15plus_350_500"]
        csv_df = csv_df.drop(columns=["notx_15plus_350_500"])

        csv_df["notx15plus250to350_low"] = csv_df["notx_15plus_250_350"]
        csv_df["notx15plus250to350_central"] = csv_df["notx_15plus_250_350"]
        csv_df["notx15plus250to350_high"] = csv_df["notx_15plus_250_350"]
        csv_df = csv_df.drop(columns=["notx_15plus_250_350"])

        csv_df["notx15plus200to250_low"] = csv_df["notx_15plus_200_250"]
        csv_df["notx15plus200to250_central"] = csv_df["notx_15plus_200_250"]
        csv_df["notx15plus200to250_high"] = csv_df["notx_15plus_200_250"]
        csv_df = csv_df.drop(columns=["notx_15plus_200_250"])

        csv_df["notx15plus100to200_low"] = csv_df["notx_15plus_100_200"]
        csv_df["notx15plus100to200_central"] = csv_df["notx_15plus_100_200"]
        csv_df["notx15plus100to200_high"] = csv_df["notx_15plus_100_200"]
        csv_df = csv_df.drop(columns=["notx_15plus_100_200"])

        csv_df["notx15plus50to100_low"] = csv_df["notx_15plus_50_100"]
        csv_df["notx15plus50to100_central"] = csv_df["notx_15plus_50_100"]
        csv_df["notx15plus50to100_high"] = csv_df["notx_15plus_50_100"]
        csv_df = csv_df.drop(columns=["notx_15plus_50_100"])

        csv_df["notx15plusless50_low"] = csv_df["notx_15plus_less50"]
        csv_df["notx15plusless50_central"] = csv_df["notx_15plus_less50"]
        csv_df["notx15plusless50_high"] = csv_df["notx_15plus_less50"]
        csv_df = csv_df.drop(columns=["notx_15plus_less50"])

        csv_df["notx5to14more1000_low"] = csv_df["notx_5_14_more1000"]
        csv_df["notx5to14more1000_central"] = csv_df["notx_5_14_more1000"]
        csv_df["notx5to14more1000_high"] = csv_df["notx_5_14_more1000"]
        csv_df = csv_df.drop(columns=["notx_5_14_more1000"])

        csv_df["notx5to14cd750to999_low"] = csv_df["notx_5_14_750_999"]
        csv_df["notx5to14cd750to999_central"] = csv_df["notx_5_14_750_999"]
        csv_df["notx5to14cd750to999_high"] = csv_df["notx_5_14_750_999"]
        csv_df = csv_df.drop(columns=["notx_5_14_750_999"])

        csv_df["notx5to14cd500to749_low"] = csv_df["notx_5_14_500_749"]
        csv_df["notx5to14cd500to749_central"] = csv_df["notx_5_14_500_749"]
        csv_df["notx5to14cd500to749_high"] = csv_df["notx_5_14_500_749"]
        csv_df = csv_df.drop(columns=["notx_5_14_500_749"])

        csv_df["notx5to14cd350to499_low"] = csv_df["notx_5_14_350_499"]
        csv_df["notx5to14cd350to499_central"] = csv_df["notx_5_14_350_499"]
        csv_df["notx5to14cd350to499_high"] = csv_df["notx_5_14_350_499"]
        csv_df = csv_df.drop(columns=["notx_5_14_350_499"])

        csv_df["notx5to14cd200to349_low"] = csv_df["notx_5_14_200_349"]
        csv_df["notx5to14cd200to349_central"] = csv_df["notx_5_14_200_349"]
        csv_df["notx5to14cd200to349_high"] = csv_df["notx_5_14_200_349"]
        csv_df = csv_df.drop(columns=["notx_5_14_200_349"])

        csv_df["notx5to14less200_low"] = csv_df["notx_5_14_less200"]
        csv_df["notx5to14less200_central"] = csv_df["notx_5_14_less200"]
        csv_df["notx5to14less200_high"] = csv_df["notx_5_14_less200"]
        csv_df = csv_df.drop(columns=["notx_5_14_less200"])

        csv_df["notxless5more30_low"] = csv_df["notx_less5_more30"]
        csv_df["notxless5more30_central"] = csv_df["notx_less5_more30"]
        csv_df["notxless5more30_high"] = csv_df["notx_less5_more30"]
        csv_df = csv_df.drop(columns=["notx_less5_more30"])

        csv_df["notxless5cd26to30_low"] = csv_df["notx_less5_26_30"]
        csv_df["notxless5cd26to30_central"] = csv_df["notx_less5_26_30"]
        csv_df["notxless5cd26to30_high"] = csv_df["notx_less5_26_30"]
        csv_df = csv_df.drop(columns=["notx_less5_26_30"])

        csv_df["notxless5cd21to25_low"] = csv_df["notx_less5_21_25"]
        csv_df["notxless5cd21to25_central"] = csv_df["notx_less5_21_25"]
        csv_df["notxless5cd21to25_high"] = csv_df["notx_less5_21_25"]
        csv_df = csv_df.drop(columns=["notx_less5_21_25"])

        csv_df["notxless5cd16to20_low"] = csv_df["notx_less5_16_20"]
        csv_df["notxless5cd16to20_central"] = csv_df["notx_less5_16_20"]
        csv_df["notxless5cd16to20_high"] = csv_df["notx_less5_16_20"]
        csv_df = csv_df.drop(columns=["notx_less5_16_20"])

        csv_df["notxless5cd11to15_low"] = csv_df["notx_less5_11_15"]
        csv_df["notxless5cd11to15_central"] = csv_df["notx_less5_11_15"]
        csv_df["notxless5cd11to15_high"] = csv_df["notx_less5_11_15"]
        csv_df = csv_df.drop(columns=["notx_less5_11_15"])

        csv_df["notxless5cd5to10_low"] = csv_df["notx_less5_5_10"]
        csv_df["notxless5cd5to10_central"] = csv_df["notx_less5_5_10"]
        csv_df["notxless5cd5to10_high"] = csv_df["notx_less5_5_10"]
        csv_df = csv_df.drop(columns=["notx_less5_5_10"])

        csv_df["notxless5less5_low"] = csv_df["notx_less5_less5"]
        csv_df["notxless5less5_central"] = csv_df["notx_less5_less5"]
        csv_df["notxless5less5_high"] = csv_df["notx_less5_less5"]
        csv_df = csv_df.drop(columns=["notx_less5_less5"])

        csv_df["pmtctcoverage_low"] = csv_df["PMTCT_cov"]
        csv_df["pmtctcoverage_central"] = csv_df["PMTCT_cov"]
        csv_df["pmtctcoverage_high"] = csv_df["PMTCT_cov"]
        csv_df = csv_df.drop(columns=["PMTCT_cov"])

        csv_df["cost_low"] = csv_df["Total_cost"]
        csv_df["cost_central"] = csv_df["Total_cost"]
        csv_df["cost_high"] = csv_df["Total_cost"]
        csv_df = csv_df.drop(columns=["Total_cost"])

        csv_df["fswcoverage_low"] = csv_df["FSW_cov"]
        csv_df["fswcoverage_central"] = csv_df["FSW_cov"]
        csv_df["fswcoverage_high"] = csv_df["FSW_cov"]
        csv_df = csv_df.drop(columns=["FSW_cov"])

        csv_df["msmcoverage_low"] = csv_df["MSM_cov"]
        csv_df["msmcoverage_central"] = csv_df["MSM_cov"]
        csv_df["msmcoverage_high"] = csv_df["MSM_cov"]
        csv_df = csv_df.drop(columns=["MSM_cov"])

        csv_df["pwidcoverage_low"] = csv_df["PWID_cov"]
        csv_df["pwidcoverage_central"] = csv_df["PWID_cov"]
        csv_df["pwidcoverage_high"] = csv_df["PWID_cov"]
        csv_df = csv_df.drop(columns=["PWID_cov"])

        # Generate HIV-negative population, incidence and mortality
        csv_df["hivneg_low"] = csv_df["population_central"] - csv_df["plhiv_high"]
        csv_df["hivneg_central"] = csv_df["population_central"] - csv_df["plhiv_central"]
        csv_df["hivneg_high"] = csv_df["population_central"] - csv_df["plhiv_low"]

        csv_df["incidence_low"] = csv_df["cases_low"] / csv_df["hivneg_central"]
        csv_df["incidence_central"] = csv_df["cases_central"] / csv_df["hivneg_central"]
        csv_df["incidence_high"] = csv_df["cases_high"] / csv_df["hivneg_central"]

        csv_df["mortality_low"] = csv_df["deaths_low"] / csv_df["plhiv_central"]
        csv_df["mortality_central"] = csv_df["deaths_central"] / csv_df["plhiv_central"]
        csv_df["mortality_high"] = csv_df["deaths_high"] / csv_df["plhiv_central"]

        # Pivot to long format
        melted = csv_df.melt(
            id_vars=["year", "country", "scenario_descriptor", "funding_fraction"]
        )

        # Label the upper and lower bounds as variants and drop the original 'variable' term
        melted["indicator"] = melted["variable"].apply(lambda s: s.split("_")[0])
        melted["variant"] = melted["variable"].apply(lambda s: s.split("_")[1])
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
class PFInputDataHIV(HIVMixin, PFInputData):
    """This is the File Handler for the HIV input data containing pf targets."""

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

        # Only keep indicators and countries of immediate interest:
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
        melted['indicator'] = melted['indicator'].str.replace('_p$', 'coverage', regex=True)
        melted['indicator'] = melted['indicator'].str.replace('_reached', '', regex=True)
        melted['indicator'] = melted['indicator'].str.replace('sw', 'fsw', regex=True)
        melted['indicator'] = melted['indicator'].str.replace('_', '', regex=True)

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


# # Load the partner data file(s)
class PartnerDataHIV(HIVMixin, PartnerData):
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

        # Load workbook
        csv_df = self._load_sheet(file)

        # Only keep columns of immediate interest.
        csv_df = csv_df[
            [
                "Year",
                "ISO3",
                "hiv_cases_n_pip",
                "hiv_deaths_n_pip",
                "HIVpos_n_pip",
                "Population_n_pip",
            ]
        ]

        # Do some renaming to make things easier
        csv_df = csv_df.rename(
            columns={
                "ISO3": "country",
                "Year": 'year',
                "hiv_deaths_n_pip": "deaths",
                "hiv_cases_n_pip": "cases",
                "HIVpos_n_pip": "plhiv",
                "Population_n_pip": 'population',
            }
        )

        # Generate HIV-negative population, incidence and mortality
        csv_df["hivneg"] = csv_df.shift(1)["population"] - csv_df.shift(1)["plhiv"]
        csv_df["incidence"] = csv_df["cases"] / csv_df["hivneg"]
        csv_df["mortality"] = csv_df["deaths"] / csv_df["plhiv"]

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


# Construct theGP
class GpHiv(HIVMixin, Gp):
    """Hold the GP for HIV. It has to construct it from a file (fixed_gp) that shows the trend over time and
    the partner data and some model results."""

    def _build_df(
            self,
            fixed_gp: FixedGp,
            model_results: ModelResultsHiv,
            partner_data: PartnerDataHIV,
            parameters: Parameters,
    ) -> pd.DataFrame:
        # Gather the parameters for this function
        gp_start_year = parameters.get(self.disease_name).get("GP_START_YEAR")
        first_year = parameters.get("START_YEAR")
        last_year = parameters.get("END_YEAR")

        hiv_countries = parameters.get_portfolio_countries_for(self.disease_name)
        hiv_m_countries = parameters.get_modelled_countries_for(self.disease_name)

        # Extract relevant partner and model data
        pop_hivneg_model = (
            model_results.df.loc[
                ("GP", slice(None), hiv_m_countries, slice(None), "hivneg")
            ]["central"]
            .groupby(axis=0, level=3)
            .sum()
        )
        pop_model = (
            model_results.df.loc[
                ("GP", slice(None), hiv_m_countries, slice(None), "population")
            ]["central"]
            .groupby(axis=0, level=3)
            .sum()
        )
        pop_hivneg_partner = (
            partner_data.df.loc[("PF", hiv_countries, slice(None), "hivneg")][
                "central"
            ]
            .groupby(axis=0, level=2)
            .sum()
        )
        pop_partner = (
            partner_data.df.loc[("PF", hiv_countries, slice(None), "population")][
                "central"
            ]
            .groupby(axis=0, level=2)
            .sum()
        )

        # Get population estimates from first GP year to generate ratio
        pop_hivneg_m_firstyear = (
            model_results.df.loc[
                ("GP", slice(None), hiv_m_countries, gp_start_year, "hivneg")
            ]["central"]
            .groupby(axis=0, level=3)
            .sum()
        )
        pop_m_firstyear = (
            model_results.df.loc[
                ("GP", slice(None), hiv_m_countries, gp_start_year, "population")
            ]["central"]
            .groupby(axis=0, level=3)
            .sum()
        )
        pop_hivneg_firstyear = partner_data.df.loc[
            ("PF", hiv_countries, gp_start_year, "hivneg")
        ].sum()["central"]
        pop_firstyear = partner_data.df.loc[
            ("PF", hiv_countries, gp_start_year, "population")
        ].sum()["central"]

        ratio_hivneg = pop_hivneg_m_firstyear / pop_hivneg_firstyear
        ratio = pop_m_firstyear / pop_firstyear

        # Use GP baseline year partner data to get the cases/deaths/incidence/mortality estimates at baseline
        cases_baseyear = partner_data.df.loc[
            ("PF", hiv_countries, gp_start_year, "cases")
        ].sum()["central"]
        deaths_baseyear = partner_data.df.loc[
            ("PF", hiv_countries, gp_start_year, "deaths")
        ].sum()["central"]
        pop_hivneg_baseyear = partner_data.df.loc[
            ("PF", hiv_countries, gp_start_year, "hivneg")
        ].sum()["central"]
        pop_baseyear = partner_data.df.loc[
            ("PF", hiv_countries, gp_start_year, "population")
        ].sum()["central"]
        incidence_baseyear = cases_baseyear / pop_hivneg_baseyear
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
                        ]
                    )
                ],
                pop_model.loc[pop_model.index.isin(range(first_year, last_year + 1))]
                / ratio.values,
            ]
        )

        pop_hivneg_glued = pd.concat(
            [
                pop_hivneg_partner.loc[
                    pop_hivneg_partner.index.isin(
                        [
                            gp_start_year,
                            gp_start_year + 1,
                            gp_start_year + 2,
                        ]
                    )
                ],
                pop_hivneg_model.loc[
                    pop_hivneg_model.index.isin(range(first_year, last_year + 1))
                ]
                / ratio_hivneg.values,
            ]
        )

        # Convert reduction and get gp time series
        relative_incidence = 1.0 - fixed_gp.df["incidence_reduction"]
        gp_cases = relative_incidence * cases_baseyear
        relative_mortality_rate = 1.0 - fixed_gp.df["death_rate_reduction"]
        gp_deaths = relative_mortality_rate * deaths_baseyear
        gp_incidence = gp_cases / pop_hivneg_glued
        gp_mortality_rate = gp_deaths / pop_glued

        # Put it all together into a df
        df = pd.DataFrame(
            {
                "incidence": gp_incidence,
                "mortality": gp_mortality_rate,
                "cases": gp_cases,
                "deaths": gp_deaths,
            }
        )

        # Return in expected format
        df.columns.name = "indicator"
        df.index.name = "year"
        return pd.DataFrame({"central": df.stack()})
