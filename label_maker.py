from enum import IntEnum, IntFlag
import sys
import contextlib
import bluetooth
from label_rasterizer import encode_png, rasterize


STATUS_OFFSET_ERROR_INFORMATION_1 = 8
STATUS_OFFSET_ERROR_INFORMATION_2 = 9
STATUS_OFFSET_MEDIA_WIDTH = 10
STATUS_OFFSET_MEDIA_TYPE = 11
STATUS_OFFSET_MODE = 15
STATUS_OFFSET_MEDIA_LENGTH = 17
STATUS_OFFSET_STATUS_TYPE = 18
STATUS_OFFSET_PHASE_TYPE = 19
STATUS_OFFSET_PHASE_NUMBER= 20
STATUS_OFFSET_NOTIFICATION_NUMBER = 22
STATUS_OFFSET_TAPE_COLOR_INFORMATION = 24
STATUS_OFFSET_TEXT_COLOR_INFORMATION = 25
STATUS_OFFSET_HARDWARE_SETTINGS = 26


class ErrorInformation1(IntFlag):
    NO_MEDIA = 0x01
    CUTTER_JAM = 0x04
    WEAK_BATTERIES = 0x08
    HIGH_VOLTAGE_ADAPTER = 0x40


class ErrorInformation2(IntFlag):
    WRONG_MEDIA = 0x01
    COVER_OPEN = 0x10
    OVERHEATING = 0x20


class MediaType(IntEnum):
    NO_MEDIA = 0x00
    LAMINATED_TAPE = 0x01
    NON_LAMINATED_TAPE = 0x03
    HEAT_SHRINK_TUBE = 0x11
    INCOMPATIBLE_TAPE = 0xFF


class Mode(IntFlag):
    AUTO_CUT = 0x40
    MIRROR_PRITING = 0x80


class StatusType(IntEnum):
    REPLY_TO_STATUS_REQUEST = 0x00
    PRINTING_COMPLETED = 0x01
    ERROR_OCCURRED = 0x02
    TURNED_OFF = 0x04
    NOTIFICATION = 0x05
    PHASE_CHANGE = 0x06


class PhaseType(IntEnum):
    EDITING_STATE = 0x00
    PRINTING_STATE = 0x01


class PhaseNumberEditingState(IntEnum):
    EDITING_STATE = 0x0000
    FEED = 0x0001

class PhaseNumberPrintingState(IntEnum):
    PRINTING = 0x0000
    COVER_OPEN_WHILE_RECEIVING = 0x0014


class NotificationNumber(IntEnum):
    NOT_AVAILABLE = 0x00
    COVER_OPEN = 0x01
    COVER_CLOSED = 0x02


class TapeColor(IntEnum):
    WHITE = 0x01
    OTHER = 0x02
    CLEAR = 0x03
    RED = 0x04
    BLUE = 0x05
    YELLOW = 0x06
    GREEN = 0x07
    BLACK = 0x08
    CLEAR_WHITE_TEXT = 0x09
    MATTE_WHITE = 0x20
    MATTE_CLEAR = 0x21
    MATTE_SILVER = 0x22
    SATIN_GOLD = 0x23
    SATIN_SILVER = 0x24
    BLUE_D = 0x30
    RED_D = 0x31
    FLUORESCENT_ORANGE = 0x40
    FLUORESCENT_YELLOW = 0x41
    BERRY_PINK_S = 0x50
    LIGHT_GRAY_S = 0x51
    LIME_GREEN_S = 0x52
    YELLOW_F = 0x60
    PINK_F = 0x61
    BLUE_F= 0x62
    WHITE_HEAT_SHRINK_TUBE = 0x70
    WHITE_FLEX_ID = 0x90
    YELLOW_FLEX_ID = 0x91
    CLEANING = 0xF0
    STENCIL = 0xF1
    INCOMPATIBLE = 0xFF


class TextColor(IntEnum):
    WHITE = 0x01
    OTHER = 0x02
    RED = 0x04
    BLUE = 0x05
    BLACK = 0x08
    GOLD = 0x0A
    BLUE_F = 0x62
    CLEANING = 0xF0
    STENCIL = 0xF1
    INCOMPATIBLE = 0XFF


@contextlib.contextmanager
def bt_socket_manager(*args, **kwargs):
    socket = bluetooth.BluetoothSocket(*args, **kwargs)

    yield socket

    socket.close()


def make_label(image_path, bt_address, bt_channel):
    data = encode_png(image_path)

    with bt_socket_manager(bluetooth.RFCOMM) as socket:
        socket.connect((bt_address, bt_channel))

        send_invalidate(socket)
        send_initialize(socket)
        send_status_information_request(socket)

        status_information = receive_status_information_response(socket)
        handle_status_information(status_information)

        send_switch_dynamic_command_mode(socket)
        send_switch_automatic_status_notification_mode(socket)
        send_print_information_command(socket, data)
        send_various_mode_settings(socket)
        send_advanced_mode_settings(socket)
        send_specify_margin_amount(socket)
        send_select_compression_mode(socket)
        send_raster_data(socket, data)
        send_print_command_with_feeding(socket)

        status_information = receive_status_information_response(socket)
        handle_status_information(status_information)


def send_invalidate(socket):
    # send 100 null bytes
    socket.send(b"\x00" * 100)


def send_initialize(socket):
    # send [1B 40]
    socket.send(b"\x1B\x40")


def send_switch_dynamic_command_mode(socket):
    # set dynamic command mode to "raster mode" [1B 69 61 {01}]
    socket.send(b"\x1B\x69\x61\x01")


def send_switch_automatic_status_notification_mode(socket):
    # set automatic status notification mode to "notify" [1B 69 21 {00}]
    socket.send(b"\x1B\x69\x21\x00")


def send_print_information_command(socket, data):
    # print to 24mm tape [1B 69 7A {84 00 18 00 <data length 4 bytes> 00 00}]
    socket.send(b"\x1B\x69\x7A\x84\x00\x18\x00")
    socket.send((len(data) >> 4).to_bytes(4, 'little'))
    socket.send(b"\x00\x00")


def send_various_mode_settings(socket):
    # set to auto-cut, no mirror printing [1B 69 4D {40}]
    socket.send(b"\x1B\x69\x4D")
    socket.send(Mode.AUTO_CUT.to_bytes(1, "big"))


def send_advanced_mode_settings(socket):
    # set print chaining off [1B 69 4B {08}]
    socket.send(b"\x1B\x69\x4B\x08")


def send_specify_margin_amount(socket):
    # set margin (feed) amount to 0 [1B 69 64 {00 00}]
    socket.send(b"\x1B\x69\x64\x00\x00")


def send_select_compression_mode(socket):
    # set to TIFF compression [4D {02}]
    socket.send(b"\x4D\x02")


def send_raster_data(socket, data):
    # send all raster data lines
    for line in rasterize(data):
        socket.send(bytes(line))


def send_print_command_with_feeding(socket):
    # print and feed [1A]
    socket.send(b"\x1A")


def send_status_information_request(socket):
    # request status information [1B 69 53]
    socket.send(b"\x1B\x69\x53")


def receive_status_information_response(socket):
    # receive status information
    response = socket.recv(32)

    if (len(response) != 32):
        sys.exit("Expected 32 bytes, but only received %d" % len(response))

    return response


def handle_status_information(status_information):
    def handle_reply_to_status_request(status_information):
        print("Media width: %dmm" % status_information[STATUS_OFFSET_MEDIA_WIDTH])    
        print("Media type: %s" % MediaType(status_information[STATUS_OFFSET_MEDIA_TYPE]))
        print("Tape color information: %s" % TapeColor(status_information[STATUS_OFFSET_TAPE_COLOR_INFORMATION]).name)
        print("Text color information: %s" % TextColor(status_information[STATUS_OFFSET_TEXT_COLOR_INFORMATION]).name)

    def handle_printing_completed(status_information):
        mode = Mode(status_information[STATUS_OFFSET_MODE])

        print("Mode: %s" % ", ".join([f.name for f in Mode if f in mode]))

        sys.exit(0)

    def handle_error_occurred(status_information):
        error_information_1 = ErrorInformation1(status_information[STATUS_OFFSET_ERROR_INFORMATION_1])
        error_information_2 = ErrorInformation1(status_information[STATUS_OFFSET_ERROR_INFORMATION_2])

        print("Error information 1: %s" % ", ".join([f.name for f in ErrorInformation1 if f in error_information_1]))
        print("Error information 2: %s" % ", ".join([f.name for f in ErrorInformation2 if f in error_information_2]))

        sys.exit("An error occurred")

    def handle_turned_off(status_information):
        sys.exit("Device was turned off")

    def handle_notification(status_information):
        print("Notification number: %s" % NotificationNumber(status_information[STATUS_OFFSET_NOTIFICATION_NUMBER]).name)

    def handle_phase_change(status_information):
        phase_type = status_information[STATUS_OFFSET_PHASE_TYPE]
        phase_number = int.from_bytes(status_information[STATUS_OFFSET_PHASE_NUMBER:STATUS_OFFSET_PHASE_NUMBER + 2], "big")

        print("Phase type: %s" % PhaseType(phase_type).name)
        print("Phase number: %s" % (PhaseNumberPrintingState(phase_number) if phase_type == PhaseType.PRINTING_STATE else PhaseNumberEditingState(phase_number)).name)

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

def main(*args):
    if len(args) < 3:
        print("Usage: %s <image-path> <bt-address> [bt-channel]" % args[0])
        sys.exit(1)

    image_path = args[1]
    bt_address = args[2]
    bt_channel = args[3] if len(args) > 3 else 1

    make_label(image_path, bt_address, bt_channel)


if __name__== "__main__":
    main(*sys.argv)