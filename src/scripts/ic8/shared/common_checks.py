from itertools import groupby

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from tgftools.checks import CheckResult, DatabaseChecks, critical
from tgftools.database import Database
from tgftools.filehandler import GFYear
from tgftools.utils import get_root_path


class CommonChecks_basicnumericalchecks:
    """A set of checks that are applicable to all of HIV, Tb and malaria"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        params = self.parameters

        # Gather the expectations for this class:
        self.EXPECTED_INDICATORS = params.get_indicators_for(self.disease_name)
        self.EXPECTED_EPI_INDICATORS = self.EXPECTED_INDICATORS.loc[self.EXPECTED_INDICATORS.use_scaling].index.to_list()

    @staticmethod
    def _summarise(idx: pd.Index) -> pd.DataFrame:
        """Returns a summary pd.DataFrame of a pd.Index, whereby there is a row for each
        `scenario_descriptor` and `country` in the index, and entries for indicator and funding_fraction are compressed
        into a dict-like-string (`year` is ignored)."""

        def agg_fn(_df):
            return (
                _df.groupby("indicator")["funding_fraction"]
                .apply(
                    lambda row: ",".join(
                        [str(r) for r in sorted(set(row.drop_duplicates()))]
                    )
                )
                .to_dict()
            )

        return (
            pd.DataFrame(idx.to_list(), columns=idx.names)
            .groupby(by=["scenario_descriptor", "country"])[
                ["funding_fraction", "indicator"]
            ]
            .apply(agg_fn)
            .reset_index()
            .rename(columns={0: "{indicator: funding_fractions}"})
        )

    @critical
    def no_negatives(self, db: Database):
        """Checks that there are no negative values in the model output."""
        df = db.model_results.df.loc[
             (slice(None), slice(None), slice(None), slice(None), slice(None)), :
             ]
        problem_lines = df.loc[(df < 0).sum(axis=1) > 0].index
        if len(problem_lines) > 0:
            return CheckResult(passes=False, message=self._summarise(problem_lines))

    @critical
    def no_missing(self, db: Database):
        """Checks that there are no missing or nan values in the model output.
        NOTE: we expect missing service coverage and cost for GP scenario. """

        df = db.model_results.df.loc[
             (slice(None), slice(None), slice(None), slice(None), slice(None)), :
             ]
        problem_lines = df.loc[(df.isna()).sum(axis=1) > 0].index
        if len(problem_lines) > 0:
            return CheckResult(passes=False, message=self._summarise(problem_lines))

    @critical
    def no_zeros(self, db: Database):
        """Check that there are no zeros in the model outputs amongst the epi variables.
        NOTE: The reason service variables are not evaluated is that CFs (all NULL and CC starting pre-2022)
        can contain zeros or in case of GF missing values. Service coverage for CC/NULL scenarios are compared to
        respective baseline and checked to be zero/constant in other checks. """

        # make a list of variables to be evaluated
        indicators = self.EXPECTED_EPI_INDICATORS

        # Second for historical scenarios, limited to historic scenarios and epi variables
        df = db.model_results.df.loc[
             (slice(None), slice(None), slice(None), slice(None), indicators), :
             ]
        problem_lines = df.loc[(df == 0).sum(axis=1) > 0].index

        if len(problem_lines) > 0:
            return CheckResult(passes=False, message=self._summarise(problem_lines))

    @critical
    def proportions_check(self, db: Database):
        """Checks that any variables expressed as proportions are between 0-1. """
        indicators = [
            name
            for name, type in self.EXPECTED_INDICATORS['type'].items()
            if type == "fraction"
        ]

        df = db.model_results.df.loc[
             (slice(None), slice(None), slice(None), slice(None), indicators), :
             ]
        problem_lines = df.loc[
            (df["low"] < 0.0)
            | (df["low"] > 1.0)
            | (df["central"] < 0.0)
            | (df["central"] > 1.0)
            | (df["high"] < 0.0)
            | (df["high"] > 1.0)
            ].index

        if len(problem_lines) > 0:
            return CheckResult(passes=False, message=self._summarise(problem_lines))

    @critical
    def correct_bounds_order(self, db: Database):
        """Checks LB, central and UB are in the right order: LB smaller than central smaller than UB. """
        df = db.model_results.df.loc[
             (slice(None), slice(None), slice(None), slice(None), slice(None)), :
             ]
        problem_lines = df.loc[
            (df["low"] > df["central"]) | (df["central"] > df["high"])
            ].index

        if len(problem_lines) > 0:
            return CheckResult(passes=False, message=self._summarise(problem_lines))


class CommonChecks_forwardchecks:
    """A set of checks that are applicable to all of HIV, Tb and malaria"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        params = self.parameters

        # Gather the expectations for these files:
        self.EXPECTED_COUNTRIES = params.get(self.disease_name).get('MODELLED_COUNTRIES')
        self.EXPECTED_CF_SCENARIOS = params.get_counterfactuals().index.to_list()
        self.EXPECTED_FUNDING_SCENARIOS = params.get_scenarios().index.to_list()
        self.CORRECT_SCENARIO_ORDER = [
            "GP",
            "PF",
            "CC_2022",
            "NULL_2022",
        ]  # <-- todo - this should be in parameters really.
        self.EXPECTED_LAST_YEAR = params.get("END_YEAR")
        self.EXPECTED_FIRST_YEAR = params.get("START_YEAR")
        self.EXPECTED_FUNDING_FRACTIONS = params.get(self.disease_name).get("FUNDING_FRACTIONS")
        self.EXPECTED_INDICATORS = params.get_indicators_for(self.disease_name)
        self.EXPECTED_EPI_INDICATORS = self.EXPECTED_INDICATORS.loc[self.EXPECTED_INDICATORS.use_scaling].index.to_list()
        self.PARTNER_DATA_YEARS = params.get(self.disease_name).get("PARTNER_DATA_YEARS")
        self.PF_DATA_YEARS = params.get(self.disease_name).get("PF_DATA_YEARS")
        self.TOLERANCE = params.get(self.disease_name).get("TOLERANCE_TO_PARTNER_AND_PF_DATA")
        self.REPLENISHMENT_YEARS = params.get("YEARS_FOR_FUNDING")

    @staticmethod
    def _summarise(idx: pd.Index) -> pd.DataFrame:
        """Returns a summary pd.DataFrame of a pd.Index, whereby there is a row for each
        `scenario_descriptor` and `country` in the index, and entries for indicator and funding_fraction are compressed
        into a dict-like-string (`year` is ignored)."""

        def agg_fn(_df):
            return (
                _df.groupby("indicator")["funding_fraction"]
                .apply(
                    lambda row: ",".join(
                        [str(r) for r in sorted(set(row.drop_duplicates()))]
                    )
                )
                .to_dict()
            )

        return (
            pd.DataFrame(idx.to_list(), columns=idx.names)
            .groupby(by=["scenario_descriptor", "country"])[
                ["funding_fraction", "indicator"]
            ]
            .apply(agg_fn)
            .reset_index()
            .rename(columns={0: "{indicator: funding_fractions}"})
        )

    @critical
    def correct_number_of_scenarios(self, db: Database):
        """Checks that there is the correct number of unique scenarios for each disease. Specifically, checks that there
        are the correct number of CFs and the correct number of actual scenarios with corresponding disease-specific
        expected number of funding fractions.
        Note: This check will not pick up missing scenarios for a given years or countries. """
        messages = []

        # Get the scenarios specified in the results
        df = db.model_results.df
        actual_scenarios = df.groupby(['scenario_descriptor', 'funding_fraction']).size().reset_index().rename(columns={0: 'count'})

        # Expected Scenarios:
        # - Each counterfactual, not iterated over funding fraction
        for cf in self.EXPECTED_CF_SCENARIOS:
            if 1 != (cf == actual_scenarios['scenario_descriptor']).sum():
                messages.append(f'Problem with counterfactual scenario {cf}: '
                                f'results provided for more than one funding_fraction')

        # - Each funding scenario should be repeated a number of time equal to the number of funding fractions
        for s in self.EXPECTED_FUNDING_SCENARIOS:
            if len(self.EXPECTED_FUNDING_FRACTIONS) != (s == actual_scenarios['scenario_descriptor']).sum():
                messages.append(f'Problem with funding scenario {s}: '
                                f'Not the right number of results for the required funding_fractions')

        if len(messages):
            return CheckResult(passes=False, message=messages)

    @critical
    def scenario_and_funding_for_each_country(self, db: Database):
        """Checks that scenarios with varying funding have a scenario for each of the modelled country
        for each year (based on the variables cases/new infections, deaths and population) based on disease-specific
        expected number of funding fractions.
        NOTE: This checks excludes GP, NULL and CC as these do not have funding fractions."""

        # Get shortcut to dataframe of model results
        df = db.model_results.df

        # We expected every an entry in the model results for each permutation of the following:
        expected_idx = pd.MultiIndex.from_product(
            [
                self.EXPECTED_FUNDING_SCENARIOS,
                self.EXPECTED_FUNDING_FRACTIONS,
                self.EXPECTED_COUNTRIES,
                range(self.EXPECTED_FIRST_YEAR, self.EXPECTED_LAST_YEAR + 1),
                self.EXPECTED_EPI_INDICATORS,
            ],
            names=df.index.names,
        )

        # Check what is missing from the model results
        missing_idx = expected_idx.difference(df.index)

        if len(missing_idx) > 0:
            return CheckResult(passes=False, message=self._summarise(missing_idx))

    def funding_vs_scenario_impact(self, db: Database):
        """Compares percentage funding-need met to impact for each modelled scenario to check that increased funding
        results in increased impact. This check is limited to the core scenarios (PF based scenario) and
        exclued GP, NULL and CC. """
        # TODO: this does not work for HIV or Malaria!
        # Percentage need met is calculated by comparing sum of funding in GP to that in each scenario
        # The impact should be more or less proportional to the percentage funding available.
        # example here: /Users/mc1405/Dropbox/The Global Fund/Strategic Targets 2022-2028/Processed Model Results/Key Stats/HIV_funding need met check.xlsx

        figs = []
        for scenario in self.EXPECTED_FUNDING_SCENARIOS:
            for country in self.EXPECTED_COUNTRIES:
                for indicator in ("cases", "deaths"):
                    df = (
                        db.model_results.df.loc[
                            (
                                scenario,
                                slice(None),
                                country,
                                range(
                                    self.EXPECTED_FIRST_YEAR,
                                    self.EXPECTED_LAST_YEAR + 1,
                                ),
                                indicator,
                            ),
                            "central",
                        ]
                        .groupby(axis=0, level="funding_fraction")
                        .sum()
                    )
                    df = df[df.index.notnull()]
                    df = df.sort_index(ascending=True)

                    fig, ax = plt.subplots()
                    df.plot(ax=ax)
                    ax.set_ylabel(indicator)
                    ax.set_title(f"{scenario=}, {country=}")
                    fig.tight_layout()
                    plt.close(fig)
                    figs.append(f"{scenario=}, {country=}, {indicator=}")

        return CheckResult(passes=True, message=figs)

    def order_of_scenarios(self, db):
        """Checks that the scenarios follow the expected a certain pattern.That is in increasing order for cases and
        deaths: GP, PF, CC, NULL and limited to scenarios with funding fractions 100%. """

        correct_order = self.CORRECT_SCENARIO_ORDER

        # Get maximum funding fraction

        figs = []
        for country in self.EXPECTED_COUNTRIES:
            for indicator in ("cases", "deaths"):
                df = (
                    db.model_results.df.loc[
                        (
                            correct_order,
                            1.0,
                            country,
                            range(self.EXPECTED_FIRST_YEAR, self.EXPECTED_LAST_YEAR+1),
                            indicator,
                        ),
                        "central",
                    ]
                )
                df = df.reset_index()
                df = df.loc[(df.funding_fraction == 1.0) | (df.funding_fraction.isnull())]
                df = df.groupby(by="scenario_descriptor")['central'].sum()
                df = df.loc[correct_order]

                if not df.is_monotonic_increasing:
                    fig, ax = plt.subplots()
                    df.plot.bar(ax=ax)
                    ax.set_ylabel(indicator)
                    ax.set_title(f"{country=}, {indicator=}")
                    fig.tight_layout()
                    plt.close(fig)
                    figs.append(fig)
        return CheckResult(passes=True, message=figs)

    def graphs_cost_vs_impact(self, db: Database):
        """This produces graphs of sum of cases/deaths (y-axis) against the total costs over the replenishment period
        (x-axis) for each country ."""

        figs = []
        years = range(min(self.REPLENISHMENT_YEARS), max(self.REPLENISHMENT_YEARS) + 1)
        for country in self.EXPECTED_COUNTRIES:
            for indicator in ("cases", "deaths"):
                indicator_names = [indicator, "cost"]

                # Filter the df for the country, the indicator and the years
                df = db.model_results.df.loc[
                    (
                        self.EXPECTED_FUNDING_SCENARIOS,
                        slice(None),
                        country,
                        years,
                        indicator_names,
                    ),
                    "central",
                ]

                # Get the GP point
                df_gp = db.model_results.df.loc[
                    (
                        "GP",
                        1.0,
                        country,
                        years,
                        indicator_names,
                    ),
                    "central",
                ]

                # Now arrange the columns and sum ready for the plotting
                df = df.reset_index()
                df = df.pivot(index=['scenario_descriptor', 'funding_fraction', 'country', 'year'], columns='indicator',
                              values='central')
                df = df.groupby(["scenario_descriptor", "funding_fraction"]).sum()
                df = df.reset_index()

                # Do the same for the data for the GP scenario
                df_gp = df_gp.reset_index()
                df_gp = df_gp.pivot(index=['scenario_descriptor', 'funding_fraction', 'country', 'year'],
                                    columns='indicator',
                                    values='central')
                df_gp = df_gp.groupby(["scenario_descriptor", "funding_fraction"]).sum()
                df_gp = df_gp.reset_index()

                def is_y_monotonic_decreasing_over_x(_x: pd.Series, _y: pd.Series):
                    """Returns True if the graph of y vs x is monotonically decreasing"""
                    return pd.concat({'_x': _x, '_y': _y}, axis=1).set_index('_x')['_y'].is_monotonic_decreasing

                # Now plot all scenarios in one plot, impact versus cost
                fig, ax = plt.subplots()
                i = 0
                for label in df['scenario_descriptor'].unique():
                    # get datapoints for that label
                    x = df[df['scenario_descriptor'] == label]['cost']
                    y = df[df['scenario_descriptor'] == label][indicator]

                    # Specify color and label (for legend)
                    ax.plot(x, y, label=label + f" is_monotonic_decreasing: {is_y_monotonic_decreasing_over_x(x,y)}", marker='o')
                    ax.legend()
                    i += 1

                # Try to add the GP point (todo cost for GP is not being captured in the case of malaria)
                try:
                    co_ords_gp = (df_gp["cost"].values[0], df_gp[indicator].values[0])
                    ax.plot(*co_ords_gp, marker='*', color='red', zorder=3)
                    ax.annotate('GP', xy=co_ords_gp, textcoords='offset points', xytext=(0, 10), ha='center')
                except:
                    ...

                # Tidy up axis labels and layout
                ax.set_ylabel(indicator)
                ax.set_xlabel("cost")
                ax.set_title(f"{country=}, {indicator=}")
                fig.tight_layout()
                plt.close(fig)
                figs.append(fig)

        return CheckResult(passes=True, message=figs)

    def pf_data(self, db: Database):
        """Model output for the period 20XX to end-20XX match the input data containing performance framework targets.
        """

        # Get shortcut to dataframe of model results
        df_model = db.model_results.df
        df_pf = db.pf_input_data.df

        # For this check limits pf data to one scenario and rename that as "pf data" and add funding fraction column
        df_pf = df_pf.loc[
            (self.EXPECTED_FUNDING_SCENARIOS, slice(None), self.PF_DATA_YEARS, slice(None))
        ]

        # For this check limit pf data and modelled data to modelled countries, right years.
        df_pf = df_pf.drop(
            df_pf.index[
                ~df_pf.index.get_level_values('country').isin(self.EXPECTED_COUNTRIES)]
        )

        df_pf = df_pf.reset_index()
        df_pf['data_source'] = 'pf'
        df_pf['funding_fraction'] = 1.0
        df_pf = df_pf.set_index(
            ["scenario_descriptor", "data_source", "funding_fraction", "country", "year", "indicator"]
        )

        df_model = df_model.loc[
            (self.EXPECTED_FUNDING_SCENARIOS, slice(None), slice(None), self.PF_DATA_YEARS, slice(None))
        ]
        df_model = df_model.reset_index()
        df_model['data_source'] = 'model'
        df_model = df_model.set_index(
            ["scenario_descriptor", "data_source", "funding_fraction", "country", "year", "indicator"]
        )

        def all_rows_similar(df: pd.DataFrame) -> bool:
            """Returns True if all the values within each column are similar."""
            return all([
                np.all(np.isclose(df[col].values, df[col].values[0], rtol=self.TOLERANCE))
                for col in country_result_for_this_indicator.columns
            ])

        messages = []  # Capture messages where a problem is detected

        # Look at each country/indicator in turn
        for indicator in db.pf_input_data.indicators:
            for country in db.model_results.countries:
                for scenario in self.EXPECTED_FUNDING_SCENARIOS:
                    for year in self.PF_DATA_YEARS:

                        # Get all the results for this country and indicator, up to (and including) the year 20XX
                        result_for_model = df_model.loc[
                            (scenario, slice(None), slice(None), country, year, indicator),
                            'central'
                        ].unstack(['year'])

                        # Filter scenario and year
                        result_for_pf = df_pf.loc[
                            (scenario, slice(None), slice(None), slice(None), year, slice(None)),
                            'central'
                        ].unstack(['year'])

                        # For this check limit pf data to selected country

                        result_for_pf = result_for_pf.drop(
                            result_for_pf.index[
                                result_for_pf.index.get_level_values('country') != country]
                        )

                        # Next limit to the right indicator
                        result_for_pf = result_for_pf.drop(
                            result_for_pf.index[
                                result_for_pf.index.get_level_values('indicator') != indicator]
                        )

                        # Now merge the results for model and partner data into one df
                        if len(result_for_pf > 0):
                            frame =[result_for_model, result_for_pf]
                            country_result_for_this_indicator = pd.concat(frame)

                            # We want the values within each column to be close to one another
                            if not all_rows_similar(country_result_for_this_indicator):
                                country_result_for_this_indicator = country_result_for_this_indicator.reset_index()
                                messages.append({
                                    'country': country,
                                    'indicator': indicator,
                                    'year': year,
                                    'scenario_descriptor': scenario,
                                    'funding_fractions': str(sorted(
                                        country_result_for_this_indicator.loc[
                                            country_result_for_this_indicator['data_source'] == 'model',
                                            'funding_fraction'].values
                                    ))
                                })

        # There should be no message. But, if they are, return CheckResult with the message.
        if len(messages) > 0:
            return CheckResult(
                passes=False,
                message=pd.DataFrame.from_dict(messages)
            )


class CommonChecks_allscenarios:
    """A set of checks that are applicable to all of HIV, Tb and malaria"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        params = self.parameters

        # Gather the expectations for these files:
        self.EXPECTED_COUNTRIES = params.get(self.disease_name).get('MODELLED_COUNTRIES')
        self.EXPECTED_CF_SCENARIOS = params.get_counterfactuals().index.to_list()
        self.EXPECTED_FUNDING_SCENARIOS = params.get_scenarios().index.to_list()
        self.EXPECTED_NULL_SCENARIOS = params.get_nullcounterfactuals().index.to_list()
        self.EXPECTED_CC_SCENARIOS = params.get_cccounterfactuals().index.to_list()
        self.EXPECTED_HISTORIC_FIRST_YEAR = params.get("HISTORIC_FIRST_YEAR")
        self.PARTNER_DATA_YEARS = params.get(self.disease_name).get("PARTNER_DATA_YEARS")
        self.EXPECTED_START_YEAR = params.get("START_YEAR")
        self.EXPECTED_GP_START_YEAR = params.get(self.disease_name).get("GP_START_YEAR")
        self.EXPECTED_LAST_YEAR_PF = params.get("LAST_YEAR_PF")
        self.EXPECTED_LAST_YEAR = params.get("END_YEAR")
        self.EXPECTED_INDICATORS = params.get_indicators_for(self.disease_name)
        self.EXPECTED_EPI_INDICATORS = self.EXPECTED_INDICATORS.loc[
        self.EXPECTED_INDICATORS.use_scaling].index.to_list()
        self.INDICATORS_FOR_NULL_CHECK = params.get(self.disease_name).get("INDICATORS_FOR_NULL_CHECK")
        self.INDICATORS_FOR_CC_CHECK = params.get(self.disease_name).get("INDICATORS_FOR_CC_CHECK")
        self.TOLERANCE = params.get(self.disease_name).get("TOLERANCE_TO_PARTNER_AND_PF_DATA")

    @staticmethod
    def _summarise(idx: pd.Index) -> pd.DataFrame:
        """Returns a summary pd.DataFrame of a pd.Index, whereby there is a row for each
        `scenario_descriptor` and `country` in the index, and entries for indicator and funding_fraction are compressed
        into a dict-like-string (`year` is ignored)."""

        def agg_fn(_df):
            return (
                _df.groupby("indicator")["funding_fraction"]
                .apply(
                    lambda row: ",".join(
                        [str(r) for r in sorted(set(row.drop_duplicates()))]
                    )
                )
                .to_dict()
            )

        return (
            pd.DataFrame(idx.to_list(), columns=idx.names)
            .groupby(by=["scenario_descriptor", "country"])[
                ["funding_fraction", "indicator"]
            ]
            .apply(agg_fn)
            .reset_index()
            .rename(columns={0: "{indicator: funding_fractions}"})
        )

    @critical
    def scenario_for_each_country(self, db: Database):
        """Checks that each of the modelled countries have each of the necessary historical scenarios for each year
        (based on the variables cases/new infections, deaths and population) for all scenarios (CFs and actual)
        including disease-specific expected number of excluding funding fractions. """

        # Get key information for this check
        expected_funding = [1.0]

        # Get shortcut to dataframe of model results
        df = db.model_results.df

        # Get the GF first year files
        if self.disease_name == 'HIV':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_hiv.csv",
            )

        if self.disease_name == 'TB':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_tb.csv",
            )

        if self.disease_name == 'MALARIA':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_malaria.csv",
            )

        expected_idx = pd.MultiIndex.from_product(
            [
                (['HH']),
                expected_funding,
                self.EXPECTED_COUNTRIES,
                range(self.EXPECTED_HISTORIC_FIRST_YEAR, self.EXPECTED_START_YEAR),
                self.EXPECTED_EPI_INDICATORS,
            ],
            names=df.index.names,
        )

        list_of_scenarios2 = self.EXPECTED_FUNDING_SCENARIOS
        list_of_scenarios2.append("CC_2022")
        list_of_scenarios2.append("NULL_2022")

        expected_idx_2 = pd.MultiIndex.from_product(
            [
                list_of_scenarios2,
                expected_funding,
                self.EXPECTED_COUNTRIES,
                range(self.EXPECTED_START_YEAR-1, self.EXPECTED_LAST_YEAR+1),
                self.EXPECTED_EPI_INDICATORS,
            ],
            names=df.index.names,
        )
        expected_idx = expected_idx.append(expected_idx_2)

        expected_idx_2 = pd.MultiIndex.from_product(
            [
                (['GP']),
                expected_funding,
                self.EXPECTED_COUNTRIES,
                range(self.EXPECTED_GP_START_YEAR, self.EXPECTED_LAST_YEAR+1),
                self.EXPECTED_EPI_INDICATORS,
            ],
            names=df.index.names,
        )
        expected_idx = expected_idx.append(expected_idx_2)

        expected_idx_2 = pd.MultiIndex.from_product(
            [
                (['CC_2000', 'NULL_2000']),
                expected_funding,
                self.EXPECTED_COUNTRIES,
                range(self.EXPECTED_HISTORIC_FIRST_YEAR, self.EXPECTED_LAST_YEAR+1),
                self.EXPECTED_EPI_INDICATORS,
            ],
            names=df.index.names,
        )
        expected_idx = expected_idx.append(expected_idx_2)

        for country in self.EXPECTED_COUNTRIES:
            year = gp_year.df.loc[(country), 'year']

            expected_idx_2 = pd.MultiIndex.from_product(
            [
                    (['CC_FIRSTYEARGF', 'NULL_FIRSTYEARGF']),
                    expected_funding,
                    [country],
                    range(year, self.EXPECTED_LAST_YEAR+1),
                    self.EXPECTED_EPI_INDICATORS,
                ],
                names=df.index.names,
            )
            expected_idx = expected_idx.append(expected_idx_2)

        # Check what is missing from the model results
        missing_idx = expected_idx.difference(df.index)

        if len(missing_idx) > 0:
            return CheckResult(passes=False, message=self._summarise(missing_idx))

    def graphs_for_basic_checks(self, db: Database):
        """This produces graphs of cases/new infections and deaths for each country for all scenarios but limited to
        funding fraction of 100%."""
        # TODO: review this with Mehran and the instructions in grey he gave (see below)
        # Plot the full set of scenarios to eyeball i) cases, ii) deaths, iii) incidence and iv) mortality
        # Compare plot of GP/NULL and CONSTCOV line to equivalent of latest exercise (IC or ST) and to
        # service level coverage for sense-check (check Table 3 here: https://docs.google.com/document/d/1TA5HtXytbOy3122KSKxuTqF10l-Kd49_5gBL9k2Fs1M/edit)
        # Check CFs for HIV deaths, cases and TB cases trends look comparable to last exercise
        # compare each scenario and make sure order makes sense

        scenarios = self.EXPECTED_CF_SCENARIOS + self.EXPECTED_FUNDING_SCENARIOS

        figs = []
        for country in self.EXPECTED_COUNTRIES:
            for indicator in ("cases", "deaths"):
                df = db.model_results.df.loc[
                    (
                        scenarios,
                        1.0,
                        country,
                        range(self.EXPECTED_HISTORIC_FIRST_YEAR, self.EXPECTED_LAST_YEAR+1),
                        indicator,
                    ),
                    "central",
                ]
                df = df.reset_index()
                df = df.loc[(df.funding_fraction == 1.0) | (df.funding_fraction.isnull())]
                col_list = ["year", "scenario_descriptor", "central"]
                df = df[col_list]
                df.set_index("year", inplace=True)

                fig, ax = plt.subplots()
                df.groupby("scenario_descriptor")["central"].plot(legend=True)
                ax.set_ylabel(indicator)
                ax.set_title(f"{country=}, {indicator=}")
                fig.tight_layout()
                plt.close(fig)
                figs.append(fig)
        return CheckResult(passes=True, message=figs)

    def graphs_of_aggregates(self, db: Database):
        """This produces graphs of cases/new infections, incidence, deaths and mortality over years aggregated across
        all countries. The graphs plot all scenarios against each other, with one graph per funding fraction. """

        scenarios = self.EXPECTED_CF_SCENARIOS + self.EXPECTED_FUNDING_SCENARIOS

        figs = []
        for indicator in ("cases", "deaths"):
            for scenario in scenarios:
                df = (
                    db.model_results.df.loc[
                        (
                            scenarios,
                            slice(None),
                            slice(None),
                            slice(None),
                            indicator,
                        ),
                        "central",
                    ]
                    .groupby(axis=0, level=("year", "scenario_descriptor"))
                    .sum()
                )
                df = df.reset_index()
                df.set_index("year", inplace=True)

                fig, ax = plt.subplots()
                df.groupby(["scenario_descriptor"])["central"].plot(legend=True)
                ax.set_ylabel(indicator)

                ax.set_title(f"{indicator},{scenario}")
                fig.tight_layout()
                plt.close(fig)
                figs.append(fig)

        return CheckResult(passes=True, message=figs)

    @critical
    def nullscenario_has_zeros_service(self, db: Database):
        """Checks that the NULL scenarios have zero service coverage from the first corresponding year"""

        if self.disease_name == 'HIV':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_hiv.csv",
            )

        if self.disease_name == 'TB':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_tb.csv",
            )

        if self.disease_name == 'MALARIA':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_malaria.csv",
            )

        messages = []  # Capture messages where a problem is detected

        for indicator in self.INDICATORS_FOR_NULL_CHECK:
            for country in db.model_results.countries:
                for scenario in self.EXPECTED_NULL_SCENARIOS:
                    # Get the right year for each scenario
                    if scenario == "NULL_2000":
                        year = self.EXPECTED_HISTORIC_FIRST_YEAR
                    if scenario == "NULL_FIRSTYEARGF":
                        year = gp_year.df.loc[(country), 'year']
                    if scenario == "NULL_2022":
                        year = self.EXPECTED_START_YEAR

                    # Get all the results for this country and indicator
                    df = db.model_results.df.loc[
                         (scenario, slice(None), country, slice(year, self.EXPECTED_LAST_YEAR), indicator), :
                         ]
                    df = df.droplevel(['funding_fraction', 'year'])  # drop levels not needed

                    problem_lines = pd.DataFrame(df.loc[(df != 0).sum(axis=1) > 0].index)
                    if problem_lines.size > 0:
                        messages.append((country, scenario, indicator))

        # There should be no message. But, if they are, return CheckResult with the message.
        if len(messages) > 0:
            return CheckResult(
                passes=False,
                message=pd.DataFrame(
                    messages,
                    columns=['country', 'scenario', 'indicator']
                ).groupby('country').agg(lambda x: ", ".join(y for y in x)).reset_index()
            )

    @critical
    def cc_scenario_has_constant_service(self, db: Database):
        """Checks that the CC scenarios have constant service coverage from the first corresponding year"""

        def all_rows_similar(df: pd.DataFrame) -> bool:
            """Returns True if all the values within each column are similar."""
            return all([
                np.all(np.isclose(df[col].values, df[col].values[0], rtol=self.TOLERANCE))
                for col in country_result_for_this_indicator.columns
            ])

        # Get key information for this check
        messages = []  # Capture messages where a problem is detected

        if self.disease_name == 'HIV':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_hiv.csv",
            )

        if self.disease_name == 'TB':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_tb.csv",
            )

        if self.disease_name == 'MALARIA':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_malaria.csv",
            )

        # Look at each country/indicator in turn for the year 2000
        for indicator in self.INDICATORS_FOR_CC_CHECK:
            for country in db.model_results.countries:
                for scenario in self.EXPECTED_CC_SCENARIOS:
                    # Get the right year for each scenario
                    if scenario == "CC_2000":
                        year = self.EXPECTED_HISTORIC_FIRST_YEAR
                    if scenario == "CC_FIRSTYEARGF":
                        year = gp_year.df.loc[(country), 'year']
                    if scenario == "CC_2022":
                        year = self.EXPECTED_START_YEAR - 1
                    # Get all the results for this country and indicator, up to (and including) the year 20XX
                    country_result_for_this_indicator = pd.DataFrame(db.model_results.df.loc[
                                                                         (scenario, slice(None), country,
                                                                          slice(year, self.EXPECTED_LAST_YEAR),
                                                                          indicator),
                                                                         'central'
                                                                     ])
                    # If the numbers are less than 0.5% make them zero to surpress error
                    country_result_for_this_indicator.loc[country_result_for_this_indicator.central <0.005] = 0

                    # We want the values within each column to be close to one another
                    if not all_rows_similar(country_result_for_this_indicator):
                        messages.append((country, scenario, indicator))

        # There should be no message. But, if they are, return CheckResult with the message.
        if len(messages) > 0:
            return CheckResult(
                passes=False,
                message=pd.DataFrame(
                    messages,
                    columns=['country', 'scenario', 'indicator']
                ).groupby(['country', 'scenario']).agg(lambda x: ", ".join(y for y in x)).reset_index()
            )

    def all_scenarios_have_same_beginning(self, db: Database):
        """Checks that each scenario has the same value for epi indicators for the corresponding year that
        they branch off from the historic trajectory. For CFs starting in 2000, we check in the year 2000, for
        scenarios starting in the first year of GF results, we compare up to that year, for scenarios starting in 2022
        we check once against the historic in 2022 and then all PF scenarios up to 2026.
        NOTE: the NULL_2000 may differ from CC_2000 and HH because for some diseases and countries there already was
        service provision and these were switched off at the start of 2000. """

        def all_rows_similar(df: pd.DataFrame) -> bool:
            """Returns True if all the values within each column are similar."""
            return all([
                np.all(np.isclose(df[col].values, df[col].values[0], rtol=self.TOLERANCE))
                for col in country_result_for_this_indicator.columns
            ])

        messages = []  # Capture messages where a problem is detected
        indicators = ['cases', 'deaths']

        if self.disease_name == 'HIV':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_hiv.csv",
            )

        if self.disease_name == 'TB':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_tb.csv",
            )

        if self.disease_name == 'MALARIA':
            gp_year = GFYear(  # Load GF start year file
                get_root_path() / "src" / "scripts" / "IC8" / "shared" / "GFyear_malaria.csv",
            )

        # Set list of historical scenarios
        list_scenarios_2000 = ["HH", "CC_2000", "NULL_2000"]
        list_scenarios_GF = ["HH", "CC_FIRSTYEARGF", "NULL_FIRSTYEARGF"]
        list_scenarios_baseline = ["HH", "CC_2022", "NULL_2022", "PF"]
        list_scenarios_2022 = ["HH", "PF"]

        scenario_type = [list_scenarios_2000, list_scenarios_GF, list_scenarios_baseline, list_scenarios_2022]


        # Look at each country/indicator in turn for the year 2000
        for indicator in indicators:
            for country in db.model_results.countries:
                for scenario in scenario_type:

                    # Get the right year for each scenario
                    if scenario == list_scenarios_2000:
                        start_year = self.EXPECTED_HISTORIC_FIRST_YEAR
                        end_year = self.EXPECTED_HISTORIC_FIRST_YEAR
                        scenario_tag = "2000start"
                    if scenario == list_scenarios_GF:
                        start_year - self.EXPECTED_HISTORIC_FIRST_YEAR
                        end_year = gp_year.df.loc[(country), 'year'] - 1
                        scenario_tag = "GFstart"
                    if scenario == list_scenarios_baseline:
                        start_year = self.EXPECTED_START_YEAR - 1
                        end_year = self.EXPECTED_START_YEAR - 1
                        scenario_tag = "baseline"
                    if scenario == list_scenarios_2022:
                        start_year = self.EXPECTED_START_YEAR - 1
                        end_year = self.EXPECTED_LAST_YEAR_PF + 1
                        scenario_tag = "2022start"

                    if (scenario == list_scenarios_2022 and self.disease_name == "HIV") or (scenario == list_scenarios_2022 and self.disease_name == "MALARIA"): # TODO: @richard, once John and Pete share the forward runs, edit this
                        print("this is an exception")
                    else:
                        # Get all the results for this country and indicator and scenario type, up to (and including) the year 20XX
                        country_result_for_this_indicator = db.model_results.df.loc[
                            (scenario, slice(None), country, slice(start_year, end_year), indicator),
                            'central'
                        ].unstack(['year'])

                        # We want the values within each column to be close to one another
                        if not all_rows_similar(country_result_for_this_indicator):
                            messages.append((country, indicator, scenario_tag))

        # There should be no message. But, if they are, return CheckResult with the message.
        if len(messages) > 0:
            return CheckResult(
                passes=False,
                message=pd.DataFrame(
                    messages,
                    columns=['country', 'indicator', 'scenario_type']
                ).groupby('country').agg(lambda x: ", ".join(y for y in x)).reset_index()
            )

    def partner_data(self, db: Database):
        """All epidemiological output (e.g. number of infections/cases and number of deaths) and all program coverage
        indicators (e.g. number of people on ART) in all scenarios are equal to WHO/UNAIDS latest published data for
        years up to and including the year 20XX. This is across all scenarios but only funding_fraction of 100% as
        another check ensures the model output all have the same beginning."""

        # Get shortcut to dataframe of model results
        df_model = db.model_results.df
        df_partner = db.partner_data.df

        # List scenarios that should match partner data
        list_of_scenarios = (['HH', 'PF', 'CC_2022', 'NULL_2022'])

        # For this check limit partner data and modelled data to modelled countries, right years.
        # For this check limits partner data to one scenario and rename that as "partner data" and for model output
        # remove the column containing funding fraction to clean output.
        df_partner = df_partner.loc[
            (self.EXPECTED_FUNDING_SCENARIOS[0], self.EXPECTED_COUNTRIES, self.PARTNER_DATA_YEARS, slice(None))
        ]
        df_partner = df_partner.reset_index()
        df_partner['scenario_descriptor'] = 'partner'
        df_partner = df_partner.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        df_model = df_model.loc[
            (list_of_scenarios, 1, slice(None), self.PARTNER_DATA_YEARS, slice(None))
        ]
        df_model = df_model.reset_index()
        df_model = df_model.drop(['funding_fraction', 'high', 'low'], axis=1)
        df_model = df_model.set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )

        def all_rows_similar(df: pd.DataFrame) -> bool:
            """Returns True if all the values within each column are similar."""
            return all([
                np.all(np.isclose(df[col].values, df[col].values[0], rtol=self.TOLERANCE))
                for col in country_result_for_this_indicator.columns
            ])

        messages = []  # Capture messages where a problem is detected

        # Look at each country/indicator in turn
        for indicator in db.partner_data.indicators:
            for country in db.model_results.countries:
                for year in self.PARTNER_DATA_YEARS:

                    # Get all the results for this country and indicator, up to (and including) the year 20XX
                    result_for_model = df_model.loc[
                        (slice(None), country, year, indicator),
                        'central'
                    ].unstack(['year'])
                    result_for_partner = df_partner.loc[
                        (slice(None), country, year, slice(None)),
                        'central'
                    ].unstack(['year'])

                    # For this check limit partner data to selected indicator
                    result_for_partner = result_for_partner.drop(
                        result_for_partner.index[
                            result_for_partner.index.get_level_values('indicator') != indicator]
                    )

                    # Now merge the results for model and partner data into one df
                    if len(result_for_partner > 0):
                        frame = [result_for_model, result_for_partner]
                        country_result_for_this_indicator = pd.concat(frame)

                        # We want the values within each column to be close to one another
                        if not all_rows_similar(country_result_for_this_indicator):
                            country_result_for_this_indicator = country_result_for_this_indicator.reset_index()
                            country_result_for_this_indicator.rename(
                                columns={country_result_for_this_indicator.columns[3]: "central"}, inplace=True)
                            country_result_for_this_indicator['year'] = year
                            country_result_for_this_indicator = round(country_result_for_this_indicator,5)
                            messages.append(country_result_for_this_indicator)

        # There should be no message. But, if they are, return CheckResult with the message.
        if len(messages) > 0:
            return CheckResult(
                passes=False,
                message=pd.concat(
                    messages,
                )
            )



