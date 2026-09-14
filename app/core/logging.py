import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False

def setup_logging() -> None:
	global _configured
	if _configured:
		return

	level = getattr(
		logging,
		settings.log_level.upper(),
		logging.INFO
	)
	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT))

	root = logging.getLogger()
	root.setLevel(level)
	root.handlers.clear()
	root.addHandler(handler)

	logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

	_configured = True

def get_logger(name: str) -> logging.Logger:
	return logging.getLogger(name)
