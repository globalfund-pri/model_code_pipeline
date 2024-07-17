from typing import Optional

import numpy as np
import pandas as pd

from tgftools.filehandler import Gp, Parameters, Indicators, Scenarios  # RegionInformation
from tgftools.filehandler import ModelResults, PartnerData, PFInputData


class Database:
    """This is the Database class. It holds all data related to a single disease. It also holds an emulator which
    can be used to create results for scenarios that are not stored."""

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

        # Check that all these filehandlers have the same disease_name (if they are defined)
        disease_name_where_args_defined = np.array([x.disease_name for x in (gp, partner_data, pf_input_data, model_results) if x is not None])
        assert (disease_name_where_args_defined == disease_name_where_args_defined[0]).all()

    def get_country(
        self,
        country: str,
        scenario_descriptor: str,
        funding_fraction: float,
        indicator: str,
    ) -> pd.DataFrame:
        """
        Data for a particular country, scenario_descriptor, funding_fraction and indicator.

        Args:
            country: The country (ISO3 code)
            scenario_descriptor: The scenario descriptor (e.g. 'default')
            funding_fraction: The funding fraction (e.g. 0.9)
            indicator: The indicator (e.g.'cases')

        Returns:
            Dataframe that assembles the information from all sources for a particular country, for a particular
             scenario, funding_fraction and indicator (If the indicator is not found within the
             pf_input_date or partner_data, then NaN's are used instead.
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
