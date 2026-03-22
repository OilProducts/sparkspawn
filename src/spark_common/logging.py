from __future__ import annotations

import logging
import sys


_SPARK_LOGGER_NAME = "spark"
_SPARK_STDOUT_HANDLER_NAME = "spark-stdout"


def configure_spark_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(_SPARK_LOGGER_NAME)
    if not any(getattr(handler, "name", "") == _SPARK_STDOUT_HANDLER_NAME for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name(_SPARK_STDOUT_HANDLER_NAME)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_spark_logger(name: str) -> logging.Logger:
    configure_spark_logging()
    normalized_name = name.strip()
    if not normalized_name:
        return logging.getLogger(_SPARK_LOGGER_NAME)
    if normalized_name.startswith(f"{_SPARK_LOGGER_NAME}."):
        return logging.getLogger(normalized_name)
    return logging.getLogger(f"{_SPARK_LOGGER_NAME}.{normalized_name}")
