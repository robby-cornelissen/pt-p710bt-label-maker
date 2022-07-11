import sys
import contextlib
import bluetooth
from label_rasterizer import encode_png, rasterize
from constants import *

SocketType = bluetooth.BluetoothSocket


@contextlib.contextmanager
def bt_socket_manager(*args, **kwargs):
    socket: SocketType = bluetooth.BluetoothSocket(*args, **kwargs)
    yield socket
    socket.close()


class PtP710LabelMaker:

    def __init__(self):
        pass

    def _send_invalidate(self, socket: SocketType):
        # send 100 null bytes
        socket.send(b"\x00" * 100)

    def _send_initialize(self, socket: SocketType):
        # send [1B 40]
        socket.send(b"\x1B\x40")

    def _send_switch_dynamic_command_mode(self, socket: SocketType):
        # set dynamic command mode to "raster mode" [1B 69 61 {01}]
        socket.send(b"\x1B\x69\x61\x01")

    def _send_switch_automatic_status_notification_mode(
        self, socket: SocketType
    ):
        # set automatic status notification mode to "notify" [1B 69 21 {00}]
        socket.send(b"\x1B\x69\x21\x00")

    def _send_print_information_command(self, socket: SocketType, data_length: int):
        # print to 24mm tape [1B 69 7A {84 00 18 00 <data length 4 bytes> 00 00}]
        # @TODO tape width is set here
        socket.send(b"\x1B\x69\x7A\x84\x00\x18\x00")
        socket.send((data_length >> 4).to_bytes(4, 'little'))
        socket.send(b"\x00\x00")

    def _send_various_mode_settings(self, socket: SocketType):
        # set to auto-cut, no mirror printing [1B 69 4D {40}]
        # @TODO auto-cut is set here
        socket.send(b"\x1B\x69\x4D")
        socket.send(Mode.AUTO_CUT.to_bytes(1, "big"))

    def _send_advanced_mode_settings(self, socket: SocketType):
        # set print chaining off [1B 69 4B {08}]
        socket.send(b"\x1B\x69\x4B\x08")

    def _send_specify_margin_amount(self, socket: SocketType):
        # set margin (feed) amount to 0 [1B 69 64 {00 00}]
        socket.send(b"\x1B\x69\x64\x00\x00")

    def _send_select_compression_mode(self, socket: SocketType):
        # set to TIFF compression [4D {02}]
        socket.send(b"\x4D\x02")

    def _send_raster_data(self, socket: SocketType, data: bytearray):
        # send all raster data lines
        # @TODO rasterize is called here
        for line in rasterize(data):
            socket.send(bytes(line))

    def _send_print_command_with_feeding(self, socket: SocketType):
        # print and feed [1A]
        socket.send(b"\x1A")

    def _send_status_information_request(self, socket: SocketType):
        # request status information [1B 69 53]
        socket.send(b"\x1B\x69\x53")

    def _receive_status_information_response(self, socket: SocketType):
        # receive status information
        response = socket.recv(32)
        # @TODO fix this
        if (len(response) != 32):
            sys.exit("Expected 32 bytes, but only received %d" % len(response))
        return response

    def _handle_status_information(self, status_information):
        # @TODO completely rewrite this using a class or something
        def handle_reply_to_status_request(status_information):
            print("Printer status")
            print("--------------")
            print(
                "Media width: %dmm" % status_information[
                    STATUS_OFFSET_MEDIA_WIDTH
                ]
            )
            print(
                "Media type: %s" % MediaType(
                    status_information[STATUS_OFFSET_MEDIA_TYPE]
                ).name
            )
            print(
                "Tape color information: %s" % TapeColor(
                    status_information[STATUS_OFFSET_TAPE_COLOR_INFORMATION]
                ).name
            )
            print(
                "Text color information: %s" % TextColor(
                    status_information[STATUS_OFFSET_TEXT_COLOR_INFORMATION]
                ).name
            )
            print()

        def handle_printing_completed(status_information):
            print("Printing completed")
            print("------------------")
            mode = Mode(status_information[STATUS_OFFSET_MODE])
            print("Mode: %s" % ", ".join([f.name for f in Mode if f in mode]))
            # @TODO fix this
            sys.exit(0)

        def handle_error_occurred(status_information):
            print("Error occurred")
            print("--------------")
            error_information_1 = ErrorInformation1(
                status_information[STATUS_OFFSET_ERROR_INFORMATION_1]
            )
            error_information_2 = ErrorInformation1(
                status_information[STATUS_OFFSET_ERROR_INFORMATION_2]
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
            # @TODO fix this
            sys.exit("An error has occurred; exiting program")

        def handle_turned_off(_):
            print("Turned off")
            print("----------")
            # @TODO fix this
            sys.exit("Device was turned off")

        def handle_notification(status_information):
            print("Notification")
            print("------------")
            print(
                "Notification number: %s" % NotificationNumber(
                    status_information[STATUS_OFFSET_NOTIFICATION_NUMBER]
                ).name
            )
            print()

        def handle_phase_change(status_information):
            print("Phase changed")
            print("-------------")
            phase_type = status_information[STATUS_OFFSET_PHASE_TYPE]
            phase_number = int.from_bytes(
                status_information[STATUS_OFFSET_PHASE_NUMBER:STATUS_OFFSET_PHASE_NUMBER + 2], "big"
            )
            print("Phase type: %s" % PhaseType(phase_type).name)
            print(
                "Phase number: %s" % (
                    PhaseNumberPrintingState(phase_number) if phase_type == PhaseType.PRINTING_STATE else PhaseNumberEditingState(phase_number)
                ).name
            )
            print()

        handlers = {
            StatusType.REPLY_TO_STATUS_REQUEST: handle_reply_to_status_request,
            StatusType.PRINTING_COMPLETED: handle_printing_completed,
            StatusType.ERROR_OCCURRED: handle_error_occurred,
            StatusType.TURNED_OFF: handle_turned_off,
            StatusType.NOTIFICATION: handle_notification,
            StatusType.PHASE_CHANGE: handle_phase_change
        }

        status_type = status_information[STATUS_OFFSET_STATUS_TYPE]

        handlers[status_type](status_information)

    def make_label(self, image_path: str, bt_address: str, bt_channel: str):
        data: bytearray = encode_png(image_path)
        with bt_socket_manager(bluetooth.RFCOMM) as socket:
            socket.connect((bt_address, bt_channel))
            self._send_invalidate(socket)
            self._send_initialize(socket)
            self._send_status_information_request(socket)

            status_information = self._receive_status_information_response(socket)
            self._handle_status_information(status_information)

            self._send_switch_dynamic_command_mode(socket)
            self._send_switch_automatic_status_notification_mode(socket)
            self._send_print_information_command(socket, len(data))
            self._send_various_mode_settings(socket)
            self._send_advanced_mode_settings(socket)
            self._send_specify_margin_amount(socket)
            self._send_select_compression_mode(socket)
            self._send_raster_data(socket, data)
            self._send_print_command_with_feeding(socket)

            while True:
                status_information = self._receive_status_information_response(socket)
                self._handle_status_information(status_information)


def main(*args):
    if len(args) < 3:
        print("Usage: %s <image-path> <bt-address> [bt-channel]" % args[0])
        sys.exit(1)

    image_path = args[1]
    bt_address = args[2]
    bt_channel = args[3] if len(args) > 3 else 1

    PtP710LabelMaker().make_label(image_path, bt_address, bt_channel)


if __name__ == "__main__":
    main(*sys.argv)
