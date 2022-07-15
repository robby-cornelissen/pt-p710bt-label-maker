import logging

import bluetooth

logger: logging.Logger = logging.getLogger(__name__)


class Connector:

    def __init__(self):
        raise NotImplementedError()

    def __del__(self):
        raise NotImplementedError()

    def send(self, data: bytes):
        raise NotImplementedError()

    def receive(self, length: int) -> bytes:
        raise NotImplementedError()


class BluetoothConnector(Connector):

    def __init__(self, bt_address: str, bt_channel: int = 1):
        super().__init__()
        logger.debug('Opening Bluetooth RFCOMM socket')
        self._socket: bluetooth.BluetoothSocket = bluetooth.BluetoothSocket(
            bluetooth.RFCOMM
        )
        logger.info(
            'Connecting to bluetooth device %s on channel %d',
            bt_address, bt_channel
        )
        self._socket.connect((bt_address, bt_channel))
        logger.debug('Connected to bluetooth device.')

    def __del__(self):
        logger.debug('Closing socket connection')
        self._socket.close()

    def send(self, data: bytes):
        self._socket.send(data)

    def receive(self, length: int) -> bytes:
        return self._socket.recv(length)
