from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler


def create_logger(module_name: str, level: int | str = logging.INFO) -> logging.Logger:
    """
    Creates logger and returns an instance of logging object.
    :param level: The level for logging. (Default: logging.INFO)
    :param module_name: Logger name that will appear in text.
    :return: Logging Object.
    """
    # Setting up the root logger
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_stream = logging.StreamHandler()
    log_stream.setLevel(level)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s')
    log_stream.setFormatter(formatter)
    logger.addHandler(log_stream)

    file_stream = TimedRotatingFileHandler("./logs/user_verification.log", when='D', interval=1, backupCount=15)
    file_stream.setLevel(level)
    file_stream.setFormatter(formatter)
    logger.addHandler(file_stream)
    return logger
