"""
This script file was created to plot graphs of each service coverage indicator at the country level. The graphs were
used in the appendix of the IC8 summary paper.
The files used here are the outputs from `src/scripts/ic8/analyses/main_results_for_investment_case.py`
"""
from tgftools.utils import get_root_path
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


# Get the output directory
outputpath = get_root_path() / 'outputs'

# Load the input files for each disease
files = {
    disease: outputpath / 'dump_files' / f'dump_ic_{disease}.csv'
    for disease in ('hiv', 'tb', 'malaria')
}

# Read the data into a dictionary
data = {
    k: pd.read_csv(v)
    for k, v in files.items()
}

# Create combined dataset
combined_data = pd.concat(
    [df.assign(disease=k) for k, df in data.items()],
    ignore_index=True
)

# Relabel indicators
combined_data['indicator'] = combined_data['disease'] + '_' + combined_data['indicator']

# Select with indicators to plot
indicators_to_plot = {
    'hiv_artcoverage': "HIV: ART Coverage",
    'hiv_fswcoverage': "HIV: FSW Coverage",
    'hiv_vmmc': "HIV: Number of VMMC per year",
    'tb_txcoverage': "TB: Treatment Coverage",
    'tb_mdrtxcoverage': "TB: MDR Treatmet Coverage",
    'tb_vaccine': "TB: Vaccine Coverage",
    'malaria_llinsuse': "MALARIA: LLIN Coverage (In Use)",
    'malaria_txcoverage': "MALARIA: Treatment Coverage",
    'malaria_vaccinecoverage': "MALARIA: Vaccine Coverage",
}

# Define scenario_descriptors to include in the plots
scenario_descriptors_to_plot = {
    'CC_2022': "No Scale-up Scenario",
    'IC': "Investment Scenario",
}


combined_data = combined_data[(
    combined_data['indicator'].isin(indicators_to_plot.keys())
    & combined_data['scenario_descriptor'].isin(scenario_descriptors_to_plot.keys())
)]
combined_data['indicator'] = combined_data['indicator'].map(indicators_to_plot)
combined_data['scenario_descriptor'] = combined_data['scenario_descriptor'].map(scenario_descriptors_to_plot)

# Get the list of unique countries and indicators
countries = combined_data['country'].unique()

# Create a single PDF to store all the figures
output_file = outputpath / 'dump_files' / 'service_coverage_country_trellis.pdf'
with PdfPages(output_file) as pdf:

    # Loop through each country to create a trellis for each country
    for country in countries:
        # Filter data for the current country
        country_data = combined_data[combined_data['country'] == country]

        # Create a Seaborn FacetGrid for this country with panels for each indicator
        g = sns.FacetGrid(
            country_data,
            col="indicator",  # Panels for each indicator
            margin_titles=False,
            height=4,  # Height of each facet
            aspect=1.5,  # Aspect ratio of each facet
            col_wrap=3,
            sharey=False,
            sharex=True,
        )

        # Define the function to plot with ribbons and central lines
        def plot_with_ribbon(data, **kwargs):
            ax = plt.gca()  # Get the current Axes

            # Get a color palette with enough colors for the groups
            unique_scenarios = data["scenario_descriptor"].unique()
            palette = sns.color_palette("husl", len(unique_scenarios))  # "husl" ensures good contrast
            color_mapping = dict(zip(unique_scenarios, palette))

            # Group the data by 'scenario_descriptor'
            grouped = data.groupby("scenario_descriptor")

            for scenario, group in grouped:
                color = color_mapping[scenario]

                # Plot the uncertainty bound (fill_between) for each scenario
                ax.fill_between(
                    group["year"],
                    group["model_low"],
                    group["model_high"],
                    alpha=0.2,
                    color=color,  # Match ribbon color with the line
                    label=f"{scenario} Range (Low-High)"
                )

                # Plot the central line for each scenario
                sns.lineplot(
                    x="year",
                    y="model_central",
                    data=group,
                    label=scenario,  # Add a label for the legend
                    ax=ax,
                    color=color,  # Match line color with the ribbon
                )

                # Adjust the legend to avoid duplicate labels
                handles, labels = ax.get_legend_handles_labels()
                by_label = dict(zip(labels, handles))  # Remove duplicates
                ax.legend(by_label.values(), by_label.keys(), title="Scenario Descriptor")
                ax.set_ylim(0, None)

        # Map the plotting function to the grid
        g.map_dataframe(plot_with_ribbon)

        # Add titles and adjust the layout
        g.set_axis_labels("Year", "")
        g.set_titles(col_template="{col_name}")
        g.add_legend(title="Scenario Descriptor")

        # Adjust the layout and add a main title
        plt.subplots_adjust(top=0.85)  # Adjust space to fit the title
        g.fig.suptitle(f"Service Coverage Indicators for {country}", fontsize=16)

        # Save the current figure to the PDF
        pdf.savefig(g.fig)

        plt.close(g.fig)  # Close the figure explicitly to avoid conflicts
