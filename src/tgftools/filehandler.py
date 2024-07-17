import tomllib
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

import pandas as pd

from tgftools.utils import get_root_path


def all_numeric(_df: pd.DataFrame, skipna=False) -> bool:
    """Returns True if all elements in a pd.DataFrame are numeric.
    If `skipna` is `True`, then na's do not cause an error."""

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
    """Data type for one datum, consisting of a central value, a low and a high value."""

    low: float
    central: float
    high: float


class FileHandler:
    """This is the base class used to interface with the raw data input files. A bespoke version
    will be needed for each type of input and these are created by inheriting from this class.
    """

    def __init__(self, path: Optional[Path] = None, parameters: Optional['Parameters'] = None):
        self.df: pd.DataFrame
        self.path: Path = path
        self.parameters: Parameters = parameters

        if path is not None:
            self.df = self._build_df(path)
            self._checks(self.df)
        else:
            self.df = (
                pd.DataFrame()
            )  # If no path is provided, do nothing and set the internal storage to an empty
            #                           pd.DataFrame.

    @property
    def disease_name(self):
        """Return the disease name, corresponding to the names used in the Parameters class and parameters.toml file."""
        return ""

    @classmethod
    def from_df(cls, _df: pd.DataFrame) -> None:
        """Create a FileHandler object directly from a dataframe."""
        new_instance = cls()
        new_instance._checks(_df)
        new_instance.df = _df
        return new_instance

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Returns pd.DataFrame that is the internal storage of these data."""
        raise NotImplementedError

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the data is stored in the expected format."""
        pass

    @property
    def countries(self):
        return sorted(set(self.df.index.get_level_values("country")))

    def get(self, **kwargs) -> Datum:
        """Returns the specified value (where key-word arguments corresponds to the levels of the multi-index of the
        internal dataframe) in the form of a Datum.
        N.B. This is a convenience function only - it's expected that most uses will address the member property
        `.df` directly."""
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
    """The type of FileHandler that is used for holding model results. This class add checks on the internally stored
    data. Bespoke versions for each disease inherit from this class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sort_df()

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
        assert isinstance(_df, pd.DataFrame)
        assert [
            "scenario_descriptor",
            "funding_fraction",
            "country",
            "year",
            "indicator",
        ] == list(_df.index.names)
        assert {"low", "central", "high"} == set(_df.columns)
        assert all_numeric(_df)
        assert not _df.index.has_duplicates

    def _sort_df(self):
        """Sort the dataframe to allow for slicing by year."""
        self.df = self.df.sort_index(axis=0, level=[0, 1, 2, 3, 4])

    @property
    def indicators(self) -> list:
        """Returns list of indicators contained within these model results."""
        return sorted(set(self.df.index.get_level_values("indicator")))

    @property
    def countries(self) -> list:
        """Returns list of the countries contained within these model results."""
        return sorted(set(self.df.index.get_level_values("country")))

    @property
    def scenario_descriptors(self) -> list:
        """Returns list of the scenario_descriptors contained within these model results. These are the intersection
        of the scenarios defined in the parameters file and the values found for 'scenario_descriptor' in the
        model results."""
        return sorted(
            set(self.df.index.get_level_values("scenario_descriptor")).intersection(
                self.parameters.get_scenarios().index.to_list()
            )
        )

    @property
    def counterfactuals(self) -> list:
        """Returns list of the counterfactuals contained within these model results. These are the intersection
        of the counterfactual defined in the parameters file and the values found for 'scenario_descriptor' in the
        model results."""
        return sorted(
            set(self.df.index.get_level_values("scenario_descriptor")).intersection(
                self.parameters.get_counterfactuals().index.to_list()
            )
        )

    @property
    def funding_fractions(self) -> list:
        """Returns list of the funding_fractions contained within these model results. NaN are dropped."""
        return sorted(set(self.df.index.get_level_values("funding_fraction").dropna()))


class PFInputData(FileHandler):
    """The type of FileHandler that is used for holding the input data on PF data for a particular disease."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
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
        """Returns list of the scenario_descriptors contained within these model results."""
        return sorted(set(self.df.index.get_level_values("scenario_descriptor")))

    @property
    def indicators(self) -> list:
        """Returns list of indicators contained within these model results."""
        return sorted(set(self.df.index.get_level_values("indicator")))

    @property
    def countries(self) -> list:
        """Returns list of the countries contained within these model results."""
        return sorted(set(self.df.index.get_level_values("country")))


class PartnerData(FileHandler):
    """The type of FileHandler that is used for holding partner data for a particular disease."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
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
        """Returns list of indicators contained within these model results."""
        return sorted(set(self.df.index.get_level_values("indicator")))

    @property
    def countries(self) -> list:
        """Returns list of the countries contained within these model results."""
        return sorted(set(self.df.index.get_level_values("country")))


class RegionInformation:
    """The type of FileHandler that is used for holding information on ISO3 codes, country names and region.
    It does not accept parameters because it only ever uses the data stored under `/shared`.
    Note that it does not inherit from the FileHandler base class as it uses different forms of internal storage and
    does not need to perform checks."""

    def __init__(self):
        rfp = get_root_path() / "resources"

        self.region: pd.DataFrame = pd.read_csv(
            rfp / "countries" / "region_information.csv"
        ).set_index("ISO3")

        self._country_name_lookup = self.region['GeographyName'].to_dict()
        self._iso3_lookup = {v: k for k, v in self._country_name_lookup.items()}

    def get_countries_in_region(self, region: str) -> List:
        """For a given region, return the list of ISO3 for the countries in that region."""
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

    def get_country_name_from_iso(self, iso: str) -> str:
        """returns country name given iso3 code"""
        return self._country_name_lookup[iso]

    def get_iso_for_country(self, name: str) -> str:
        """returns iso3 code for a given country"""
        return self._iso3_lookup[name]


class Indicators:
    """FileHandler that holds the definitions of each indicator."""

    def __init__(self, path: Path):
        self._dict = pd.read_csv(path).set_index("name").to_dict()

    @property
    def defn(self) -> Dict:
        """Returns dict with definitions of all indicators in the form {indicator: description}."""
        return self._dict["description"]

    @property
    def types(self) -> Dict:
        """Returns dict with definitions of all indicators in the form {indicator: type}."""
        return self._dict["type"]

    @property
    def use_scaling(self) -> List:
        """Returns a list of the indicators that are flagged 'yes' for `use_scaling'."""
        return [name for name, use_scaling in self._dict["use_scaling"].items() if use_scaling == 'yes']


class Scenarios:
    """FileHandler that holds the definitions of each indicator."""

    def __init__(self, path: Path):
        self.scenarios = (
            pd.read_csv(path)
            .set_index("name")["description"]
            .to_dict()
        )

    @property
    def names(self) -> List:
        """Returns list of the scenarios defined in `scenario_descriptors.csv`"""
        return sorted(self.scenarios.keys())

    @property
    def definitions(self) -> Dict:
        """Returns dict of the scenarios defined in `scenario_descriptors.csv` in the form {name: description}."""
        return self.scenarios


class Parameters:
    """FileHandler that holds parameters for the analysis."""

    def __init__(self, path: Path):
        # Load the parameters file using tomllib library
        with open(path, 'rb') as f:
            self.int_store: dict = tomllib.load(f)

    def get(self, what) -> Any:
        """Pass through to `get` of the internally stored dict."""
        return self.int_store.get(what)

    def get_scenarios(self) -> pd.Series:
        """Helper function to return pd.Series of all the defined scenarios (index is the name of the scenario)."""
        return pd.DataFrame(self.int_store.get('scenario')).set_index('name')['description']

    def get_counterfactuals(self) -> pd.Series:
        """Helper function to return pd.Series of all the defined scenarios (index is the name of the scenario)."""
        return pd.DataFrame(self.int_store.get('counterfactual')).set_index('name')['description']

    def get_historiccounterfactuals(self) -> pd.Series:
        """Helper function to return pd.Series of all the defined scenarios (index is the name of the scenario).
        If there is no flag for historical counterfactual, return empty pd.DataFrame(provided for backward compatibility).
        """
        try:
            df = pd.DataFrame(self.int_store.get('counterfactual')).set_index('name')
            return df.loc[df['is_historic'], 'description']
        except:
            return pd.Series()

    def get_indicators_for(self, disease_name) -> pd.DataFrame:
        """Helper function to return pd.DataFrame of all the indicators for a particular disease (index is the name of
        the indicator)."""
        return pd.DataFrame(self.int_store.get(disease_name).get('indicator')).set_index('name')

    def get_modelled_countries_for(self, disease_name) -> List:
        """Helper function to return list for all the modelled countries for a particular disease."""
        return self.int_store.get(disease_name).get('MODELLED_COUNTRIES')

    def get_portfolio_countries_for(self, disease_name) -> List:
        """Helper function to return list for all the portfolio countries for a particular disease."""
        return self.int_store.get(disease_name).get('PORTFOLIO_COUNTRIES')


class Variables:
    """FileHandler that holds variable names for the analysis."""

    def __init__(self):
        self.int_store: Dict = (
            pd.read_csv(get_root_path() / "shared" / "variables.csv")
            .set_index("name")["description"]
            .to_dict()
        )

    def get(self, what: str) -> Any:
        """Returns list of the variables defined in `variables.csv`"""
        return self.int_store.get(what)


class GFYear(FileHandler):
    """The type of FileHandler that is used for holding in a file containing the first years of GF results reporting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame."""
        return pd.read_csv(path).set_index(["iso3"])

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
        assert isinstance(_df, pd.DataFrame)
        # TODO: they are not all incidence/mortality; hiv are cases/deaths etc
        assert {"year"} == set(_df.columns)
        assert all_numeric(_df)


class FixedGp(FileHandler):
    """The type of FileHandler that is used for holding a Fixed GP that is defined by proportion reductions in incidence
    and deaths."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame."""
        return pd.read_csv(path).set_index(["year"])

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
        assert isinstance(_df, pd.DataFrame)
        # TODO: they are not all incidence/mortality; hiv are cases/deaths etc
        assert {"incidence_reduction", "death_rate_reduction"} == set(_df.columns)
        assert all_numeric(_df)


class Gp:
    """The type of FileHandler that is used for holding the Global Plan data for a particular disease for the whole
    portfolio."""

    def __init__(
        self,
        fixed_gp: FixedGp,
        model_results: ModelResults,
        partner_data: PartnerData,
        parameters: Optional[Parameters] = None,
    ):
        self.df: pd.DataFrame = self._build_df(
            fixed_gp=fixed_gp,
            model_results=model_results,
            partner_data=partner_data,
            parameters=parameters
        )
        self._checks(self.df)

    def _build_df(self, *args, **kwargs) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame with multi-index (country, year, indicator) and columns
        (low, central, high)."""
        raise NotImplementedError

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
        assert isinstance(_df, pd.DataFrame)
        assert ["year", "indicator"] == list(_df.index.names)
        assert {"central"} == set(_df.columns)
        assert all_numeric(_df)

    def save(self, filename: Path):
        """This saves the GP output into a csv"""
        self.df = self.df.reset_index()
        a = self.df.pivot(index="year", columns="indicator", values="central")
        a.to_csv(filename)


class CalibrationData(FileHandler):
    """The type of FileHandler that is used for holding the external calibration data for a particular disease."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame with multi-index (country, year, indicator) and columns (low, central, high)."""
        return pd.read_csv(path).set_index(["country", "year", "indicator"])

    @staticmethod
    def _checks(_df: pd.DataFrame):
        """Check that the df that is built adheres to some size/shape expectations."""
        assert isinstance(_df, pd.DataFrame)
        assert ["country", "year", "indicator"] == list(_df.index.names)
        assert {"low", "central", "high"} == set(_df.columns)
        assert all_numeric(_df)


class FundingData(FileHandler):
    """The type of FileHandler that is used for data about the amount of shared that are available to a country."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build dataframe with the index as the country ISO code and one column (named `value`) with the amounts."""
        raise NotImplementedError

    @staticmethod
    def _checks(_df):
        """Check that the df that is built adheres to some size/shape expectations."""
        assert isinstance(_df, pd.DataFrame)
        assert list(_df.columns) == ["value"]
        assert not pd.isnull(_df["value"]).any()
        assert all_numeric(_df)
        assert _df.dtypes['value'].name.startswith('int'), "Values are not integers: We want the values to be dollar amounts (not funding fractions)."
        assert not _df.index.has_duplicates, "Countries should not be duplicated."


class TgfFunding(FundingData):
    """This class holds information about the TGF funding that is allocated to each country."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build dataframe with the index as the country ISO code, and one column (named `value`) with the amounts"""
        df = pd.read_csv(path).set_index("country").fillna(0).round(0).astype(int)  # fill blanks with 0.0 and make ints
        return df.rename(columns={df.columns[0]: "value"})


class NonTgfFunding(FundingData):
    """This class holds information about the Non-TGF funding that is allocated to each country."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Build dataframe with the index as the country ISO code, and one column (named `value`) with the amounts"""
        df = pd.read_csv(path).set_index("country").fillna(0).round(0).astype(int)  # fill blanks with 0.0 and make ints
        return df.rename(columns={df.columns[0]: "value"})
