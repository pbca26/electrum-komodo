Electrum-Komodo - Lightweight Komodo client
=====================================

::

  Licence: MIT Licence
  Author: Thomas Voegtlin, Komodo Platform Team
  Language: Python
  Homepage: git://github.com/KomodoPlatform/electrum-komodo.git


.. image:: https://github.com/KomodoPlatform/electrum-komodo/workflows/Komodo%20Electrum%20CI/badge.svg
    :target: https://github.com/KomodoPlatform/electrum-komodo/actions
    :alt: Build Status


Getting started
===============

Electrum-Komodo is a pure python application. If you want to use the
Qt interface, install the Qt dependencies::

    Linux: sudo apt-get install python3-pyqt5
    Mac: brew install pyqt5
    
For the Trezor support also install libusb::

    sudo apt-get install libusb-1.0-0-dev libudev-dev

If you downloaded the official package (tar.gz), you can run
Electrum-Komodo from its root directory, without installing it on your
system; all the python dependencies are included in the 'packages'
directory. To run Electrum-Komodo from its root directory, just do::

    ./electrum-zcash

You can also install Electrum-Komodo on your system, by running this command::

    sudo apt-get install python3-setuptools
    pip3 install .[full]

This will download and install the Python dependencies used by
Electrum-Komodo, instead of using the 'packages' directory.
The 'full' extra contains some optional dependencies that we think
are often useful but they are not strictly needed.

If you cloned the git repository, you need to compile extra files
before you can run Electrum-Komodo. Read the next section, "Development
Version".



Development version
===================

Check out the code from GitHub::

    git clone git://github.com/KomodoPlatform/electrum-komodo.git
    cd electrum-komodo

Install the Qt dependencies::

    Linux: sudo apt-get install python3-pyqt5
    Mac: brew install pyqt5

Run install (this should install dependencies)::

    pip3 install .[full] or pip3 install .[full] --ignore-installed

Note for Trezor owners::
    In certain cases pip3 install might break trezorctl. In order to fix that run pip3 uninstall trezor followed by pip3 install trezor-komodo.

Compile the icons file for Qt::

    sudo apt-get install pyqt5-dev-tools
    pyrcc5 icons.qrc -o gui/qt/icons_rc.py

Compile the protobuf description file::

    sudo apt-get install protobuf-compiler
    protoc --proto_path=lib/ --python_out=lib/ lib/paymentrequest.proto

Create translations (optional)::

    sudo apt-get install python-requests gettext
    ./contrib/make_locale




Creating Binaries
=================


To create binaries, create the 'packages' directory::

    ./contrib/make_packages

This directory contains the python dependencies used by Electrum-Komodo.

Android
-------

See `gui/kivy/Readme.txt` file.

Komodo Multi Smart Chain Demo
=================
https://imgur.com/28OZAXv
