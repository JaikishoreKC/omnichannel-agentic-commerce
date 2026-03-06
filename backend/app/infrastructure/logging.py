import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def _ensure_console_encoding_safety() -> None:
    """Avoid hard failures when console encoding cannot represent rich trace glyphs."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                # Keep existing encoding, but make unencodable chars non-fatal.
                reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                continue

def setup_logging(level: int = logging.INFO) -> None:
    """Configures structured logging with structlog."""
    _ensure_console_encoding_safety()
    
    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if sys.stderr.isatty():
        # Colorful console logging for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=False,
                exception_formatter=structlog.dev.plain_traceback,
            )
        ]
    else:
        # JSON logging for production/piped logs
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

def get_logger(name: str | None = None) -> Any:
    """Returns a structlog logger."""
    return structlog.get_logger(name)
