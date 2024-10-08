import warnings
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from tgftools.filehandler import Parameters


class Emulator:
    """This class uses a database of results in order to produce a full set of model results (all indicators) for any
    funding fraction, or any dollar amount.
    :param years_for_funding: the years which are referred to when looking-up a scenario based on it's total cost, using
     `get()`.
    :param handle_out_of_bounds_costs: If `False`, an error is raised for a requested cost that is not within
     the range of costs found in the model results. If `True`, then costs lower the lowest cost in model results and
     costs greater than the highest cost in the model results, lead to results returned corresponding to the model
     results for the lowest and highest costs, respectively.
    """

    def __init__(
        self,
        database: "Database",
        scenario_descriptor: str,
        country: str,
        years_for_funding: Iterable[int],
        handle_out_of_bounds_costs: bool = False,
    ):
        self.database = database
        self.scenario_descriptor = scenario_descriptor
        self.country = country
        self.handle_out_of_bounds_costs = handle_out_of_bounds_costs
        self.indicators = self.database.model_results.indicators
        self._lookup_dollars_to_funding_fraction: dict = self._build_lookup(
            years_for_funding
        )

    def _build_lookup(self, years_for_funding: Iterable[int]) -> Dict:
        """Returns dictionary of the form {<funding_fraction>: <total cost in replenishment period>} for the specified
        country and scenario descriptor."""
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

        # Raise Warning if measured cost does not increase monotonically with funding_fraction (will cause errors with interpolation)
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
        """Return a dict of pd.DataFrames (keyed by indicator) that corresponds to that dollar amount during
        a given period (`years_for_funding` provided in `__init__`, or a specified funding_fraction scenario, for the
         country and scenario_descriptor declared at `__init__`, interpolating between the two nearest-neighbour
         scenarios if needed."""
        # Establish that that only one of the funding_fraction OR dollars argument can be used.
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
        """Interpolation from funding fraction. Returns dict of pd.DataFrames for each indicator that is consistent
         with the funding_fraction specified. If the funding_fraction or dollar amount requested is greater than the
         greatest value in the actual model results, or less than the least value in the model results, then an error
         may be thrown because the result cannot be interpolated (if `handle_out_of_bounds_costs` is `False`); or, these
         cases can be handled by providing the results corresponding to highest and lowest cost in the model results,
         respectively (if `handle_out_of_bounds_costs` is `True`).
        """

        # Get the funding_fractions which are known, for this particular scenario_descriptor; put in ascending order
        # in a numpy array
        funding_fractions_known = self.database.model_results.df.loc[
            (self.scenario_descriptor, slice(None), self.country, slice(None), slice(None))
        ].index.get_level_values("funding_fraction").dropna().unique().sort_values().to_numpy()

        if (
            min(funding_fractions_known)
            <= funding_fraction
            <= max(funding_fractions_known)
        ):
            # The requested funding fraction can be interpolated.
            i_f_above = (
                funding_fraction > funding_fractions_known
            ).argmin()  # Index of funding_fraction below target
            i_f_below = i_f_above - 1  # Index of funding_fraction above target

            f_below = funding_fractions_known[
                i_f_below
            ]  # Value of funding_fraction below target
            f_above = funding_fractions_known[
                i_f_above
            ]  # Value of funding_fraction above target
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

        # In order to handle out of bounds costs (rather than raise an error) we use the result for the
        # highest/lowest costs
        elif (
                self.handle_out_of_bounds_costs
                and (funding_fraction > max(funding_fractions_known))
        ):
            # If the requested funding_fraction exceeds the greatest value for which we have a result, use the
            #  result for highest funding_fraction for which we do have a result.
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
            # If the requested funding_fraction is lower the lowest value for which we have a result (but still > 0),
            # use the result for lowest funding_fraction for which we do have a result.
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

    def _interpolation_from_dollars(self, dollars: float):
        """Interpolation from dollar amount, corresponding to the sum of total costs in the `years_for_funding`
        specified in `__init__`. Returns dict of pd.DataFrames for each indicator that is consistent
        with the dollar amount specified.
        It has to convert dollars to a funding_fraction scenario (within this scenario_descriptor), and then calls
        `_interpolation_from_funding_fraction`.
        For logic of the interpolation, see `_interpolation_from_funding_fraction`.
        """

        # Find the funding fraction that corresponds to the specified dollar amount.
        max_ff = max(self._lookup_dollars_to_funding_fraction.keys())
        max_dollars = self._lookup_dollars_to_funding_fraction[max_ff]
        ff = max_ff * (dollars / max_dollars)

        return self._interpolation_from_funding_fraction(ff)
