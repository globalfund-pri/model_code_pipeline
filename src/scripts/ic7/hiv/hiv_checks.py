from scripts.ic7.hiv.hiv_filehandlers import HIVMixin
from scripts.ic7.shared.common_checks import CommonChecks
from tgftools.checks import DatabaseChecks


class DatabaseChecksHiv(HIVMixin, CommonChecks, DatabaseChecks):
    """Database validation checks for HIV data.

    This class performs comprehensive validation checks on HIV data including
    structural checks, data quality checks, and consistency checks against
    partner data and PF targets.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
