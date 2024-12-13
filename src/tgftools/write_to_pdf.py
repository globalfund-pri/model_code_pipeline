import io
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    Table, SimpleDocTemplate, Spacer, HRFlowable,
)

from tgftools.utils import get_commit_revision_number, current_date_and_time_as_string


def df2table(df):
    df.columns = df.columns.astype(str)  # Ensure that no columns have non-string types
    return Table(
        [[Paragraph(col) for col in df.columns]] + df.values.tolist(),
        style=[
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.lightgrey, colors.white]),
        ],
        hAlign="LEFT",
    )


def fig2image(f):
    buf = io.BytesIO()
    f.savefig(buf, format="png", dpi=300)
    buf.seek(0)
    x, y = f.get_size_inches()
    return Image(buf, x * inch, y * inch)


def build_pdf(
    filename: Path,
    content: dict,
):
    """Build pdf from contents of a dict. The keys are labels and the values are elements (can be text, a figure or
    a dataframe)."""
    doc = SimpleDocTemplate(str(filename), pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []
    spacer = Spacer(1, 0.25 * inch)
    hr = HRFlowable()

    # Add header of date-time stamp and git commit
    flowables.append(Paragraph(f'Date-Time: {current_date_and_time_as_string()}, Commit: {get_commit_revision_number()}'))

    for label, element in content.items():
        flowables.append(Paragraph(label, styles["Heading2"]))
        if isinstance(element, str):
            flowables.append(Paragraph(element, styles["Heading3"]))
        else:
            for line in element:
                if isinstance(line, str):
                    flowables.append(Paragraph(line, styles["Heading3"]))

                elif isinstance(line, plt.Figure):
                    flowables.append(fig2image(line))

                elif isinstance(line, pd.DataFrame):
                    flowables.append(df2table(line))

                else:
                    continue
        flowables.append(spacer)
        flowables.append(hr)

    doc.build(flowables)
