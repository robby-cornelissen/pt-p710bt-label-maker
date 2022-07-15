import sys
from typing import Iterator, Any, Dict

import png
import packbits

from pt_p710bt_label_maker.exceptions import InvalidImageHeightException

IMAGE_HEIGHT: int = 128
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


def encode_png(image_path: str) -> bytearray:
    width: int
    height: int
    rows: Iterator[bytearray]
    info: Dict[str, Any]
    width, height, rows, info = png.Reader(filename=image_path).asRGBA()

    if height != IMAGE_HEIGHT:
        raise InvalidImageHeightException(IMAGE_HEIGHT, height)

    # get all the alpha channel values, rotate 90 degrees and flip horizontally
    data = list(zip(*[row[3::4] for row in rows]))
    buffer = bytearray()
    for line in data:
        # create one byte for every 8 values
        for i in range(0, len(line), 8):
            byte = 0
            for j in range(0, 8):
                value = line[i + j]
                if value > 0:
                    byte |= (1 << (7 - j))
            buffer.append(byte)
    return buffer
