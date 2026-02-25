from scripts.ic7.shared.common_checks import CommonChecks
from scripts.ic7.tb.tb_filehandlers import TBMixin
from tgftools.checks import DatabaseChecks


class DatabaseChecksTb(TBMixin, CommonChecks, DatabaseChecks):
    """Database validation checks for TB data.

    This class performs comprehensive validation checks on TB data including
    structural checks, data quality checks, and consistency checks against
    partner data and PF targets.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
