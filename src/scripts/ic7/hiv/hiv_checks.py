from scripts.ic7.hiv.hiv_filehandlers import HIVMixin
from scripts.ic7.shared.common_checks import CommonChecks
from tgftools.checks import DatabaseChecks


class DatabaseChecksHiv(HIVMixin, CommonChecks, DatabaseChecks):
    """This is the class for DatabaseChecks to do with the HIV data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
