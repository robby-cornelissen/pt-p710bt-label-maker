import sys
import argparse
import logging
from typing import Optional, Tuple, Dict, Any, List, Literal, Callable
from datetime import datetime
from math import ceil, floor
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from barcode.writer import ImageWriter
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
        self.font_filename: str = font_filename
        self.symbology: str = barcode_class_name
        self.maxlen_px: Optional[int] = maxlen_px
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
        self.num_modules: int = self._get_num_modules()
        if not self.maxlen_px:
            self.maxlen_px = self.num_modules + 22
        self._barcode_image: Image = self._generate_barcode_image(
            self.maxlen_px
        )
        logger.info(
            'Generated barcode image of %spx wide x %spx high',
            self._barcode_image.width, self._barcode_image.height
        )
        self._image: Image
        if self.show_text:
            self._image = self._generate_combined_image()
        else:
            self._image = self._barcode_image

    def _white_to_transparent(self, img: Image) -> Image:
        img = img.convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] == 255 and item[1] == 255 and item[2] == 255:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        return img

    def _generate_combined_image(self) -> Image:
        font: ImageFont.FreeTypeFont
        text_w: int
        text_h: int
        font, text_w, text_h = self._fit_text_to_box(
            self.height_px / 4, self.maxlen_px
        )
        width = max([self._barcode_image.width, text_w])
        logger.debug(
            'Generating %d x %d RGBA image', width, self.height_px
        )
        img: Image = Image.new(
            'RGBA',
            (width, self.height_px),
            (255, 255, 255, 0)
        )
        # paste the barcode at the top left
        img.paste(
            self._barcode_image,
            box=(
                floor((width - self._barcode_image.width) / 2),
                0
            )
        )
        # now add the text
        draw: ImageDraw = ImageDraw.Draw(img)
        pos: Tuple[int, int] = (
            floor(width / 2),
            self._barcode_image.height +
            floor((self.height_px - self._barcode_image.height) / 2)
        )
        kwargs: Dict[str, Any] = {
            'xy': pos,
            'text': self.value,
            'fill': (0, 0, 0, 255),
            'font': font,
            'anchor': 'mm'
        }
        draw.text(**kwargs)
        return img

    def _generate_barcode_image(self, maxlen_px: Optional[int]) -> Image:
        self.mod_width_px: int
        if maxlen_px is None:
            self.mod_width_px = 1
        else:
            # 11 quiet modules on each end
            self.mod_width_px = floor(self.maxlen_px / (self.num_modules + 22))
        logger.debug('Module width: %spx', self.mod_width_px)
        self.writer: ImageWriter = ImageWriter(format='PNG')
        logger.debug('Writing image at %d DPI', self.DPI)
        self.writer.dpi = self.DPI
        writer_opts: Dict = self._writer_opts()
        logger.debug('Setting writer options: %s', writer_opts)
        self.writer.set_options(writer_opts)
        logger.debug('Generating barcode image')
        self.barcode: Barcode = self.barcode_cls(self.value, writer=self.writer)
        return self._white_to_transparent(
            self.barcode.render(writer_options=writer_opts)
        )

    def _get_num_modules(self) -> int:
        writer: ImageWriter = ImageWriter(format='PNG')
        writer.dpi = self.DPI
        writer_opts: Dict = dict(self.barcode_cls.default_writer_options)
        writer_opts['module_width'] = self.px2mm(1)
        writer_opts['quiet_zone'] = 0
        writer.set_options(writer_opts)
        barcode: Barcode = self.barcode_cls(self.value, writer=writer)
        _image: Image = barcode.render(writer_options=writer_opts)
        logger.debug(
            'Minimum barcode width (1 module == 1 px): %s', _image.width
        )
        return _image.width

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
            'Font size %d is largest to fit; resulting width: %dpx; height: '
            '%dpx', last, last_width, last_height
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
        result['font_path'] = self.font_filename
        result['write_text'] = False
        result['module_width'] = self.px2mm(self.mod_width_px)
        result['quiet_zone'] = self.px2mm(11)
        if self.show_text:
            result['module_height'] = self.px2mm(floor(self.height_px / 2))
        else:
            result['module_height'] = self.px2mm(self.height_px)
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
