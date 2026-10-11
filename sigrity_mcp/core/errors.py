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
    """Legacy exception class. This install is PREMIUM / no-license-required, so this
    should never be raised in normal operation. Kept for backward compatibility."""
