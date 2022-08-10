from typing import Iterator, Any, Dict, Union, List
import logging
from io import BytesIO

import png
import packbits

from pt_p710bt_label_maker.exceptions import InvalidImageHeightException
from pt_p710bt_label_maker.media_info import TAPE_MM_TO_PX, TAPE_MM_TO_MARGIN_PX

logger = logging.getLogger(__name__)

CHUNK_SIZE: int = 16
ZERO_CHUNK: bytearray = bytearray(b"\x00" * CHUNK_SIZE)
RASTER_COMMAND: bytes = b"\x47"
ZERO_COMMAND: bytes = b"\x5A"


def rasterize(encoded_image_data: bytearray) -> Iterator[bytearray]:
    i: int
    for i in range(0, len(encoded_image_data), CHUNK_SIZE):
        buffer: bytearray = bytearray()
        chunk: bytearray = encoded_image_data[i:i + CHUNK_SIZE]
        if chunk == ZERO_CHUNK:
            buffer += ZERO_COMMAND
        else:
            packed_chunk: bytes = packbits.encode(chunk)
            buffer += RASTER_COMMAND
            buffer += len(packed_chunk).to_bytes(2, "little")
            buffer += packbits.encode(chunk)
        yield buffer


def encode_png(data: Union[str, BytesIO], tape_mm: int) -> bytearray:
    expected_height: int = TAPE_MM_TO_PX[tape_mm]
    width: int
    height: int
    rows: Iterator[bytearray]
    info: Dict[str, Any]
    if isinstance(data, str):
        logger.debug('Using PNG from file at: %s', data)
        width, height, rows, info = png.Reader(filename=data).asRGBA()
    else:
        logger.debug('Using PNG from file-like object')
        width, height, rows, info = png.Reader(file=data).asRGBA()

    if height != expected_height:
        raise InvalidImageHeightException(expected_height, height)

    # build a margin list to add to the start and end of each line
    margin: List[int] = [0] * TAPE_MM_TO_MARGIN_PX[tape_mm]

    # get all the alpha channel values, rotate 90 degrees and flip horizontally
    data = list(zip(*[row[3::4] for row in rows]))
    # build the data buffer
    buffer = bytearray()
    for line in data:
        # add the margins
        line = margin + list(line) + margin
        # create one byte for every 8 values
        for i in range(0, len(line), 8):
            byte = 0
            for j in range(0, 8):
                value = line[i + j]
                if value > 0:
                    byte |= (1 << (7 - j))
            buffer.append(byte)
    return buffer
