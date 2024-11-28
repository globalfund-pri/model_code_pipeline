from scipy.spatial import ConvexHull
import numpy as np


def find_cost_effective_frontier(points: np.array, upper_edge: bool = True) -> np.array:
    """Return the points on the cost-effectiveness frontier.
    Accepts points in `np.array` of the form [(cost, value), ..., ], and returns `np.array` of the same form but only
    including the non-dominated points on the frontier, and sorted in ascending cost order.
     * If `upper_edge=True`, then frontier includes the points that give the GREATEST value for the cost.
     * If `upper_edge=False`, then frontier includes the points that give the SMALLEST value for the cost.
    """

    # Start by efficiently computing the Convex Hull (polygon of the outside edge of all the points)
    hull = ConvexHull(points)

    def get_lower(polygon):
        """Find the lower edge of the convex hull, between the lowest cost point and the lowest value point.
        From https://stackoverflow.com/a/76839030
        This relies on the fact that the vertices are given in anti-clockwise order, so, as we read from the point with
        the lowest cost to the point with the lowest value, we get the lower part of the hull."""
        minx = np.argmin(polygon[:, 0])  # index of lowest cost point
        maxx = np.argmin(polygon[:, 1]) + 1  # index of lowest value point
        if minx >= maxx:
            lower_curve = np.concatenate([polygon[minx:], polygon[:maxx]])
        else:
            lower_curve = polygon[minx:maxx]
        return lower_curve

    def get_upper(polygon):
        """Find the upper edge of the convex hull, between the lowest cost point and the highest value point.
        Based on the solution for `get_lower()`. We reverse the order of points so that they are in clockwise order,
        and then read from the lowest cost point to the highest value point.."""

        # Reverse order of points in polygon so that it's going clockwise
        polygon = np.flip(polygon, axis=0)

        minx = np.argmin(polygon[:, 0])  # index of lowest cost point
        maxx = np.argmax(polygon[:, 1]) + 1  # index of highest value point

        if minx >= maxx:
            lower_curve = np.concatenate([polygon[minx:], polygon[:maxx]])
        else:
            lower_curve = polygon[minx:maxx]
        return lower_curve

    if upper_edge:
        frontier = get_upper(points[hull.vertices])
    else:
        frontier = get_lower(points[hull.vertices])

    # # PLots for checking
    # lfrontier = get_lower(points[hull.vertices])
    # ufrontier = get_upper(points[hull.vertices])
    # import matplotlib.pyplot as plt
    # pts_on_the_hull = points[hull.vertices]
    # fig, ax = plt.subplots(ncols=1, figsize=(4, 4))
    # ax.set_title('Frontier')
    # ax.plot(points[:, 0], points[:, 1], '.', color='black', label='points')
    # ax.plot(pts_on_the_hull[:, 0], pts_on_the_hull[:, 1],
    #         'o', linestyle='-', mec='b', lw=1, markersize=10, color='none', label='hull')
    # ax.plot(pts_on_the_hull[:, 0], pts_on_the_hull[:, 1],
    #         linestyle='-', color='b')
    # ax.plot(lfrontier[:, 0], lfrontier[:, 1],
    #         '*', linestyle='-', mec='r', lw=1, markersize=10, color='none', label='lower frontier')
    # ax.plot(lfrontier[:, 0], lfrontier[:, 1],
    #         linestyle='-', color='r')
    # ax.plot(ufrontier[:, 0], ufrontier[:, 1],
    #         '*', linestyle='-', mec='g', lw=1, markersize=10, color='none', label='upper frontier')
    # ax.plot(ufrontier[:, 0], ufrontier[:, 1],
    #         linestyle='-', color='g')
    # ax.set_xlabel('Cost')
    # ax.set_ylabel('Value')
    # ax.legend()
    # fig.tight_layout()
    # fig.show()

    return frontier


def which_points_on_frontier(points: np.array, **kwargs) -> np.array:
    """Returns the indices of the points that are the cost-effective frontier"""

    pts_on_frontier = find_cost_effective_frontier(points, **kwargs)

    # Return the index of the points on the frontier
    index_of_points_on_frontier = list()
    for ix, (x, y), in enumerate(points):
        for (xf, yf) in pts_on_frontier:
            if xf == x and yf == y:
                index_of_points_on_frontier.append(ix)
                continue

    print(index_of_points_on_frontier)

    return index_of_points_on_frontier




