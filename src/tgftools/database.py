from typing import Optional

import numpy as np
import pandas as pd

from tgftools.filehandler import Gp, Parameters, Indicators, Scenarios  # RegionInformation
from tgftools.filehandler import ModelResults, PartnerData, PFInputData


class Database:
    """Database for holding and managing disease-related data.

    This class holds all data related to a single disease, including model results,
    partner data, and portfolio input data. It also holds an emulator which can be
    used to create results for scenarios that are not stored.

    Attributes:
        gp: General parameters handler.
        partner_data: Partner data handler.
        pf_input_data: Portfolio input data handler.
        model_results: Model results data handler.
        disease_name: Name of the disease.

    Args:
        gp: Optional general parameters handler.
        partner_data: Optional partner data handler.
        pf_input_data: Optional portfolio input data handler.
        model_results: Optional model results data handler.
    """

    def __init__(
        self,
        gp: Optional[Gp] = None,
        partner_data: Optional[PartnerData] = None,
        pf_input_data: Optional[PFInputData] = None,
        model_results: Optional[ModelResults] = None,
    ):
        self.gp = gp
        self.partner_data = partner_data
        self.pf_input_data = pf_input_data
        self.model_results = model_results
        self.disease_name = model_results.disease_name

        # Check that all filehandlers have the same disease_name (if they are defined).
        disease_name_where_args_defined = np.array([x.disease_name for x in (gp, partner_data, pf_input_data, model_results) if x is not None])
        assert (disease_name_where_args_defined == disease_name_where_args_defined[0]).all()

    def get_country(
        self,
        country: str,
        scenario_descriptor: str,
        funding_fraction: float,
        indicator: str,
    ) -> pd.DataFrame:
        """Retrieve data for a specific country, scenario, funding fraction, and indicator.

        Assembles information from all data sources (model results, portfolio input data,
        and partner data) for the specified parameters. If the indicator is not found in
        the portfolio input data or partner data, NaN values are used instead.

        Args:
            country: The country ISO3 code.
            scenario_descriptor: The scenario descriptor (e.g., 'default').
            funding_fraction: The funding fraction (e.g., 0.9).
            indicator: The indicator name (e.g., 'cases').

        Returns:
            DataFrame with columns prefixed by source ('model_', 'pf_', 'partner_')
            containing low, central, and high estimates for the specified parameters.
        """
        _model = self.model_results.df.loc[
            (scenario_descriptor, funding_fraction, country, slice(None), indicator)
        ].add_prefix("model_")

        try:
            _pf = self.pf_input_data.df.loc[
                (scenario_descriptor, country, slice(None), indicator)
            ].add_prefix("pf_")
        except KeyError:
            _pf = pd.DataFrame(
                index=_model.index,
                columns=["pf_" + c for c in ("low", "central", "high")],
                data=float("nan"),
            )

        try:
            _partner = self.partner_data.df.loc[
                (scenario_descriptor, country, slice(None), indicator)
            ].add_prefix("partner_")
        except KeyError:
            _partner = pd.DataFrame(
                index=_model.index,
                columns=["partner_" + c for c in ("low", "central", "high")],
                data=float("nan"),
            )

        return pd.concat([_model, _pf, _partner], axis=1).sort_index()
