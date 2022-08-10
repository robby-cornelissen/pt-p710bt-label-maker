import logging
from argparse import ArgumentParser
from pt_p710bt_label_maker.media_info import TAPE_MM_TO_PX


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


def add_printer_args(p: ArgumentParser):
    p.add_argument(
        '-v', '--verbose', dest='verbose', action='store_true',
        default=False, help='debug-level output.'
    )
    p.add_argument(
        '-C', '--bt-channel', dest='bt_channel', action='store', type=int,
        default=1, help='BlueTooth Channel (default: 1)'
    )
    p.add_argument(
        '-c', '--copies', dest='num_copies', action='store', type=int,
        default=1, help='Print this number of copies of each image (default: 1)'
    )
    usb_or_bt = p.add_mutually_exclusive_group(required=True)
    usb_or_bt.add_argument(
        '-B', '--bluetooth-address', dest='bt_address', action='store',
        type=str,
        default=None, help='BlueTooth device (MAC) address to connect to; must '
                           'already be paired'
    )
    usb_or_bt.add_argument(
        '-U', '--usb', dest='usb', action='store_true', default=False,
        help='Use USB instead of bluetooth'
    )
    p.add_argument(
        '-T', '--tape-mm', dest='tape_mm', action='store', type=int,
        default=24, choices=TAPE_MM_TO_PX.keys(),
        help='Width of tape in mm. Use 4 for 3.5mm tape.'
    )
