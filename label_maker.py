from enum import Flag
import sys
import contextlib
import bluetooth


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


class ErrorInformation1(Flag):
    NO_MEDIA = 0x01
    CUTTER_JAM = 0x04
    WEAK_BATTERIES = 0x08
    HIGH_VOLTAGE_ADAPTER = 0x40


class ErrorInformation2(Flag):
    WRONG_MEDIA = 0x01
    COVER_OPEN = 0x10
    OVERHEATING = 0x20


class MediaType(Flag):
    NO_MEDIA = 0x00
    LAMINATED_TAPE = 0x01
    NON_LAMINATED_TAPE = 0x03
    HEAT_SHRINK_TUBE = 0x11
    INCOMPATIBLE_TAPE = 0xFF


class StatusType(Flag):
    REPLY_TO_STATUS_REQUEST = 0x00
    PRINTING_COMPLETED = 0x01
    ERROR_OCCURRED = 0x02
    TURNED_OFF = 0x04
    NOTIFICATION = 0x05
    PHASE_CHANGE = 0x06


class PhaseType(Flag):
    EDITING_STATE = 0x00
    PRINTING_STATE = 0x01


class PhaseNumberEditingState(Flag):
    EDITING_STATE = 0x0000
    FEED = 0x0001

class PhaseNumberPrintingState(Flag):
    PRINTING = 0x0000
    COVER_OPEN_WHILE_RECEIVING = 0x0014


class NotificationNumber(Flag):
    COVER_OPEN = 0x01
    COVER_CLOSED = 0x02


class TapeColor(Flag):
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


class TextColor(Flag):
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
    with bt_socket_manager(bluetooth.RFCOMM) as socket:
        socket.connect((bt_address, bt_channel))

        send_invalidate(socket)
        send_initialize(socket)
        send_status_information_request(socket)

        receive_status_information_response(socket)



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
    # set automatic status notification mode to "do not notify" [1B 69 21 {01}]
    socket.send(b"\x1B\x69\x21\x01")


def send_print_information_command(socket, data):
    # print to 24mm tape [1B 69 7A {84 00 18 00 <data length 4 bytes> 00 00}]
    socket.send(b"\x1B\x69\x7A\x84\x00\x18\x00")
    socket.send((len(data) >> 4).to_bytes(4, 'little'))
    socket.send(b"\x00\x00")


def send_various_mode_settings(socket):
    # set to auto-cut, no mirror printing [1B 69 4D {40}]
    socket.send(b"\x1B\x69\x4D\x40")


def send_advanced_mode_settings(socket):
    # set print chaining off [1B 69 4B {08}]
    socket.send(b"\x1B\x69\x4B\x08")


def send_specify_margin_amount(socket):
    # set margin (feed) amount to 0 [1B 69 64 {00 00}]
    socket.send(b"\x1B\x69\x64\x00\x00")


def send_select_compression_mode(socket):
    # set to TIFF compression [4D {02}]
    socket.send(b"\x4D\x02")


def send_raster_data(socket):
    pass


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
        sys.exit("Expected 32 bytes, but only received [%d]" % len(response))

    print(response.hex())


def print_status_information(status_information):
    pass


def check_status_information_for_error(status_information):
    pass


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