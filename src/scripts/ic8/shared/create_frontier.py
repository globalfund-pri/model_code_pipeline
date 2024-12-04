from tgftools.filehandler import ModelResults, Parameters
from tgftools.find_cost_effective_frontier import which_points_on_frontier
from tgftools.utils import get_root_path, open_file

project_root = get_root_path()
parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")


def filter_for_frontier(model_results: ModelResults):
    """ This will convert the cost impact curves in the raw model output file to
    a frontier-based cost impact curve"""

    print("hello")
    years_for_obj_func = parameters.get("YEARS_FOR_OBJ_FUNC")
    years_for_funding = parameters.get("YEARS_FOR_FUNDING")
    scenario_descriptor = "PF"
    # ---------------

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

    # Summarise cost for each funding_fraction: sums within `self.years_for_funding`
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
