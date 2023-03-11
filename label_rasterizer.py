import sys
import png
import packbits

IMAGE_HEIGHT = 128
CHUNK_SIZE = 16
ZERO_CHUNK = bytearray(b"\x00" * CHUNK_SIZE)
RASTER_COMMAND = b"\x47"
ZERO_COMMAND = b"\x5A"


def rasterize(encoded_image_data):
    for i in range(0, len(encoded_image_data), CHUNK_SIZE):
        buffer = bytearray()
        chunk = encoded_image_data[i:i + CHUNK_SIZE]
        
        if chunk == ZERO_CHUNK:
            buffer += ZERO_COMMAND
        else:
            packed_chunk = packbits.encode(chunk)

            buffer += RASTER_COMMAND
            buffer += len(packed_chunk).to_bytes(2, "little")
            buffer += packed_chunk
        
        yield buffer


def encode_png(image_path):
    width, height, rows, info = png.Reader(filename=image_path).asRGBA()

    if height != IMAGE_HEIGHT:
        sys.exit("Image height is %d pixels, %d required" % (height, IMAGE_HEIGHT))

    # get all the alpha channel values, rotate 90 degrees and flip horizontally
    data = [row[3::4] for row in rows]
    data = list(zip(*data))

    buffer = bytearray()

    for line in data:
        # create one byte for every 8 values
        for i in range(0, len(line), 8):
            byte = 0;

            for j in range(0, 8):
                value = line[i + j]
                
                if value > 0:
                    byte |= (1 << (7 - j))
            
            buffer.append(byte)

    return buffer
