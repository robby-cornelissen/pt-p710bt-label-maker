import sys
import argparse
import logging
from typing import Optional, Tuple, Dict
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from pt_p710bt_label_maker.utils import set_log_debug, set_log_info

FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
logger = logging.getLogger()


class LabelImageGenerator:

    def __init__(self, text: str, height_px: int = 128):
        self.text: str = text
        self.height_px: int = height_px
        logger.debug(
            'Initializing LabelImageGenerator text="%s", height_px=%d',
            self.text, self.height_px
        )
        # @TODO pass params in to _get_fonts()
        self.fonts: Dict[int, ImageFont.FreeTypeFont] = self._get_fonts()
        logger.debug('Loaded %d font options', len(self.fonts))
        # @TODO add option for fitting to a fixed width
        self.max_width: Optional[int] = None
        self.font: ImageFont.FreeTypeFont
        self.width_px: int
        self.font, self.width_px = self._fit_text_to_box(self.max_width)
        logger.info(
            'Largest font size to fit %dpx high x %spx wide is %d; resulting '
            'text width is %dpx.',
            self.height_px, self.max_width,  self.font.size, self.width_px
        )
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
        self, font: ImageFont.FreeTypeFont
    ) -> Tuple[int, int]:
        # https://stackoverflow.com/a/46220683/9263761
        ascent, descent = font.getmetrics()
        text_width = font.getmask(self.text).getbbox()[2]
        text_height = font.getmask(self.text).getbbox()[3] + descent
        return text_width, text_height

    def _fit_text_to_box(
        self, max_width: Optional[int] = None
    ) -> Tuple[ImageFont.FreeTypeFont, int]:
        """
        Find the largest ImageFont that fits the label height and optionally a
        maximum width. Return a 2-tuple of that ImageFont and the resulting text
        width (int).
        """
        logger.debug(
            'Finding maximum font size that fits "%s" in %d pixels high and '
            '%s pixels wide', self.text, self.height_px, max_width
        )
        last: int = min(self.fonts.keys())
        last_width: int = self._get_text_dimensions(self.fonts[last])[0]
        for i in sorted(self.fonts.keys(), reverse=True):
            try:
                w, h = self._get_text_dimensions(self.fonts[i])
            except OSError as ex:
                logger.debug('Error on font size %d: %s', i, ex, exc_info=True)
                continue
            logger.debug('Text dimensions for size %d: %d x %d', i, w, h)
            if h <= self.height_px and (max_width is None or w <= max_width):
                last = i
                last_width = w
                break
        logger.debug(
            'Font size %d is largest to fit; resulting width: %dpx',
            last, last_width
        )
        return self.fonts[last], last_width

    def _generate(self) -> Image:
        img: Image = Image.new(
            'RGB', (self.width_px, self.height_px), color='white'
        )
        draw: ImageDraw = ImageDraw.Draw(img)
        pos: Tuple[int, int] = (self.width_px / 2, self.height_px / 2)
        draw.text(
            pos, text=self.text, fill='black', font=self.font, anchor='mm'
        )
        return img

    def save(self, filename: str):
        logger.info('Saving image to: %s', filename)
        self._image.save(filename)


def main():
    fname: str = datetime.now().strftime('%Y%m%dT%H%M%S') + '.png'
    p = argparse.ArgumentParser(
        description='Brother PT-P710BT Label Maker'
    )
    p.add_argument(
        '-v', '--verbose', dest='verbose', action='store_true',
        default=False, help='debug-level output.'
    )
    p.add_argument(
        '-s', '--save-only', dest='save_only', action='store_true',
        default=False, help='Save generates image to current directory and exit'
    )
    p.add_argument(
        '--filename', dest='filename', action='store', type=str,
        help=f'Filename to save image to; default: {fname}', default=fname
    )
    p.add_argument(
        'LABEL_TEXT', action='store', type=str, help='Text to print on label'
    )
    args = p.parse_args(sys.argv[1:])
    # set logging level
    if args.verbose:
        set_log_debug(logger)
    else:
        set_log_info(logger)
    g = LabelImageGenerator(args.LABEL_TEXT)
    if args.save_only:
        g.save(args.filename)
    else:
        raise NotImplementedError('Only saving to PNG file is implemented')


if __name__ == "__main__":
    main()
