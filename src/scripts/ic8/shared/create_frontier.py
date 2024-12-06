from typing import Iterable

from tgftools.filehandler import ModelResults, Parameters
from tgftools.find_cost_effective_frontier import which_points_on_frontier
from tgftools.utils import get_root_path, open_file


def filter_for_frontier(
        model_results: ModelResults,
        scenario_descriptor: str,
        years_for_obj_func: Iterable[int],
        years_for_funding: Iterable[int],
) -> ModelResults:
    """Returns instance of ModelResults from which have been filters points that are dominated.
    This is done only for the `scenario_descriptor` specified.
    The objective function used to determine domination is the same as used in Approach B, which requires specifying:
     * 'years_for_obj_func': the years in which cases and deaths should be minimised
     * 'years_for_funding': the years for which costs are summed as the 'cost' of the strategy'
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

    # Summarise cost for each funding_fraction
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
        fundingfractions_nondominated = df.loc[a,'funding_fraction'].values
        fundingfractions_dominated = set(df['funding_fraction'].unique()) - set(fundingfractions_nondominated)
        model_results.df = model_results.df.drop(
            model_results.df.loc[
                (model_results.df.index.get_level_values('country') == country)
                & (model_results.df.index.get_level_values('funding_fraction').isin(fundingfractions_dominated))
                & (model_results.df.index.get_level_values('scenario_descriptor') == scenario_descriptor)
            ].index
        )

    return model_results
