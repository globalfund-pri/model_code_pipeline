import warnings
from collections import Counter
from pathlib import Path
from pprint import pprint
from typing import Iterable, NamedTuple, Optional, Union, List

import matplotlib
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.optimize import LinearConstraint, dual_annealing, minimize


from tgftools.utils import get_root_path
from tgftools.write_to_pdf import build_pdf

"""Approach B allocation optimization for TGF funding across countries.

This module contains all the classes needed to accomplish "Approach B", whereby
TGF funding is allocated across countries to optimize health outcomes according
to a defined objective function.

Important Notes:
    The optimization works on a full set of model results from 0% to 100% of
    the possible costs that a program could use. Where results do not span that
    range, the implementation handles out-of-bounds costs as follows:

    * The highest cost in the model results is taken as the maximum amount a
      country could receive to generate the greatest possible impact.
    * If the non-TGF budget is not within the range of costs covered in the
      model results, the optimizers will not run. This is because they need
      to evaluate a scenario where TGF budget to a country is zero. Not being
      able to do so would introduce an artificial constraint to the optimization
      based on which model results happen to have been run.
    * If necessary and accepted, this constraint could be removed by updating
      the bounds in the optimizers and editing the greedy algorithms to start
      countries at their respective minima when going forward, or stop at their
      respective maxima when going backwards.
"""


def find_max_ignoring_inf(x: Iterable[float]) -> float:
    """Return the maximum value in an iterable, ignoring infinite values.

    Args:
        x: An iterable of float values.

    Returns:
        The maximum finite value in the iterable.
    """
    return x[np.isfinite(x)].max()

class ResultDatum(NamedTuple):
    """Result data for cases and deaths at a given program cost.

    Attributes:
        cases: Number of disease cases.
        deaths: Number of deaths.
        cost: Program cost in dollars.
    """

    cases: float
    deaths: float
    cost: float


class ApproachBResult(NamedTuple):
    """Results from an Approach B allocation analysis.

    Attributes:
        tgf_budget_by_country: TGF budget allocation for each country.
        non_tgf_budget_by_country: Non-TGF budget for each country.
        total_budget_by_country: Total budget (TGF + non-TGF) for each country.
        country_results: Health outcome results for each country.
        total_result: Aggregated health outcomes across all countries.
    """

    tgf_budget_by_country: dict[str, float]
    non_tgf_budget_by_country: dict[str, float]
    total_budget_by_country: dict[str, float]
    country_results: dict[str, ResultDatum]
    total_result: ResultDatum


class ApproachB:
    """Class for running allocation analysis using model output files.

    This class orchestrates the optimization of TGF funding allocation across
    countries using various optimization methods including greedy algorithms
    and global/local optimizers.

    Attributes:
        dataset: Dataset containing country-level model results.
        non_tgf_budgets: Dictionary mapping country names to non-TGF budgets.
        tgf_budgets: Dictionary mapping country names to TGF budgets.
        tgf_budget: Total TGF budget across all countries.
        greedy_algorithm: Instance of GreedyAlgorithm for heuristic optimization.
        optimisers: Instance of Optimisers for numerical optimization methods.
    """

    def __init__(
        self,
        model_results: pd.DataFrame,
        non_tgf_budgets: pd.DataFrame,
        tgf_budgets: pd.DataFrame,
    ):
        """Initialize ApproachB with model results and budget data.

        Args:
            model_results: DataFrame with columns country, cases, deaths, cost.
                Multiple rows per country, one for each costing value.
            non_tgf_budgets: DataFrame with columns country and value.
                One row per country specifying non-TGF budget.
            tgf_budgets: DataFrame with columns country and value.
                One row per country specifying TGF budget allocation.
        """
        # Create database of country level information
        self.dataset = ApproachBDataSet(model_results=model_results)

        # Load the budget files
        self.non_tgf_budgets = non_tgf_budgets.set_index("country")["value"].to_dict()
        self.tgf_budgets = (
            tgf_budgets.set_index("country")["value"].fillna(0.0).to_dict()
        )
        self.tgf_budget = sum(self.tgf_budgets.values())

        # Instantiate classes that will do the optimizations
        self.greedy_algorithm = GreedyAlgorithm(self)
        self.optimisers = Optimisers(self)

        # Do the checks
        self._checks()

    def _checks(self):
        """Validate that model results support required funding scenarios.

        Check if scenarios with zero TGF funding can be evaluated for each
        country. This ensures that model results exist that allow interpolation
        at the non-TGF funding level, enabling examination of solutions where
        TGF funding to a country is zero.

        Raises:
            UserWarning: If non-TGF funding falls outside the range of costs
                covered in the model results for any country.
        """
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
        """Run both Approach A and Approach B analyses and generate report.

        Args:
            plt_show: Whether to display plots. Defaults to False.
            filename: Path to save report PDF. If None, no PDF is saved.
            **kwargs: Additional arguments passed to do_approach_b.

        Returns:
            Dictionary with keys 'a' and 'b' containing ApproachBResult instances
            for Approach A and Approach B respectively.
        """
        results = {"a": self.do_approach_a(), "b": self.do_approach_b(**kwargs)}
        self.do_report(results=results, plt_show=plt_show, filename=filename)
        return results

    def gen_analysis_result_from_tgf_budget_by_country(
        self, tgf_budget_by_country: dict[str, float]
    ) -> ApproachBResult:
        """Generate analysis results given a TGF budget allocation.

        Args:
            tgf_budget_by_country: Dictionary mapping country names to TGF
                budget allocations.

        Returns:
            ApproachBResult containing budget allocations and health outcomes
            for each country and in aggregate.
        """
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
        """Run Approach A analysis using pre-specified TGF budget allocations.

        Approach A uses the TGF budget allocations as provided in the input
        data without optimization.

        Returns:
            ApproachBResult containing health outcomes for each country given
            their pre-specified funding levels.
        """
        return self.gen_analysis_result_from_tgf_budget_by_country(
            tgf_budget_by_country=self.tgf_budgets
        )

    def do_approach_b(
        self,
        methods: Optional[Iterable[str]],
        provide_best_only: bool,
    ) -> Union[ApproachBResult, tuple[dict[str, ApproachBResult], str]]:
        """Run Approach B optimization to allocate TGF budget across countries.

        Optimize the allocation of TGF budget across countries to minimize the
        objective function (combination of cases and deaths) using specified
        optimization methods.

        Args:
            methods: List of optimization methods to use. Can include:
                - 'ga_forwards': Greedy algorithm starting with $0 allocations.
                - 'ga_backwards': Greedy algorithm starting from Approach A allocations.
                - 'global_start_at_a': Global optimization from Approach A allocations.
                - 'global_start_at_random': Global optimization from random start.
                - 'local_start_at_a': Local optimization from Approach A allocations.
                - 'local_start_at_random': Local optimization from random start.
                If None, all methods are used with one random repetition.
                Can contain repeats of random methods for multiple random starts.
            provide_best_only: If True, return only the best result. If False,
                return all results and the key to the best method.

        Returns:
            If provide_best_only is True: ApproachBResult for the best method.
            If provide_best_only is False: Tuple of (dict of all results, best method key).
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
                {"ga: forwards": self.greedy_algorithm.run_forward(n_steps=10_000)}
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
        """Generate plots of model results, GP, and interpolations for countries.

        Creates visualization of actual model results, Gaussian process fits,
        and interpolated results for cases and deaths versus cost.

        Args:
            country: Specific country to plot. If None, plots all countries.
            plt_show: Whether to display plots. Defaults to True.
            filename: Path to save plots as PDF. If None, no PDF is saved.

        Returns:
            List of matplotlib Figure objects, one per country.
        """
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
        """Produce summary plots from Approach B results.

        Generate comprehensive visualization of results including allocation
        comparisons, health impacts, and country-specific outcomes.

        Args:
            results: Dictionary containing 'a' and 'b' keys with ApproachBResult
                values or tuples of results.
            plt_show: Whether to display plots. Defaults to True.
            filename: Path to save plots as PDF. If None, no PDF is saved.
        """
        if not plt_show and not filename:
            # No need to do anything, as results will not be displayed or saved
            return

        content_for_pdf = {}

        # - compare results of the optimization analysis (if more than one method has been used)
        if not isinstance(results["b"], ApproachBResult):
            b_methods = results["b"][0]
            allocations = {method: result.tgf_budget_by_country for method, result in b_methods.items()}
            allocations.update({
                'Approach A': results["a"].tgf_budget_by_country
            })
            tgf_funding_allox = pd.DataFrame(allocations)

            fig, ax = plt.subplots()
            tgf_funding_allox.plot(ax=ax, marker='x')
            ax.set_ylabel('Funding Allocated to the Country')
            ax.set_xlabel('Country')
            ax.set_xticks(list(range(len(tgf_funding_allox.index))),
                          labels=tgf_funding_allox.index.to_list())
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
        """Generate standard plots for Approach B results.

        Create comprehensive visualizations comparing Approach A and B including
        portfolio-level outcomes, funding allocations, and country-specific results.

        Args:
            results: Dictionary with 'a' and 'b' keys containing ApproachBResult
                instances for each approach.
            plt_show: Whether to display plots. Defaults to True.

        Returns:
            List of matplotlib Figure objects for all generated plots.
        """

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
        """Evaluate the objective function for a set of country results.

        Calculate the normalized sum of cases and deaths relative to the
        portfolio-level global plan values. This method can be overridden in
        subclasses or redirected to another function for custom objective functions.

        Args:
            results: List of ResultDatum objects, one per country.

        Returns:
            Objective function value (lower is better). Computed as the sum of
            normalized cases and normalized deaths.
        """
        totals = add_list_of_results(results)
        portfolio_gp = self.dataset.portfolio_values_when_maximum_cost_in_all_countries
        return (totals.cases / portfolio_gp.cases) + (totals.deaths / portfolio_gp.deaths)

class ApproachBDataSet:
    """Container for country-level model results and helper functions.

    Manages a collection of Country objects and provides utilities for
    accessing and analyzing results across multiple countries.

    Attributes:
        countries: Sorted list of country names.
        data: Dictionary mapping country names to Country objects.
    """

    def __init__(self, model_results: pd.DataFrame):
        """Initialize dataset from model results.

        Args:
            model_results: DataFrame with columns country, cases, deaths, cost.
                Multiple rows per country for different cost scenarios.
        """
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
        """Get portfolio results when all countries are at maximum cost.

        Returns:
            ResultDatum representing the sum of global plan results across
            all countries at their highest cost scenarios.
        """
        return add_list_of_results([self.data[_country].gp for _country in self.countries])

    def get_country_results_given_budgets(
        self, budget_by_country: dict = None
    ) -> dict[str, ResultDatum]:
        """Get country-specific results for given budget allocations.

        Args:
            budget_by_country: Dictionary mapping country names to budget amounts.

        Returns:
            Dictionary mapping country names to ResultDatum objects containing
            health outcomes at the specified budget levels.
        """
        return {
            _country: self.data[_country].get_result_for_a_cost(
                budget_by_country[_country]
            )
            for _country in self.countries
        }

    def get_cost_vs_impact_scaled_to_gp(self) -> dict[str, pd.DataFrame]:
        """Get cost versus impact scaled to global plan for all countries.

        Compile cost-impact relationships for each country, normalized relative
        to their global plan values, and interpolate onto a standard grid.

        Returns:
            Dictionary with keys 'cases' and 'deaths', each containing a DataFrame
            where rows represent cost as fraction of GP cost (0 to 1.1) and
            columns represent countries, with values as fraction of GP impact.
        """
        costs_per_gp = np.linspace(0, 1.1, 100)

        cases_df = pd.DataFrame(columns=self.countries, index=costs_per_gp)
        deaths_df = pd.DataFrame(columns=self.countries, index=costs_per_gp)

        for _name, _country in self.data.items():
            raw_results = _country.get_cost_vs_impact_scaled_to_gp()
            # Use interpolation to put this onto a standard set of cost_per_gp
            cases_df.loc[:, _name] = np.interp(
                costs_per_gp, raw_results.index, raw_results.cases
            )
            deaths_df.loc[:, _name] = np.interp(
                costs_per_gp, raw_results.index, raw_results.deaths
            )

        return {"cases": cases_df, "deaths": deaths_df}

    def do_checks(self) -> None:
        """Run validation checks on all countries.

        Execute checks on each country's data and report any issues found.
        Prints results and raises a warning if any abnormalities are detected.

        Raises:
            UserWarning: If any country data fails validation checks.
        """
        results = dict()
        for _name, _country in self.data.items():
            results[_name] = _country.check()

        if any([len(x) > 0 for x in results.values()]):
            pprint(results)
            warnings.warn(
                UserWarning(
                    "Some abnormalities detected in the construction of the Country dataclasses."
                )
            )


class Country:
    """Container for a single country's model results and analysis methods.

    Stores health outcome data at various cost levels for a country and provides
    methods for interpolation and analysis.

    Attributes:
        name: Country name.
        results: DataFrame indexed by cost with columns for cases and deaths.
        gp: ResultDatum for the global plan (maximum cost scenario).
    """

    def __init__(
        self, model_results: pd.DataFrame, name: str,
    ):
        """Initialize Country with model results.

        Args:
            model_results: DataFrame with columns country, cases, deaths, cost.
            name: Name of the country.
        """
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
    ) -> pd.DataFrame:
        """Load and process model results for a specific country.

        Extract model results for the specified country and organize them
        by cost level.

        Args:
            model_results: DataFrame with columns country, cases, deaths, cost.
                If None and name is "__Dummy__", generates dummy data.
            name: Name of the country. Use "__Dummy__" to generate test data.

        Returns:
            DataFrame indexed by cost with columns cases and deaths, sorted
            by cost in ascending order.
        """
        if (model_results is None) and (name == "__Dummy__"):
            # Create dummy data
            return get_dummy_country_result()

        # Get the results (only cases and deaths) for this country
        results_data = model_results
        _results = (
            results_data.loc[results_data.country == name]
            .set_index("cost")
            .sort_index()[["cases", "deaths"]]
        )
        return _results

    def get_result_for_a_cost(self, cost: Union[int, float]) -> ResultDatum:
        """Get health outcomes for a specified program cost.

        Interpolate between model results to estimate health outcomes at
        the requested cost level. If cost exceeds the maximum modeled cost,
        returns outcomes at the maximum cost (impact is capped).

        Args:
            cost: Program cost in dollars.

        Returns:
            ResultDatum containing interpolated cases, deaths, and the cost.

        Raises:
            ValueError: If cost is below the minimum cost in model results.
        """
        if min(self.results.index) <= cost <= max(self.results.index):
            _cases: float = np.interp(
                cost, np.array(self.results.index), np.array(self.results.cases)
            )
            _deaths: float = np.interp(
                cost, np.array(self.results.index), np.array(self.results.deaths)
            )
        elif cost >= max(self.results.index):
            # If funding exceeds max_cost, impact is capped at the maximum cost level
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
        """Get cost versus impact normalized to global plan values.

        Scale cost and health impacts as fractions of the global plan (GP)
        values, showing how impact scales with funding level.

        Returns:
            DataFrame indexed by cost as fraction of GP cost, with columns
            for cases and deaths as fractions of GP values. Returns NaN if
            GP cases or deaths are zero.
        """
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
        """Validate that country data meets expected constraints.

        Verify that interpolation works correctly and that health outcomes
        (cases and deaths) decrease monotonically with increasing cost.

        Returns:
            List of error messages. Empty list if all checks pass.
        """
        results = list()

        # Check that interpolation works for values between lowest and highest cost
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
    """Heuristic algorithm for optimal TGF budget allocation across countries.

    Implements forward and backward greedy algorithms that allocate budget
    incrementally to maximize health impact at each step.

    Attributes:
        approach_b: Reference to the parent ApproachB instance.
        _database: Reference to the ApproachBDataSet containing country data.
    """

    def __init__(self, approach_b: ApproachB):
        """Initialize GreedyAlgorithm with ApproachB instance.

        Args:
            approach_b: Parent ApproachB instance containing dataset and budgets.
        """
        self.approach_b = approach_b
        self._database = approach_b.dataset

    def generate_initial_state(
        self, starting_cost: dict[str, float], budget_increment: float
    ) -> dict[str, list[ResultDatum]]:
        """Generate initial state for greedy algorithm with incremental costs.

        Create a dictionary of results for each country at incremental cost
        levels. The first element is the starting program, with subsequent
        elements representing cost increments.

        Args:
            starting_cost: Dictionary mapping country names to starting costs.
            budget_increment: Size of budget increment (positive for forward,
                negative for backward algorithm).

        Returns:
            Dictionary mapping country names to lists of ResultDatum objects
            at incremental cost levels. List length is one if no deviations
            from starting position are possible.
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
        """Get results at incremental cost levels for a country.

        Pre-compute results at regular cost intervals to improve algorithm
        efficiency by avoiding repeated interpolation calls.

        Args:
            country: Country object containing model results.
            minimum_cost: Starting cost level.
            increments: Step size for cost increments. Positive for forward
                (minimum_cost to GP cost), negative for backward (GP cost
                to minimum_cost).

        Returns:
            List of ResultDatum objects at incremental cost levels. List has
            length >= 1, with first element at the starting cost.

        Raises:
            AssertionError: If increments is not finite.
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
        self, states
    ) -> Optional[str]:
        """Find country where next increment yields greatest objective reduction.

        Evaluate which country would produce the largest reduction in the
        objective function if it receives the next budget increment.

        Args:
            states: Dictionary mapping country names to lists of ResultDatum
                objects at incremental cost levels.

        Returns:
            Country name that yields the greatest objective function reduction,
            or None if no more increments are possible for any country.
        """
        reduction_in_obj_function_by_country = dict()

        current_obj_func = self._eval_objective_function(
            [states[_c][0] for _c in states]
        )
        _countries_that_can_pop = [_c for _c in states if (len(states[_c]) > 1)]

        if not _countries_that_can_pop:
            # No country can absorb the increment
            return None

        for _country_to_try in _countries_that_can_pop:
            # Compile list of results for all countries where results for all
            # countries other than _country_to_try are at their current funding level
            __tmp_results = [states[_c][0] for _c in states if _c != _country_to_try]

            # Add result for _country_to_try at increased funding (if possible)
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
        """Evaluate objective function using parent ApproachB instance.

        Args:
            results: List of ResultDatum objects for evaluation.

        Returns:
            Objective function value.
        """
        return self.approach_b.eval_objective_function(results)

    @staticmethod
    def get_current_results(_states):
        """Get current results for all countries at their current funding levels.

        Args:
            _states: Dictionary mapping country names to lists of ResultDatum.

        Returns:
            List of ResultDatum objects at current funding level (0th position)
            for each country.
        """
        return [_states[_c][0] for _c in _states]

    def run_forward(self, n_steps: int) -> dict[str, float]:
        """Run forward greedy algorithm starting from non-TGF budgets.

        Start each country at its non-TGF budget and incrementally allocate
        TGF budget to the country that yields the greatest reduction in the
        objective function at each step.

        Args:
            n_steps: Number of increments to divide the TGF budget into.

        Returns:
            Dictionary mapping country names to final TGF budget allocations.
        """
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

        while tgf_budget > sum(tgf_allocation.values()):
            # Determine the country for which the objective function is most reduced for the next increment:
            allocate_increment_to = (
                self.find_country_where_next_pop_leads_to_greatest_reduc_in_objfn(
                    states
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
        """Run backward greedy algorithm starting from global plan allocations.

        Start each country at its global plan cost and incrementally remove
        funding from the country that minimizes the increase in the objective
        function, until total allocations match the TGF budget.

        Args:
            n_steps: Number of decrements to divide the budget reduction into.

        Returns:
            Dictionary mapping country names to final TGF budget allocations,
            or None if the algorithm cannot run (e.g., TGF budget exceeds
            total global plan cost).
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
    """Container for local and global optimization routines.

    Implements numerical optimization methods (local and global) for
    allocating TGF budget across countries to minimize the objective function.

    Attributes:
        approach_b: Reference to the parent ApproachB instance.
    """

    def __init__(self, approach_b: ApproachB):
        """Initialize Optimisers with ApproachB instance.

        Args:
            approach_b: Parent ApproachB instance containing dataset and budgets.
        """
        self.approach_b = approach_b

    def to_minimise(self, x: np.array) -> float:
        """Evaluate objective function for a given TGF allocation array.

        Convert allocation array to total budgets and compute the objective
        function value.

        Args:
            x: Array of TGF budget allocations, one per country in the order
                of dataset.countries.

        Returns:
            Objective function value for the given allocation.
        """
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
        """Optimize TGF allocation using global optimization (dual annealing).

        Set up and solve a constrained optimization problem to minimize the
        objective function representing total cases and deaths across countries.
        Uses scipy.optimize.dual_annealing for global optimization.

        Constraints:
            * Allocation to each country is non-negative
            * Total TGF allocation does not exceed the total TGF budget
            * Allocation to each country does not exceed its unmet funding need

        Args:
            start_from_random: If True, start from a random allocation. If False,
                start from Approach A allocations.

        Returns:
            Dictionary mapping country names to optimized TGF budget allocations,
            or None if optimization fails to satisfy constraints.
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
        """Optimize TGF allocation using local optimization (minimize).

        Set up and solve a constrained optimization problem using local
        minimization (scipy.optimize.minimize). Same constraints as global
        optimizer, but uses local descent from starting position.

        Args:
            start_from_random: If True, start from a random allocation. If False,
                start from Approach A allocations.

        Returns:
            Dictionary mapping country names to optimized TGF budget allocations.

        Raises:
            AssertionError: If solution violates constraints.
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
        """Get starting point array from Approach A allocations.

        Returns:
            Array of TGF budget allocations from Approach A, in the order
            of dataset.countries.
        """
        return np.array(list(self.approach_b.tgf_budgets.values()))

    def randomly_chosen_starting_point(self) -> np.array:
        """Generate a random valid starting point for optimization.

        Create a random TGF allocation that satisfies all constraints:
        total equals TGF budget, all allocations non-negative, and no country
        receives more than its unmet funding need.

        Returns:
            Array of valid random TGF budget allocations, in the order of
            dataset.countries.
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
            """Check if allocation is valid (sums to budget, within bounds).

            Args:
                _x: Array of TGF allocations.

            Returns:
                True if allocation is valid, False otherwise.
            """
            return np.isclose(sum(_x), tgf_budget) and all(
                [0 <= _v <= _unmet for _v, _unmet in zip(_x, unmet_funding.values())]
            )

        final_allox = {_c: 0.0 for _c in countries}
        while not is_valid(np.array(list(final_allox.values()))):
            # Start by setting allocation to a random fraction of unmet need
            putative_allox = {
                _c: unmet_funding[_c] * np.random.rand() for _c in countries
            }

            # Adjust all countries equally to meet the total TGF budget constraint
            re_allocate_to_each_country = (
                tgf_budget - sum(putative_allox.values())
            ) / len(countries)
            final_allox = {
                _c: putative_allox[_c] + re_allocate_to_each_country for _c in countries
            }

            # Repeat until a valid solution is found

        assert is_valid(np.array(list(final_allox.values())))

        return np.array(list(final_allox.values()))


def add_list_of_results(list_of_results: list[ResultDatum]) -> ResultDatum:
    """Aggregate a list of results into a single ResultDatum.

    Sum cases, deaths, and costs across all ResultDatum objects in the list.

    Args:
        list_of_results: List of ResultDatum objects to aggregate.

    Returns:
        Single ResultDatum with summed cases, deaths, and costs.
    """
    tot_cases, tot_deaths, tot_costs = 0.0, 0.0, 0.0
    for _res in list_of_results:
        tot_cases += _res.cases
        tot_deaths += _res.deaths
        tot_costs += _res.cost
    return ResultDatum(cases=tot_cases, deaths=tot_deaths, cost=tot_costs)




def get_dummy_country_result(rng=None):
    """Create dummy model results for testing purposes.

    Generate synthetic country data with realistic diminishing returns curves
    for cases and deaths versus budget.

    Args:
        rng: Random number generator. If None, creates a new default generator.

    Returns:
        Tuple of (results DataFrame, global plan ResultDatum) where results
        is indexed by cost with columns for cases and deaths.
    """

    def create_dummy_result_curve(
        the_budgets: Iterable[float],
        zero_budget_value: float,
        the_gp_cost: float,
        the_gp_value: float,
        the_beta_value: float,
        the_turn_value: float,
    ) -> np.array:
        """Construct a curve with diminishing returns using a scaled logistic.

        Create a curve representing diminishing returns between budget and
        health outcomes that passes through the zero-budget point and saturates
        at the global plan value.

        Args:
            the_budgets: Array of budget values.
            zero_budget_value: Health outcome value at zero budget.
            the_gp_cost: Global plan cost.
            the_gp_value: Global plan health outcome value.
            the_beta_value: Rate parameter for the logistic curve.
            the_turn_value: Turning point parameter for the logistic curve.

        Returns:
            Array of health outcome values at the specified budget levels.
        """
        unscaled_logistic = 1.0 / (
            1.0
            + np.exp(-the_beta_value * ((the_gp_cost / the_turn_value) - the_budgets))
        )

        # Scale to vertical range [0, 1]
        x = unscaled_logistic - min(unscaled_logistic)
        y = x / max(x)

        return the_gp_value + (zero_budget_value - the_gp_value) * y

    if rng is None:
        # If random generator not provided, use default
        rng = np.random.default_rng(seed=None)

    # Randomly choose features of the impact-cost curve
    zero_budget_cases = rng.random() * 0.1 * 10_000
    cfr = rng.random() * 0.25
    reduction_in_cases_in_gp = rng.random()
    cost_per_reduction_in_cases = 0.20 * rng.random() * 10_000
    beta = 0.01 + rng.random() * (0.01 - 0.01)  # Rate of change in logistic curve
    turn = 2.0

    # Derive the specification of the global plan
    gp_cases = zero_budget_cases * (1.0 - reduction_in_cases_in_gp)
    gp_deaths = cfr * zero_budget_cases * (1.0 - reduction_in_cases_in_gp)
    gp_cost = reduction_in_cases_in_gp * cost_per_reduction_in_cases

    # Create the global plan specification
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




