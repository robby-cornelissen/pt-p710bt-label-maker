from enum import IntEnum, IntFlag
import logging

from exceptions import (
    DeviceTurnedOffException, InvalidStatusResponseException,
    InvalidStatusCodeException
)

logger = logging.getLogger(__name__)


class Mode(IntFlag):
    AUTO_CUT = 0x40
    MIRROR_PRITING = 0x80


class RawStatusMessage:

    class StatusType(IntEnum):
        REPLY_TO_STATUS_REQUEST = 0x00
        PRINTING_COMPLETED = 0x01
        ERROR_OCCURRED = 0x02
        TURNED_OFF = 0x04
        NOTIFICATION = 0x05
        PHASE_CHANGE = 0x06

    def __init__(self, message: bytes):
        self.raw_response: bytes = message
        if len(self.raw_response) != 32:
            raise InvalidStatusResponseException(len(self.raw_response))
        # these are unpacked bytes from the status message,
        # using the offsets specified in the documentation
        self.error_information1: int = self.raw_response[8]
        self.error_information2: int = self.raw_response[9]
        self.media_width: int = self.raw_response[10]
        self.media_type: int = self.raw_response[11]
        self.mode: int = self.raw_response[15]
        self.media_length: int = self.raw_response[17]
        self.status_type: int = self.raw_response[18]
        self.phase_type: int = self.raw_response[19]
        self.phase_number: int = int.from_bytes(
            self.raw_response[20:22], "big"
        )
        self.notification_number: int = self.raw_response[22]
        self.tape_color: int = self.raw_response[24]
        self.text_color: int = self.raw_response[25]
        self.hardware_settings: int = self.raw_response[26]

    def __str__(self):
        return f'RawStatusMessage({self.raw_response}): ' \
               f'error_information1={self.error_information1:x} ' \
               f'error_information2={self.error_information2:x} ' \
               f'media_width={self.media_width:x} ' \
               f'media_type={self.media_type:x} ' \
               f'mode={self.mode:x} ' \
               f'media_length={self.media_length:x} ' \
               f'status_type={self.status_type:x} ' \
               f'phase_type={self.phase_type:x} ' \
               f'phase_number={self.phase_number:x} ' \
               f'notification_number={self.notification_number:x} ' \
               f'tape_color={self.tape_color:x} ' \
               f'text_color={self.text_color:x} ' \
               f'hardware_settings={self.hardware_settings:x}'


class StatusMessage:

    def __init__(self, raw: RawStatusMessage):
        self._raw: RawStatusMessage = raw


class ReplyToStatusRequest(StatusMessage):

    class MediaType(IntEnum):
        NO_MEDIA = 0x00
        LAMINATED_TAPE = 0x01
        NON_LAMINATED_TAPE = 0x03
        HEAT_SHRINK_TUBE = 0x11
        INCOMPATIBLE_TAPE = 0xFF

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
        BLUE_F = 0x62
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

    def __init__(self, raw: RawStatusMessage):
        super().__init__(raw)
        self.media_width: int = raw.media_width
        self.media_type: int = raw.media_type
        self.media_type_name: str = self.MediaType(raw.media_type).name
        self.tape_color: int = raw.tape_color
        self.tape_color_name: str = self.TapeColor(raw.tape_color).name
        self.text_color: int = raw.text_color
        self.text_color_name: str = self.TextColor(raw.text_color).name

    def __str__(self):
        return 'ReplyToStatusRequest: ' \
               f'media width={self.media_width}mm; ' \
               f'media_type={self.media_type_name} ({self.media_type}); ' \
               f'tape_color={self.tape_color_name} ({self.tape_color}); ' \
               f'text_color={self.text_color_name} ({self.text_color})'


class PrintingCompleted(StatusMessage):

    def __init__(self, raw: RawStatusMessage):
        super().__init__(raw)
        mode = Mode(raw.mode)
        self.auto_cut: bool = Mode.AUTO_CUT in mode
        self.mirror_printing: bool = Mode.MIRROR_PRITING in mode

    def __str__(self):
        return 'Printing Completed; ' \
               f'AUTO_CUT={self.auto_cut} ' \
               f'MIRROR_PRINTING={self.mirror_printing}'


class Notification(StatusMessage):

    class NotificationNumber(IntEnum):
        NOT_AVAILABLE = 0x00
        COVER_OPEN = 0x01
        COVER_CLOSED = 0x02

    def __init__(self, raw: RawStatusMessage):
        super().__init__(raw)
        self.number: int = raw.notification_number
        self.name: str = self.NotificationNumber(self.number).name

    def __str__(self):
        return f'Notification {self.number:x}: {self.name}'


class PhaseChange(StatusMessage):

    class PhaseType(IntEnum):
        EDITING_STATE = 0x00
        PRINTING_STATE = 0x01

    class PhaseNumberEditingState(IntEnum):
        EDITING_STATE = 0x0000
        FEED = 0x0001

    class PhaseNumberPrintingState(IntEnum):
        PRINTING = 0x0000
        COVER_OPEN_WHILE_RECEIVING = 0x0014

    def __init__(self, raw: RawStatusMessage):
        super().__init__(raw)
        self.phase_type: int = raw.phase_type
        self.phase_type_name: str = self.PhaseType(self.phase_type).name
        self.phase_number: int = raw.phase_number
        self.phase_name: int
        if self.phase_type == self.PhaseType.PRINTING_STATE:
            self.phase_name = self.PhaseNumberPrintingState(
                self.phase_number
            ).name
        elif self.phase_type == self.PhaseType.EDITING_STATE:
            self.phase_name = self.PhaseNumberEditingState(
                self.phase_number
            ).name
        else:
            raise RuntimeError(
                f'ERROR: Unknown phase number {self.phase_number:x}'
            )

    def __str__(self):
        return f'PhaseChange: Phase Type {self.phase_type:x} ' \
               f'({self.phase_type_name}); Phase ' \
               f'{self.phase_number:x} ({self.phase_name})'
