import sys
import os
import argparse
import logging
from typing import Optional, Tuple, Dict, Any, List, Literal
from datetime import datetime
from math import ceil
from io import BytesIO
import shlex
from tempfile import mkdtemp
from shutil import which, rmtree
import subprocess

from PIL import Image, ImageDraw, ImageFont

from pt_p710bt_label_maker.utils import (
    set_log_debug, set_log_info, add_printer_args
)
from pt_p710bt_label_maker.label_printer import (
    Connector, UsbConnector, BluetoothConnector, PtP710LabelPrinter
)
from pt_p710bt_label_maker.media_info import TAPE_MM_TO_PX
from pt_p710bt_label_maker.pil_autowrap import fit_text

Alignment = Literal["center", "left", "right"]

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class LabelImageGenerator:

    # Printer DPI
    DPI: int = 180

    def __init__(
        self, text: str, height_px: int, maxlen_px: Optional[int] = None,
        font_filename: str = 'DejaVuSans.ttf', padding_right: int = 4,
        text_align: Alignment = 'center', rotate: bool = False,
        rotate_repeat: bool = False, max_font_size: Optional[int] = None,
        wrap: bool = False, fixed_len_px: Optional[int] = None
    ):
        self.text: str = text
        # for height, see media_info.TAPE_MM_TO_PX
        self.height_px: int = height_px
        self.padding_right: int = padding_right
        logger.debug(
            'Initializing LabelImageGenerator text="%s", height_px=%d',
            self.text, self.height_px
        )
        kwargs = {'font_file': font_filename}
        if max_font_size:
            kwargs['max_size'] = max_font_size
        self.fonts: Dict[int, ImageFont.FreeTypeFont] = self._get_fonts(
            **kwargs
        )
        logger.debug('Loaded %d font options', len(self.fonts))
        self.text_anchor: str = 'mm'
        self.text_align: Alignment = text_align
        self.rotate: bool = rotate
        self.rotate_repeat: bool = rotate_repeat
        self.wrap: bool = wrap
        self.font: ImageFont.FreeTypeFont
        self.width_px: int
        #: when printing rotated or rotated repeated, this is the width of one
        #: line of text
        self.text_width_px: int = 0
        self.text_height_px: int = 0
        if self.rotate or self.rotate_repeat:
            if self.wrap:
                raise NotImplementedError(
                    'ERROR: Text wrap is not implemented for rotated text.'
                )
            self.width_px = ceil(maxlen_px)
            # swap height and width to find what will fit when rotated
            self.font, self.text_width_px, self.text_height_px = self._fit_text_to_box(
                maxlen_px, self.height_px
            )
            logger.info(
                'Largest font size to fit rotated %dpx high x %spx wide is %d;'
                ' resulting text height is %dpx and width is %dpx.',
                maxlen_px, self.height_px, self.font.size, self.text_height_px,
                self.text_width_px
            )
        elif self.wrap:
            self.font, self.text = fit_text(
                self.fonts[max(self.fonts.keys())], self.text, maxlen_px,
                self.height_px, max_iterations=100
            )
            img: Image = Image.new("RGB", (2, 2), (255, 255, 255))
            draw: ImageDraw = ImageDraw.Draw(img)
            self.width_px, height_px = self._get_text_dimensions(
                self.font, draw, self.text
            )
            self.width_px = int(self.width_px)
            logger.info(
                'Wrapped text to fit in %dpx high x %spx wide; best fit is '
                'font size %s resulting in text %spx wide wrapped as: %s',
                self.height_px, maxlen_px, self.font.size, self.width_px,
                self.text
            )
        else:
            self.font, self.width_px, _ = self._fit_text_to_box(
                self.height_px, maxlen_px
            )
            logger.info(
                'Largest font size to fit %dpx high x %spx wide is %d; resulting '
                'text width is %dpx wide.',
                self.height_px, maxlen_px, self.font.size, self.width_px
            )
        if self.width_px < self.height_px:
            self.width_px = self.height_px
            logger.info('Overriding minimum label width to be equal to height')
        self._image: Image
        if self.rotate or self.rotate_repeat:
            self._image = self._generate_rotated()
        else:
            self._image = self._generate()
        if fixed_len_px:
            self._image = self._center_in_width(self._image, fixed_len_px)

    @property
    def image(self) -> Image:
        return self._image

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
        # https://stackoverflow.com/a/46220683/9263761
        bbox: Tuple[float, float, float, float] = draw.textbbox(
            xy=(0, 0), text=text, font=font, anchor=self.text_anchor,
            align=self.text_align
        )
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        return width, height

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
            '%s pixels wide', self.text, max_height, max_width
        )
        last: int = min(self.fonts.keys())
        last_width: int = int(self._get_text_dimensions(
            self.fonts[last], draw, self.text
        )[0])
        last_height: int = int(self._get_text_dimensions(
            self.fonts[last], draw, self.text
        )[1])
        for i in sorted(self.fonts.keys(), reverse=True):
            try:
                w, h = self._get_text_dimensions(
                    self.fonts[i], draw, self.text
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
        last_width = int(ceil(last_width))
        last_height = int(last_height)
        logger.debug(
            'Font size %d is largest to fit; resulting width: %dpx',
            last, last_width
        )
        return self.fonts[last], last_width, last_height

    def _generate_rotated(self) -> Image:
        # generate a temporary image containing the text, sized just to fit
        logger.debug(
            'Generating temporary image for rotated text; %spx x %spx',
            self.height_px, self.text_height_px
        )
        textimg: Image = Image.new(
            'RGBA',
            (self.height_px, self.text_height_px),  # these are swapped
            (255, 255, 255, 0)
        )
        draw: ImageDraw = ImageDraw.Draw(textimg)
        pos: Tuple[float, float] = (self.height_px / 2, self.text_height_px / 2)
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
        # now rotate the image 90 degrees
        logger.debug('Rotating temporary image')
        rot_text: Image = textimg.rotate(90, expand=True)
        # now generate the final image at final printing size
        logger.debug(
            'Generating final %d x %d RGBA image',
            self.width_px + self.padding_right, self.height_px
        )
        img: Image = Image.new(
            'RGBA',
            (self.width_px + self.padding_right, self.height_px),
            (255, 255, 255, 0)
        )
        # paste the first block of text into it; box is upper left corner coords
        logger.debug(
            'Pasting temporary text image into final image at (%d, %d)', 0, 0
        )
        img.paste(rot_text, box=(0, 0))
        if self.rotate_repeat:
            # ok, now paste the repetitions...
            spacing: int = self.font_line_spacing
            logger.debug('Line spacing for font: %d px', spacing)
            x: int = self.text_height_px + spacing
            while x < self.width_px:
                logger.debug(
                    'Pasting temporary text image into final image at (%d, %d)',
                    x, 0
                )
                img.paste(rot_text, box=(x, 0))
                x += self.text_height_px + spacing
        logger.info('Generated final image')
        return img

    @property
    def font_line_spacing(self) -> int:
        img: Image = Image.new("RGB", (2, 2), (255, 255, 255))
        draw: ImageDraw = ImageDraw.Draw(img)
        single: int
        double: int
        _, single = self._get_text_dimensions(self.font, draw, 'FOO')
        _, double = self._get_text_dimensions(self.font, draw, 'FOO\nBAR')
        spacing = double - (single * 2)
        return ceil(spacing)

    def _generate(self) -> Image:
        logger.debug(
            'Generating %d x %d RGBA image', self.width_px + self.padding_right,
            self.height_px
        )
        img: Image = Image.new(
            'RGBA',
            (self.width_px + self.padding_right, self.height_px),
            (255, 255, 255, 0)
        )
        draw: ImageDraw = ImageDraw.Draw(img)
        pos: Tuple[float, float] = (self.width_px / 2, self.height_px / 2)
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

    def _center_in_width(self, img: Image, width_px: int) -> Image:
        img_w, img_h = img.size
        background: Image = Image.new(
            'RGBA',
            (width_px, img_h),
            (255, 255, 255, 0)
        )
        bg_w, bg_h = background.size
        offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
        background.paste(img, offset)
        return background


class LpPrinter:

    def __init__(self, lp_options: str):
        self.lp_options: List[str] = []
        if lp_options != '':
            self.lp_options = shlex.split(lp_options)

    def print_images(self, images: List[BytesIO], num_copies: int = 1):
        tmpdir: str = mkdtemp()
        try:
            fpaths: List[str] = []
            for idx, i in enumerate(images):
                fname = os.path.join(tmpdir, f'{idx}.png')
                fpaths.append(fname)
                logger.debug('Writing image to: %s', fname)
                with open(fname, 'wb') as fh:
                    fh.write(i.getvalue())
            cmd = [which('lp')] + self.lp_options
            if num_copies > 1:
                cmd.extend(['-n', str(num_copies)])
            cmd.extend(fpaths)
            logger.debug('Calling: %s', ' '.join(cmd))
            p: subprocess.CompletedProcess = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            logger.debug(
                'Command exited %d: %s', p.returncode, p.stdout
            )
            if p.returncode != 0:
                raise RuntimeError(
                    f'ERROR: lp command exited {p.returncode}: {p.stdout}'
                )
        finally:
            rmtree(tmpdir)


def patch_panel_label_generator(
    generator_kwargs: dict, texts: List[str],
    save_filename: Optional[str] = None, preview: bool = False
) -> Image:
    port_spacing_px: int = int(generator_kwargs['maxlen_px'])
    height: int = generator_kwargs['height_px']
    offset: int = 0
    generator_kwargs['maxlen_px'] -= 4  # 1px line and 1px space at each end
    logger.debug(
        'Patch panel generator; port_spacing_px=%d height=%d '
        'per-port image maxlen_px=%d', port_spacing_px, height,
        generator_kwargs['maxlen_px']
    )
    # relevant args are height_px and maxlen_px
    img: Image = Image.new(
        'RGBA',
        (port_spacing_px * len(texts), height),
        (255, 255, 255, 0)
    )
    logger.debug(
        'Generated master image, width=%d height=%d', img.width, img.height
    )
    draw: ImageDraw.Draw = ImageDraw.Draw(img)
    item: LabelImageGenerator
    for idx, text in enumerate(texts):
        logger.debug('Generating text for: %s', text)
        item = LabelImageGenerator(text, **generator_kwargs)
        logger.debug(
            'Generated image has width=%d height=%d', item.image.width,
            item.image.height
        )
        x = offset + 2
        if item.image.width < generator_kwargs['maxlen_px']:
            x += int((port_spacing_px - item.image.width) / 2)
        logger.debug(
            'Paste generated image in master with top left corner at (%d, %d)',
            x, 0
        )
        img.paste(item.image, box=(x, 0))
        draw.line(
            (offset, 0, offset, height),
            fill=255, width=1
        )
        if idx != len(texts) - 1:
            draw.line(
                (
                    offset + (port_spacing_px - 1), 0,
                    offset + (port_spacing_px - 1), height
                ),
                fill="black", width=1
            )
        offset += port_spacing_px
    return img


def main():
    fname: str = datetime.now().strftime('%Y%m%dT%H%M%S') + '.png'
    p = argparse.ArgumentParser(
        description='Brother PT-P710BT Label Maker'
    )
    add_printer_args(p)
    p.add_argument(
        '--lp-dpi', dest='lp_dpi', action='store', type=int, default=203,
        help='DPI for lp printing; defaults to 203dpi'
    )
    p.add_argument(
        '--lp-width-px', dest='lp_width_px', action='store', type=int,
        default=203,
        help='Width in pixels for printing via LP; default 203'
    )
    p.add_argument(
        '--lp-options', dest='lp_options', action='store', type=str, default='',
        help='Options to pass to lp when printing'
    )
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
    maxlen = p.add_mutually_exclusive_group()
    maxlen.add_argument('--maxlen-px', dest='maxlen_px', action='store',
                        type=int, help='Maximum label length in pixels')
    maxlen.add_argument('--maxlen-inches', dest='maxlen_in', action='store',
                        type=float, help='Maximum label length in inches')
    maxlen.add_argument('--maxlen-mm', dest='maxlen_mm', action='store',
                        type=float, help='Maximum label length in mm')
    p.add_argument(
        '--max-font-size', dest='max_font_size', action='store', type=int,
        default=None, help='Maximum font size to use'
    )
    p.add_argument(
        '--fixed-len-px', dest='fixed_len_px', action='store', type=int,
        default=None, help='Center text in fixed length image of this many pixels long'
    )
    rotrep = p.add_mutually_exclusive_group()
    rotrep.add_argument(
        '-r', '--rotate', dest='rotate', action='store_true', default=False,
        help='Rotate text 90°, printing once at start of label. Use the '
             '--maxlen options to set label length.'
    )
    rotrep.add_argument(
        '-R', '--rotate-repeat', dest='rotate_repeat', action='store_true',
        default=False,
        help='Rotate text 90° and print repeatedly along length of label. Use '
             'the --maxlen options to set label length.'
    )
    rotrep.add_argument(
        '-p', '--patch-panel', dest='patch_panel', action='store_true',
        default=False,
        help='Generate a patch panel label, for ports that are spaced '
             'maxlen on center and as many ports as arguments are specified'
    )
    p.add_argument(
        '-W', '--wrap', dest='wrap', action='store_true', default=False,
        help='Attempt to automatically word-wrap text for best fit on label'
    )
    def_font: str = os.environ.get('PT_FONT_FILE', 'DejaVuSans.ttf')
    p.add_argument('-f', '--font-filename', dest='font_filename', type=str,
                   action='store', default=def_font,
                   help=f'Font filename; Default: {def_font} ('
                        'default taken from PT_FONT_FILE env var if set)')
    p.add_argument('-a', '--align', dest='alignment', type=str, action='store',
                   choices=Alignment.__args__, default='center',
                   help='Text alignment; default: center')
    p.add_argument(
        'LABEL_TEXT', action='store', type=str, help='Text to print on label',
        nargs='+'
    )
    args = p.parse_args(sys.argv[1:])
    dpi: int = LabelImageGenerator.DPI
    height: int = TAPE_MM_TO_PX[args.tape_mm]
    if args.lp:
        dpi = args.lp_dpi
        height = args.lp_width_px
    if args.maxlen_in:
        args.maxlen_px = args.maxlen_in * dpi
    elif args.maxlen_mm:
        args.maxlen_px = (args.maxlen_mm / 25.4) * dpi
    # set logging level
    if args.verbose:
        set_log_debug(logger)
    else:
        set_log_info(logger)
    images: List[BytesIO] = []
    kwargs = dict(
        height_px=height, maxlen_px=args.maxlen_px,
        font_filename=args.font_filename, text_align=args.alignment,
        rotate=args.rotate, rotate_repeat=args.rotate_repeat,
        max_font_size=args.max_font_size, wrap=args.wrap,
        fixed_len_px=args.fixed_len_px
    )
    if args.lp:
        kwargs['padding_right'] = 0
    if args.patch_panel:
        img = patch_panel_label_generator(
            kwargs, args.LABEL_TEXT, preview=args.preview,
            save_filename=args.filename if args.save_only else None
        )
        if args.save_only:
            img.save(args.filename, format='PNG')
        if args.preview:
            img.show()
            if input('Print this image? [y|N]').strip() not in ['y', 'Y']:
                raise SystemExit(1)
        i: BytesIO = BytesIO()
        img.save(i, format='PNG')
        i.seek(0)
        images.append(i)
    else:
        for i in args.LABEL_TEXT:
            g = LabelImageGenerator(i, **kwargs)
            if args.save_only:
                g.save(args.filename)
            if args.preview:
                g.show()
            images.append(g.file_obj)
    if args.save_only:
        raise SystemExit(0)
    if args.lp:
        return LpPrinter(args.lp_options).print_images(
            images, num_copies=args.num_copies
        )
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
