"""
This script file was created to plot graphs of each service coverage indicator at the country level. The graphs were
used in the appendix of the IC8 summary paper.
The files used here are the outputs from `src/scripts/ic8/analyses/main_results_for_investment_case.py`
"""
from pathlib import Path
from textwrap import fill
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages

from tgftools.filehandler import RegionInformation
from tgftools.utils import get_root_path

# Load Region Information
r = RegionInformation()


# Get the ouyput directory
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

# Drop Any data before 2024 and after 2029 as do not want that plotted
combined_data = combined_data.drop(
    combined_data.index[(combined_data['year'] < 2024) | (combined_data['year'] > 2029)]
)

# Merge in Region Information
combined_data['region'] = combined_data['country'].map(r.get_region_for_iso)

# Cut Time into Periods
combined_data['year'] = combined_data['year'].astype(int)
combined_data['period'] = pd.cut(
    combined_data['year'],
    bins=[-float('inf'), 2027, 2030],  # inclusive on left-side, exclusive on right-side
    labels=['2024-2026', '2027-2029']
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
countries = {
    c: r.get_country_name_from_iso(c)
    for c in countries
}

# Get the list of unique regions
regions = sorted(set([r.get_region_for_iso(c) for c in countries]))


# Create a single PDF to store all the figures

def write_appendix_doc(
        data: pd.DataFrame,
        filename: Path,
        aggregate_time: bool = False,  # False --> plot by year, True --> plot by period
        aggregate_country: bool = False,  # False --> plot by country, True --> plot by region
):
    time_axis = "year" if not aggregate_time else "period"
    geo_axis = "country" if not aggregate_country else "region"
    geo_units = countries if not aggregate_country else regions

    data = data.groupby(
        ['scenario_descriptor', 'indicator'] + [time_axis] + [geo_axis]
    )['model_central'].mean().reset_index()
    data['model_central'] = data['model_central'].fillna(0.0)

    with (PdfPages(filename) as pdf):
        # Loop through each country to create a trellis for each country

        for geo_unit in geo_units:

            # Filter data for the current geographic unit
            geo_unit_data = data[data[geo_axis] == geo_unit]

            # Create a Seaborn FacetGrid for this geo_unit, with panels for each indicator
            g = sns.FacetGrid(
                geo_unit_data,
                col="indicator",  # Panels for each indicator
                hue="scenario_descriptor",  # Different lines for each scenario
                margin_titles=False,
                height=4,  # Height of each facet
                aspect=1.5,  # Aspect ratio of each facet
                col_wrap=3,
                sharey=False,
                sharex=False,
            )

            # Add line plots to each panel
            g.map(sns.lineplot, time_axis, "model_central", marker='o')
            g.add_legend(title="Scenario")

            # Adjust labels and remove "indicator = " prefix
            for ax in g.axes.flat:
                ax.set_ylim(0.0, 1.0)
                ax.set_xlabel(time_axis.capitalize())
                ax.set_ylabel("")
                if ax.get_title():
                    ax.set_title(ax.get_title().replace("indicator = ", ""), fontsize=10)

            if not aggregate_country:
                suptitle_text = f"Service Coverage Indicators for {r.get_country_name_from_iso(geo_unit)} (ISO: {geo_unit})"
            else:

                country_names_in_region = ", ".join(
                    sorted(map(r.get_country_name_from_iso, r.get_countries_in_region(geo_unit))))
                suptitle_text = f"Service Coverage Indicators for {(geo_unit)}\n" \
                                + fill(f"\n({country_names_in_region})", width=100)


            # plt.tight_layout()
            plt.subplots_adjust(top=0.85, wspace=0.3, hspace=0.4)  # Adjust spacing and make space to fit the title
            g.fig.suptitle(suptitle_text, fontsize=16)  # Adjust y to prevent overlap

            # Save the current figure to the PDF
            pdf.savefig(g.fig)
            plt.close(g.fig)  # Close the figure explicitly to avoid conflicts



# Aggregation by Period & Region
write_appendix_doc(
    data=combined_data,
    filename=outputpath / 'dump_files' / 'service_coverage_country_trellis_aggregate_period_and_region.pdf',
    aggregate_time=True,
    aggregate_country=True
)


# Original version (no aggregation)
write_appendix_doc(
    data=combined_data,
    filename=outputpath / 'dump_files' / 'service_coverage_country_trellis_original.pdf',
    aggregate_time=False,
    aggregate_country=False
)

# Aggregation by Period only
write_appendix_doc(
    data=combined_data,
    filename=outputpath / 'dump_files' / 'service_coverage_country_trellis_aggregate_period.pdf',
    aggregate_time=True,
    aggregate_country=False
)

# Aggregation by Region only
write_appendix_doc(
    data=combined_data,
    filename=outputpath / 'dump_files' / 'service_coverage_country_trellis_aggregate_region.pdf',
    aggregate_time=False,
    aggregate_country=True
)




print('Done!')