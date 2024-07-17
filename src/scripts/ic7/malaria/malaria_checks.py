from scripts.ic7.malaria.malaria_filehandlers import MALARIAMixin
from scripts.ic7.shared.common_checks import CommonChecks
from tgftools.checks import DatabaseChecks


class DatabaseChecksMalaria(MALARIAMixin, CommonChecks, DatabaseChecks):
    """This is the class for DatabaseChecks to do with the Malaria data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
