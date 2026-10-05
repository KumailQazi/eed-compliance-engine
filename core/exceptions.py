"""Domain-specific exceptions for the EED compliance engine."""


class EEDComplianceError(Exception):
    """Base exception for all EED compliance engine errors."""
    pass


class ValidationError(EEDComplianceError):
    """Raised when input telemetry fails schema or business-rule validation."""
    pass


class CalculationError(EEDComplianceError):
    """Raised when a metric cannot be computed from the supplied inputs."""
    pass


class AuditError(EEDComplianceError):
    """Raised when the audit trail cannot be written or is tampered with."""
    pass
