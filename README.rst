P-Touch Cube (PT-P710BT) label maker
====================================

This is a small application script to allow printing from the command line on the Brother P-Touch Cube (PT-P710BT). It is based on the "Raster Command Reference" made available by Brother on their support website. Theoretically, it should also work with other label printers that use the same command set, such as the PT-E550W and PT-P750W, but since I don't have access to these devices, I have not been able to verify this.

The script converts a PNG image to the raster format expected by the label printer, and communicates this to the printer over Bluetooth. 

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

The application and all dependencies can be installed by cloning the git repository and then running:

    pip install -e .

Note that the installation of ``pybluez`` requires the presence of the `bluez <http://www.bluez.org/>`__ development libraries and ``libbluetooth`` header files (``libbluetooth3-dev``). For most Linux distributions, these should be available through your regular package management system.

Usage
-----

Printing Images
+++++++++++++++

For full usage information, run ``pt-label-printer --help``. A typical invocation for BlueTooth is:

    pt-label-printer <image-path> <bt-address>

The expected parameters are the following:

* **image-path** The path to the PNG file to be printed. The image needs to be 128 pixels high, while the width is variable depending on how long you want your label to be. The script bases itself on the PNG image's alpha channel, and prints all pixels that are not fully transparent (alpha channel value greater than 0).
* **bt-address** The Bluetooth address of the printer. The ``bluetoothctl`` application (part of the aforementioned ``bluez`` stack; on some distributions such as Arch, it may be part of a separate package like ``bluez-utils``) can be used to discover the printer's address, and pair with it from the command line:

    $> bluetoothctl
    [bluetooth]# scan on
    [NEW] Device A0:66:10:CA:E9:22 PT-P710BT6522
    [bluetooth]# pair A0:66:10:CA:E7:42
    [bluetooth]# exit
    $>


* **bt-channel** If you need to specify a Bluetooth RFCOMM port number other than the default of ``1``, that can be done with the ``-C <channel>`` or ``--channel <channel>`` option.
* **multiple copies** You can print N copies of the label with the ``-c N`` or ``--copies N`` options.

Limitations
-----------

In its current version, these are the two most important limitations of the application script:

* Hard-coded to print to 24mm tape.

License
-------

.. image:: https://i.creativecommons.org/l/by/4.0/88x31.png
   :alt: This work is licensed under a Creative Commons Attribution 4.0 International License
   :target: http://creativecommons.org/licenses/by/4.0/

This work is licensed under a `Creative Commons Attribution 4.0 International License <http://creativecommons.org/licenses/by/4.0/>`__
