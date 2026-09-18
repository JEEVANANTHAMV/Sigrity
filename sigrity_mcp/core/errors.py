"""Exceptions raised by the Sigrity automation core."""


class SigrityError(Exception):
    """Base class for all Sigrity automation errors."""


class ExecutableNotFoundError(SigrityError):
    """Raised when a required Sigrity tool executable cannot be located under SIGRITY_HOME."""


class JobNotFoundError(SigrityError):
    """Raised when a job_id does not correspond to a known job."""


class JobStillRunningError(SigrityError):
    """Raised when a blocking result is requested from a job that has not finished."""


class LicenseError(SigrityError):
    """Raised when a Sigrity tool exits with a recognizable FlexNet license failure."""
