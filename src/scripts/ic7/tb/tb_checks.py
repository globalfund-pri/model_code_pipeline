from scripts.ic7.shared.common_checks import CommonChecks
from scripts.ic7.tb.tb_filehandlers import TBMixin
from tgftools.checks import DatabaseChecks


class DatabaseChecksTb(TBMixin, CommonChecks, DatabaseChecks):
    """This is the class for DatabaseChecks to do with the Tb data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
