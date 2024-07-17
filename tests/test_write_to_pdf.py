from os import path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from tgftools.utils import get_output_path
from tgftools.write_to_pdf import build_pdf


def test_write_to_pdf(tmpdir):
    """Check that we can write the results of the checks to a pdf report."""

    # Generate some data
    def make_a_graph(title: str):
        """Returns fig of made-up data"""
        fig, ax = plt.subplots()
        pd.DataFrame(np.random.rand(10, 5)).plot(ax=ax)
        ax.set_title(title)
        fig.tight_layout()
        return fig

    # Create facsimile of the results of the checks
    content = {
        # value is a bare string
        "test0 >> not critical": "It passes",
        # value is a list of strings
        "test1 >> critical": ["It passes", "... and it feels great!"],
        # value is a pd.DataFrame
        "test2 >> not critical": [
            pd.DataFrame(
                index=range(2), columns=["country", "indicator"], data=[[0, 1], [2, 3]]
            )
        ],
        # value is a mixture of strings and figures
        "test3 >> critical": [
            "problem line 1",
            make_a_graph("graph one"),
            "problem line 2",
            make_a_graph("graph two"),
        ],
    }

    target_file = get_output_path() / "test.pdf"

    build_pdf(
        filename=target_file,
        content=content,
    )

    assert path.exists(target_file)
    # open_file(target_file)
