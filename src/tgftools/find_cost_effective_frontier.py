import pandas as pd
from scipy.spatial import ConvexHull
import matplotlib.pyplot as plt
import numpy as np


def find_cost_effective_frontier(points: np.array) -> np.array:
    """Return the points on the cost-effectiveness frontier.
    Accepts points in an np.array of the form [(cost, impact), ...], and return an np.array of the same form but only
    including the non-dominated points on the frontier, and sorted in ascedning cost order. The froniter includes the
    points that give the GREATEST impact for the cost.
    """

    # Start by efficiently computing the Convex Hull (the outside edge of all the points)
    hull = ConvexHull(points)
    df = pd.DataFrame(points[hull.vertices])

    # Get dataframe of the points on the hull and sort by ascending cost
    df = df.sort_values(by=0, ascending=True)

    # Remove those points that don't trace the upper edge of the polygon
    cumulative_max_impact = df[1].cummax()
    pts_on_the_frontier = df.loc[df[1] >= cumulative_max_impact].values

    return pts_on_the_frontier