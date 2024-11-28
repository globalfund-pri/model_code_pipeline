import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from tgftools.find_cost_effective_frontier import find_cost_effective_frontier, which_points_on_frontier

PLT_SHOW = False

def test_find_cost_effective_frontier_when_maximising():
    """Check that we can find the points on the cost-effectiveness frontier, when we have impact to be MAXIMISED"""

    for _ in range(10):
        # Generate some random points
        points = 10 * np.random.rand(15, 2)  # Random points in 2-D in the form (cost, impact)

        # Get the frontier from the function `find_cost_effective_frontier`
        pts_on_the_frontier = find_cost_effective_frontier(points)

        # Cost of the first point is the lowest cost strategy
        assert pts_on_the_frontier[0][0] == min(points[:, 0])

        # Impact of last point on the frontier is the highest impact point
        assert pts_on_the_frontier[-1][1] == max(points[:, 1])

        # Gradient between the successive points should be decreasing
        list_of_gradients_between_pts_on_frontier = list()
        for ix in range(0, len(pts_on_the_frontier) - 1):
            list_of_gradients_between_pts_on_frontier.append(
                (pts_on_the_frontier[ix + 1, 1] - pts_on_the_frontier[ix, 1])
                / (pts_on_the_frontier[ix + 1, 0] - pts_on_the_frontier[ix, 0])
            )
        assert pd.Series(list_of_gradients_between_pts_on_frontier).is_monotonic_decreasing

        # Plot
        if PLT_SHOW:
            fig, ax = plt.subplots(ncols=1, figsize=(4, 4))
            ax.set_title('Frontier')
            ax.plot(points[:, 0], points[:, 1], '.', color='black')
            ax.plot(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1],
                    'o', linestyle='-', mec='r', lw=1, markersize=10, color='none')
            ax.plot(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1],
                    linestyle='-', color='r')
            ax.set_xticks(range(12))
            ax.set_yticks(range(12))
            ax.set_xlabel('Cost')
            ax.set_ylabel('Impact')
            fig.tight_layout()
            fig.show()

        # # Check can get indices of the points on the frontier
        pts_on_the_frontier_from_ix = points[which_points_on_frontier(points)]
        pd.testing.assert_series_equal(
            pd.Series(pts_on_the_frontier_from_ix[:, 0], pts_on_the_frontier_from_ix[:, 1]).sort_index(),
            pd.Series(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1]).sort_index()
        )


def test_find_cost_effective_frontier_when_minimising():
    """Check that we can find the points on the cost-effectiveness frontier, when we have impact to be MINIMISED"""

    for _ in range(10):
        # Generate some random points
        points = 10 * np.random.rand(15, 2)  # Random points in 2-D in the form (cost, impact)

        # Get the frontier from the function `find_cost_effective_frontier`
        pts_on_the_frontier = find_cost_effective_frontier(points, upper_edge=False)

        # Cost of the first point is the lowest cost strategy
        assert pts_on_the_frontier[0][0] == min(points[:, 0])

        # Value of last point on the frontier is the *lowest* value point
        assert pts_on_the_frontier[-1][1] == min(points[:, 1])

        # Gradient between the successive points should be decreasing
        list_of_gradients_between_pts_on_frontier = list()
        for ix in range(0, len(pts_on_the_frontier) - 1):
            list_of_gradients_between_pts_on_frontier.append(
                (pts_on_the_frontier[ix + 1, 1] - pts_on_the_frontier[ix, 1])
                / (pts_on_the_frontier[ix + 1, 0] - pts_on_the_frontier[ix, 0])
            )
        assert pd.Series(list_of_gradients_between_pts_on_frontier).abs().is_monotonic_decreasing

        # Plot
        if PLT_SHOW:
            fig, ax = plt.subplots(ncols=1, figsize=(4, 4))
            ax.set_title('Frontier')
            ax.plot(points[:, 0], points[:, 1], '.', color='black')
            ax.plot(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1],
                    'o', linestyle='-', mec='b', lw=1, markersize=10, color='none')
            ax.plot(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1],
                    linestyle='-', color='b')
            ax.set_xticks(range(12))
            ax.set_yticks(range(12))
            ax.set_xlabel('Cost')
            ax.set_ylabel('Impact')
            fig.tight_layout()
            fig.show()
