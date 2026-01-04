from agentic_fs_archaeologist.exceptions import BaseExceptionFSArchaeologist


class SafetyError(BaseExceptionFSArchaeologist):
    """
    Base exception for safety violations.
    """
    pass


class SystemFileError(SafetyError):
    """
    Used to indicate the error scenario where an operation failed because it
    attempted an operation on a system file.
    """

    def __init__(self, path: str):
        self.path = path
        exception_message = f"Operation blocked: {path} is a system file"
        super().__init__(exception_message)


class FileInUseError(SafetyError):
    """
    Used to indicate the error scenario where an operation failed because the
    file is in use.
    """

    def __init__(self, path: str):
        self.path = path
        exception_message = f"Operation blocked: {path} is currently in use"
        super().__init__(exception_message)


class PermissionError(SafetyError):
    """
    Used to indicate the error scenario where an agent has insufficient
    permissions for operation.
    """
    def __init__(self, path: str, operation: str):
        self.path = path
        self.operation = operation
        exception_message = f"Permission denied: cannot {operation} {path}"
        super().__init__(exception_message)
