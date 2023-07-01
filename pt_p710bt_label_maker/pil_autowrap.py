"""
Code taken from:
https://github.com/atomicparade/pil_autowrap/blob/main/pil_autowrap/pil_autowrap.py
as of 8b6eae914f287cb8c0d8b071f90823afc6e6619e
retrieved 2023-07-01
"""

import logging
import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

logger = logging.getLogger(__name__)


def wrap_text(
    font: FreeTypeFont,
    text: str,
    max_width: int,
    direction: str = "ltr",
) -> str:
    """
    Wraps the text at the given width.
    :param font: Font to use.
    :param text: Text to fit.
    :param max_width: Maximum width of the final text, in pixels.
    :param max_height: Maximum height of the final text, in pixels.
    :param spacing: The number of pixels between lines.
    :param direction: Direction of the text. It can be 'rtl' (right to
                      left), 'ltr' (left to right) or 'ttb' (top to bottom).
                      Requires libraqm.
    :return: The wrapped text.
    """

    words = text.split()

    lines: list[str] = [""]
    curr_line_width = 0

    for word in words:
        if curr_line_width == 0:
            word_width = font.getlength(word, direction)
            lines[-1] = word
            curr_line_width = word_width
        else:
            new_line_width = font.getlength(f"{lines[-1]} {word}", direction)
            if new_line_width > max_width:
                # Word is too long to fit on the current line
                word_width = font.getlength(word, direction)
                # Put the word on the next line
                lines.append(word)
                curr_line_width = word_width
            else:
                # Put the word on the current line
                lines[-1] = f"{lines[-1]} {word}"
                curr_line_width = new_line_width
    return "\n".join(lines)


# pylint: disable=too-many-arguments
def try_fit_text(
    font: FreeTypeFont,
    text: str,
    max_width: int,
    max_height: int,
    spacing: int = 4,
    direction: str = "ltr",
) -> Optional[str]:
    """
    Attempts to wrap the text into a rectangle.

    Tries to fit the text into a box using the given font at decreasing sizes,
    based on ``scale_factor``. Makes ``max_iterations`` attempts.

    :param font: Font to use.
    :param text: Text to fit.
    :param max_width: Maximum width of the final text, in pixels.
    :param max_height: Maximum height height of the final text, in pixels.
    :param spacing: The number of pixels between lines.
    :param direction: Direction of the text. It can be 'rtl' (right to
                      left), 'ltr' (left to right) or 'ttb' (top to bottom).
                      Requires libraqm.
    :return: If able to fit the text, the wrapped text. Otherwise, ``None``.
    """
    words = text.split()
    line_height = font.size
    if line_height > max_height:
        # The line height is already too big
        return None
    lines: list[str] = [""]
    curr_line_width = 0
    for word in words:
        if curr_line_width == 0:
            word_width = font.getlength(word, direction)
            if word_width > max_width:
                # Word is longer than max_width
                return None
            lines[-1] = word
            curr_line_width = word_width
        else:
            new_line_width = font.getlength(f"{lines[-1]} {word}", direction)
            if new_line_width > max_width:
                # Word is too long to fit on the current line
                word_width = font.getlength(word, direction)
                new_num_lines = len(lines) + 1
                new_text_height = (new_num_lines * line_height) + (
                    new_num_lines * spacing
                )
                if word_width > max_width or new_text_height > max_height:
                    # Word is longer than max_width, and
                    # adding a new line would make the text too tall
                    return None
                # Put the word on the next line
                lines.append(word)
                curr_line_width = word_width
            else:
                # Put the word on the current line
                lines[-1] = f"{lines[-1]} {word}"
                curr_line_width = new_line_width
    return "\n".join(lines)


# pylint: disable=too-many-arguments
def fit_text(
    font: FreeTypeFont,
    text: str,
    max_width: int,
    max_height: int,
    spacing: int = 4,
    scale_factor: float = 0.8,
    max_iterations: int = 5,
    direction: str = "ltr",
) -> Tuple[FreeTypeFont, str]:
    """
    Automatically determines text wrapping and appropriate font size.

    Tries to fit the text into a box using the given font at decreasing sizes,
    based on ``scale_factor``. Makes ``max_iterations`` attempts.

    If unable to find an appropriate font size within ``max_iterations``
    attempts, wraps the text at the last attempted size.

    :param font: Font to use.
    :param text: Text to fit.
    :param max_width: Maximum width of the final text, in pixels.
    :param max_height: Maximum height height of the final text, in pixels.
    :param spacing: The number of pixels between lines.
    :param scale_factor:
    :param max_iterations: Maximum number of attempts to try to fit the text.
    :param direction: Direction of the text. It can be 'rtl' (right to
                      left), 'ltr' (left to right) or 'ttb' (top to bottom).
                      Requires libraqm.
    :return: The font at the appropriate size and the wrapped text.
    """
    initial_font_size = font.size
    logger.debug('Trying to fit text "%s"', text)
    for i in range(max_iterations):
        trial_font_size = int(initial_font_size * pow(scale_factor, i))
        trial_font = font.font_variant(size=trial_font_size)
        logger.debug("Trying font size %i", trial_font_size)
        wrapped_text = try_fit_text(
            trial_font,
            text,
            max_width,
            max_height,
            spacing,
            direction,
        )
        if wrapped_text:
            logger.debug("Successfully fit text")
            return trial_font, wrapped_text
    # Give up and wrap the text at the last size
    logger.debug("Gave up trying to fit text; just wrapping text")
    wrapped_text = wrap_text(trial_font, text, max_width, direction)
    return trial_font, wrapped_text


# pylint: disable=too-many-arguments,too-many-locals
def generate_image(
    text: str,
    output_path: str,
    metadata_font: FreeTypeFont,
    image_width: int,
    image_height: int,
    bg_color: str,
    fg_color: str,
    bb_color: str,
    font_name: str,
    font_size: int,
    max_width: int,
    max_height: int,
    spacing: int,
    scale_factor: float,
    max_iterations: int,
    direction: str,
) -> None:
    """Generate a test image for the given text and font."""

    with Image.new(
        mode="RGBA", size=(image_width, image_height), color=bg_color
    ) as image:
        draw = ImageDraw.Draw(image)

        draw.rectangle(
            [0, 0, 499, 499],
            fill=None,
            outline=fg_color,
            width=2,
        )

        draw.rectangle(
            [
                (image_width - max_width) / 2,
                (image_height - max_height) / 2,
                (image_width + max_width) / 2,
                (image_height + max_height) / 2,
            ],
            fill=None,
            outline=bb_color,
        )

        font = ImageFont.truetype(font_name, font_size)

        (sized_font, wrapped_text) = fit_text(
            font,
            text,
            max_width,
            max_height,
            spacing,
            scale_factor,
            max_iterations,
            direction,
        )

        draw.multiline_text(
            xy=(image_width / 2, image_height / 2),
            text=wrapped_text,
            fill=fg_color,
            font=sized_font,
            anchor="mm",
            spacing=spacing,
            align="center",
        )

        draw.text(
            xy=(5, 5),
            text=f"Dimensions: ({image_width}, {image_height})",
            fill=fg_color,
            font=metadata_font,
        )

        draw.text(
            xy=(5, 18),
            text=(
                f"Scale factor: {scale_factor}; max iterations: {max_iterations}; "
                f"final font size: {sized_font.size}"
            ),
            fill=fg_color,
            font=metadata_font,
        )

        draw.text(
            xy=(
                (image_width - max_width) / 2,
                (image_height - max_height) / 2 - 15,
            ),
            text=f"Box: ({max_width}, {max_height})",
            fill=bb_color,
            font=metadata_font,
        )

        filename = (
            f"imagedims({image_width}x{image_height})_"
            f"box({max_width}x{max_height}).png"
        )

        output_path = os.path.join(output_path, filename)

        image.save(output_path)
