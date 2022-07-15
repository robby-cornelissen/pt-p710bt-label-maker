import typing

if typing.TYPE_CHECKING:
    from status_message import RawStatusMessage


class UnknownStatusMessageError(Exception):

    def __init__(self, raw: 'RawStatusMessage'):
        self.raw_message: 'RawStatusMessage' = raw
        super().__init__(f'ERROR: Unknown status message: {raw}')


class InvalidStatusResponseException(Exception):

    def __init__(self, message_length: int):
        self.message_length: int = message_length
        super().__init__(
            f'Invalid status message from printer: Expected 32 bytes but only '
            f'received {message_length}.'
        )


class InvalidImageHeightException(Exception):

    def __init__(self, required_height: int, actual_height: int):
        self.required_height: int = required_height
        self.actual_height: int = actual_height
        super().__init__(
            f'Supplied image has invalid height. An image {required_height} px '
            f'high is requred, but supplied image is {actual_height} px high.'
        )


class InvalidStatusCodeException(Exception):

    def __init__(self, status_code: int):
        self.status_code: int = status_code
        super().__init__(
            f'ERROR: Printer responded with unknown status type {status_code:x}'
        )


class PrinterError(Exception):

    def __init__(self, message: str, raw: 'RawStatusMessage'):
        self.raw_message: 'RawStatusMessage' = raw
        self.message: str = message
        super().__init__(message)


class DeviceTurnedOffException(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: Device was turned off', raw)


class NoMediaError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: No media in printer', raw)


class CutterJamError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: Cutter jammed', raw)


class WeakBatteriesError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: Weak batteries', raw)


class HighVoltageAdapterError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: High voltage adapter', raw)


class WrongMediaError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: Wrong media in printer', raw)


class CoverOpenError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: Cover open', raw)


class OverheatingError(PrinterError):

    def __init__(self, raw: 'RawStatusMessage'):
        super().__init__('ERROR: Printer overheating', raw)
