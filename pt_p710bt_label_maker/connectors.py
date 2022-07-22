import logging
from typing import Optional

import bluetooth
import usb.core
import usb.util

logger: logging.Logger = logging.getLogger(__name__)


class Connector:

    def __init__(self):
        pass

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


class UsbConnector(Connector):

    def __init__(self, vendor_id: int = 0x04F9, product_id: int = 0x20af):
        super().__init__()
        self._vendor_id: int = vendor_id
        self._product_id: int = product_id
        logger.debug(
            'Finding USB device with idVendor=%s and idProduct=%s',
            vendor_id, product_id
        )
        self._dev: Optional[usb.core.Device] = usb.core.find(
            idVendor=vendor_id, idProduct=product_id
        )
        if not self._dev:
            raise RuntimeError(
                f'ERROR: No USB device found with idVendor=0x{vendor_id:04x} '
                f'idProduct=0x{product_id:04x}'
            )
        logger.debug('Found device: %s', self._dev)
        logger.debug('Setting device configuration')
        try:
            self._dev.set_configuration()
        except usb.core.USBError as ex:
            logger.debug('Could not set device configuration: %s', ex)
        # get an endpoint instance
        cfg: usb.core.Configuration = self._dev.get_active_configuration()
        logger.debug('Got device configuration: %s', cfg)
        intf: usb.core.Interface = cfg[(0, 0)]
        logger.debug('Got device interface: %s', intf)
        logger.debug('Looking for IN endpoint')
        self._in_endpoint: usb.core.Endpoint = usb.util.find_descriptor(
            intf,
            # match the first IN endpoint
            custom_match= \
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_IN)
        logger.debug('Found IN endpoint as: %s', self._in_endpoint)
        if self._in_endpoint is None:
            raise RuntimeError('ERROR: Unable to find IN USB endpoint')
        logger.debug('Looking for OUT endpoint')
        self._out_endpoint: usb.core.Endpoint = usb.util.find_descriptor(
            intf,
            # match the first IN endpoint
            custom_match= \
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_OUT)
        logger.debug('Found OUT endpoint as: %s', self._out_endpoint)
        if self._out_endpoint is None:
            raise RuntimeError('ERROR: Unable to find OUT USB endpoint')

    def __del__(self):
        pass

    def send(self, data: bytes):
        self._in_endpoint.write(data)

    def receive(self, length: int) -> bytes:
        return self._out_endpoint.read(length).tobytes()
