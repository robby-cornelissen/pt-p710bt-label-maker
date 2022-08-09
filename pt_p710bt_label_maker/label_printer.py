import sys
import argparse
import logging
from typing import Union
from io import BytesIO

from pt_p710bt_label_maker.utils import (
    set_log_debug, set_log_info, add_printer_args
)
from pt_p710bt_label_maker.label_rasterizer import encode_png, rasterize
from pt_p710bt_label_maker.exceptions import (
    DeviceTurnedOffException, InvalidStatusCodeException,
    NoMediaError, CutterJamError, WeakBatteriesError, HighVoltageAdapterError,
    WrongMediaError, CoverOpenError, OverheatingError, UnknownStatusMessageError
)
from pt_p710bt_label_maker.status_message import (
    Mode, RawStatusMessage, ReplyToStatusRequest, PrintingCompleted,
    Notification, PhaseChange, StatusMessage
)
from pt_p710bt_label_maker.connectors import (
    Connector, BluetoothConnector, UsbConnector
)

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class PtP710LabelPrinter:

    def __init__(self, device: Connector):
        self._device: Connector = device

    def __del__(self):
        del self._device

    def _send_invalidate(self):
        # send 100 null bytes
        logger.debug('Sending invalidate command (100 null bytes)')
        self._device.send(b"\x00" * 100)

    def _send_initialize(self):
        # send [1B 40]
        logger.debug('Sending initialize command')
        self._device.send(b"\x1B\x40")

    def _send_switch_dynamic_command_mode(self):
        # set dynamic command mode to "raster mode" [1B 69 61 {01}]
        logger.debug('Setting dynamic command mode to "raster mode"')
        self._device.send(b"\x1B\x69\x61\x01")

    def _send_switch_automatic_status_notification_mode(self):
        # set automatic status notification mode to "notify" [1B 69 21 {00}]
        logger.debug('Setting automatic status notification mode to "notify"')
        self._device.send(b"\x1B\x69\x21\x00")

    def _send_print_information_command(self, data_length: int):
        # print to 24mm tape [1B 69 7A {84 00 18 00 <data length 4 bytes> 00 00}]
        logger.debug('Setting to print on 24mm tape')
        # @TODO tape width is set here
        self._device.send(b"\x1B\x69\x7A\x84\x00\x18\x00")
        self._device.send((data_length >> 4).to_bytes(4, 'little'))
        self._device.send(b"\x00\x00")

    def _send_various_mode_settings(self):
        # set to auto-cut, no mirror printing [1B 69 4D {40}]
        logger.debug('Setting auto-cut mode, no mirror printing')
        # @TODO auto-cut is set here
        self._device.send(b"\x1B\x69\x4D")
        self._device.send(Mode.AUTO_CUT.to_bytes(1, "big"))

    def _send_advanced_mode_settings(self):
        # set print chaining off [1B 69 4B {08}]
        logger.debug('Set print chaining off')
        self._device.send(b"\x1B\x69\x4B\x08")

    def _send_specify_margin_amount(self):
        # set margin (feed) amount to 0 [1B 69 64 {00 00}]
        logger.debug('Set margin (feed) amount to zero (0)')
        self._device.send(b"\x1B\x69\x64\x00\x00")

    def _send_select_compression_mode(self):
        # set to TIFF compression [4D {02}]
        logger.debug('Set compression mode to TIFF')
        self._device.send(b"\x4D\x02")

    def _send_raster_data(self, data: bytearray):
        # send all raster data lines
        logger.debug('Rasterizing image...')
        # @TODO rasterize is called here
        line: bytearray
        for line in rasterize(data):
            logger.debug('Sending raster data line: %s', line.hex(' '))
            self._device.send(bytes(line))
        logger.debug('Done sending raster image data')

    def _send_print_command_with_feeding(self):
        # print and feed [1A]
        logger.debug('Send print and feed command')
        self._device.send(b"\x1A")

    def _send_print_command_without_feeding(self):
        # print and feed [0C]
        logger.debug('Send print WITHOUT feeding command')
        self._device.send(b"\x0C")

    def _send_status_information_request(self):
        # request status information [1B 69 53]
        logger.debug('Request status information')
        self._device.send(b"\x1B\x69\x53")

    def _receive_status_information_response(self) -> StatusMessage:
        # receive status information
        response: bytes = self._device.receive(32)
        logger.debug(
            'Received %d-byte status response ; %s',
            len(response), response.hex(' ')
        )
        raw: RawStatusMessage = RawStatusMessage(response)
        logger.debug('Got status message: %s', raw)
        if raw.status_type == RawStatusMessage.StatusType.TURNED_OFF:
            raise DeviceTurnedOffException(raw)
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
        if raw.error_information1 == 0x01:
            raise NoMediaError(raw)
        if raw.error_information1 == 0x04:
            raise CutterJamError(raw)
        if raw.error_information1 == 0x08:
            raise WeakBatteriesError(raw)
        if raw.error_information1 == 0x40:
            raise HighVoltageAdapterError(raw)
        if raw.error_information2 == 0x01:
            raise WrongMediaError(raw)
        if raw.error_information2 == 0x10:
            raise CoverOpenError(raw)
        if raw.error_information2 == 0x20:
            raise OverheatingError(raw)
        raise UnknownStatusMessageError(raw)

    def print_image(self, image: Union[str, BytesIO], num_copies: int = 1):
        data: bytearray = encode_png(image)
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


def main():
    p = argparse.ArgumentParser(
        description='Brother PT-P710BT Label Printer controller'
    )
    add_printer_args(p)
    p.add_argument(
        'IMAGE_PATH', action='store', type=str, help='Path to image to print'
    )
    args = p.parse_args(sys.argv[1:])
    # set logging level
    if args.verbose:
        set_log_debug(logger)
    else:
        set_log_info(logger)
    device: Connector
    if args.usb:
        device = UsbConnector()
    else:
        device = BluetoothConnector(
            args.bt_address, bt_channel=args.bt_channel
        )
    PtP710LabelPrinter(device).print_image(
        args.IMAGE_PATH, num_copies=args.num_copies
    )


if __name__ == "__main__":
    main()
