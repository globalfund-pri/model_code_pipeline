"""
This script file was created to plot graphs of each service coverage indicator at the country level. The graphs were
used in the appendix of the IC8 summary paper.
The files used here are the outputs from `src/scripts/ic8/analyses/main_results_for_investment_case.py`
"""
from tgftools.filehandler import RegionInformation
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

# Add indicator in the TB file to make vaccine coverage (doses divided by population)
df = data['tb']
df.loc[df['indicator'] == 'vaccine', ['model_central', 'model_low', 'model_high']] = (
    df.loc[df['indicator'] == 'vaccine', ['model_central', 'model_low', 'model_high']]
    / df.loc[df['indicator'] == 'population', ['model_central', 'model_low', 'model_high']]
).fillna(0.0)

# Add indicator to the HIV file to make PREP coverage (number on prep divided by HIV-neg pop)
x = data['hiv']
x.loc[x['indicator'] == 'prep', ['model_central', 'model_low', 'model_high']] = (
    x.loc[x['indicator'] == 'prep', ['model_central', 'model_low', 'model_high']]
    / x.loc[x['indicator'] == 'hivneg', ['model_central', 'model_low', 'model_high']]
).fillna(0.0)


# Create combined dataset
combined_data = pd.concat(
    [df.assign(disease=k) for k, df in data.items()],
    ignore_index=True
)

# Relabel indicators
combined_data['indicator'] = combined_data['disease'] + '_' + combined_data['indicator']

# Select with indicators to plot
indicators_to_plot = {
    'hiv_artcoverage': "HIV: Fraction of all persons living with HIV on ART",
    'hiv_fswcoverage': "HIV: Fraction of Female Sex Workers Accessing Prevention Services",
    'hiv_prep': "HIV: The fraction of HIV-negative persons (all ages) receiving PrEP",
    'tb_txcoverage': "TB: Fraction of persons with TB that receive treatment (among all cases)",
    'tb_mdrtxcoverage': "TB: Fraction of persons wih drug-resistant TB that begin 2nd-line treatment",
    'tb_vaccine': "TB: Fraction of persons (all ages) vaccinated in that year",
    'malaria_vectorcontrolcoverage': "MALARIA: Fraction of persons reached with vectoral control (any form)",
    'malaria_smccoverage': "MALARIA: Fraction of all children protected by Seasonal Malaria Chemoprevention",
    'malaria_txcoverage': "MALARIA: Fraction of malaria cases (all ages) that receive treatment",
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

# Trim all values to be in the range [0,1]
combined_data[['model_central', 'model_low', 'model_high']] = combined_data[['model_central', 'model_low', 'model_high']].clip(lower=0.0, upper=1.0)


# Get the list of unique countries and indicators
countries = combined_data['country'].unique()

r = RegionInformation()
countries = {
    c: r.get_country_name_from_iso(c)
    for c in countries
}

# Create a single PDF to store all the figures
output_file = outputpath / 'dump_files' / 'service_coverage_country_trellis.pdf'
with PdfPages(output_file) as pdf:

    # Loop through each country to create a trellis for each country
    for country in countries.keys():
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
            sharex=False,
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

                # # Plot the uncertainty bound (fill_between) for each scenario
                # ax.fill_between(
                #     group["year"],
                #     group["model_low"],
                #     group["model_high"],
                #     alpha=0.2,
                #     color=color,  # Match ribbon color with the line
                #     label=f"{scenario} Range (Low-High)"
                # )

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
                ax.set_ylim(0, 1.0)
                ax.set_xlim(2024, 2029)


        # Map the plotting function to the grid
        g.map_dataframe(plot_with_ribbon)

        # Add titles and adjust the layout
        g.set_axis_labels("Year", "")
        g.set_titles(col_template="{col_name}")
        g.add_legend(title="Scenario Descriptor")

        # Adjust the layout and add a main title
        plt.subplots_adjust(top=0.85)  # Adjust space to fit the title

        g.fig.suptitle(f"Service Coverage Indicators for {countries[country]} (ISO: {country})", fontsize=16)

        # Save the current figure to the PDF
        pdf.savefig(g.fig)

        plt.close(g.fig)  # Close the figure explicitly to avoid conflicts

print('Done!')