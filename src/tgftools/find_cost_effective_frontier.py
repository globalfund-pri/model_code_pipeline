import pandas as pd
from scipy.spatial import ConvexHull
import numpy as np


def find_cost_effective_frontier(points: np.array) -> np.array:
    """Return the points on the cost-effectiveness frontier.
    Accepts points in `np.array` of the form [(cost, impact), ..., ], and return `np.array` of the same form but only
    including the non-dominated points on the frontier, and sorted in ascending cost order. The frontier includes the
    points that give the GREATEST impact for the cost.
    """

    # Start by efficiently computing the Convex Hull (polygon of the outside edge of all the points)
    hull = ConvexHull(points)

    # Get dataframe of the points on the hull and sort by ascending cost
    df = pd.DataFrame(points[hull.vertices]).sort_values(by=0, ascending=True)

    # Remove those points that don't trace the upper edge of the polygon
    return df.loc[df[1] >= df[1].cummax()].values


def which_points_on_frontier(points: np.array) -> np.array:
    """Returns the indices of the points that are the cost-effective frontier"""

    pts_on_frontier = find_cost_effective_frontier(points)

    # Return the index of the points on the frontier
    index_of_points_on_frontier = list()
    for ix, (x, y), in enumerate(points):
        for (xf, yf) in pts_on_frontier:
            if xf == x and yf == y:
                index_of_points_on_frontier.append(ix)
                continue

    return index_of_points_on_frontier




