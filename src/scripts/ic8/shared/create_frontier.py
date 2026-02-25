from typing import Iterable

from tgftools.filehandler import ModelResults
from tgftools.find_cost_effective_frontier import which_points_on_frontier


def filter_for_frontier(
        model_results: ModelResults,
        scenario_descriptor: str,
        years_for_obj_func: Iterable[int],
        years_for_funding: Iterable[int],
) -> ModelResults:
    """Filters model results to retain only non-dominated points on the cost-effectiveness frontier.

    Removes dominated strategies from the model results for the specified scenario.
    The objective function used to determine domination is the same as used in Approach B.

    Args:
        model_results: ModelResults object containing scenario data to filter.
        scenario_descriptor: Identifier for the scenario to filter (e.g., 'PF').
        years_for_obj_func: Years in which cases and deaths should be minimized
            for the objective function calculation.
        years_for_funding: Years for which costs are summed as the 'cost' of
            each strategy.

    Returns:
        ModelResults: A ModelResults object with dominated funding fractions removed,
            containing only strategies on the cost-effectiveness frontier.
    """

    # Summarise cases/death for each funding_fraction: sums within  `years_for_obj_func`
    cases_and_deaths = (
        model_results.df.loc[
            (
                scenario_descriptor,
                slice(None),
                slice(None),
                years_for_obj_func,
                ["cases", "deaths"],
            )
        ]["central"]
        .groupby(axis=0, level=["funding_fraction", "country", "indicator"])
        .sum()
        .unstack("indicator")
    )

    # Summarise cost for each funding_fraction: sums within `years_for_funding`
    costs = (
        model_results.df.loc[
            (
                scenario_descriptor,
                slice(None),
                slice(None),
                years_for_funding,
                ["cost"],
            )
        ]["central"]
        .groupby(axis=0, level=["funding_fraction", "country", "indicator"])
        .sum()
        .unstack("indicator")
    )

    # join these two dataframes:
    cost_impact_points = cases_and_deaths.join(costs).reset_index().sort_values(["country", "cost"]).reset_index(drop=True)

    for country in cost_impact_points.country.unique():
        df = cost_impact_points.loc[cost_impact_points.country == country].copy().reset_index()
        df['obj_col'] = (df.cases/df.cases.max() + df.deaths/df.deaths.max())
        pts_on_curve = df[['cost', 'obj_col']].to_numpy()
        a = which_points_on_frontier(pts_on_curve, upper_edge=False)
        fundingfractions_nondominated = df.loc[a, 'funding_fraction'].values
        fundingfractions_dominated = set(df['funding_fraction'].unique()) - set(fundingfractions_nondominated)
        model_results.df = model_results.df.drop(
            model_results.df.loc[
                (model_results.df.index.get_level_values('country') == country)
                & (model_results.df.index.get_level_values('funding_fraction').isin(fundingfractions_dominated))
                & (model_results.df.index.get_level_values('scenario_descriptor') == scenario_descriptor)
            ].index
        )

    return model_results
