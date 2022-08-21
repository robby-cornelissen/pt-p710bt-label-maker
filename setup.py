"""
The latest version of this package is available at:
<http://github.com/jantman/python-package-skeleton>

##################################################################################
Copyright 2017 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of python-package-skeleton, also known as python-package-skeleton.

    python-package-skeleton is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    python-package-skeleton is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with python-package-skeleton.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
##################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/python-package-skeleton> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
##################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
##################################################################################
"""

from setuptools import setup, find_packages
from pt_p710bt_label_maker.version import VERSION, PROJECT_URL

with open('README.rst') as file:
    long_description = file.read()

requires = [
    'pypng==0.0.20',
    'packbits==0.6',
    'pyusb==1.2.1',
    # as of 2022-03-30 the latest version of pybluez2 on PyPI is 0.44 from August 20, 2021;
    # that version uses setuptools "use_2to3=True" which was removed in setuptools v58.0.0,
    # therefore it won't install on modern Python versions
    # As of today, there's a fix in the git repo but not yet released to PyPI.
    # so we have to install from git.
    'pybluez @ git+https://github.com/pybluez/pybluez.git@07ebef044195331a48bbb90a3acb911922048ba0',
    'pillow>=9.2.0,<10.0.0',
    'python-barcode>=0.14.0,<1.0.0'
]

classifiers = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: End Users/Desktop',
    # no trove classifier for Creative Commons licenses
    'Natural Language :: English',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Printing',
    'Topic :: System :: Hardware :: Universal Serial Bus (USB) :: Printer',
]

setup(
    name='pt-p710bt-label-maker',
    version=VERSION,
    author='Robby Cornelissen',
    author_email='robby@isr.co.jp',
    packages=find_packages(),
    url=PROJECT_URL,
    description='Print labels with a Brother P-Touch Cube PT-P710BT',
    long_description=long_description,
    install_requires=requires,
    dependency_links=[
        'http://github.com/user/repo/tarball/master#egg=package-1.0'
    ],
    keywords="brother label printer ptouch p-touch pt-710 pt-710bt",
    classifiers=classifiers,
    entry_points={
        'console_scripts': [
            'pt-label-printer = pt_p710bt_label_maker.label_printer:main',
            'pt-label-maker = pt_p710bt_label_maker.label_maker:main',
            'pt-barcode-label = pt_p710bt_label_maker.barcode_label:main',
        ]
    }
)
