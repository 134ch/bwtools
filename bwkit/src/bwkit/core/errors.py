"""Typed errors with stable machine-readable codes.

The `code` attribute is the contract agents branch on. `error_class` (the
Python class name) is for humans in logs. These codes are written verbatim
to the metrics `error_code` column.
"""

from __future__ import annotations


class BwkitError(Exception):
    """Base class. All bwkit-raised errors carry a stable `code`."""

    code: str = "unexpected"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class MissingExtraError(BwkitError):
    code = "missing_extra"

    def __init__(self, *, extra: str, install: str) -> None:
        self.extra = extra
        self.install = install
        super().__init__(
            f"extra '{extra}' is not installed. run: {install}",
            code="missing_extra",
        )


class MissingCredentialError(BwkitError):
    code = "missing_credential"

    def __init__(self, *, var: str, hint: str = "") -> None:
        self.var = var
        self.hint = hint or f"set {var} in ~/.bwkit/.env or export it in your shell"
        super().__init__(
            f"required credential not set: {var}. {self.hint}",
            code="missing_credential",
        )


class ToolError(BwkitError):
    """A tool's run() raised a classified failure. Use a stable `code`."""

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message, code=code)


class InvalidArgumentsError(BwkitError):
    code = "invalid_arguments"

    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_arguments")


class ToolDisabledError(BwkitError):
    code = "tool_disabled"

    def __init__(self, tool: str) -> None:
        self.tool = tool
        super().__init__(
            f"tool '{tool}' is disabled. enable it with: bwkit enable {tool}",
            code="tool_disabled",
        )


class UnknownToolError(BwkitError):
    code = "unknown_tool"

    def __init__(self, tool: str) -> None:
        self.tool = tool
        super().__init__(f"unknown tool: {tool!r}", code="unknown_tool")
