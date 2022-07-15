import logging


def set_log_info(l: logging.Logger):
    """set logger level to INFO"""
    set_log_level_format(
        l,
        logging.INFO,
        '%(asctime)s %(levelname)s:%(name)s:%(message)s'
    )


def set_log_debug(l: logging.Logger):
    """set logger level to DEBUG, and debug-level output format"""
    set_log_level_format(
        l,
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(l: logging.Logger, level: int, format: str):
    """
    Set logger level and format.

    :param l: logger to configure
    :param level: logging level; see the :py:mod:`logging` constants.
    :param format: logging formatter format string
    """
    formatter: logging.Formatter = logging.Formatter(fmt=format)
    l.handlers[0].setFormatter(formatter)
    l.setLevel(level)
