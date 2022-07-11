
class DeviceTurnedOffException(RuntimeError):

    def __init__(self):
        super(DeviceTurnedOffException, self).__init__('Device was turned off')


class InvalidStatusResponseException(RuntimeError):

    def __init__(self, message_length: int):
        self.message_length: int = message_length
        super(InvalidStatusResponseException, self).__init__(
            f'Invalid status message from printer: Expected 32 bytes but only '
            f'received {message_length}.'
        )


class InvalidImageHeightException(ValueError):

    def __init__(self, required_height: int, actual_height: int):
        self.required_height: int = required_height
        self.actual_height: int = actual_height
        super(InvalidImageHeightException, self).__init__(
            f'Supplied image has invalid height. An image {required_height} px '
            f'high is requred, but supplied image is {actual_height} px high.'
        )


class InvalidStatusCodeException(ValueError):

    def __init__(self, status_code: int):
        self.status_code: int = status_code
        super(InvalidStatusCodeException, self).__init__(
            f'ERROR: Printer responded with unknown status type {status_code:x}'
        )
