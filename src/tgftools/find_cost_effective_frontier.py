from scipy.spatial import ConvexHull
import numpy as np


def find_cost_effective_frontier(points: np.array, upper_edge: bool = True) -> np.array:
    """Return the points on the cost-effectiveness frontier.

    This function identifies non-dominated points on the cost-effectiveness frontier
    using convex hull computation. The points are sorted in ascending cost order.

    Args:
        points: Array of points in the form [(cost, value), ...].
        upper_edge: If True, the frontier includes points that give the greatest
            value for the cost. If False, the frontier includes points that give
            the smallest value for the cost. Defaults to True.

    Returns:
        Array containing only the non-dominated points on the frontier, sorted
        in ascending cost order.
    """

    # Start by efficiently computing the Convex Hull (polygon of the outside edge of all the points)
    hull = ConvexHull(points)

    def get_lower(polygon):
        """Find the lower edge of the convex hull.

        Extracts the lower edge between the lowest cost point and the lowest value point.
        This relies on the fact that the vertices are given in anti-clockwise order,
        so reading from the point with the lowest cost to the point with the lowest
        value yields the lower part of the hull.

        Based on: https://stackoverflow.com/a/76839030

        Args:
            polygon: Array of polygon vertices.

        Returns:
            Array containing the lower curve of the convex hull.
        """
        minx = np.argmin(polygon[:, 0])  # index of lowest cost point
        maxx = np.argmin(polygon[:, 1]) + 1  # index of lowest value point
        if minx >= maxx:
            lower_curve = np.concatenate([polygon[minx:], polygon[:maxx]])
        else:
            lower_curve = polygon[minx:maxx]
        return lower_curve

    def get_upper(polygon):
        """Find the upper edge of the convex hull.

        Extracts the upper edge between the lowest cost point and the highest value point.
        Based on the solution for get_lower(). The order of points is reversed to
        clockwise order, then we read from the lowest cost point to the highest
        value point.

        Args:
            polygon: Array of polygon vertices.

        Returns:
            Array containing the upper curve of the convex hull.
        """

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
    """Return the indices of points on the cost-effective frontier.

    Args:
        points: Array of points in the form [(cost, value), ...].
        **kwargs: Additional keyword arguments passed to find_cost_effective_frontier().

    Returns:
        Array of indices indicating which points lie on the cost-effective frontier.
    """

    pts_on_frontier = find_cost_effective_frontier(points, **kwargs)

    # Return the index of the points on the frontier
    index_of_points_on_frontier = list()
    for ix, (x, y), in enumerate(points):
        for (xf, yf) in pts_on_frontier:
            if xf == x and yf == y:
                index_of_points_on_frontier.append(ix)
                continue

    return index_of_points_on_frontier




