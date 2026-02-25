import warnings
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from tgftools.filehandler import Parameters


class Emulator:
    """Uses a database of results to produce model results for any funding fraction or dollar amount.

    This class provides interpolation capabilities to generate complete sets of model results
    (all indicators) for funding scenarios that may not exist explicitly in the database. It
    supports lookups by either funding fraction or total dollar amount.

    Attributes:
        database: The database instance containing model results.
        scenario_descriptor: Identifier for the scenario being emulated.
        country: The country for which results are being emulated.
        handle_out_of_bounds_costs: Whether to handle costs outside the available range.
        indicators: List of indicators available in the model results.
    """

    def __init__(
        self,
        database: "Database",
        scenario_descriptor: str,
        country: str,
        years_for_funding: Iterable[int],
        handle_out_of_bounds_costs: bool = False,
    ):
        """Initializes the Emulator with database and scenario specifications.

        Args:
            database: The database instance containing model results.
            scenario_descriptor: Identifier for the scenario to emulate.
            country: The country for which to generate results.
            years_for_funding: The years used when looking up scenarios based on total cost
                in the `get()` method.
            handle_out_of_bounds_costs: If False, raises an error for requested costs outside
                the range of available model results. If True, returns results corresponding to
                the lowest or highest available costs when requests fall outside the range.
        """
        self.database = database
        self.scenario_descriptor = scenario_descriptor
        self.country = country
        self.handle_out_of_bounds_costs = handle_out_of_bounds_costs
        self.indicators = self.database.model_results.indicators
        self._lookup_dollars_to_funding_fraction: dict = self._build_lookup(
            years_for_funding
        )

    def _build_lookup(self, years_for_funding: Iterable[int]) -> Dict:
        """Builds a lookup dictionary mapping funding fractions to total costs.

        Constructs a dictionary mapping each funding fraction to the total cost during the
        specified years for the given country and scenario descriptor.

        Args:
            years_for_funding: The years over which to sum costs.

        Returns:
            Dictionary mapping funding fractions to total costs in the replenishment period.

        Warnings:
            Issues a warning if total costs do not increase monotonically with funding fraction,
            which can cause interpolation errors.
        """
        lookup = (
            self.database.model_results.df.loc[
                (
                    self.scenario_descriptor,
                    slice(None),
                    self.country,
                    years_for_funding,
                    "cost",
                ),
                "central",
            ]
            .groupby(axis=0, level="funding_fraction", sort=True)
            .sum()
            .to_dict()
        )

        # Issue warning if measured cost does not increase monotonically with funding_fraction,
        # which will cause errors with interpolation.
        if not pd.Series(lookup).sort_index().is_monotonic_increasing:
            warnings.warn(
                "The total cost of this scenario is not monotonically increasing with the "
                "funding_fraction."
            )

        return lookup

    def get(
        self,
        funding_fraction: Optional[float] = None,
        dollars: Optional[float] = None
    ) -> Dict[str, pd.DataFrame]:
        """Retrieves model results for a specified funding fraction or dollar amount.

        Returns a dictionary of DataFrames (keyed by indicator) corresponding to the specified
        funding fraction or dollar amount during the period defined by `years_for_funding` in
        `__init__`. Interpolates between the two nearest-neighbor scenarios when necessary for
        the country and scenario_descriptor declared at initialization.

        Args:
            funding_fraction: The funding fraction for which to retrieve results. Must be
                between 0 and 1. Cannot be specified together with dollars.
            dollars: The total dollar amount for which to retrieve results. Cannot be
                specified together with funding_fraction.

        Returns:
            Dictionary mapping indicator names to DataFrames containing the corresponding
            model results.

        Raises:
            ValueError: If both funding_fraction and dollars are specified, or if neither
                is specified.
        """
        # Ensure that only one of the funding_fraction or dollars argument is provided.
        if (funding_fraction is not None) and (dollars is not None):
            raise ValueError(
                "Both funding_fraction and dollars were specified: use only one."
            )

        if funding_fraction is not None:
            return self._interpolation_from_funding_fraction(
                funding_fraction=funding_fraction
            )
        elif dollars is not None:
            return self._interpolation_from_dollars(dollars=dollars)
        else:
            raise ValueError(
                "Neither funding_fraction or dollars were specified: use one."
            )

    def _interpolation_from_funding_fraction(
        self, funding_fraction: float
    ) -> Dict[str, pd.DataFrame]:
        """Performs interpolation based on funding fraction.

        Returns a dictionary of DataFrames for each indicator consistent with the specified
        funding fraction. The method interpolates between the two nearest-neighbor funding
        fractions available in the model results.

        Out-of-bounds behavior depends on `handle_out_of_bounds_costs`:
        - If False: Raises an error when the requested funding fraction is outside the
          available range.
        - If True: Returns results corresponding to the highest or lowest available funding
          fraction when requests exceed the available range.

        Args:
            funding_fraction: The funding fraction for which to compute results.

        Returns:
            Dictionary mapping indicator names to DataFrames containing interpolated results.

        Raises:
            ValueError: If the funding fraction is outside the available range and
                `handle_out_of_bounds_costs` is False, or if the funding fraction is zero
                or negative.
        """

        # Get the known funding fractions for this scenario_descriptor and country,
        # sorted in ascending order as a numpy array.
        funding_fractions_known = self.database.model_results.df.loc[
            (self.scenario_descriptor, slice(None), self.country, slice(None), slice(None))
        ].index.get_level_values("funding_fraction").dropna().unique().sort_values().to_numpy()

        if (
            min(funding_fractions_known)
            <= funding_fraction
            <= max(funding_fractions_known)
        ):
            # The requested funding fraction is within range and can be interpolated.
            # Index of funding_fraction above target.
            i_f_above = (funding_fraction > funding_fractions_known).argmin()
            # Index of funding_fraction below target.
            i_f_below = i_f_above - 1

            # Value of funding_fraction below target.
            f_below = funding_fractions_known[i_f_below]
            # Value of funding_fraction above target.
            f_above = funding_fractions_known[i_f_above]
            weighting_to_below = 1.0 - (funding_fraction - f_below) / (
                f_above - f_below
            )
            assert 0.0 <= weighting_to_below <= 1.0

            return {
                indicator: (
                    weighting_to_below
                    * self.database.get_country(
                        country=self.country,
                        scenario_descriptor=self.scenario_descriptor,
                        indicator=indicator,
                        funding_fraction=f_below,
                    )
                    + (1.0 - weighting_to_below)
                    * self.database.get_country(
                        country=self.country,
                        scenario_descriptor=self.scenario_descriptor,
                        indicator=indicator,
                        funding_fraction=f_above,
                    )
                )
                for indicator in self.indicators
            }

        # Handle out-of-bounds costs by using results for the highest or lowest available costs
        # rather than raising an error.
        elif (
                self.handle_out_of_bounds_costs
                and (funding_fraction > max(funding_fractions_known))
        ):
            # If the requested funding_fraction exceeds the maximum available value,
            # use the result for the highest available funding_fraction.
            return {
                indicator: self.database.get_country(
                    country=self.country,
                    scenario_descriptor=self.scenario_descriptor,
                    indicator=indicator,
                    funding_fraction=max(funding_fractions_known),
                )
                for indicator in self.indicators
            }

        elif (
                self.handle_out_of_bounds_costs
                and (funding_fraction < min(funding_fractions_known))
                and (funding_fraction > 0)
        ):
            # If the requested funding_fraction is below the minimum available value (but still positive),
            # use the result for the lowest available funding_fraction.
            return {
                indicator: self.database.get_country(
                    country=self.country,
                    scenario_descriptor=self.scenario_descriptor,
                    indicator=indicator,
                    funding_fraction=min(funding_fractions_known),
                )
                for indicator in self.indicators
            }

        else:
            raise ValueError(
                f"Results cannot be computed using available results: "
                f"{funding_fraction=} {funding_fractions_known=} {self.country=} {self.scenario_descriptor=}"
            )

    def _interpolation_from_dollars(self, dollars: float) -> Dict[str, pd.DataFrame]:
        """Performs interpolation based on dollar amount.

        Converts the specified dollar amount to an equivalent funding fraction and then
        performs interpolation. The dollar amount corresponds to the sum of total costs
        over the `years_for_funding` specified in `__init__`.

        The conversion is based on the ratio of the requested dollars to the maximum dollars
        in the available results, applied to the maximum funding fraction.

        Args:
            dollars: The total dollar amount for which to compute results.

        Returns:
            Dictionary mapping indicator names to DataFrames containing interpolated results.

        Raises:
            ValueError: If the computed funding fraction is outside the available range and
                `handle_out_of_bounds_costs` is False.
        """

        # Convert the dollar amount to an equivalent funding fraction.
        max_ff = max(self._lookup_dollars_to_funding_fraction.keys())
        max_dollars = self._lookup_dollars_to_funding_fraction[max_ff]
        ff = max_ff * (dollars / max_dollars)

        return self._interpolation_from_funding_fraction(ff)
