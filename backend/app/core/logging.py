from __future__ import annotations

import logging
import sys

# ANSI Farben
C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
}


def color(level: str) -> str:
    mapping = {
        "DEBUG": C["dim"],
        "INFO": C["cyan"],
        "WARNING": C["yellow"],
        "ERROR": C["red"],
        "CRITICAL": C["red"],
    }
    return mapping.get(level, C["reset"])


class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        s = super().format(record)
        return f"{color(record.levelname)}{s}{C['reset']}"


def progress_bar(label: str, current: int, total: int, width: int = 30) -> str:
    pct = current / total if total else 1.0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"{C['blue']}[{bar}]{C['reset']} {label} {C['green']}{current}/{total}{C['reset']}"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    handler.setFormatter(ColoredFormatter(fmt=fmt, datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
