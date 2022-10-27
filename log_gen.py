from __future__ import annotations

import logging
from logging.config import fileConfig


def create_logger() -> logging.Logger:
    """
    Creates logger and returns an instance of logging object.
    :return: Logging Object.
    """
    # Setting up the logger
    fileConfig("logging.conf")
    logger = logging.getLogger("user_verification")
    return logger
