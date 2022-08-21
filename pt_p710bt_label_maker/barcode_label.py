import sys
import argparse
import logging
from typing import Optional, Tuple, Dict, Any, List, Literal, Callable
from datetime import datetime
from math import ceil
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from barcode.writer import ImageWriter, pt2mm, mm2px
import barcode
from barcode.base import Barcode

from pt_p710bt_label_maker.utils import (
    set_log_debug, set_log_info, add_printer_args
)
from pt_p710bt_label_maker.label_printer import (
    Connector, UsbConnector, BluetoothConnector, PtP710LabelPrinter
)
from pt_p710bt_label_maker.media_info import TAPE_MM_TO_PX

Alignment = Literal["center", "left", "right"]

BARCODE_CLASSES: Dict[str, Callable] = {
    x.__name__: x for x in Barcode.__subclasses__()
}

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class BarcodeLabelGenerator:

    # Printer DPI
    DPI: int = 180

    def __init__(
        self, value: str, height_px: int, maxlen_px: Optional[int] = None,
        font_filename: str = 'DejaVuSans.ttf',
        barcode_class_name: str = 'Code128', show_text: bool = True
    ):
        self.value: str = value
        self.show_text: bool = show_text
        self.symbology: str = barcode_class_name
        self.barcode_cls: Callable = BARCODE_CLASSES[self.symbology]
        # for height, see media_info.TAPE_MM_TO_PX
        self.height_px: int = height_px
        self.fonts: Dict[int, ImageFont.FreeTypeFont] = self._get_fonts(
            font_file=font_filename
        )
        logger.debug('Loaded %d font options', len(self.fonts))
        logger.debug(
            'Initializing BarcodeLabelGenerator value="%s", symbology="%s" (%s)'
            ', height_px=%d, maxlen_px=%s, show_text=%s',
            self.value, self.symbology, self.barcode_cls, self.height_px,
            maxlen_px, show_text
        )
        self.writer: ImageWriter = ImageWriter(format='PNG')
        logger.debug('Writing image at %d DPI', self.DPI)
        self.writer.dpi = self.DPI
        writer_opts: Dict = self._writer_opts()
        writer_opts['font_path'] = font_filename
        writer_opts['write_text'] =  show_text
        logger.debug('Setting writer options: %s', writer_opts)
        self.writer.set_options(writer_opts)
        logger.debug('Generating barcode image')
        self.barcode: Barcode = self.barcode_cls(self.value, writer=self.writer)
        # used for width
        # code = self.barcode.build()
        # modules_per_line: int = len(code[0])
        self._image: Image = self.barcode.render(writer_options=writer_opts)
        logger.info(
            'Generated barcode image of %spx wide x %spx high',
            self._image.width, self._image.height
        )

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
        self, font: ImageFont.FreeTypeFont, draw: ImageDraw, text: str
    ) -> Tuple[int, int]:
        # modified to use same method as barcode.writer
        return font.getsize(text)

    def _fit_text_to_box(
        self, max_height: int, max_width: Optional[int] = None
    ) -> Tuple[ImageFont.FreeTypeFont, int, int]:
        """
        Find the largest ImageFont that fits the label height and optionally a
        maximum width. Return a 3-tuple of that ImageFont and the resulting text
        width (int) and height (int).
        """
        # temporary image and draw
        img: Image = Image.new("RGB", (2, 2), (255, 255, 255))
        draw: ImageDraw = ImageDraw.Draw(img)
        logger.debug(
            'Finding maximum font size that fits "%s" in %d pixels high and '
            '%s pixels wide', self.value, max_height, max_width
        )
        last: int = min(self.fonts.keys())
        last_width: int = self._get_text_dimensions(
            self.fonts[last], draw, self.value
        )[0]
        last_height: int = self._get_text_dimensions(
            self.fonts[last], draw, self.value
        )[1]
        for i in sorted(self.fonts.keys(), reverse=True):
            try:
                w, h = self._get_text_dimensions(
                    self.fonts[i], draw, self.value
                )
            except OSError as ex:
                logger.debug('Error on font size %d: %s', i, ex, exc_info=True)
                continue
            logger.debug('Text dimensions for size %d: %d x %d', i, w, h)
            if h <= max_height and (max_width is None or w <= max_width):
                last = i
                last_width = w
                last_height = h
                break
        last_width = ceil(last_width)
        logger.debug(
            'Font size %d is largest to fit; resulting width: %dpx',
            last, last_width
        )
        return self.fonts[last], last_width, last_height

    def mm2px(self, mm: float) -> float:
        # copied from barcode.writer
        return (mm / 25.4) * self.DPI

    def px2mm(self, px: float) -> float:
        return (px / self.DPI) * 25.4

    def pt2mm(self, pt: float) -> float:
        return pt * 0.352777778

    def mm2pt(self, mm: float) -> float:
        return mm / 0.352777778

    def _writer_opts(self) -> Dict:
        result: Dict = dict(self.barcode_cls.default_writer_options)
        height_opts: Dict = self._opts_for_heights()
        logger.debug('Options for height: %s', height_opts)
        result.update(height_opts)
        return result

    def _opts_for_heights(self) -> Dict:
        # there's a 2mm hard-coded unusable area
        usable_px: float = self.height_px - self.mm2px(2)
        logger.debug('Usable height: %spx', usable_px)
        if not self.show_text:
            return {'module_height': self.px2mm(usable_px)}
        # else we're showing text; a bit more complicated
        # break usable height into sixths
        unit: float = usable_px / 6
        logger.debug('Height units (sixths): %spx', unit)
        # 3/6 for barcode, 1/6 for spacing, 2/6 for text
        font: ImageFont.FreeTypeFont
        font_width: int
        font_height: int
        font, font_width, font_height = self._fit_text_to_box(int(unit * 2))
        font_size: float = font.size
        result = {
            "module_height": self.px2mm(unit * 3),
            # python-barcode expects the font size to be specified (incorrectly)
            # in pixels
            "font_size": self.px2mm(self.mm2pt(font_size)),
            # this is the distance from the BOTTOM of the barcode to the
            # BOTTOM of the text
            "text_distance": self.px2mm(unit)
        }
        return result

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
        description='Brother PT-P710BT Barcode Label Maker'
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
    p.add_argument('-P', '--preview', dest='preview', action='store_true',
                   default=False,
                   help='Preview image after generating and ask if it should '
                        'be printed')
    p.add_argument(
        '-S', '--symbology', dest='symbology', action='store', type=str,
        help='Barcode symbology to use', choices=sorted(BARCODE_CLASSES.keys()),
        default='Code128'
    )
    p.add_argument(
        '-t', '--no-text', dest='show_text', action='store_false', default=True,
        help='Do not show text below barcode'
    )
    maxlen = p.add_mutually_exclusive_group()
    maxlen.add_argument('--maxlen-px', dest='maxlen_px', action='store',
                        type=int, help='Maximum label length in pixels')
    maxlen.add_argument('--maxlen-inches', dest='maxlen_in', action='store',
                        type=float, help='Maximum label length in inches')
    maxlen.add_argument('--maxlen-mm', dest='maxlen_mm', action='store',
                        type=float, help='Maximum label length in mm')
    p.add_argument('-f', '--font-filename', dest='font_filename', type=str,
                   action='store', default='DejaVuSans.ttf',
                   help='Font filename; Default: DejaVuSans.ttf')
    p.add_argument(
        'BARCODE_VALUE', action='store', type=str, help='Value for barcode',
        nargs='+'
    )
    args = p.parse_args(sys.argv[1:])
    if args.maxlen_in:
        args.maxlen_px = args.maxlen_in * BarcodeLabelGenerator.DPI
    elif args.maxlen_mm:
        args.maxlen_px = (args.maxlen_mm / 25.4) * BarcodeLabelGenerator.DPI
    # set logging level
    if args.verbose:
        set_log_debug(logger)
    else:
        set_log_info(logger)
    images: List[BytesIO] = []
    for i in args.BARCODE_VALUE:
        g = BarcodeLabelGenerator(
            i, height_px=TAPE_MM_TO_PX[args.tape_mm], maxlen_px=args.maxlen_px,
            font_filename=args.font_filename, barcode_class_name=args.symbology,
            show_text=args.show_text
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
    PtP710LabelPrinter(device, tape_mm=args.tape_mm).print_images(
        images, num_copies=args.num_copies
    )


if __name__ == "__main__":
    main()
