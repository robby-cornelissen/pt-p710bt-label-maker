import bluetooth

@contextlib.contextmanager
def bt_socket_manager(*args, **kwargs):
    socket = bluetooth.BluetoothSocket(*args, **kwargs)

    yield socket

    socket.close()

def make_label():
    with bt_socket_manager(bluetooth.RFCOMM) as socket:
        pass


def invalidate(socket):
    # send 100 null bytes
    socket.send(b"\x00" * 100)

def initialize(socket):
    # send [1b 40]
    socket.send(b"\x1b\x40")

def switch_dynamic_command_mode(socket):
    # set dynamic command mode to "raster mode" [1b 69 61 {01}]
    socket.send(b"\x1b\x69\x61\x01")

def switch_automatic_status_notification_mode(socket):
    # set automatic status notification mode to "do not notify" [1b 69 21 {01}]
    socket.send(b"\x1b\x69\x21\x01")

def print_information_command(socket):
    # print to 24mm tape [1b 69 7a {84 00 18 00 aa 02 00 00 00 00}]
    #                                           ^^ ^^ ^^ ^^
    socket.send(b"\x1b\x69\x7a\x84\x00\x18\x00\xaa\x02\x00\x00\x00\x00")