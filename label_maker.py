#!/usr/bin/env python
import sys
import argparse
import logging

import bluetooth

from label_rasterizer import encode_png, rasterize
from exceptions import (
    DeviceTurnedOffException, InvalidStatusResponseException,
    InvalidStatusCodeException
)
from status_message import (
    Mode, RawStatusMessage, ReplyToStatusRequest, PrintingCompleted,
    Notification, PhaseChange, StatusMessage
)

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()

SocketType = bluetooth.BluetoothSocket


class PtP710LabelMaker:

    def __init__(self, bt_address: str, bt_channel: int):
        logger.debug('Opening Bluetooth RFCOMM socket')
        self._socket: SocketType = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        logger.info(
            'Connecting to bluetooth device %s on channel %d',
            bt_address, bt_channel
        )
        self._socket.connect((bt_address, bt_channel))
        logger.debug('Connected to bluetooth device.')

    def __del__(self):
        logger.debug('Closing socket connection')
        self._socket.close()

    def _send_invalidate(self):
        # send 100 null bytes
        logger.debug('Sending invalidate command (100 null bytes)')
        self._socket.send(b"\x00" * 100)

    def _send_initialize(self):
        # send [1B 40]
        logger.debug('Sending initialize command')
        self._socket.send(b"\x1B\x40")

    def _send_switch_dynamic_command_mode(self):
        # set dynamic command mode to "raster mode" [1B 69 61 {01}]
        logger.debug('Setting dynamic command mode to "raster mode"')
        self._socket.send(b"\x1B\x69\x61\x01")

    def _send_switch_automatic_status_notification_mode(self):
        # set automatic status notification mode to "notify" [1B 69 21 {00}]
        logger.debug('Setting automatic status notification mode to "notify"')
        self._socket.send(b"\x1B\x69\x21\x00")

    def _send_print_information_command(self, data_length: int):
        # print to 24mm tape [1B 69 7A {84 00 18 00 <data length 4 bytes> 00 00}]
        logger.debug('Setting to print on 24mm tape')
        # @TODO tape width is set here
        self._socket.send(b"\x1B\x69\x7A\x84\x00\x18\x00")
        self._socket.send((data_length >> 4).to_bytes(4, 'little'))
        self._socket.send(b"\x00\x00")

    def _send_various_mode_settings(self):
        # set to auto-cut, no mirror printing [1B 69 4D {40}]
        logger.debug('Setting auto-cut mode, no mirror printing')
        # @TODO auto-cut is set here
        self._socket.send(b"\x1B\x69\x4D")
        self._socket.send(Mode.AUTO_CUT.to_bytes(1, "big"))

    def _send_advanced_mode_settings(self):
        # set print chaining off [1B 69 4B {08}]
        logger.debug('Set print chaining off')
        self._socket.send(b"\x1B\x69\x4B\x08")

    def _send_specify_margin_amount(self):
        # set margin (feed) amount to 0 [1B 69 64 {00 00}]
        logger.debug('Set margin (feed) amount to zero (0)')
        self._socket.send(b"\x1B\x69\x64\x00\x00")

    def _send_select_compression_mode(self):
        # set to TIFF compression [4D {02}]
        logger.debug('Set compression mode to TIFF')
        self._socket.send(b"\x4D\x02")

    def _send_raster_data(self, data: bytearray):
        # send all raster data lines
        logger.debug('Rasterizing image...')
        # @TODO rasterize is called here
        line: bytearray
        for line in rasterize(data):
            logger.debug('Sending raster data line: %x', line)
            self._socket.send(bytes(line))
        logger.debug('Done sending raster image data')

    def _send_print_command_with_feeding(self):
        # print and feed [1A]
        logger.debug('Send print and feed command')
        self._socket.send(b"\x1A")

    def _send_print_command_without_feeding(self):
        # print and feed [0C]
        logger.debug('Send print WITHOUT feeding command')
        self._socket.send(b"\x0C")

    def _send_status_information_request(self):
        # request status information [1B 69 53]
        logger.debug('Request status information')
        self._socket.send(b"\x1B\x69\x53")

    def _receive_status_information_response(self) -> StatusMessage:
        # receive status information
        response: bytes = self._socket.recv(32)
        logger.debug(
            'Received %d-byte status response ; %x', len(response), response
        )
        raw: RawStatusMessage = RawStatusMessage(response)
        logger.debug('Got status message: %s', raw)
        if raw.status_type == RawStatusMessage.StatusType.TURNED_OFF:
            raise DeviceTurnedOffException()
        elif raw.status_type == RawStatusMessage.StatusType.REPLY_TO_STATUS_REQUEST:
            return ReplyToStatusRequest(raw)
        elif raw.status_type == RawStatusMessage.StatusType.PRINTING_COMPLETED:
            return PrintingCompleted(raw)
        elif raw.status_type == RawStatusMessage.StatusType.NOTIFICATION:
            return Notification(raw)
        elif raw.status_type == RawStatusMessage.StatusType.PHASE_CHANGE:
            return PhaseChange(raw)
        elif raw.status_type != RawStatusMessage.StatusType.ERROR_OCCURRED:
            raise InvalidStatusCodeException(raw.status_type)
        # else it's an ERROR_OCCURRED type
        """
        class ErrorInformation1(IntFlag):
            NO_MEDIA = 0x01
            CUTTER_JAM = 0x04
            WEAK_BATTERIES = 0x08
            HIGH_VOLTAGE_ADAPTER = 0x40


        class ErrorInformation2(IntFlag):
            WRONG_MEDIA = 0x01
            COVER_OPEN = 0x10
            OVERHEATING = 0x20
        """
        # @TODO raise specific exception classes
        raise RuntimeError(
            f'PRINTER ERROR Occurred: status_type={raw.status_type:x} '
            f'error_information_1={raw.error_information1:x} '
            f'error_information_2={raw.error_information2:x}'
        )

    def print_image(self, image_path: str, num_copies: int = 1):
        logger.debug('Encoding PNG image at %s', image_path)
        data: bytearray = encode_png(image_path)
        logger.debug('Encoded to bytearray of length %d', len(data))
        self._send_invalidate()
        self._send_initialize()
        self._send_status_information_request()
        status: StatusMessage = self._receive_status_information_response()
        logger.info('Status: %s', status)
        self._send_switch_dynamic_command_mode()
        self._send_switch_automatic_status_notification_mode()
        self._send_print_information_command(len(data))
        self._send_various_mode_settings()
        self._send_advanced_mode_settings()
        self._send_specify_margin_amount()
        self._send_select_compression_mode()
        i: int
        for i in range(0, num_copies):
            logger.info('Printing copy %d of %d', i + 1, num_copies)
            self._send_raster_data(data)
            if i == num_copies - 1:
                self._send_print_command_with_feeding()
            else:
                self._send_print_command_without_feeding()
            while not isinstance(status, PrintingCompleted):
                status: StatusMessage = self._receive_status_information_response()
                logger.info('Status: %s', status)
        logger.info('Done.')


def set_log_info():
    """set logger level to INFO"""
    set_log_level_format(logging.INFO,
                         '%(asctime)s %(levelname)s:%(name)s:%(message)s')


def set_log_debug():
    """set logger level to DEBUG, and debug-level output format"""
    set_log_level_format(
        logging.DEBUG,
        "%(asctime)s [%(levelname)s %(filename)s:%(lineno)s - "
        "%(name)s.%(funcName)s() ] %(message)s"
    )


def set_log_level_format(level, format):
    """
    Set logger level and format.

    :param level: logging level; see the :py:mod:`logging` constants.
    :type level: int
    :param format: logging formatter format string
    :type format: str
    """
    formatter = logging.Formatter(fmt=format)
    logger.handlers[0].setFormatter(formatter)
    logger.setLevel(level)


def main(argv):
    p = argparse.ArgumentParser(
        description='Brother PT-P710BT Label Maker controller'
    )
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
    p.add_argument(
        'IMAGE_PATH', action='store', type=str, help='Path to image to print'
    )
    p.add_argument(
        'BT_ADDRESS', action='store', type=str,
        help='BlueTooth device (MAC) address to connect to; must '
             'already be paired'
    )
    args = p.parse_args(argv)
    # set logging level
    if args.verbose:
        set_log_debug()
    else:
        set_log_info()
    PtP710LabelMaker(
        args.BT_ADDRESS, args.bt_channel
    ).print_image(args.IMAGE_PATH, num_copies=args.num_copies)


if __name__ == "__main__":
    main(sys.argv[1:])
