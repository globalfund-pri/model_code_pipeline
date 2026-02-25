from scripts.ic7.malaria.malaria_filehandlers import MALARIAMixin
from scripts.ic7.shared.common_checks import CommonChecks
from tgftools.checks import DatabaseChecks


class DatabaseChecksMalaria(MALARIAMixin, CommonChecks, DatabaseChecks):
    """Database validation checks for malaria data.

    This class performs comprehensive validation checks on malaria data including
    structural checks, data quality checks, and consistency checks against
    partner data and PF targets.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
