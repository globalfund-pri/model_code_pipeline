
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

""" START HERE FOR MALARIA: This file sets up everything needed to run malaria related code, including reading in the 
relevant files, cleans up the data in these files (harmonizing naming convention, generate needed variables, filters out 
variables that are not needed), puts them in the format defined for the database format. 

The database format is: 
1) scenario_descriptor: contains shorthands for scenario names
2) funding fraction: contains the funding fractions and refer to % of GP funding need 
3) country: holds iso3 code for a country
4) year: contains year
5) indicator: contains the variable names (short-hand). The parameters.toml file maps the short-hand to definition
6) low, central and high: contains the value for the lower bound, central and upper bound of a given variable. Where 
   LB and UB are not available these should be set to be the same as the "central" value.  

 This following files are read in in this script: 
 1) The malaria model results shared by Pete
 2) The PF input data. These were prepared by TGF and shared with modellers as input data to the model
 3) The WHO partner data as prepared by the TGF. These contain variables including e.g., year, iso3, cases, deaths, and
    population at risk (for a given year). The partner data should contain data for each of these variable for each 
    country eligible for GF funding for 2000 to latest year. 
 4) The fixed gp values to compute the non-modelled GP timeseries. 

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
     f) ensure all variables are available for Nick and Stephen
 4) List of scenarios: The parameter file provides the mapping of the scenario descriptions to their short-hand. 
    This list is used to:
    a) to map the variable (short-hand) name to the full definition
    b) in the checks to ensure, for example, that we have results for each country, for each year, for each variable 
    defined in this set of lists 
    c) for filtering when generating the output (i.e., select the final investment case and necessary counterfactual 
    scenario)
 5) Central parameters: In file "parameters.toml" update the years. Those are the first year of the model results, the 
    last year of model (e.g. model output may be provided up to 2050, but we only need projections up to 2030), years of 
    the replenishment, years that should be used in the objector funding for the optimizer, etc.  They also include key
    parameters for the analysis, e.g which scenario to run etc. 

CAUTION: 
Adding or removing items from the aforementioned lists will automatically be reflected in the rest of the code. If 
the code is running from local copies of the model data and analysis by e.g. setting LOAD_DATA_FROM_RAW_FILES to false
these may not be reflected. 

CAUTION: 
Scenarios without funding fractions (e.g GP, NULL, CC) should be given a funding fraction of 100% in this filehandler 
script in order to pass the database check and later will be used to run key checks.  

GOOD CODE PRACTICE:
Variable names: should be use small letter and be short but easy to understand
Hard-coding: to be avoided at all costs and if at all limited to these disease filehandlers and report class, only. 
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

        # This gives us the flexibility to read in all files in this folder and concatenate them.
        all_csv_file_at_the_path = get_files_with_extension(path, "xlsx")
        list_of_df = [
            self._turn_workbook_into_df(file) for file in all_csv_file_at_the_path
        ]

        concatenated_dfs = pd.concat(list_of_df, axis=0)

        # Filter out any countries that we do not need
        expected_countries = self.parameters.get_modelled_countries_for(self.disease_name)
        scenario_names = (self.parameters.get_scenarios().index.to_list() +
                          self.parameters.get_counterfactuals().index.to_list())
        concatenated_dfs = concatenated_dfs.loc[
            (scenario_names, slice(None), expected_countries, slice(None), slice(None))
        ]

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

        # smooth out 2027-2029
        adj_concatenated_dfs = self.adjust_dfs(
            concatenated_dfs
        )

        # return adj_concatenated_dfs
        return concatenated_dfs

    def adjust_dfs(self, df: pd.DataFrame) -> pd.DataFrame:
        """ this function will adjust the data in the df for the period 2027 to 2029 to match 2027 estimates. """

        df_keep = df.copy()

        cols_to_be_adjusted = [
            'cases',
            'deaths',
            'mortality',
            'incidence',
            'par',
        ]

        df = df.reset_index()
        df = df.drop(df[(df['scenario_descriptor'] == 'PF') & (df['year'] == 2029) & (df['indicator'].isin(cols_to_be_adjusted))].index)
        df = df.set_index(
            ["scenario_descriptor", "funding_fraction", "country", "year", "indicator"]
        )  # repack the index

        # Extract 2028 interested indicators and change year to 2029
        replace = df.loc[
            ("PF", slice(None), slice(None), 2028, cols_to_be_adjusted)
        ].copy().reset_index()
        replace['year'] = 2029
        replace = replace.set_index(
            ["scenario_descriptor", "funding_fraction", "country", "year", "indicator"]
        )  # repack the index

        # Concat the two and sort
        frames = [df, replace]
        df = pd.concat(frames, axis=0)
        df.reset_index()
        df = df.sort_values(['funding_fraction', 'country', 'year', 'scenario_descriptor', 'indicator'])

        # Implement smoothing, using 3 year rolling-average, using right-window
        # (Using for-loop as use rolling on groupby/multi-index is not supported:
        # see https://github.com/pandas-dev/pandas/issues/34642)
        for country in df.index.get_level_values('country').unique():
            funding_fractions_known = df.loc[
                (slice(None), slice(None), country, slice(None), slice(None))
            ].index.get_level_values("funding_fraction").dropna().unique().sort_values().to_numpy()
            for funding_fraction in funding_fractions_known:
                for indicator in cols_to_be_adjusted:
                    mask = ("PF", funding_fraction, country, slice(None), indicator)
                    for variant in ("central", "high", "low"):
                        df.loc[mask, variant] = df.loc[mask, variant].rolling(window=5, center=False).mean()

        # Check:
        # mask_cases_test = ("PF", 1.0, "BFA", slice(None), "cases")
        # pd.concat([
        #     df_keep.loc[mask_cases_test, 'central'].reset_index()[['year', 'central']],
        #     df.loc[mask_cases_test, 'central'].reset_index()['central']
        #     ], axis=1).plot(x='year')
        # plt.show()

        return df

    def _turn_workbook_into_df(self, file: Path) -> pd.DataFrame:
        """Returns formatted pd.DataFrame from the csv file provided. The returned dataframe is specific to one country,
        and has the required multi-index and column specifications."""
        print(f"Reading: {file}  .....", end="")

        # Load csv
        df = self._load_sheet(file)

        # Get costs without vaccine
        df['TotalCost'] = df["total_cost"]
        df['total_cost'] = df["TotalCost"] - df["cost_vaccine"]
        cols_needed = [
                "iso3",
                "year",
                "scenario",
                "budget_proportion",
                "cases",
                "cases_lb",
                "cases_ub",
                "deaths",
                "deaths_lb",
                "deaths_ub",
                "cases_smooth",
                "cases_smooth_lb",
                "cases_smooth_ub",
                "deaths_smooth",
                "deaths_smooth_lb",
                "deaths_smooth_ub",
                "net_n",
                "itn_use_n",
                "irs_people_protected",
                "irs_hh",
                "treatments_given_public",
                "treatments_given_private",
                "treatment_coverage",
                "hosp_malaria",
                "smc_children_protected",
                "smc_coverage",
                "vector_control_n",
                "vector_control_coverage",
                "vaccine_n",
                "vaccine_doses_n",
                "vaccine_coverage",
                "par",
                "par_targeted_smc",
                "par_vx",
                "total_cost",
                "cost_private",
                "cost_vaccine",
                "vaccine_compete",
                "cases_0_4",
                "cases_5_14",
                "cases_15_plus",
                "deaths_0_4",
                "deaths_5_14",
                "deaths_15_plus",
                "par_0_4",
                "par_5_14",
                "par_15_plus",
                "yld",
                "yld_lb",
                "yld_ub",

        ]

        # Only keep columns of immediate interest:
        df = df[cols_needed]

        # TODO: If we want to switch back to smoothed cases/deaths uncomment below and above smoothed cases/deaths
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
        df_gp = df[df.scenario == "GP"]
        df = df[df.scenario != "GP"]

        df_gp[[
            "net_n",
            "itn_use_n",
            "irs_people_protected",
            'irs_hh',
            "treatments_given_public",
            "treatments_given_private",
            "treatment_coverage",
            "hosp_malaria",
            "smc_children_protected",
            "smc_coverage",
            "vector_control_n",
            "vector_control_coverage",
            "vaccine_n",
            "vaccine_doses_n",
            "vaccine_coverage",
            "par",
            "par_targeted_smc",
            "par_vx",
            "total_cost",
            "cost_private",
            "cost_vaccine",
            "cases_0_4",
            "cases_5_14",
            "cases_15_plus",
            "deaths_0_4",
            "deaths_5_14",
            "deaths_15_plus",
            "par_0_4",
            "par_5_14",
            "par_15_plus",
            "yld",
            "yld_lb",
            "yld_ub",
        ]] = df_gp[[
            "net_n",
            "itn_use_n",
            "irs_people_protected",
            'irs_hh',
            "treatments_given_public",
            "treatments_given_private",
            "treatment_coverage",
            "hosp_malaria",
            "smc_children_protected",
            "smc_coverage",
            "vector_control_n",
            "vector_control_coverage",
            "vaccine_n",
            "vaccine_doses_n",
            "vaccine_coverage",
            "par",
            "par_targeted_smc",
            "par_vx",
            "total_cost",
            "cost_private",
            "cost_vaccine",
            "cases_0_4",
            "cases_5_14",
            "cases_15_plus",
            "deaths_0_4",
            "deaths_5_14",
            "deaths_15_plus",
            "par_0_4",
            "par_5_14",
            "par_15_plus",
            "yld",
            "yld_lb",
            "yld_ub",
            ]].fillna(0)

        # Then put GP back into df
        df = pd.concat([df, df_gp], axis=0)

        # TODO: Which vaccine scenario do we want to use?
        # Note if you want to run competing change both zeros below to ones!
        df["vaccine_compete"] = df["vaccine_compete"].fillna(0)
        df = df.loc[df['vaccine_compete'] == 0]
        df = df.drop(columns=["vaccine_compete"])

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
                "yld": "yld_central",
                "yld_lb": "yld_low",
                "yld_ub": "yld_high",

            }
        )

        # relabel all the PF_**_CC scenarios as 'PF' only: this is the name of the scenario defined in parameters.toml
        df.loc[df['scenario_descriptor'].str.startswith('PF_'), 'scenario_descriptor'] = 'PF'

        # Give all CFs scenarios a funding fraction of 1
        df['funding_fraction'] = df['funding_fraction'].fillna(1)  # Where there is no funding fraction, set it to 1

        # Duplicate indicators that do not have LB and UB to give low and high columns and remove duplicates
        df["par_low"] = df["par"]
        df["par_central"] = df["par"]
        df["par_high"] = df["par"]
        df = df.drop(columns=["par"])

        df["par0to4_low"] = df["par_0_4"]
        df["par0to4_central"] = df["par_0_4"]
        df["par0to4_high"] = df["par_0_4"]
        df = df.drop(columns=["par_0_4"])

        df["par5to14_low"] = df["par_5_14"]
        df["par5to14_central"] = df["par_5_14"]
        df["par5to14_high"] = df["par_5_14"]
        df = df.drop(columns=["par_5_14"])

        df["par15plus_low"] = df["par_15_plus"]
        df["par15plus_central"] = df["par_15_plus"]
        df["par15plus_high"] = df["par_15_plus"]
        df = df.drop(columns=["par_15_plus"])

        df["cases0to4_low"] = df["cases_0_4"]
        df["cases0to4_central"] = df["cases_0_4"]
        df["cases0to4_high"] = df["cases_0_4"]
        df = df.drop(columns=["cases_0_4"])

        df["cases5to14_low"] = df["cases_5_14"]
        df["cases5to14_central"] = df["cases_5_14"]
        df["cases5to14_high"] = df["cases_5_14"]
        df = df.drop(columns=["cases_5_14"])

        df["cases15plus_low"] = df["cases_15_plus"]
        df["cases15plus_central"] = df["cases_15_plus"]
        df["cases15plus_high"] = df["cases_15_plus"]
        df = df.drop(columns=["cases_15_plus"])

        df["deaths0to4_low"] = df["deaths_0_4"]
        df["deaths0to4_central"] = df["deaths_0_4"]
        df["deaths0to4_high"] = df["deaths_0_4"]
        df = df.drop(columns=["deaths_0_4"])

        df["deaths5to14_low"] = df["deaths_5_14"]
        df["deaths5to14_central"] = df["deaths_5_14"]
        df["deaths5to14_high"] = df["deaths_5_14"]
        df = df.drop(columns=["deaths_5_14"])

        df["deaths15plus_low"] = df["deaths_15_plus"]
        df["deaths15plus_central"] = df["deaths_15_plus"]
        df["deaths15plus_high"] = df["deaths_15_plus"]
        df = df.drop(columns=["deaths_15_plus"])

        df["llins_low"] = df["net_n"]
        df["llins_central"] = df["net_n"]
        df["llins_high"] = df["net_n"]
        df = df.drop(columns=["net_n"])

        df["llinsuse_low"] = df["itn_use_n"]
        df["llinsuse_central"] = df["itn_use_n"]
        df["llinsuse_high"] = df["itn_use_n"]
        df = df.drop(columns=["itn_use_n"])

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

        df["txprivate_low"] = df["treatments_given_private"]
        df["txprivate_central"] = df["treatments_given_private"]
        df["txprivate_high"] = df["treatments_given_private"]
        df = df.drop(columns=["treatments_given_private"])

        df["nrtx_low"] = df["treatment_coverage"] * df["cases_low"]
        df["nrtx_central"] = df["treatment_coverage"] * df["cases_central"]
        df["nrtx_high"] = df["treatment_coverage"] * df[("cases_high")]

        df["txcoverage_low"] = df["treatment_coverage"]
        df["txcoverage_central"] = df["treatment_coverage"]
        df["txcoverage_high"] = df["treatment_coverage"]
        df = df.drop(columns=["treatment_coverage"])

        df["hospitalization_low"] = df["hosp_malaria"]
        df["hospitalization_central"] = df["hosp_malaria"]
        df["hospitalization_high"] = df["hosp_malaria"]
        df = df.drop(columns=["hosp_malaria"])

        df["smc_low"] = df["smc_children_protected"]
        df["smc_central"] = df["smc_children_protected"]
        df["smc_high"] = df["smc_children_protected"]
        df = df.drop(columns=["smc_children_protected"])

        df["smccoverage_low"] = df["smc_coverage"]
        df["smccoverage_central"] = df["smc_coverage"]
        df["smccoverage_high"] = df["smc_coverage"]
        df = df.drop(columns=["smc_coverage"])

        df["vectorcontrol_low"] = df["vector_control_n"]
        df["vectorcontrol_central"] = df["vector_control_n"]
        df["vectorcontrol_high"] = df["vector_control_n"]
        df = df.drop(columns=["vector_control_n"])

        df["vectorcontrolcoverage_low"] = df["vector_control_coverage"]
        df["vectorcontrolcoverage_central"] = df["vector_control_coverage"]
        df["vectorcontrolcoverage_high"] = df["vector_control_coverage"]
        df = df.drop(columns=["vector_control_coverage"])

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


class GpMalaria(MALARIAMixin, Gp):
    """Hold the GP for malaria. It has to construct it from a file (fixed_gp) that shows the trend over time and
    the partner data and some model results."""

    def _build_df(
        self,
        fixed_gp: FixedGp,
        model_results: ModelResults,
        partner_data: PartnerData,
        parameters: Parameters,
        country_list: list = None,
    ) -> pd.DataFrame:

        # Gather the parameters for this function
        gp_start_year = parameters.get(self.disease_name).get("GP_START_YEAR")
        last_year = parameters.get("END_YEAR")

        if country_list is not None:
            modelled_countries_in_modelled_list = [c for c in country_list if c in model_results.countries]
        else:
            country_list = parameters.get_portfolio_countries_for(self.disease_name)
            modelled_countries_in_modelled_list = parameters.get_modelled_countries_for(self.disease_name)

        # Extract relevant partner and model data
        pop_model = (
            model_results.df.loc[("PF", 1, modelled_countries_in_modelled_list, slice(None), "par")][
                "central"
            ]
            .groupby(axis=0, level=3)
            .sum()
        )

        # Get population estimates from first model year to generate ratio
        pop_m_firstyear = (
            model_results.df.loc[
                ("PF", 1, modelled_countries_in_modelled_list, gp_start_year, "par")
            ]["central"]
            .groupby(axis=0, level=1)
            .sum()
        )
        pop_firstyear = partner_data.df.loc[
            ("PF", country_list, gp_start_year, "par")
        ].sum()["central"]
        ratio = pop_m_firstyear / pop_firstyear

        # Use baseline partner data to get the cases/deaths/incidence/mortality estimates at baseline
        cases_baseyear = partner_data.df.loc[
            ("PF", country_list, gp_start_year, "cases")
        ].sum()["central"]
        pop_baseyear = partner_data.df.loc[
            ("PF", country_list, gp_start_year, "par")
        ].sum()["central"]
        deaths_baseyear = partner_data.df.loc[
            ("PF", country_list, gp_start_year, "deaths")
        ].sum()["central"]
        incidence_baseyear = cases_baseyear / pop_baseyear
        mortality_rate_baseyear = deaths_baseyear / pop_baseyear

        # Make a time series of population estimate
        pop_glued = (
            pop_model.loc[pop_model.index.isin(range(gp_start_year, last_year + 1))]
            / ratio.values
        )

        # Convert reduction and get gp time series
        relative_incidence = 1.0 - fixed_gp.df["incidence_reduction"]
        gp_incidence = relative_incidence * incidence_baseyear
        relative_mortality_rate = 1.0 - fixed_gp.df["death_rate_reduction"]
        gp_mortality_rate = relative_mortality_rate * mortality_rate_baseyear
        gp_cases = gp_incidence * pop_glued
        gp_deaths = gp_mortality_rate * pop_glued

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
