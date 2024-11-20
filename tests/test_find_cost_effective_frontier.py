

def test_find_cost_effective_frontier():
    """Check that we can find the points on the cost-effectiveness frontier."""

    # Generate some random points
    points = 10 * np.random.rand(15, 2)  # Random points in 2-D in the form (cost, impact)

    # Get the frontier from the function `find_cost_effective_frontier`
    pts_on_the_frontier = find_cost_effective_frontier(points)

    fig, ax = plt.subplots(ncols=1, figsize=(10, 3))
    ax.set_title('Convex hull')
    ax.plot(points[:, 0], points[:, 1], '.', color='black')
    ax.plot(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1], 'o', linestyle='-', mec='r', lw=1, markersize=10, color='none')
    ax.plot(pts_on_the_frontier[:, 0], pts_on_the_frontier[:, 1], linestyle='-', color='r')
    ax.set_xticks(range(12))
    ax.set_yticks(range(12))
    fig.tight_layout()
    fig.show()

