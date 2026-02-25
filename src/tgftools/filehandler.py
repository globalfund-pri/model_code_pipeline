import tomllib
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

import pandas as pd

from tgftools.utils import get_root_path


def all_numeric(_df: pd.DataFrame, skipna: bool = False) -> bool:
    """Check if all elements in a DataFrame are numeric.

    Args:
        _df: The DataFrame to check for numeric values.
        skipna: If True, NaN values are ignored during the check. Defaults to False.

    Returns:
        True if all elements are numeric, False otherwise.
    """

    if skipna is False:
        return _df.apply(
            lambda s: pd.to_numeric(s, errors="coerce").notnull().all(), axis=0
        ).all()
    else:
        # We want to ignore na's
        return _df.dropna().apply(
            lambda s: pd.to_numeric(s, errors="coerce").notnull().all(), axis=0
        ).all()


class Datum(NamedTuple):
    """Data type for one datum, consisting of a central value with low and high bounds.

    Attributes:
        low: The lower bound value.
        central: The central (point estimate) value.
        high: The upper bound value.
    """

    low: float
    central: float
    high: float


class FileHandler:
    """Base class for interfacing with raw data input files.

    This class provides the foundational structure for handling various types of input data.
    Disease-specific implementations should inherit from this class and override the
    appropriate methods.

    Attributes:
        df: The internal DataFrame storage for the data.
        path: The file path to the data source.
        parameters: The parameters object containing configuration settings.

    Args:
        path: Optional path to the data file. If None, an empty DataFrame is created.
        parameters: Optional Parameters object for configuration settings.
    """

    def __init__(self, path: Optional[Path] = None, parameters: Optional['Parameters'] = None):
        self.df: pd.DataFrame
        self.path: Path = path
        self.parameters: Parameters = parameters

        if path is not None:
            self.df = self._build_df(path)
            self._checks(self.df)
        else:
            # If no path is provided, set the internal storage to an empty DataFrame.
            self.df = pd.DataFrame()

    @property
    def disease_name(self) -> str:
        """Return the disease name corresponding to the Parameters class and parameters.toml file.

        Returns:
            An empty string by default. Subclasses should override to return the appropriate disease name.
        """
        return ""

    @classmethod
    def from_df(cls, _df: pd.DataFrame) -> 'FileHandler':
        """Create a FileHandler object directly from a DataFrame.

        Args:
            _df: The DataFrame to use as the internal storage.

        Returns:
            A new FileHandler instance with the provided DataFrame.
        """
        new_instance = cls()
        new_instance._checks(_df)
        new_instance.df = _df
        return new_instance

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build a DataFrame from the file at the given path.

        This method must be implemented by subclasses to define how to construct
        the DataFrame from the specific file format.

        Args:
            path: The file path to read data from.

        Returns:
            A DataFrame containing the data from the file.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the data is stored in the expected format.

        Subclasses should override this method to implement specific validation rules.

        Args:
            _df: The DataFrame to validate.
        """
        pass

    @property
    def countries(self) -> list:
        """Return a sorted list of unique countries in the dataset.

        Returns:
            A sorted list of country codes from the 'country' index level.
        """
        return sorted(set(self.df.index.get_level_values("country")))

    def get(self, **kwargs) -> Datum:
        """Return the specified value as a Datum object.

        This is a convenience function where keyword arguments correspond to the levels
        of the multi-index of the internal DataFrame. For most use cases, accessing the
        `.df` property directly is preferred.

        Args:
            **kwargs: Index level names and their values for lookup.

        Returns:
            A Datum object containing the low, central, and high values.

        Raises:
            KeyError: If the requested data is not found in the DataFrame.
            Exception: If the lookup matches more than one entry.
        """
        try:
            lookup = self.df.loc[
                tuple(kwargs[k] for k in self.df.index.names)
            ].squeeze()
        except KeyError:
            raise KeyError(
                f"Data requested in {self.__class__} is not recognised: {kwargs=}"
            )

        try:
            assert isinstance(lookup, pd.Series)
        except AssertionError:
            raise Exception(
                f"Data requested in {self.__class__} matches more than one entry: {kwargs=}"
            )

        return Datum(**lookup)


class ModelResults(FileHandler):
    """FileHandler for holding model results.

    This class adds validation checks on the internally stored data to ensure proper
    structure and format. Disease-specific versions should inherit from this class.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sort_df()

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Validates the DataFrame has the correct index levels, columns, data types,
        and no duplicate indices.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        assert [
            "scenario_descriptor",
            "funding_fraction",
            "country",
            "year",
            "indicator",
        ] == list(_df.index.names)
        assert {"low", "central", "high"} == set(_df.columns)
        assert all_numeric(_df, skipna=True)  # na's in some places is OK
        assert not _df.index.has_duplicates

    def _sort_df(self) -> None:
        """Sort the DataFrame by all index levels to enable efficient slicing by year."""
        self.df = self.df.sort_index(axis=0, level=[0, 1, 2, 3, 4])

    @property
    def indicators(self) -> list:
        """Return a sorted list of unique indicators in the model results.

        Returns:
            A sorted list of indicator names from the 'indicator' index level.
        """
        return sorted(set(self.df.index.get_level_values("indicator")))

    @property
    def countries(self) -> list:
        """Return a sorted list of unique countries in the model results.

        Returns:
            A sorted list of country codes from the 'country' index level.
        """
        return sorted(set(self.df.index.get_level_values("country")))

    @property
    def scenario_descriptors(self) -> list:
        """Return a sorted list of scenario descriptors in the model results.

        This returns the intersection of scenarios defined in the parameters file and
        the 'scenario_descriptor' values found in the model results.

        Returns:
            A sorted list of scenario descriptor names.
        """
        return sorted(
            set(self.df.index.get_level_values("scenario_descriptor")).intersection(
                self.parameters.get_scenarios().index.to_list()
            )
        )

    @property
    def counterfactuals(self) -> list:
        """Return a sorted list of counterfactuals in the model results.

        This returns the intersection of counterfactuals defined in the parameters file
        and the 'scenario_descriptor' values found in the model results.

        Returns:
            A sorted list of counterfactual names.
        """
        return sorted(
            set(self.df.index.get_level_values("scenario_descriptor")).intersection(
                self.parameters.get_counterfactuals().index.to_list()
            )
        )

    @property
    def funding_fractions(self) -> list:
        """Return a sorted list of funding fractions in the model results.

        NaN values are excluded from the returned list.

        Returns:
            A sorted list of funding fraction values.
        """
        return sorted(set(self.df.index.get_level_values("funding_fraction").dropna()))


class PFInputData(FileHandler):
    """FileHandler for holding Portfolio Projection (PF) input data for a specific disease."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Validates the DataFrame has the correct index levels, columns, and numeric data.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        assert list(_df.index.names) == [
            "scenario_descriptor",
            "country",
            "year",
            "indicator",
        ]
        assert list(_df.columns) == ["central"]
        assert all_numeric(_df, skipna=True)

    @property
    def scenario_descriptors(self) -> list:
        """Return a sorted list of unique scenario descriptors in the data.

        Returns:
            A sorted list of scenario descriptor names.
        """
        return sorted(set(self.df.index.get_level_values("scenario_descriptor")))

    @property
    def indicators(self) -> list:
        """Return a sorted list of unique indicators in the data.

        Returns:
            A sorted list of indicator names.
        """
        return sorted(set(self.df.index.get_level_values("indicator")))

    @property
    def countries(self) -> list:
        """Return a sorted list of unique countries in the data.

        Returns:
            A sorted list of country codes.
        """
        return sorted(set(self.df.index.get_level_values("country")))


class PartnerData(FileHandler):
    """FileHandler for holding partner data for a specific disease."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Validates the DataFrame has the correct index levels, columns, and numeric data.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        assert list(_df.index.names) == [
            "scenario_descriptor",
            "country",
            "year",
            "indicator",
        ]
        assert list(_df.columns) == ["central"]
        assert all_numeric(_df, skipna=True)

    @property
    def indicators(self) -> list:
        """Return a sorted list of unique indicators in the partner data.

        Returns:
            A sorted list of indicator names.
        """
        return sorted(set(self.df.index.get_level_values("indicator")))

    @property
    def countries(self) -> list:
        """Return a sorted list of unique countries in the partner data.

        Returns:
            A sorted list of country codes.
        """
        return sorted(set(self.df.index.get_level_values("country")))


class RegionInformation:
    """Handler for country and region information including ISO3 codes and names.

    This class does not accept parameters because it always uses the data stored under
    `/shared`. It does not inherit from FileHandler as it uses different internal storage
    mechanisms and validation approaches.

    Attributes:
        region: DataFrame containing country information indexed by ISO3 code.
    """

    def __init__(self):
        rfp = get_root_path() / "resources"

        self.region: pd.DataFrame = pd.read_csv(
            rfp / "countries" / "region_information.csv"
        ).set_index("ISO3")

        self._country_name_lookup = self.region['GeographyName'].to_dict()
        self._iso3_lookup = {v: k for k, v in self._country_name_lookup.items()}

    def get_countries_in_region(self, region: str) -> List[str]:
        """Return the list of ISO3 codes for countries in a given Global Fund region.

        Args:
            region: The Global Fund region name.

        Returns:
            A sorted list of ISO3 country codes in the specified region.

        Raises:
            ValueError: If the region name is not recognized.
        """
        if region not in (
            "South East Asia",
            "Southern and Eastern Africa",
            "Eastern Europe and Central Asia",
            "Latin America and Caribbean",
            "Central Africa",
            "High Impact Africa 1",
            "High Impact Asia",
            "Middle East and North Africa",
            "High Impact Africa 2",
            "Western Africa",
        ):
            raise ValueError(f"Region not recognised {region=}.")
        else:
            return sorted(
                self.region.loc[self.region.GlobalFundRegion == region].index.to_list()
            )

    def get_countries_in_wbregion(self, region: str) -> List[str]:
        """Return the list of ISO3 codes for countries in a given World Bank region.

        Args:
            region: The World Bank region name.

        Returns:
            A sorted list of ISO3 country codes in the specified region.

        Raises:
            ValueError: If the region name is not recognized.
        """
        if region not in (
                'South Asia',
                'Sub-Saharan Africa',
                'Europe & Central Asia',
                'Latin America & Caribbean',
                'East Asia & Pacific',
                'Middle East & North Africa'
        ):
            raise ValueError(f"World Bank Region not recognised {region=}.")
        else:
            return sorted(
                self.region.loc[self.region.WorldBank == region].index.to_list()
            )

    def get_country_name_from_iso(self, iso: str) -> str:
        """Return the country name for a given ISO3 code.

        Args:
            iso: The ISO3 country code.

        Returns:
            The full country name.
        """
        return self._country_name_lookup[iso]

    def get_iso_for_country(self, name: str) -> str:
        """Return the ISO3 code for a given country name.

        Args:
            name: The full country name.

        Returns:
            The ISO3 country code.
        """
        return self._iso3_lookup[name]

    def get_region_for_iso(self, iso: str) -> str:
        """Return the Global Fund region for a given ISO3 code.

        Args:
            iso: The ISO3 country code.

        Returns:
            The Global Fund region name.
        """
        return self.region.at[iso, "GlobalFundRegion"]

    def get_wbregion_for_iso(self, iso: str) -> str:
        """Return the World Bank region for a given ISO3 code.

        Args:
            iso: The ISO3 country code.

        Returns:
            The World Bank region name.
        """
        return self.region.at[iso, "WorldBank"]

    def get_countries_by_regional_flag(self, regional_flag: str) -> List[str]:
        """Return ISO3 codes based on a regional flag or all countries if 'ALL'.

        Args:
            regional_flag: The regional flag identifier (e.g., 'OIC', 'SSA') or 'ALL' for all countries.

        Returns:
            A sorted list of ISO3 country codes matching the regional flag.

        Raises:
            ValueError: If the regional flag is not recognized.
        """
        # Recognized flags: {'ARABLEAGUE', 'COE', 'Johannes', 'OIC', 'PKU', 'SSA'}
        recognised_flags = (
                set(self.region.columns) - {'ISO3', 'ISO2', 'GeographyName', 'Differentiation', 'GlobalFundRegion', 'GlobalFundDepartment'})

        if regional_flag == "ALL":
            return sorted(self.region.index.tolist())

        elif regional_flag not in recognised_flags:
            raise ValueError(f"Column '{regional_flag}' does not exist in the dataset.")

        else:
            mask_within_region = self.region[regional_flag].astype(bool)
            return sorted(self.region.loc[mask_within_region].index.tolist())

class Indicators:
    """Handler for indicator definitions and metadata.

    Attributes:
        _dict: Dictionary containing indicator metadata including descriptions, types, and scaling flags.

    Args:
        path: Path to the CSV file containing indicator definitions.
    """

    def __init__(self, path: Path):
        self._dict = pd.read_csv(path).set_index("name").to_dict()

    @property
    def defn(self) -> Dict[str, str]:
        """Return a dictionary of indicator definitions.

        Returns:
            Dictionary mapping indicator names to their descriptions.
        """
        return self._dict["description"]

    @property
    def types(self) -> Dict[str, str]:
        """Return a dictionary of indicator types.

        Returns:
            Dictionary mapping indicator names to their types.
        """
        return self._dict["type"]

    @property
    def use_scaling(self) -> List[str]:
        """Return a list of indicators flagged for scaling.

        Returns:
            List of indicator names where use_scaling is 'yes'.
        """
        return [name for name, use_scaling in self._dict["use_scaling"].items() if use_scaling == 'yes']


class Scenarios:
    """Handler for scenario definitions.

    Attributes:
        scenarios: Dictionary mapping scenario names to their descriptions.

    Args:
        path: Path to the CSV file containing scenario definitions.
    """

    def __init__(self, path: Path):
        self.scenarios = (
            pd.read_csv(path)
            .set_index("name")["description"]
            .to_dict()
        )

    @property
    def names(self) -> List[str]:
        """Return a list of scenario names defined in scenario_descriptors.csv.

        Returns:
            A sorted list of scenario names.
        """
        return sorted(self.scenarios.keys())

    @property
    def definitions(self) -> Dict[str, str]:
        """Return scenario definitions as a dictionary.

        Returns:
            Dictionary mapping scenario names to their descriptions.
        """
        return self.scenarios


class Parameters:
    """Handler for analysis parameters from TOML configuration files.

    Attributes:
        int_store: Dictionary containing the parsed TOML parameters.
        raw_store: Raw string content of the TOML file.

    Args:
        path: Path to the TOML parameters file.
    """

    def __init__(self, path: Path):
        # Load and interpret the parameter file using tomllib library.
        with open(path, 'rb') as f:
            self.int_store: dict = tomllib.load(f)

        # Store contents of .toml file as raw text.
        with open(path, 'rb') as f:
            raw_content = f.read()
            f.seek(0)
            self.raw_store: str = raw_content.decode('utf-8')



    def get(self, what: str) -> Any:
        """Retrieve a parameter value from the internal store.

        Args:
            what: The parameter key to retrieve.

        Returns:
            The parameter value, or None if not found.
        """
        return self.int_store.get(what)

    def get_scenarios(self) -> pd.Series:
        """Return a Series of all defined scenarios.

        Returns:
            A Series indexed by scenario name with descriptions as values.
        """
        return pd.DataFrame(self.int_store.get('scenario')).set_index('name')['description']

    def get_counterfactuals(self) -> pd.Series:
        """Return a Series of all defined counterfactuals.

        Returns:
            A Series indexed by counterfactual name with descriptions as values.
        """
        return pd.DataFrame(self.int_store.get('counterfactual')).set_index('name')['description']

    def get_nullcounterfactuals(self) -> pd.Series:
        """Return a Series of null counterfactuals.

        Returns:
            A Series indexed by counterfactual name where is_null is True, or an empty
            Series if the flag is not present (for backward compatibility).
        """
        try:
            df = pd.DataFrame(self.int_store.get('counterfactual')).set_index('name')
            return df.loc[df['is_null'], 'description']
        except:
            return pd.Series()

    def get_cccounterfactuals(self) -> pd.Series:
        """Return a Series of constant coverage counterfactuals.

        Returns:
            A Series indexed by counterfactual name where is_cc is True, or an empty
            Series if the flag is not present (for backward compatibility).
        """
        try:
            df = pd.DataFrame(self.int_store.get('counterfactual')).set_index('name')
            return df.loc[df['is_cc'], 'description']
        except:
            return pd.Series()

    def get_gpscenario(self) -> pd.Series:
        """Return a Series of Global Plan scenarios.

        Returns:
            A Series indexed by scenario name where is_gp is True, or an empty Series
            if the flag is not present (for backward compatibility).
        """
        try:
            df = pd.DataFrame(self.int_store.get('counterfactual')).set_index('name')
            return df.loc[df['is_gp'], 'description']
        except:
            return pd.Series()

    def get_indicators_for(self, disease_name: str) -> pd.DataFrame:
        """Return a DataFrame of all indicators for a specific disease.

        Args:
            disease_name: The name of the disease.

        Returns:
            A DataFrame indexed by indicator name containing indicator metadata.
        """
        return pd.DataFrame(self.int_store.get(disease_name).get('indicator')).set_index('name')

    def get_modelled_countries_for(self, disease_name: str) -> List[str]:
        """Return a list of modelled countries for a specific disease.

        Args:
            disease_name: The name of the disease.

        Returns:
            A list of country codes that are modelled for the disease.
        """
        return self.int_store.get(disease_name).get('MODELLED_COUNTRIES')

    def get_portfolio_countries_for(self, disease_name: str) -> List[str]:
        """Return a list of portfolio countries for a specific disease.

        Args:
            disease_name: The name of the disease.

        Returns:
            A list of country codes in the portfolio for the disease.
        """
        return self.int_store.get(disease_name).get('PORTFOLIO_COUNTRIES')


class Variables:
    """Handler for variable names and definitions used in the analysis.

    Attributes:
        int_store: Dictionary mapping variable names to their descriptions.
    """

    def __init__(self):
        self.int_store: Dict[str, str] = (
            pd.read_csv(get_root_path() / "shared" / "variables.csv")
            .set_index("name")["description"]
            .to_dict()
        )

    def get(self, what: str) -> Any:
        """Return the description for a given variable name.

        Args:
            what: The variable name to look up.

        Returns:
            The variable description, or None if not found.
        """
        return self.int_store.get(what)


class GFYear(FileHandler):
    """FileHandler for holding the first years of Global Fund results reporting by country."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Read the data from a CSV file and return a DataFrame.

        Args:
            path: Path to the CSV file.

        Returns:
            A DataFrame indexed by iso3 country code.
        """
        return pd.read_csv(path).set_index(["iso3"])

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        # TODO: they are not all incidence/mortality; HIV uses cases/deaths etc.
        assert {"year"} == set(_df.columns)
        assert all_numeric(_df)


class FixedGp(FileHandler):
    """FileHandler for holding Fixed Global Plan targets defined by proportional reductions.

    This class holds data for a Fixed GP defined by percentage reductions in incidence
    and death rates.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Read the data from a CSV file and return a DataFrame.

        Args:
            path: Path to the CSV file.

        Returns:
            A DataFrame indexed by year.
        """
        return pd.read_csv(path).set_index(["year"])

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        # TODO: they are not all incidence/mortality; HIV uses cases/deaths etc.
        assert {"incidence_reduction", "death_rate_reduction"} == set(_df.columns)
        assert all_numeric(_df)


class Gp:
    """Handler for Global Plan data for a specific disease across the portfolio.

    Attributes:
        df: DataFrame containing Global Plan data with multi-index (year, indicator).

    Args:
        fixed_gp: FixedGp object containing target reductions.
        model_results: ModelResults object containing model outputs.
        partner_data: PartnerData object containing partner projections.
        parameters: Optional Parameters object for configuration settings.
        **kwargs: Additional keyword arguments passed to _build_df.
    """

    def __init__(
        self,
        fixed_gp: FixedGp,
        model_results: ModelResults,
        partner_data: PartnerData,
        parameters: Optional[Parameters] = None,
        **kwargs,
    ):
        self.df: pd.DataFrame = self._build_df(
            fixed_gp=fixed_gp,
            model_results=model_results,
            partner_data=partner_data,
            parameters=parameters,
            **kwargs,
        )
        self._checks(self.df)

    def _build_df(self, *args, **kwargs) -> pd.DataFrame:
        """Build a DataFrame from Global Plan inputs.

        This method must be implemented by disease-specific subclasses.

        Args:
            *args: Positional arguments for building the DataFrame.
            **kwargs: Keyword arguments for building the DataFrame.

        Returns:
            A DataFrame with multi-index (year, indicator) and 'central' column.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        assert ["year", "indicator"] == list(_df.index.names)
        assert {"central"} == set(_df.columns)
        assert all_numeric(_df)

    def save(self, filename: Path) -> None:
        """Save the Global Plan output to a CSV file.

        Args:
            filename: Path where the CSV file should be saved.
        """
        self.df = self.df.reset_index()
        a = self.df.pivot(index="year", columns="indicator", values="central")
        a.to_csv(filename)


class CalibrationData(FileHandler):
    """FileHandler for holding external calibration data for a specific disease."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Read calibration data from a CSV file and return a DataFrame.

        Args:
            path: Path to the CSV file.

        Returns:
            A DataFrame with multi-index (country, year, indicator) and columns (low, central, high).
        """
        return pd.read_csv(path).set_index(["country", "year", "indicator"])

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails.
        """
        assert isinstance(_df, pd.DataFrame)
        assert ["country", "year", "indicator"] == list(_df.index.names)
        assert {"low", "central", "high"} == set(_df.columns)
        assert all_numeric(_df)


class FundingData(FileHandler):
    """FileHandler for data about funding amounts available to each country."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build a DataFrame with country ISO codes as index and funding amounts.

        This method must be implemented by subclasses.

        Args:
            path: Path to the funding data file.

        Returns:
            A DataFrame indexed by country ISO code with a 'value' column containing amounts.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError

    @staticmethod
    def _checks(_df: pd.DataFrame) -> None:
        """Check that the DataFrame adheres to expected structure requirements.

        Args:
            _df: The DataFrame to validate.

        Raises:
            AssertionError: If any validation check fails. Values must be integers
                representing dollar amounts (not funding fractions), and countries
                should not be duplicated.
        """
        assert isinstance(_df, pd.DataFrame)
        assert list(_df.columns) == ["value"]
        assert not pd.isnull(_df["value"]).any()
        assert all_numeric(_df)
        assert _df.dtypes['value'].name.startswith('int'), "Values are not integers: We want the values to be dollar amounts (not funding fractions)."
        assert not _df.index.has_duplicates, "Countries should not be duplicated."


class TgfFunding(FundingData):
    """Handler for The Global Fund (TGF) funding allocations by country.

    This class holds information about TGF funding amounts allocated to each country.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build a DataFrame from TGF funding data.

        Args:
            path: Path to the CSV file containing TGF funding data.

        Returns:
            A DataFrame indexed by country ISO code with a 'value' column containing
            funding amounts as integers.
        """
        # Fill blanks with 0 and convert to integers.
        df = pd.read_csv(path).set_index("country").fillna(0).round(0).astype(int)
        return df.rename(columns={df.columns[0]: "value"})


class NonTgfFunding(FundingData):
    """Handler for Non-TGF funding allocations by country.

    This class holds information about non-TGF funding amounts allocated to each country
    from other sources.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build a DataFrame from Non-TGF funding data.

        Args:
            path: Path to the CSV file containing Non-TGF funding data.

        Returns:
            A DataFrame indexed by country ISO code with a 'value' column containing
            funding amounts as integers.
        """
        # Fill blanks with 0 and convert to integers.
        df = pd.read_csv(path).set_index("country").fillna(0).round(0).astype(int)
        return df.rename(columns={df.columns[0]: "value"})
