from __future__ import annotations

import logging
from logging.config import fileConfig


def create_logger(logger_name: str) -> logging.Logger:
    """
    Creates logger and returns an instance of logging object.

    :param logger_name: Gets the logger by that name

    :return: Logging Object.
    """
    # Setting up the logger
    fileConfig("logging.conf")
    logger = logging.getLogger(logger_name)
    return logger
