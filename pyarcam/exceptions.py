"""Errors raised by the Arcam control client."""


class ArcamError(Exception):
    """Base class for pyarcam errors."""


class ArcamProtocolError(ArcamError):
    """Malformed frame or unexpected message layout."""


class ArcamCommandError(ArcamError):
    """The amplifier rejected a command (non-zero answer code).

    Attributes:
        answer_code: Raw answer byte from the unit.
        zone: Zone number from the response.
        command: Command code from the response.
    """

    def __init__(
        self,
        message: str,
        *,
        answer_code: int,
        zone: int,
        command: int,
    ) -> None:
        super().__init__(message)
        self.answer_code = answer_code
        self.zone = zone
        self.command = command


class ArcamTimeoutError(ArcamError):
    """No matching response before timeout."""
