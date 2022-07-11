import sys
import argparse
import logging

import bluetooth

from label_rasterizer import encode_png, rasterize
from constants import (
    ErrorInformation1, ErrorInformation2, MediaType, Mode, NotificationNumber,
    PhaseNumberEditingState, PhaseNumberPrintingState, PhaseType, StatusOffset,
    StatusType, TapeColor, TextColor
)
from exceptions import (
    DeviceTurnedOffException, InvalidStatusResponseException,
    InvalidStatusCodeException
)

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


SocketType = bluetooth.BluetoothSocket


class StatusMessage:

    def __init__(self, status_response: bytes):
        self._raw_response: bytes = status_response
        if len(self._raw_response) != 32:
            raise InvalidStatusResponseException(len(self._raw_response))
        self.status_type: int = self._raw_response[StatusOffset.STATUS_TYPE]
        self.type_name: str = StatusType(self.status_type).name
        logger.debug(
            'Parsing status response of type %s (%d)',
            self.type_name, self.status_type
        )
        self.is_final_status: bool = False
        # @TODO Fix up the rest of these to provide the information programmatically, and maybe use subclasses...
        if self.status_type == StatusType.TURNED_OFF:
            self.is_final_status = True
            raise DeviceTurnedOffException()
        elif self.status_type == StatusType.REPLY_TO_STATUS_REQUEST:
            self.handle_reply_to_status_request(self._raw_response)
        elif self.status_type == StatusType.PRINTING_COMPLETED:
            self.handle_printing_completed(self._raw_response)
        elif self.status_type == StatusType.ERROR_OCCURRED:
            self.handle_error_occurred(self._raw_response)
        elif self.status_type == StatusType.NOTIFICATION:
            self.handle_notification(self._raw_response)
        elif self.status_type == StatusType.PHASE_CHANGE:
            self.handle_phase_change(self._raw_response)
        else:
            raise InvalidStatusCodeException(self.status_type)

    def handle_reply_to_status_request(self, status_information: bytes):
        print("Printer status")
        print("--------------")
        print(
            "Media width: %dmm" % status_information[
                StatusOffset.MEDIA_WIDTH
            ]
        )
        print(
            "Media type: %s" % MediaType(
                status_information[StatusOffset.MEDIA_TYPE]
            ).name
        )
        print(
            "Tape color information: %s" % TapeColor(
                status_information[StatusOffset.TAPE_COLOR_INFORMATION]
            ).name
        )
        print(
            "Text color information: %s" % TextColor(
                status_information[StatusOffset.TEXT_COLOR_INFORMATION]
            ).name
        )
        print()

    def handle_printing_completed(self, status_information: bytes):
        print("Printing completed")
        print("------------------")
        mode = Mode(status_information[StatusOffset.MODE])
        logger.debug('Printing completed; mode: %x', status_information[StatusOffset.MODE])
        print("Mode: %s" % ", ".join([f.name for f in Mode if f in mode]))
        # @TODO fix this
        sys.exit(0)

    def handle_error_occurred(self, status_information: bytes):
        print("Error occurred")
        print("--------------")
        logger.debug(
            'Error occurred. ERROR_INFORMATION_1=%x ERROR_INFORMATION_2=%s',
            status_information[StatusOffset.ERROR_INFORMATION_1],
            status_information[StatusOffset.ERROR_INFORMATION_2]
        )
        error_information_1 = ErrorInformation1(
            status_information[StatusOffset.ERROR_INFORMATION_1]
        )
        error_information_2 = ErrorInformation1(
            status_information[StatusOffset.ERROR_INFORMATION_2]
        )
        print(
            "Error information 1: %s" % ", ".join([
                f.name for f in ErrorInformation1 if f in error_information_1
            ])
        )
        print(
            "Error information 2: %s" % ", ".join([
                f.name for f in ErrorInformation2 if f in error_information_2
            ])
        )
        # @TODO replace with custom status error exceptions
        raise RuntimeError(
            'Printer status error. '
            '@TODO replace this with custom exceptions'
        )

    def handle_notification(self, status_information: bytes):
        print("Notification")
        print("------------")
        logger.debug(
            'Got notification: %x',
            status_information[StatusOffset.NOTIFICATION_NUMBER]
        )
        print(
            "Notification number: %s" % NotificationNumber(
                status_information[StatusOffset.NOTIFICATION_NUMBER]
            ).name
        )
        print()

    def handle_phase_change(self, status_information: bytes):
        print("Phase changed")
        print("-------------")
        phase_type = status_information[StatusOffset.PHASE_TYPE]
        phase_number = int.from_bytes(
            status_information[StatusOffset.PHASE_NUMBER:StatusOffset.PHASE_NUMBER + 2], "big"
        )
        logger.debug(
            'Phase change; phase_type=%x, phase_number=%x',
            phase_type, phase_number
        )
        print("Phase type: %s" % PhaseType(phase_type).name)
        print(
            "Phase number: %s" % (
                PhaseNumberPrintingState(phase_number) if phase_type == PhaseType.PRINTING_STATE else PhaseNumberEditingState(phase_number)
            ).name
        )
        print()


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
        return StatusMessage(response)

    def print_image(self, image_path: str):
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
        self._send_raster_data(data)
        self._send_print_command_with_feeding()
        # @TODO fix this infinite loop
        while True:
            status: StatusMessage = self._receive_status_information_response()
            logger.info('Status: %s', status)


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
    ).print_image(args.IMAGE_PATH)


if __name__ == "__main__":
    main(sys.argv[1:])
