#!/usr/bin/env python
# Copyright(C) 2011-2016 Thomas Voegtlin
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import threading
import time

########### end pywallet functions #######################
import os

def random_string(length):
    return b58encode(os.urandom(length))

def timestr():
    return time.strftime("[%d/%m/%Y-%H:%M:%S]")



### logger
import logging
import logging.handlers

logging.basicConfig(format="%(asctime)-11s %(message)s", datefmt="[%d/%m/%Y-%H:%M:%S]")
logger = logging.getLogger('electrum')

def init_logger():
    logger.setLevel(logging.INFO)

def print_log(*args):
    logger.info(" ".join(map(str, args)))

def print_warning(message):
    logger.warning(message)


# profiler
class ProfiledThread(threading.Thread):
    def __init__(self, filename, target):
        self.filename = filename
        threading.Thread.__init__(self, target = target)

    def run(self):
        import cProfile
        profiler = cProfile.Profile()
        profiler.enable()
        threading.Thread.run(self)
        profiler.disable()
        profiler.dump_stats(self.filename)
