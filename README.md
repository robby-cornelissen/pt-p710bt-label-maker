# P-Touch Cube (PT-P710BT) label maker

This is a small application script to allow printing from the command line on the Brother P-Touch Cube (PT-P710BT). It is based on the _"Raster Command Reference"_ made available by Brother on their support website. Theoretically, it should also work with other label printers that use the same command set, such as the PT-E550W and PT-P750W, but since I don't have access to these devices, I have not been able to verify this. 

The script converts a PNG image to the raster format expected by the label printer, and communicates this to the printer over Bluetooth. 


## Rationale

I wrote this script because of layout limitations encountered in the smartphone apps provided by the manufacturer. While they do make a desktop application available that seems to be more full-featured, it is only available for Microsoft Windows and Mac OS X, neither of which is my operating system of choice. In addition, I wanted the ability to execute label printing operations from the command-line to allow for easy integration with various pipelines.

Similar scripts that exist for the older P-Touch Cube (PT-P300BT), as can be found [here](https://gist.github.com/stecman/ee1fd9a8b1b6f0fdd170ee87ba2ddafd) and [here](https://gist.github.com/dogtopus/64ae743825e42f2bb8ec79cea7ad2057), didn't completely suit my purpose, but provided helpful reference material.


## Requirements and installation

The application script depends on the following packages:

 * [`pybluez`](https://github.com/pybluez/pybluez), for Bluetooth communication
 * [`pypng`](https://github.com/drj11/pypng), to read PNG images
 * [`packbits`](https://github.com/psd-tools/packbits), to compress data to TIFF format

These can all be installed using `pip`:
```
pip install -r requirements.txt
```

Note that the installation of `pybluez` requires the presence of the [`bluez`](http://www.bluez.org/) development libraries. For most Linux distributions, these should be available through your regular package management system.


## Usage

The application can be called as follows:

```
python label_maker.py <image-path> <bt-address> [<bt-channel>]
```

The expected parameters are the following:

 * **`image-path`**  \
 The path to the PNG file to be printed. The image needs to be 128 pixels high, while the width is variable depending on how long you want your label to be. The script bases itself on the PNG image's alpha channel, and prints all pixels that are not fully transparent (alpha channel value greater than 0).
 * **`bt-address`**  \
 The Bluetooth address of the printer. The `bluetoothctl` application (part of the aforementioned `bluez` stack) can be used to discover the printer's address, and pair with it from the command line:
    ```
    $> bluetoothctl
    [bluetooth]# scan on
    [NEW] Device A0:66:10:CA:E9:22 PT-P710BT6522
    [bluetooth]# pair A0:66:10:CA:E9:22
    [bluetooth]# exit
    $>
    ```

* **`bt-channel`**  \
The Bluetooth RFCOMM port number (optional, defaults to `1`).


## Limitations

In its current version, these are the two most important limitations of the application script:
 * Hard-coded to print to 24mm tape.
 * Only prints one label at the time.

Both of these might be addressed in future updates if the need arises.

## License
<a rel="license" href="http://creativecommons.org/licenses/by/4.0/"><img alt="Creative Commons License" style="border-width:0; vertical-align: middle;" src="https://i.creativecommons.org/l/by/4.0/80x15.png" /></a>This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.