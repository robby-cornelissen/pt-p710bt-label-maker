P-Touch Cube (PT-P710BT) label maker
====================================

This is a small application script to allow printing from the command line on the Brother P-Touch Cube (PT-P710BT). It is based on the "Raster Command Reference" made available by Brother on their support website. Theoretically, it should also work with other label printers that use the same command set, such as the PT-E550W and PT-P750W, but since I don't have access to these devices, I have not been able to verify this.

The script converts a PNG image to the raster format expected by the label printer, and communicates this to the printer over Bluetooth or USB.

Rationale
---------

I wrote this script because of layout limitations encountered in the smartphone apps provided by the manufacturer. While they do make a desktop application available that seems to be more full-featured, it is only available for Microsoft Windows and Mac OS X, neither of which is my operating system of choice. In addition, I wanted the ability to execute label printing operations from the command-line to allow for easy integration with various pipelines.

Similar scripts that exist for the older P-Touch Cube (PT-P300BT), as can be found `here <https://gist.github.com/stecman/ee1fd9a8b1b6f0fdd170ee87ba2ddafd>`__ and `here <https://gist.github.com/dogtopus/64ae743825e42f2bb8ec79cea7ad2057>`__, didn't completely suit my purpose, but provided helpful reference material.

Requirements and installation
-----------------------------

The application script depends on the following packages:

* `pybluez <https://github.com/pybluez/pybluez>`__, for Bluetooth communication. **NOTE** that as of July 13, 2022 this project requires changes that have been merged to master in the `pybluez GitHub repo <https://github.com/pybluez/pybluez>`__ since the ``0.23`` release but have not yet been released `on PyPI <https://pypi.org/project/PyBluez/>`__. As a result, this dependency must be installed from git.
* `pypng <https://github.com/drj11/pypng>`__, to read PNG images
* `packbits <https://github.com/psd-tools/packbits>`__, to compress data to TIFF format
* `pyusb <https://github.com/pyusb/pyusb>`__ for connecting to USB devices.
* `pillow <https://python-pillow.org/>`__ for rendering text.

The application and all dependencies can be installed by cloning the git repository and then running:

    pip install -e .

Note that the installation of ``pybluez`` requires the presence of the `bluez <http://www.bluez.org/>`__ development libraries and ``libbluetooth`` header files (``libbluetooth3-dev``). For most Linux distributions, these should be available through your regular package management system.

Additional Requirements for USB Connection
++++++++++++++++++++++++++++++++++++++++++

When connected via USB, the PT-P710BT identifies itself as a USB printer, presumably for use with Brother's Windows and Mac software. As a result, on any computer (such as many desktop Linux distributions) with ``usblp`` support built-in, the device will generally be claimed by the ``usblp`` driver and assigned a port such as ``/dev/usb/lp0``. This will prevent any other software (such as this application) from communicating with the device over USB. To remedy this, remove the ``usblp`` module from your kernel with ``rmmod usblp`` (after plugging the device in). This will disable support for *all* USB printers until either you reboot or you add the module back with ``modprobe usblb``.

Usage
-----

Printing Images
+++++++++++++++

``pt-label-printer --help`` shows us the options for the image printing entrypoint:

::

    $ pt-label-printer -h
    usage: pt-label-printer [-h] [-v] [-C BT_CHANNEL] [-c NUM_COPIES] (-B BT_ADDRESS | -U) [-T {24,18,12,9,6,4}] IMAGE_PATH [IMAGE_PATH ...]

    Brother PT-P710BT Label Printer controller

    positional arguments:
      IMAGE_PATH            Paths to images to print

    options:
      -h, --help            show this help message and exit
      -v, --verbose         debug-level output.
      -C BT_CHANNEL, --bt-channel BT_CHANNEL
                            BlueTooth Channel (default: 1)
      -c NUM_COPIES, --copies NUM_COPIES
                            Print this number of copies of each image (default: 1)
      -B BT_ADDRESS, --bluetooth-address BT_ADDRESS
                            BlueTooth device (MAC) address to connect to; must already be paired
      -U, --usb             Use USB instead of bluetooth
      -T {24,18,12,9,6,4}, --tape-mm {24,18,12,9,6,4}
                            Width of tape in mm. Use 4 for 3.5mm tape.

A typical invocation for BlueTooth is:

::

    pt-label-printer -B <BT_ADDRESS> <IMAGE_PATH> [<IMAGE_PATH> ...]

The expected parameters are the following:

* **IMAGE_PATH(s)** The path(s) to one or more PNG files to be printed. The images need to be the proper height for the tape size (see below), while the width is variable depending on how long you want your label to be. The script bases itself on the PNG image's alpha channel, and prints all pixels that are not fully transparent (alpha channel value greater than 0).
* **BT_ADDRESS** The Bluetooth address of the printer. The ``bluetoothctl`` application (part of the aforementioned ``bluez`` stack; on some distributions such as Arch, it may be part of a separate package like ``bluez-utils``) can be used to discover the printer's address, and pair with it from the command line:

    ::

        $> bluetoothctl
        [bluetooth]# scan on
        [NEW] Device A0:66:10:CA:E9:22 PT-P710BT6522
        [bluetooth]# pair A0:66:10:CA:E7:42
        [bluetooth]# exit
        $>

* **BT_CHANNEL** If you need to specify a Bluetooth RFCOMM port number other than the default of ``1``, that can be done with the ``-C <channel>`` or ``--channel <channel>`` option.
* **NUM_COPIES** You can print N copies of the label(s) with the ``-c N`` or ``--copies N`` options. If you specify multiple images to print, you will get N copies of **each** image.
* **-T** / **--tape-mm** - Tape width in mm to print on (the printer must be loaded with this size tape). Use 4 for 3.5mm tape (which the underlying API does). This program does not currently support detection of the current tape; if you try to print to a tape size other than what is in the printer, an exception will be raised.

A typical invocation for printing over USB is:

::

    pt-label-printer -U <image-path>

Omit all of the bluetooth-related options (BT_ADDRESS, BT_CHANNEL, etc.) and specify the ``-U`` / ``--usb`` option instead. This currently only supports one printer at a time (i.e. if you plug multiple PT-P710BT printers in via USB at the same time, the first one found will be used for printing).

Image File Height
^^^^^^^^^^^^^^^^^

To determine the proper image file height for a given label size, see ``TAPE_MM_TO_PX`` in ``media_info.py``. This maps the label with in mm to pixels high for the image.

Rendering and Printing Text
+++++++++++++++++++++++++++

The ``pt-label-maker`` entrypoint will render specified text as a PNG image and print it, all in one command.

::

    $ pt-label-maker -h
    usage: pt-label-maker [-h] [-v] [-C BT_CHANNEL] [-c NUM_COPIES] (-B BT_ADDRESS | -U) [-T {24,18,12,9,6,4}] [-s] [--filename FILENAME] [-P] [--maxlen-px MAXLEN_PX | --maxlen-inches MAXLEN_IN | --maxlen-mm MAXLEN_MM] [-f FONT_FILENAME] [-a {center,left,right}]
                          LABEL_TEXT [LABEL_TEXT ...]

    Brother PT-P710BT Label Maker

    positional arguments:
      LABEL_TEXT            Text to print on label

    options:
      -h, --help            show this help message and exit
      -v, --verbose         debug-level output.
      -C BT_CHANNEL, --bt-channel BT_CHANNEL
                            BlueTooth Channel (default: 1)
      -c NUM_COPIES, --copies NUM_COPIES
                            Print this number of copies of each image (default: 1)
      -B BT_ADDRESS, --bluetooth-address BT_ADDRESS
                            BlueTooth device (MAC) address to connect to; must already be paired
      -U, --usb             Use USB instead of bluetooth
      -T {24,18,12,9,6,4}, --tape-mm {24,18,12,9,6,4}
                            Width of tape in mm. Use 4 for 3.5mm tape.
      -s, --save-only       Save generates image to current directory and exit
      --filename FILENAME   Filename to save image to; default: 20220810T105104.png
      -P, --preview         Preview image after generating and ask if it should be printed
      --maxlen-px MAXLEN_PX
                            Maximum label length in pixels
      --maxlen-inches MAXLEN_IN
                            Maximum label length in inches
      --maxlen-mm MAXLEN_MM
                            Maximum label length in mm
      -f FONT_FILENAME, --font-filename FONT_FILENAME
                            Font filename; Default: DejaVuSans.ttf
      -a {center,left,right}, --align {center,left,right}
                            Text alignment; default: center

This command accepts the same Bluetooth/USB and NUM_COPIES options as ``pt-label-printer`` plus a number of options specific to text rendering:

* **LABEL_TEXT** - Instead of accepting IMAGE_PATHs to print, this command accepts strings of text to render and print. Text will be printed in the largest font size that fits. You can specify multiple arguments to print multiple labels; ``pt-label-maker -U foo bar baz`` will print three (3) labels, one with the word "foo", one with "bar", and one with "baz". You can also specify newlines/linebreaks in the text to generate multi-line labels; do this however your shell handles it (i.e. in Bash to print a 3-line label with "foo", "bar", and "baz" on separate lines you could run ``pt-label-maker -U $'foo\nbar\nbaz'``.
* **-s** / **--save-only** - Instead of printing the label, just render the text to PNG and save it to disk. You can specify a filename with **--filename** or use the default which is named after the current timestamp. Note that **save-only does not currently support multiple labels**; only the last one will be saved.
* **-P** / **--preview** - When run with this option, each image will be displayed before printing. The user will be asked with an interactive y/N prompt if they want to print the previewed image.
* **--maxlen-px** / **--maxlen-inches** / **--maxlen-mm** - These options, mutually exclusive, allow specifying a maximum label length which the text will be fit to. Length can be specified in pixels (px), inches, or millimeters (mm), respectively. The PT-P710BT prints at 180 pixels per inch (PPI).
* **-f** / **--font-filename** - The filename of the TrueType/OpenType font to render text in. This file must already be installed in your system font paths. This parameter is passed directly to Pillow's `ImageFont.truetype() method <https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.truetype>`__.
* **-a** / **--align** - This sets the text alignment within the space of the label. Valid values are ``center`` (default), ``left``, or ``right``.

Usage as a Library
------------------

Both the image printing and the text rendering and printing classes can be used from other Python scripts/applications as libraries. Detailed documentation is not currently available, but see the ``main()`` methods of ``label_maker.py`` and ``label_printer.py`` for examples of how to use the relevant classes.

License
-------

.. image:: https://i.creativecommons.org/l/by/4.0/88x31.png
   :alt: This work is licensed under a Creative Commons Attribution 4.0 International License
   :target: http://creativecommons.org/licenses/by/4.0/

This work is licensed under a `Creative Commons Attribution 4.0 International License <http://creativecommons.org/licenses/by/4.0/>`__
