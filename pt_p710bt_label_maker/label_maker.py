import sys
import argparse
import logging
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from math import ceil
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from pt_p710bt_label_maker.utils import (
    set_log_debug, set_log_info, add_printer_args
)
from pt_p710bt_label_maker.label_printer import (
    Connector, UsbConnector, BluetoothConnector, PtP710LabelPrinter
)

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class LabelImageGenerator:

    # Printer DPI
    DPI: int = 180

    def __init__(
        self, text: str, height_px: int = 128, maxlen_px: Optional[int] = None,
        font_filename: str = 'DejaVuSans.ttf'
    ):
        self.text: str = text
        self.height_px: int = height_px
        logger.debug(
            'Initializing LabelImageGenerator text="%s", height_px=%d',
            self.text, self.height_px
        )
        self.fonts: Dict[int, ImageFont.FreeTypeFont] = self._get_fonts(
            font_file=font_filename
        )
        logger.debug('Loaded %d font options', len(self.fonts))
        self.text_anchor: str = 'mm'
        # @TODO add an option for alignment of multi-line text
        # options are "left", "center", or "right"
        self.text_align: str = 'center'
        self.font: ImageFont.FreeTypeFont
        self.width_px: int
        self.font, self.width_px = self._fit_text_to_box(maxlen_px)
        logger.info(
            'Largest font size to fit %dpx high x %spx wide is %d; resulting '
            'text width is %dpx.',
            self.height_px, maxlen_px,  self.font.size, self.width_px
        )
        if self.width_px < self.height_px:
            self.width_px = self.height_px
            logger.info('Overriding minimum label width to be equal to height')
        self._image: Image = self._generate()

    def _get_fonts(
        self, font_file: str = 'DejaVuSans.ttf', min_size: int = 4,
        max_size: int = 144, size_step: int = 2
    ) -> Dict[int, ImageFont.FreeTypeFont]:
        logger.debug(
            'Generating font options for TrueType font %s: min_size=%d, '
            'max_size=%d, size_step=%d',
            font_file, min_size, max_size, size_step
        )
        return {
            i: ImageFont.truetype(font_file, size=i)
            for i in range(min_size, max_size, size_step)
        }

    def _get_text_dimensions(
        self, font: ImageFont.FreeTypeFont, draw: ImageDraw
    ) -> Tuple[int, int]:
        # https://stackoverflow.com/a/46220683/9263761
        bbox: Tuple[float, float, float, float] = draw.textbbox(
            xy=(0, 0), text=self.text, font=font, anchor=self.text_anchor,
            align=self.text_align
        )
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height

    def _fit_text_to_box(
        self, max_width: Optional[int] = None
    ) -> Tuple[ImageFont.FreeTypeFont, int]:
        """
        Find the largest ImageFont that fits the label height and optionally a
        maximum width. Return a 2-tuple of that ImageFont and the resulting text
        width (int).
        """
        # temporary image and draw
        img: Image = Image.new("RGB", (2, 2), (255, 255, 255))
        draw: ImageDraw = ImageDraw.Draw(img)
        logger.debug(
            'Finding maximum font size that fits "%s" in %d pixels high and '
            '%s pixels wide', self.text, self.height_px, max_width
        )
        last: int = min(self.fonts.keys())
        last_width: int = self._get_text_dimensions(self.fonts[last], draw)[0]
        for i in sorted(self.fonts.keys(), reverse=True):
            try:
                w, h = self._get_text_dimensions(self.fonts[i], draw)
            except OSError as ex:
                logger.debug('Error on font size %d: %s', i, ex, exc_info=True)
                continue
            logger.debug('Text dimensions for size %d: %d x %d', i, w, h)
            if h <= self.height_px and (max_width is None or w <= max_width):
                last = i
                last_width = w
                break
        last_width = ceil(last_width)
        logger.debug(
            'Font size %d is largest to fit; resulting width: %dpx',
            last, last_width
        )
        return self.fonts[last], last_width

    def _generate(self) -> Image:
        logger.debug(
            'Generating %d x %d RGBA image', self.width_px, self.height_px
        )
        img: Image = Image.new(
            'RGBA', (self.width_px, self.height_px), (255, 255, 255, 0)
        )
        draw: ImageDraw = ImageDraw.Draw(img)
        pos: Tuple[int, int] = (self.width_px / 2, self.height_px / 2)
        kwargs: Dict[str, Any] = {
            'xy': pos,
            'text': self.text,
            'fill': (0, 0, 0, 255),
            'font': self.font,
            'anchor': self.text_anchor
        }
        if "\n" in self.text:
            draw.multiline_text(align=self.text_align, **kwargs)
        else:
            draw.text(**kwargs)
        logger.info('Generated image')
        return img

    def save(self, filename: str):
        logger.info('Saving image to: %s', filename)
        self._image.save(filename)

    def show(self):
        self._image.show()
        i = input('Print this image? [y|N]').strip()
        if i not in ['y', 'Y']:
            raise SystemExit(1)

    @property
    def file_obj(self) -> BytesIO:
        i: BytesIO = BytesIO()
        self._image.save(i, format='PNG')
        i.seek(0)
        return i


def main():
    fname: str = datetime.now().strftime('%Y%m%dT%H%M%S') + '.png'
    p = argparse.ArgumentParser(
        description='Brother PT-P710BT Label Maker'
    )
    add_printer_args(p)
    p.add_argument(
        '-s', '--save-only', dest='save_only', action='store_true',
        default=False, help='Save generates image to current directory and exit'
    )
    p.add_argument(
        '--filename', dest='filename', action='store', type=str,
        help=f'Filename to save image to; default: {fname}', default=fname
    )
    p.add_argument('-P', '--no-preview', dest='preview', action='store_false',
                   default=True, help='Do not preview image before printing')
    maxlen = p.add_mutually_exclusive_group()
    maxlen.add_argument('--maxlen-px', dest='maxlen_px', action='store',
                        type=int, help='Maximum label length in pixels')
    maxlen.add_argument('--maxlen-inches', dest='maxlen_in', action='store',
                        type=float, help='Maximum label length in inches')
    p.add_argument('-f', '--font-filename', dest='font_filename', type=str,
                   action='store', default='DejaVuSans.ttf',
                   help='Font filename; Default: DejaVuSans.ttf')
    p.add_argument(
        'LABEL_TEXT', action='store', type=str, help='Text to print on label',
        nargs='+'
    )
    args = p.parse_args(sys.argv[1:])
    if args.maxlen_in:
        args.maxlen_px = args.maxlen_in * LabelImageGenerator.DPI
    # set logging level
    if args.verbose:
        set_log_debug(logger)
    else:
        set_log_info(logger)
    images: List[BytesIO] = []
    for i in args.LABEL_TEXT:
        g = LabelImageGenerator(
            i, maxlen_px=args.maxlen_px, font_filename=args.font_filename
        )
        if args.save_only:
            g.save(args.filename)
        if args.preview:
            g.show()
        images.append(g.file_obj)
    if args.save_only:
        raise SystemExit(0)
    # Begin code copied from label_printer.py
    device: Connector
    if args.usb:
        device = UsbConnector()
    else:
        device = BluetoothConnector(
            args.bt_address, bt_channel=args.bt_channel
        )
    PtP710LabelPrinter(device).print_images(
        images, num_copies=args.num_copies
    )


if __name__ == "__main__":
    main()
