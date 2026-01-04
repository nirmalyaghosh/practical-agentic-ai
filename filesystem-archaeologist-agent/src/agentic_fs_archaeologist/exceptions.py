class BaseExceptionFSArchaeologist(Exception):
    """
    Base exception for all agent errors.
    """
    pass


class ConfigurationError(BaseExceptionFSArchaeologist):
    """
    Configuration error.
    """
    pass


class MemoryError(BaseExceptionFSArchaeologist):
    """
    Base exception for memory system errors.
    """
    pass


class MemoryStorageError(MemoryError):
    """
    Used to indicate error when an agent attempts to store to memory.
    """
    pass


class MemoryRetrievalError(MemoryError):
    """
    Used to indicate error when an agent attempts to retrieve from memory.
    """
    pass


class ValidationError(BaseExceptionFSArchaeologist):
    """
    Used to indicate error scenario when validation failed.
    """
    pass


class ClassificationError(BaseExceptionFSArchaeologist):
    """
    Used to indicate error scenario when an error was encountered during
    classification.
    """
    pass


class QuarantineError(BaseExceptionFSArchaeologist):
    """
    Used to indicate error scenario when an error was encountered during
    quarantine operations.
    """
    pass


class RecoveryError(QuarantineError):
    """
    Used to indicate error scenario when an error was encountered when
    recovering from quarantine.
    """

    def __init__(self, quarantine_id: str, reason: str):
        self.quarantine_id = quarantine_id
        self.reason = reason
        exception_message = f"Failed to recover '{quarantine_id}': {reason}"
        super().__init__(exception_message)
