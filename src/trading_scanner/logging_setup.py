"""Console compartida — mismo output que antes (Rich, colores en terminal)
más un espejo en texto plano a logs/scanner.log (rotativo) para poder
diagnosticar después de que algo ya pasó (ej. desconexiones de Schwab
fuera de la sesión interactiva)."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_MARKUP_RE = re.compile(r"\[/?[a-zA-Z][^\]]*\]")

_file_logger = logging.getLogger("trading_scanner.file")
_file_logger.setLevel(logging.INFO)
_file_logger.propagate = False
if not _file_logger.handlers:
    _handler = RotatingFileHandler(
        _LOG_DIR / "scanner.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _file_logger.addHandler(_handler)


class TeeConsole(Console):
    """Console de Rich que además escribe cada log() a archivo, sin
    markup de color (ilegible en texto plano)."""

    def log(self, *objects, **kwargs):
        super().log(*objects, **kwargs)
        try:
            texto = " ".join(str(o) for o in objects)
            _file_logger.info(_MARKUP_RE.sub("", texto))
        except Exception:
            pass


console = TeeConsole()
