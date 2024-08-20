import warnings
from collections import Counter, defaultdict
from pathlib import Path
from pprint import pprint
from typing import Iterable, NamedTuple, Optional, Union, List, Set

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.optimize import LinearConstraint, dual_annealing, minimize


from tgftools.utils import get_root_path
from tgftools.write_to_pdf import build_pdf

"""

This file contains all the classes needed to accomplish "Approach B", whereby the TGF Funding is allocated across
 countries so as to be optimal (according to some definition).

IMPORTANT NOTES
===============

We want all the optimisation to work on a full set of model results from 0% to 100% of the possible costs that a program
 could use.
 However, where results do not span that range, the option `handle_out_of_bounds_costs` so that they will not use a cost for a country that it outside of the domain
 of costs for which there are model results:
 * The highest cost in the model results is taken to the highest possible amount that a country could ever receive and
   generate the greatest possible impact.
 * If the NON_TGF BUDGET is not within the the range of costs covered in the model results, then the optimisers will not
   run. This is because they _need_ to be able to run a scenario in which the TGF BUDGET to a country is ZERO (not being
   able to do so, would introduce a *constraint* to the optimisation, which would just an artefact of the model results
   that happen to have been run.)
   NB. If necessary and accepted as OK, then this constraint could be removed by updating the `bounds` in the optimisers
       and editing the greedy algorithms (to start the countries as their respective minima when going forward, or
       stopping countries as their respective maxima when going backwards).
 
"""


def find_max_ignoring_inf(x: Iterable[float]) -> float:
    """Returns the maximum value in an iterable, ignoring float('inf')."""
    return x[np.isfinite(x)].max()

class ResultDatum(NamedTuple):
    """NamedTuple for cases and death for a given program cost."""

    cases: float
    deaths: float
    cost: float


class ApproachBResult(NamedTuple):
    """NamedTuple for the results of an analysis."""

    tgf_budget_by_country: dict[str, float]
    non_tgf_budget_by_country: dict[str, float]
    total_budget_by_country: dict[str, float]
    country_results: dict[str, ResultDatum]
    total_result: ResultDatum


class ApproachB:
    """This is the class for running a specific analysis using a set of model output files"""

    def __init__(
        self,
        model_results: pd.DataFrame,
        # <--- This is: country|cases|deaths|cost (multiple row per country, one for each costing value)
        non_tgf_budgets: pd.DataFrame,
        # <--- This is country|cost (one row per country)
        tgf_budgets: pd.DataFrame,
        # <--- This is country|cost (one row per country)
    ):
        # Create database of country level information
        self.dataset = ApproachBDataSet(model_results=model_results)

        # Load the budget files
        self.non_tgf_budgets = non_tgf_budgets.set_index("country")["value"].to_dict()
        self.tgf_budgets = (
            tgf_budgets.set_index("country")["value"].fillna(0.0).to_dict()
        )
        self.tgf_budget = sum(self.tgf_budgets.values())

        # Instantiate classes that that will do the optimisations
        self.greedy_algorithm = GreedyAlgorithm(self)
        self.optimisers = Optimisers(self)

        # Do the checks
        self._checks()

    def _checks(self):
        """Do Some Checks"""
        # 1) Check if the scenario when NON_TGF Funding is 0.0 can be evaluated (i.e., that model results exists
        # that allow an interpolation at that point.) and raise error if it cannot. This means that, for instance, a
        # solution of zero TGF funding to that country could not be examined.
        for _c in self.dataset.countries:
            lowest_cost = self.dataset.data[_c].results.index.min()
            highest_cost = self.dataset.data[_c].results.index.max()
            non_tgf_funding = self.non_tgf_budgets[_c]
            if not (lowest_cost <= non_tgf_funding <= highest_cost):
                warnings.warn(
                    "The scenario when TGF_FUNDING = 0.0: "
                    f"country:{_c}, non_tgf_funding:{non_tgf_funding}, "
                    f"range of costs in model results: {lowest_cost}-{highest_cost}"
                )

    def run(self, plt_show=False, filename=None, **kwargs) -> dict[str, ApproachBResult]:
        """Return results from running Approach A and Approach B. Any arguments provided are passed through to
        `do_approach_b`."""
        results = {"a": self.do_approach_a(), "b": self.do_approach_b(**kwargs)}
        self.do_report(results=results, plt_show=plt_show, filename=filename)
        return results

    def gen_analysis_result_from_tgf_budget_by_country(
        self, tgf_budget_by_country: dict[str, float]
    ) -> ApproachBResult:
        """Generate the AnalysisResults instance given a tgf_budget."""
        total_budget_by_country = {
            c: self.non_tgf_budgets[c] + tgf_budget_by_country[c]
            for c in self.dataset.countries
        }
        country_results = self.dataset.get_country_results_given_budgets(
            total_budget_by_country
        )

        return ApproachBResult(
            tgf_budget_by_country=tgf_budget_by_country,
            non_tgf_budget_by_country=self.non_tgf_budgets,
            total_budget_by_country=total_budget_by_country,
            country_results=country_results,
            total_result=add_list_of_results(list(country_results.values())),
        )

    def do_approach_a(self) -> ApproachBResult:
        """Returns results for each country, given a total amount of funding available to each country."""
        return self.gen_analysis_result_from_tgf_budget_by_country(
            tgf_budget_by_country=self.tgf_budgets
        )

    def do_approach_b(
        self,
        methods: Optional[Iterable[str]],
        provide_best_only: bool,
        max_allocation_to_a_country: float = 1.0,
        max_allocation_within_a_disease_to_a_country: float = 1.0,
    ) -> Union[ApproachBResult, tuple[dict[str, ApproachBResult], str]]:
        """Returns results for each country and the allocation of TGF budget by country, given a non-tgf-budget by
        country and a total amount of TGF funding, following an optimisation procedure.
        The `method` argument is a list of methods that will be used. The can include:
           * 'ga_forwards': The Greedy Algorithm starting with $0 allocations to each country.
           * 'ga_backwards': The Greedy Algorithm starting with allocations to each country per Approach A.
           * 'global_start_at_a': A Global Optimisation starting with allocations to each country per Approach A.
           * 'global_start_at_random': A Global Optimisation starting with a randomly-chosen allocations.
           * 'local_start_at_a': A Local Optimisation starting with allocations to each country per Approach A.
           * 'local_start_at_random': A Local Optimisation starting with a randomly-chosen allocations.

        If `methods` is `None`, all method are used (with one repetition of the random starting positions).

           Note that this list of methods can contain repeats of `global_start_at_random` and `local_start_at_random`
           so that different randomly-chosen starting points are used.
        """
        print("\n")
        all_methods = [
            "ga_forwards",
            "ga_backwards",
            "global_start_at_a",
            "global_start_at_random",
            "local_start_at_a",
            "local_start_at_random",
        ]

        if methods is None:
            methods = all_methods

        assert set(methods).issubset(all_methods), "Some methods not recognised."

        methods = Counter(
            methods
        )  # Use Counter to compute number of times each method is included in the list (also does sorting).

        solutions = dict()
        if "ga_forwards" in methods:
            solutions.update(
                {"ga: forwards": self.greedy_algorithm.run_forward(
                    n_steps=10_000,
                    max_allocation_to_a_country=max_allocation_to_a_country,
                    max_allocation_within_a_disease_to_a_country=max_allocation_within_a_disease_to_a_country)
                }
            )

        if "ga_backwards" in methods:
            solutions.update(
                {
                    "ga: backwards": self.greedy_algorithm.run_backward(n_steps=10_000),
                }
            )

        if "global_start_at_a" in methods:
            solutions.update(
                {
                    "global optimisation (from Approach A)": self.optimisers.use_global_optimiser(
                        start_from_random=False
                    )
                }
            )

        if "global_start_at_random" in methods:
            for _try_num in range(methods["global_start_at_random"]):
                solutions.update(
                    {
                        f"global optimisation (random start #{_try_num})": self.optimisers.use_global_optimiser(
                            start_from_random=True
                        )
                    }
                )

        if "local_start_at_a" in methods:
            solutions.update(
                {
                    "local minimisation (from Approach A)": self.optimisers.use_local_minimiser(
                        start_from_random=False
                    )
                }
            )

        if "local_start_at_random" in methods:
            for _try_num in range(methods["local_start_at_random"]):
                solutions.update(
                    {
                        f"local minimisation (random start #{_try_num})": self.optimisers.use_local_minimiser(
                            start_from_random=True
                        ),
                    }
                )

        # Determine which solution is favoured (among that those satisfy core requirements of the solution).
        optimised_impact = dict()
        for sol in solutions:
            if solutions[sol] is not None:
                # Check veracity of the solution
                x = np.array(list(solutions[sol].values()))
                assert (sum(x) <= self.tgf_budget) or np.isclose(
                    sum(x), self.tgf_budget, rtol=1e-4
                ), f'Error in the solution for method "{sol}"'
                assert all(x >= 0), f'Error in the solution for method "{sol}"'

                # Get portfolio level health impact of the solution:
                optimised_impact[sol] = self.eval_objective_function(
                    results=list(
                        self.dataset.get_country_results_given_budgets(
                            budget_by_country={
                                c: self.non_tgf_budgets[c] + solutions[sol][c]
                                for c in self.dataset.countries
                            }
                        ).values()
                    ),
                )
        pprint(optimised_impact)

        # Favoured solution
        best_sol = min(optimised_impact, key=optimised_impact.get)
        pprint(
            f"* Best solution from: {best_sol}. "
            f"It spends {round(100.0 * (np.array(list(solutions[best_sol].values())).sum() / self.tgf_budget), 2)}"
            f"% of the TGF budget."
        )

        if provide_best_only:
            return self.gen_analysis_result_from_tgf_budget_by_country(
                tgf_budget_by_country=solutions[best_sol]
            )
        else:
            return (
                {
                    # Position in tuple 0: Dict of the AnalysisResult from each method tried
                    _sol: self.gen_analysis_result_from_tgf_budget_by_country(
                        tgf_budget_by_country=solutions[_sol]
                    )
                    for _sol in solutions
                },
                # Position in tuple 1: Key to the best method
                best_sol,
            )

    def inspect_model_results(
        self, country: Union[None, str] = None, plt_show=True, filename=None,
    ) -> List[matplotlib.figure.Figure]:
        """Generate plots of all inputted model results, GP and the interpolated results for each country. Returns a
        list of Figures"""
        list_of_figs = []

        if country is None:
            countries_to_do = self.dataset.data.values()
        else:
            countries_to_do = [self.dataset.data[country]]

        for country in countries_to_do:
            _name = country.name
            res_actual = country.results
            res_interp = pd.DataFrame.from_dict(
                {
                    _res.cost: {"cases": _res.cases, "deaths": _res.deaths}
                    for _res in [
                        country.get_result_for_a_cost(_cost)
                        for _cost in np.linspace(
                            min(res_actual.index), find_max_ignoring_inf(res_actual.index), 100
                        )
                    ]
                }
            ).T

            fig, axes = plt.subplots(nrows=1, ncols=2)
            axes[0].plot(res_actual.index, res_actual.cases, "^y", label=f"Results")
            axes[0].plot(
                res_interp.index, res_interp.cases, "b", label=f"Interpolation"
            )
            axes[0].plot(
                country.gp.cost, country.gp.cases, "g*", markersize=8, label="GP"
            )
            axes[0].set_xlabel("Cost")
            axes[0].set_xlim(0)
            axes[0].set_ylim(0)
            axes[0].set_title(f"Country {_name}: Cases")
            axes[0].legend()

            # Deaths
            axes[1].plot(res_actual.index, res_actual.deaths, "^y", label=f"Results")
            axes[1].plot(
                res_interp.index, res_interp.deaths, "b", label=f"Interpolation"
            )
            axes[1].plot(
                country.gp.cost, country.gp.deaths, "g*", markersize=8, label="GP"
            )
            axes[1].set_xlabel("Cost")
            axes[1].set_xlim(0)
            axes[1].set_ylim(0)
            axes[1].set_title(f"Country {_name}: Deaths")
            axes[1].legend()

            fig.tight_layout()
            if plt_show:
                fig.show()
            plt.close(fig)
            list_of_figs.append(fig)

        # Save to pdf
        if filename is not None:
            build_pdf(
                filename=filename,
                content={'Inspect Model Results': list_of_figs},
            )

        return list_of_figs

    def do_report(
            self,
            results: dict,
            plt_show=True,
            filename=None,
    ) -> None:
        """With results from a run of Approach B, produce summary plots of the results.
        If a filename is specified, then a pdf of the all the plots is created.
        If plt_show=False, then plots are not displayed.
        """
        if not plt_show and not filename:
            # No need to do anything, as results will not be displayed or saved
            return

        content_for_pdf = {}

        # - compare results of the optimization analysis (if more than one method has been used)
        if not isinstance(results["b"], ApproachBResult):
            b_methods = results["b"][0]

            tgf_funding_allox = pd.DataFrame(
                {method: result.tgf_budget_by_country for method, result in b_methods.items()}
            )
            fig, ax = plt.subplots()
            tgf_funding_allox.plot(ax=ax)
            if plt_show:
                plt.show()
            plt.close(fig)
            content_for_pdf['Compare Results from Different Optimisation Methods'] = [fig]

            # Look at overall impact
            overall_impact = pd.DataFrame(
                {
                    method: (result.total_result.deaths, result.total_result.cases)
                    for method, result in b_methods.items()
                },
            ).T.rename(columns={0: "deaths", 1: "cases"})
            fig, ax = plt.subplots()
            overall_impact.T.plot.bar(ax=ax)
            plt.tight_layout()
            if plt_show:
                plt.show()
            plt.close(fig)
            content_for_pdf['Overall Impact'] = [fig]

        # Get best result for approach B
        if not isinstance(results["b"], ApproachBResult):
            # if many methods run, identify the results that is best
            best_result_for_approach_b = results["b"][0][results["b"][1]]
        else:
            # if only the best results returned anyway, just point to it
            best_result_for_approach_b = results["b"]

        # - plot favoured results
        best_result = {"a": results["a"], "b": best_result_for_approach_b}
        content_for_pdf['Results From Best Method'] = self.plot_approach_b_results(best_result, plt_show=plt_show)

        # Save to pdf
        if filename is not None:
            build_pdf(
                filename=filename,
                content=content_for_pdf,
            )

    def plot_approach_b_results(
            self,
            results: dict[str, ApproachBResult],
            plt_show: bool = True,
    ) -> List[matplotlib.figure.Figure]:
        """Convenience function to generate a standard set of plots for the results of ApproachB."""

        # Create list of Figures that will be returned
        list_of_figs = []

        # Inspect portfolio level results between Approach A and Approach B
        fig, ax = plt.subplots(ncols=3, nrows=1)
        pd.Series({x: results[x].total_result.cases for x in results}).plot.bar(ax=ax[0])
        ax[0].set_title("Total Cases")
        ax[0].set_xlabel("Approach")

        pd.Series({x: results[x].total_result.deaths for x in results}).plot.bar(ax=ax[1])
        ax[1].set_title("Total Deaths")
        ax[1].set_xlabel("Approach")

        pd.Series({x: results[x].total_result.cost for x in results}).plot.bar(ax=ax[2])
        ax[2].set_title("Total Cost")
        ax[2].set_xlabel("Approach")

        fig.tight_layout()
        if plt_show:
            fig.show()
        plt.close(fig)
        list_of_figs.append(fig)

        # Show Allocation of Funds between Approach A and Approach B
        # Non_TGF Budget + TGF Allocation as stacked bars:
        fig, ax = plt.subplots(nrows=2, ncols=1, sharex=True, sharey=True)
        for _i, _approach in enumerate(["a", "b"]):
            ax[_i].set_title(f'Approach "{_approach}"')
            ax[_i].bar(
                results[_approach].non_tgf_budget_by_country.keys(),
                results[_approach].non_tgf_budget_by_country.values(),
                label="Non-TGF",
            )
            ax[_i].bar(
                results[_approach].tgf_budget_by_country.keys(),
                results[_approach].tgf_budget_by_country.values(),
                label="TGF",
                bottom=[results[_approach].non_tgf_budget_by_country[_c] for _c in
                        results[_approach].tgf_budget_by_country.keys()],
            )
            if _i != 0:
                ax[_i].set_xlabel("Country")
            ax[_i].set_ylabel("Budgets")
            ax[_i].tick_params(axis="x", labelrotation=90)
            ax[_i].legend()
        fig.tight_layout()
        if plt_show:
            fig.show()
        plt.close(fig)
        list_of_figs.append(fig)

        fig, ax = plt.subplots()
        tgf_allocation = pd.DataFrame(
            {_i: results[_i].tgf_budget_by_country for _i in ["a", "b"]}
        ).apply(lambda x: 100.0 * x / x.sum())
        tgf_allocation.plot.bar(ax=ax)
        ax.set_title("TGF Allocation By Country")
        ax.set_ylabel("Percent of TGF Budget")
        ax.set_xlabel("Country")
        fig.tight_layout()
        if plt_show:
            fig.show()
        plt.close(fig)
        list_of_figs.append(fig)

        # Inspect results for each country
        # Non_TGF Budget + TGF Allocation on the Health-Budget Graph (one figure per country)
        for _c in self.dataset.countries:
            fig, axes = plt.subplots(nrows=1, ncols=2)
            res_actual = self.dataset.data[_c].results
            res_interp = pd.DataFrame.from_dict(
                {
                    _res.cost: {"cases": _res.cases, "deaths": _res.deaths}
                    for _res in [
                    self.dataset.data[_c].get_result_for_a_cost(_cost)
                    for _cost in np.linspace(
                        min(self.dataset.data[_c].results.index),
                        find_max_ignoring_inf(self.dataset.data[_c].results.index),
                        100,
                    )
                ]
                }
            ).T

            # Cases
            ax = axes[0]
            ax.plot(res_actual.index, res_actual.cases, "^y", label=f"Results")
            ax.plot(res_interp.index, res_interp.cases, "b", label=f"Interpolation")
            ax.plot(
                self.dataset.data[_c].gp.cost,
                self.dataset.data[_c].gp.cases,
                "g*",
                markersize=8,
                label="GP",
            )
            ax.plot(
                results["b"].non_tgf_budget_by_country[_c],
                self.dataset.data[_c]
                .get_result_for_a_cost(results["b"].non_tgf_budget_by_country[_c])
                .cases,
                "ko",
                markersize=8,
                label="Non-TGF",
            )
            ax.plot(
                results["a"].total_budget_by_country[_c],
                results["a"].country_results[_c].cases,
                "r^",
                markersize=8,
                label='Non-TGF + TGF (Approach "a")',
            )
            ax.plot(
                results["b"].total_budget_by_country[_c],
                results["b"].country_results[_c].cases,
                "r.",
                markersize=8,
                label='Non-TGF + TGF (Approach "b")',
            )
            ax.set_xlabel("Budget")
            ax.set_xlim(0)
            ax.set_ylim(0)
            ax.set_title(f"Country {_c}: Cases")

            # Deaths
            ax = axes[1]
            ax.plot(res_actual.index, res_actual.deaths, "^y", label=f"Results")
            ax.plot(res_interp.index, res_interp.deaths, "b", label=f"Interpolation")
            ax.plot(
                self.dataset.data[_c].gp.cost,
                self.dataset.data[_c].gp.deaths,
                "g*",
                markersize=8,
                label="GP",
            )
            ax.plot(
                results["b"].non_tgf_budget_by_country[_c],
                self.dataset.data[_c]
                .get_result_for_a_cost(results["b"].non_tgf_budget_by_country[_c])
                .deaths,
                "ko",
                markersize=8,
                label="Non-TGF",
            )
            ax.plot(
                results["a"].total_budget_by_country[_c],
                results["a"].country_results[_c].deaths,
                "r^",
                markersize=8,
                label='Non-TGF + TGF (Approach "a")',
            )
            ax.plot(
                results["b"].total_budget_by_country[_c],
                results["b"].country_results[_c].deaths,
                "r.",
                markersize=8,
                label='Non-TGF + TGF (Approach "b")',
            )
            ax.set_xlabel("Budget")
            ax.set_xlim(0)
            ax.set_ylim(0)
            ax.set_title(f"Country {_c}: Deaths")
            ax.legend()
            fig.tight_layout()
            if plt_show:
                fig.show()
            plt.close(fig)
            list_of_figs.append(fig)

        return list_of_figs

    def eval_objective_function(
            self,
            results: list[ResultDatum],
    ) -> float:
        """Return evaluation of objective function for a given list of Results, representing the Results from each
        country, and the specification of the portfolio-level GP.
        NB. This method and can be overridden through subclasses, or just redirecting this to another
        function."""
        totals = add_list_of_results(results)
        portfolio_gp = self.dataset.portfolio_values_when_maximum_cost_in_all_countries
        return (totals.cases / portfolio_gp.cases) + (totals.deaths / portfolio_gp.deaths)

class ApproachBDataSet:
    """This class holds all the `Country` objects and some helper functions to make life easier"""

    def __init__(self, model_results: pd.DataFrame):
        self.countries = sorted(set(model_results["country"]))
        self.data = {
            _country: Country(
                model_results=model_results,
                name=_country,
            )
            for _country in self.countries
        }
        self.do_checks()

    @property
    def portfolio_values_when_maximum_cost_in_all_countries(self) -> ResultDatum:
        """Returns the sum of the "Results" from all the countries for the highest cost scenario in the model results."""
        return add_list_of_results([self.data[_country].gp for _country in self.countries])

    def get_country_results_given_budgets(
        self, budget_by_country: dict = None
    ) -> dict[str, ResultDatum]:
        """Returns a list of the country-specific results given a budget allocated to each country."""
        return {
            _country: self.data[_country].get_result_for_a_cost(
                budget_by_country[_country]
            )
            for _country in self.countries
        }

    def get_cost_vs_impact_scaled_to_gp(self) -> dict[str, pd.DataFrame]:
        """Get the cost vs impact (scaled to GP) in each country and assemble into dataframes"""

        costs_per_gp = np.linspace(0, 1.1, 100)

        cases_df = pd.DataFrame(columns=self.countries, index=costs_per_gp)
        deaths_df = pd.DataFrame(columns=self.countries, index=costs_per_gp)

        for _name, _country in self.data.items():
            raw_results = _country.get_cost_vs_impact_scaled_to_gp()
            # use interpolation to put this onto a standard set of cost_per_gp
            cases_df.loc[:, _name] = np.interp(
                costs_per_gp, raw_results.index, raw_results.cases
            )
            deaths_df.loc[:, _name] = np.interp(
                costs_per_gp, raw_results.index, raw_results.deaths
            )

        return {"cases": cases_df, "deaths": deaths_df}

    def do_checks(self) -> None:
        """Run the checks on each country and print the results to the console and raise a warning if there are any
        messages."""
        results = dict()
        for _name, _country in self.data.items():
            results[_name] = _country.check()

        if any([len(x) > 0 for x in results.values()]):
            pprint(results)
            warnings.warn(
                UserWarning(
                    "Some abnormalities detecting in the construction of the Country dataclasses."
                )
            )


class Country:
    """This class holds all the information for a particular country."""

    def __init__(
        self, model_results: pd.DataFrame, name: str,
    ):
        self.name = name
        self.results = self.load_results(
            model_results=model_results,
            name=name,
        )

        get_value_for_max_cost = lambda x: x.loc[x["cost"] == find_max_ignoring_inf(x["cost"])]
        self.gp = ResultDatum(
            **self.results.reset_index().pipe(get_value_for_max_cost).iloc[0]
        )

    @staticmethod
    def load_results(
        model_results: pd.DataFrame, name: str,
    ) -> (pd.DataFrame, ResultDatum):
        """This is where the results file(s) for a particular country are loaded.
        * gp: Results instance specifying the Global Plan (GP).
        * results: pd.DataFrame of the disease model's results (index=cost of the program; columns=[total cases, total
        deaths]);
        """
        if (model_results is None) and (name == "__Dummy__"):
            # create dummy data:
            return get_dummy_country_result()

        # Get the 'results' (only cases and deaths) for this country
        results_data = model_results
        _results = (
            results_data.loc[results_data.country == name]
            .set_index("cost")
            .sort_index()[["cases", "deaths"]]
        )
        return _results

    def get_result_for_a_cost(self, cost: Union[int, float]) -> ResultDatum:
        """Returns the results for a given cost of a programme, interpolating between loaded model results where
        necessary. It throws an error if a cost is requested that it outside the domain of the costs for which
        there are modelling results."""

        if min(self.results.index) <= cost <= max(self.results.index):
            _cases: float = np.interp(
                cost, np.array(self.results.index), np.array(self.results.cases)
            )
            _deaths: float = np.interp(
                cost, np.array(self.results.index), np.array(self.results.deaths)
            )
        elif cost >= max(self.results.index):
            # If a greater amount of funding is available than the max_cost, the impact is capped at that for the
            # maximum cost.
            _cases: float = np.interp(
                max(self.results.index), np.array(self.results.index), np.array(self.results.cases)
            )
            _deaths: float = np.interp(
                max(self.results.index), np.array(self.results.index), np.array(self.results.deaths)
            )
        else:
            raise ValueError("Result requested for a cost that is out of domain.")

        return ResultDatum(cases=_cases, deaths=_deaths, cost=float(cost))

    def get_cost_vs_impact_scaled_to_gp(self) -> pd.DataFrame:
        """Return a pd.DataFrame that shows how the fraction of the GP funding is relates to the fraction of the cost
        and impact achieved, relative to the GP."""
        return pd.DataFrame(
            index=self.results.index / self.gp.cost,
            data={
                "cases": self.results.cases.values / self.gp.cases
                if self.gp.cases > 0
                else np.nan,
                "deaths": self.results.deaths.values / self.gp.deaths
                if self.gp.deaths > 0
                else np.nan,
            },
        )

    def check(self) -> list:
        """Check that the data for this country conforms to expectations."""
        results = list()

        # Check can do interpolation for values between the lowest and highest cost run for which we have a result:
        [
            self.get_result_for_a_cost(_cost)
            for _cost in np.linspace(
                self.results.index.min(), find_max_ignoring_inf(self.results.index), 100
            )
        ]

        # Check that cases and deaths are both monotonically decreasing with cost
        if not self.results.cases.is_monotonic_decreasing:
            results.append("Cases not monotonic decreasing.")

        if not self.results.deaths.is_monotonic_decreasing:
            results.append("Deaths not monotonic decreasing.")

        return results


class GreedyAlgorithm:
    """This is a "home-made" heuristic algorithm for finding the best allocation of TGF budget among the countries."""

    def __init__(self, approach_b: ApproachB):
        self.approach_b = approach_b
        self._database = approach_b.dataset

    def generate_initial_state(
        self, starting_cost: dict[str, float], budget_increment: float
    ) -> dict[str, list[ResultDatum]]:
        """We arrange the results for each country by increment. This a dict, keyed by countries, giving a list of
        Results for a sequence of program costs. The *first* element in the list for each country gives the 'starting'
        program in that country, and subsequent elements describe deviation from that. [If no deviations from the
        starting position are possible, then the list has a length of one.]
        """
        return {
            _c: self.get_results_at_increments(
                country=self._database.data[_c],
                minimum_cost=starting_cost[_c],
                increments=budget_increment,
            )
            for _c in self._database.countries
        }

    @staticmethod
    def get_results_at_increments(
        country, minimum_cost, increments
    ) -> list[ResultDatum]:
        """Return a list of Results for a sequence of program costs. This pre-processing step improves the efficiency
        of the algorithm by avoiding repeated calls to 'get_results_for_a_cost' in the Country.

        * If increment is positive, the sequence goes from `minimum_cost` to the GP cost for the country;
        * If increment is negative, the sequence goes from the GP cost for the country to the `minimum_cost`.

        A list of len >= 1 is returned (the first position is for the starting_cost).
        """
        assert np.isfinite(increments), "Increment must be finite!"

        if increments > 0:
            steps = [minimum_cost] + list(np.arange(minimum_cost + increments, country.gp.cost, increments))
            return [
                country.get_result_for_a_cost(_b)
                for _b in steps
            ]
        else:
            steps = [country.gp.cost] + list(np.arange(country.gp.cost + increments, minimum_cost, increments))
            return [
                country.get_result_for_a_cost(_b)
                for _b in steps
            ]

    def find_country_where_next_pop_leads_to_greatest_reduc_in_objfn(
            self,
            states,
            countries_not_allowed_to_change: Optional[Set] = None,
    ) -> Optional[str]:
        """Returns the country symbol for which the next `pop` operation on its list would lead to the greatest
        reduction in the objective function; or None, if no more `pop`s are possible."""
        if countries_not_allowed_to_change is None:
            countries_not_allowed_to_change = set()

        reduction_in_obj_function_by_country = dict()

        current_obj_func = self._eval_objective_function(
            [states[_c][0] for _c in states]
        )

        # filter out countries that cannot receive additional funding because:
        # * we're at the end of their state variable
        # * the countries are not allowed to change
        _countries_that_can_pop = [
            _c for _c in states
            if (len(states[_c]) > 1) and (_c not in countries_not_allowed_to_change)
        ]

        if not _countries_that_can_pop:
            # No country can absorb the increment
            return None

        for _country_to_try in _countries_that_can_pop:
            # Compile list of Results for all countries...
            # ... in which, results for all countries other than `_country_to_try` are at their current level of funding
            __tmp_results = [states[_c][0] for _c in states if _c != _country_to_try]

            # ... and the `_country_to_try` is at increased funding (if there can be increased funding)
            if len(states[_country_to_try]) >= 2:
                __tmp_results.append(states[_country_to_try][1])
            else:
                __tmp_results.append(states[_country_to_try][0])

            reduction_in_obj_function_by_country[
                _country_to_try
            ] = current_obj_func - self._eval_objective_function(__tmp_results)

        return max(
            reduction_in_obj_function_by_country,
            key=reduction_in_obj_function_by_country.get,
        )

    def _eval_objective_function(self, results):
        """Helper function, to neaten call from within the class to the `eval_objective_function` on ApproachB."""
        return self.approach_b.eval_objective_function(results)

    @staticmethod
    def get_current_results(_states):
        """Return the list of Results for each country at the current funding level (i.e., 0th position in each list)"""
        return [_states[_c][0] for _c in _states]

    def run_forward(self,
                    n_steps: int,
                    max_allocation_to_a_country: float,
                    max_allocation_within_a_disease_to_a_country: float
                    ) -> dict[str, float]:
        """Run the algorithm in "forward" mode, wherein we start each country at its non_tgf_budget and allocate each
        increment of the tgf budget to a country, until the TGF budget is exhausted."""

        assert 0. <= max_allocation_to_a_country <= 1.
        assert 0. <= max_allocation_within_a_disease_to_a_country <= 1.

        non_tgf_budget_by_country = self.approach_b.non_tgf_budgets
        tgf_budget = self.approach_b.tgf_budget

        print("Running GreedyAlgorithm.run_forward...", end="")

        budget_increment = tgf_budget / n_steps

        # Generate initial states
        states = self.generate_initial_state(
            starting_cost=non_tgf_budget_by_country, budget_increment=budget_increment
        )

        # Start by assuming that no country has any allocation of TGF funding
        tgf_allocation = {_c: 0.0 for _c in self._database.countries}


        def countries_that_exceed_max_allocations(_tgf_allocation: dict) -> Set:
            """Return set of countries that have reached the maximum allocation"""
            diseases = ('hiv', 'tb', 'malaria')
            countries_exceeding = set()

            s = pd.Series(_tgf_allocation)
            s.index = s.index.map(lambda _s: (_s[0:-3], _s[-3:]))

            # consider the max amount that any country can receive
            fr_to_each_country = (s.groupby(axis=0, level=1).sum() / s.sum()).fillna(0.0)
            countries_exceeding_across_all_disease = fr_to_each_country.index[fr_to_each_country > max_allocation_to_a_country]

            countries_exceeding.update(set([
                f"{disease}{country}" for country in countries_exceeding_across_all_disease for disease in diseases]
            ))

            # consider the max amount that any country can receive within the disease
            for disease in diseases:
                _per_disease = s.loc[(disease, slice(None))]
                _per_disease = (_per_disease / _per_disease.sum()).fillna(0.0)
                countries_exceeding.update(
                    set([
                        f"{disease}{country}" for country in _per_disease.index[_per_disease > max_allocation_within_a_disease_to_a_country]
                    ])
                )

            return countries_exceeding.intersection(_tgf_allocation.keys())  # only return countries-disease combos that were defined originally


        while tgf_budget > sum(tgf_allocation.values()):

            # Determine which countries are not eligible to receive any more funding because the constrains have been
            # met, and use this to specify which countries cannot receive any more (`countries_not_allowed_to_change`).
            countries_exceeding = countries_that_exceed_max_allocations(tgf_allocation)

            # Determine the country for which the objective function is most reduced for the next increment:
            allocate_increment_to = (
                self.find_country_where_next_pop_leads_to_greatest_reduc_in_objfn(
                    states=states,
                    countries_not_allowed_to_change=countries_exceeding,
                )
            )

            if allocate_increment_to:
                tgf_allocation[
                    allocate_increment_to
                ] += budget_increment  # Record the allocation
                states[allocate_increment_to].pop(0)  # Update the states accordingly
            else:
                # No country can absorb the next increment
                break

        print("Done!")
        return tgf_allocation

    def run_backward(self, n_steps: int) -> Union[dict[str, float], None]:
        """Run the algorithm in "backward" mode, wherein we start each country at its gp and remove increments from
        each country until the costs that remain in each country can be met by the tgf budget.
        """
        non_tgf_budget_by_country = self.approach_b.non_tgf_budgets
        tgf_budget = self.approach_b.tgf_budget

        print("Running GreedyAlgorithm.run_backward...", end="")

        # Start by assuming that TGF can cover entire unmet need:
        tgf_allocation = {
            c: max(0.0, self._database.data[c].gp.cost - non_tgf_budget_by_country[c])
            for c in self._database.countries
        }

        amount_to_remove_from_countries = (
            self._database.portfolio_values_when_maximum_cost_in_all_countries.cost
            - sum(non_tgf_budget_by_country.values())
        ) - tgf_budget

        if not (amount_to_remove_from_countries > 0):
            warnings.warn(
                "Greedy Algorithm Backwards Mode does not work because there the total amount "
                "available in TGF_Budget Exceeds that required in the GP of each country."
            )
            return tgf_allocation

        budget_decrement = amount_to_remove_from_countries / n_steps

        # Generate initial states
        states = self.generate_initial_state(
            starting_cost=non_tgf_budget_by_country, budget_increment=-budget_decrement
        )

        while sum(tgf_allocation.values()) > tgf_budget:
            # Determine the country for which the objective function is most reduced for the next increment:
            allocate_increment_to = (
                self.find_country_where_next_pop_leads_to_greatest_reduc_in_objfn(
                    states
                )
            )

            if allocate_increment_to:
                tgf_allocation[
                    allocate_increment_to
                ] -= budget_decrement  # Record the allocation
                states[allocate_increment_to].pop(0)  # Update the states accordingly
            else:
                # No country can absorb the next increment
                break

        print("Done!")
        return tgf_allocation


class Optimisers:
    """Class containing the local and global optimisation routines."""

    def __init__(self, approach_b: ApproachB):
        self.approach_b = approach_b

    def to_minimise(self, x: np.array) -> float:
        """Return evaluation of the objective function, given an array of the allocation to each country."""

        non_tgf_budget_by_country = self.approach_b.non_tgf_budgets
        database = self.approach_b.dataset

        total_budget_by_country = {
            _c: x[_i] + non_tgf_budget_by_country[_c]
            for _i, _c in enumerate(database.countries)
        }
        results_given_budget = list(
            database.get_country_results_given_budgets(total_budget_by_country).values()
        )
        return self.approach_b.eval_objective_function(results_given_budget)

    def use_global_optimiser(self, start_from_random: bool) -> dict[str, float]:
        """We have a TGF Budget, and we wish to allocate in among countries, such that we minimise some function
        representing the total of cases and deaths across all the countries. We set this up as a
        constrained-optimisation problem in which the variables are the allocation of the TGF budget (which are
        additional to a basal level of funding from non-TGF sources).
        The constraints are:
         * the allocation to each country is non-negative
         * the total allocation of TGF funds for all countries does not exceed the total TGF budget.

        For the global optimisation, we use `dual_annealing` to do a global optimisation (but many options possible)
        (https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.dual_annealing.html).
        In this method - the constraint is represented as a penalty in the objective function.

        With `start_from_random`=True, we start from a randomly selected starting position; otherwise we start from the
        `tgf_budgets` defined for Approach A (in `analysis.tgf_budgets`).
        """
        database = self.approach_b.dataset
        non_tgf_budget_by_country = self.approach_b.non_tgf_budgets
        tgf_budget = self.approach_b.tgf_budget

        print(
            f"Running use_global_optimiser from {'random' if start_from_random else 'non-random'} start...",
            end="",
        )

        # Define the constraints and bounds:
        # 1) Represent the constraint that the total of the tgf allocations to each country cannot exceed tgf budget
        def to_minimise_with_constraint_as_penalty(x: np.array) -> float:
            """Add a penalty to the objective function if the constraints are not met."""
            eval_to_minimise = self.to_minimise(x)
            return (
                eval_to_minimise
                if ((tgf_budget + 1e-5) >= sum(x))
                else eval_to_minimise + 10_000
            )

        # 2) Bounds on the allocation to each country to be non-zero and no more than its unmet funding
        #    (it's trimmed to 1e-5 dollar allocation to the country, even when fully funded to allow bounds to be
        #     uniformly min < max.)
        unmet_funding = {
            c: max(1e-5, database.data[c].gp.cost - non_tgf_budget_by_country[c])
            for c in database.countries
        }
        bounds = [(0.0, unmet_funding[c]) for c in database.countries]

        # 3) Find starting point
        x0 = (
            self.starting_point_from_approach_a()
            if not start_from_random
            else self.randomly_chosen_starting_point()
        )

        # Run the algorithm
        sol = dual_annealing(
            to_minimise_with_constraint_as_penalty,
            x0=x0,
            bounds=bounds,
            initial_temp=20_000,
        )

        print("Done!")
        if (
            sol.success
            and (sum(sol.x) <= (tgf_budget + 1e-5))
            and all([x >= 0 for x in sol.x])
        ):
            return dict(zip(database.countries, sol.x))

    def use_local_minimiser(self, start_from_random: bool) -> dict[str, float]:
        """Using same approach as in `use_global_optimiser`, here we use a local minimiser: `minimize`.
        With `start_from_random`=True, we start from a randomly selected starting position; otherwise we start from the
        `tgf_budgets` defined for Approach A (in `analysis.tgf_budgets`).
        (https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html)
        """
        database = self.approach_b.dataset
        non_tgf_budget_by_country = self.approach_b.non_tgf_budgets
        tgf_budget = self.approach_b.tgf_budget

        print(
            f"Running use_local_optimiser from {'random' if start_from_random else 'non-random'} start...",
            end="",
        )

        # Define the constraints and bounds:
        # 1) Represent the constraint that the total of the tgf allocations to each country cannot exceed tgf budget
        constraint = LinearConstraint(
            np.ones(len(database.countries)), lb=0.0, ub=tgf_budget
        )

        # 2) Bounds on the allocation to each country to be non-zero and no more than its unmet funding
        #    (it's trimmed to 1e-5 dollar allocation to the country, even when fully funded to allow bounds to be
        #     uniformly min < max.)
        unmet_funding = {
            c: max(1e-5, database.data[c].gp.cost - non_tgf_budget_by_country[c])
            for c in database.countries
        }
        bounds = np.array([(0, unmet_funding[c]) for c in database.countries])

        # 3) Find reasonable starting point
        x0 = (
            self.starting_point_from_approach_a()
            if not start_from_random
            else self.randomly_chosen_starting_point()
        )

        # Run the minimization algorithm
        sol = minimize(
            lambda _x: self.to_minimise(_x),
            x0=x0,
            bounds=bounds,
            constraints=constraint,
        )

        # Check the results against the constraints.
        assert sum(sol.x) <= (tgf_budget + 1e-5)
        assert all([x >= 0 for x in sol.x])

        print("Done!")
        return dict(zip(database.countries, sol.x))

    def starting_point_from_approach_a(self) -> np.array:
        """Return a starting point `np.array` for the optimization that is the allocation defined in Approach A"""
        return np.array(list(self.approach_b.tgf_budgets.values()))

    def randomly_chosen_starting_point(self) -> np.array:
        """Suggest a randomly selected started point that complies with the constraint that the TGF allocation to a
        country cannot be such that the total funding to the country exceeds the cost of its GP.
        """

        database = self.approach_b.dataset
        non_tgf_budget_by_country = self.approach_b.non_tgf_budgets
        unmet_funding = {
            c: database.data[c].gp.cost - non_tgf_budget_by_country[c]
            for c in database.countries
        }
        countries = np.array(database.countries)
        tgf_budget = self.approach_b.tgf_budget

        def is_valid(_x: np.array):
            """Check if this is a valid solution for the TGF allocation."""
            return np.isclose(sum(_x), tgf_budget) and all(
                [0 <= _v <= _unmet for _v, _unmet in zip(_x, unmet_funding.values())]
            )

        final_allox = {_c: 0.0 for _c in countries}
        while not is_valid(np.array(list(final_allox.values()))):
            # Start by setting the allocation to a country to be some random fraction of its unmet need:
            putative_allox = {
                _c: unmet_funding[_c] * np.random.rand() for _c in countries
            }

            # If the sum of these amounts to each country exceeds the TGF total funds, then remove some from countries
            # (each country equally); Or, if the sum of these amounts to each country is less the TGF total funds, then
            # add more to each country (each country equally).
            re_allocate_to_each_country = (
                tgf_budget - sum(putative_allox.values())
            ) / len(countries)
            final_allox = {
                _c: putative_allox[_c] + re_allocate_to_each_country for _c in countries
            }

            # Repeat this procedure until a valid solution is valid

        assert is_valid(np.array(list(final_allox.values())))

        return np.array(list(final_allox.values()))


def add_list_of_results(list_of_results: list[ResultDatum]) -> ResultDatum:
    """Returns Results that is the sum of each element in a list of Results"""
    tot_cases, tot_deaths, tot_costs = 0.0, 0.0, 0.0
    for _res in list_of_results:
        tot_cases += _res.cases
        tot_deaths += _res.deaths
        tot_costs += _res.cost
    return ResultDatum(cases=tot_cases, deaths=tot_deaths, cost=tot_costs)




def get_dummy_country_result(rng=None):
    """Create a dummy set of results for a country."""

    def create_dummy_result_curve(
        the_budgets: Iterable[float],
        zero_budget_value: float,
        the_gp_cost: float,
        the_gp_value: float,
        the_beta_value: float,
        the_turn_value: float,
    ) -> np.array:
        """Construct a curve that conforms to our expectations of diminishing returns between budget and health_gains,
        that intersects the point (0, 0) and saturates at `value_at_max_cost` when the cost exceeds `max_cost`.
        We choose to represent this with a scaled logistic curve."""

        unscaled_logistic = 1.0 / (
            1.0
            + np.exp(-the_beta_value * ((the_gp_cost / the_turn_value) - the_budgets))
        )

        # Scale to be on vertical to [0, 1]:
        x = unscaled_logistic - min(unscaled_logistic)
        y = x / max(x)

        return the_gp_value + (zero_budget_value - the_gp_value) * y

    if rng is None:
        # if random generator not provided use own.
        rng = np.random.default_rng(seed=None)

    # Randomly choose some features of the results impact-cost curve
    zero_budget_cases = rng.random() * 0.1 * 10_000
    cfr = rng.random() * 0.25
    reduction_in_cases_in_gp = rng.random()
    cost_per_reduction_in_cases = 0.20 * rng.random() * 10_000
    beta = 0.01 + rng.random() * (0.01 - 0.01)  # rate of change in the logistic curve
    turn = 2.0

    # Derive the specification of the GP
    gp_cases = zero_budget_cases * (1.0 - reduction_in_cases_in_gp)
    gp_deaths = cfr * zero_budget_cases * (1.0 - reduction_in_cases_in_gp)
    gp_cost = reduction_in_cases_in_gp * cost_per_reduction_in_cases

    # Declare the specification of the GP
    gp = ResultDatum(cases=gp_cases, deaths=gp_deaths, cost=gp_cost)

    # Define the budget levels for which we have model results
    budgets = np.linspace(0, gp.cost, 15)

    results = pd.DataFrame(
        index=budgets,
        data={
            "cases": create_dummy_result_curve(
                budgets,
                zero_budget_value=zero_budget_cases,
                the_gp_cost=gp.cost,
                the_gp_value=gp.cases,
                the_beta_value=beta,
                the_turn_value=turn,
            ),
            "deaths": create_dummy_result_curve(
                budgets,
                zero_budget_value=zero_budget_cases * cfr,
                the_gp_cost=gp.cost,
                the_gp_value=gp.deaths,
                the_beta_value=beta,
                the_turn_value=turn,
            ),
        },
    ).rename_axis("cost")

    return results, gp




