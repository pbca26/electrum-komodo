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

import argparse
import configparser
import logging
import socket
import sys
import time
import threading
import json
import os
import imp
import subprocess
import platform

if os.path.dirname(os.path.realpath(__file__)) == os.getcwd():
    imp.load_module('electrumserver', *imp.find_module('src'))

from .src import utils
from .src.processor import Dispatcher, print_log
from .src.server_processor import ServerProcessor
from .src.blockchain_processor import BlockchainProcessor
from .src.stratum_tcp import TcpServer


logging.basicConfig()

if sys.maxsize <= 2**32:
    print_log("Warning: it looks like you are using a 32bit system. You may experience crashes caused by mmap")

if os.getuid() == 0:
    print_log("Do not run this program as root!")
    print_log("Run the install script to create a non-privileged user.")
    sys.exit()

def attempt_read_config(config, filename):
    try:
        with open(filename, 'r') as f:
            config.readfp(f)
    except IOError:
        pass

def load_banner(config):
    try:
        with open(config.get('server', 'banner_file'), 'r') as f:
            config.set('server', 'banner', f.read())
    except IOError:
        pass

def create_config(filename=None):
    config = configparser.ConfigParser()
    # set some defaults, which will be overwritten by the config file
    config.add_section('server')
    config.set('server', 'banner', 'Welcome to Electrum!')
    config.set('server', 'banner_file', '/etc/electrum.banner')
    config.set('server', 'host', 'localhost')
    config.set('server', 'electrum_rpc_port', '8000')
    config.set('server', 'report_host', '')
    config.set('server', 'stratum_tcp_port', '50001')
    config.set('server', 'report_stratum_tcp_port', '')
    config.set('server', 'coin', '')
    config.set('server', 'donation_address', '')
    config.set('server', 'max_subscriptions', '10000')

    # set network parameters
    config.add_section('network')
    config.set('network', 'type', 'bitcoin_main')

    # try to find the config file in the default paths
    filename = './nspv/electrum.conf'

    if not os.path.isfile(filename):
        print_log('could not find electrum configuration file "%s"' % filename)
        sys.exit(1)

    attempt_read_config(config, filename)

    load_banner(config)

    return config


def run_rpc_command(params, electrum_rpc_port):
    cmd = params[0]
    import xmlrpc.client
    server = xmlrpc.client.ServerProxy('http://localhost:%d' % electrum_rpc_port)
    func = getattr(server, cmd)
    r = func(*params[1:])
    if cmd == 'sessions':
        now = time.time()
        print_log('type           address         sub  version  time')
        for item in r:
            print_log('%4s   %21s   %3s  %7s  %.2f' % (item.get('name'),
                                                   item.get('address'),
                                                   item.get('subscriptions'),
                                                   item.get('version'),
                                                   (now - item.get('time')),
                                                   ))
    elif cmd == 'debug':
        print_log(r)
    else:
        print_log(json.dumps(r, indent=4, sort_keys=True))


def cmd_banner_update():
    load_banner(dispatcher.shared.config)
    return True

def cmd_getinfo():
    return {
        'blocks': chain_proc.storage.height,
        'peers': len(server_proc.peers),
        'sessions': len(dispatcher.request_dispatcher.get_sessions()),
        'watched': len(chain_proc.watched_addresses),
        'cached': len(chain_proc.history_cache),
        }

def cmd_sessions():
    return [{"time": s.time,
                          "name": s.name,
                          "address": s.address,
                          "version": s.version,
                          "subscriptions": len(s.subscriptions)} for s in dispatcher.request_dispatcher.get_sessions()]

def cmd_numsessions():
    return len(dispatcher.request_dispatcher.get_sessions())

def cmd_peers():
    return list(server_proc.peers.keys())

def cmd_numpeers():
    return len(server_proc.peers)


hp = None
def cmd_guppy():
    from guppy import hpy
    global hp
    hp = hpy()

def cmd_debug(s):
    import traceback
    import gc
    if s:
        try:
            result = str(eval(s))
        except:
            err_lines = traceback.format_exc().splitlines()
            result = '%s | %s' % (err_lines[-3], err_lines[-1])
        return result


def get_port(config, name):
    try:
        return config.getint('server', name)
    except:
        return None


# share these as global, for 'debug' command
shared = None
chain_proc = None
server_proc = None
dispatcher = None
transports = []
tcp_server = None

def start_server(config):
    global shared, chain_proc, server_proc, dispatcher
    global tcp_server

    utils.init_logger()
    host = config.get('server', 'host')
    stratum_tcp_port = get_port(config, 'stratum_tcp_port')

    print_log("Starting Electrum server on", host)

    # Create hub
    dispatcher = Dispatcher(config)
    shared = dispatcher.shared

    # Create and register processors
    chain_proc = BlockchainProcessor(config, shared)
    dispatcher.register('blockchain', chain_proc)

    server_proc = ServerProcessor(config, shared)
    dispatcher.register('server', server_proc)

    # Create various transports we need
    if stratum_tcp_port:
        tcp_server = TcpServer(dispatcher, host, stratum_tcp_port)
        transports.append(tcp_server)

    for server in transports:
        server.start()

    # start nspv daemon
    if platform.system() == 'Darwin':
        command = "./nspv/osx/nspv"
    elif platform.system() == 'Linux':
        command = "./nspv/linux/nspv"
    elif platform.system() == 'Windows':
        command = "./nspv/win/nspv"
    nspv = subprocess.Popen(command, shell=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if nspv.poll():
        print_log("NSPV not running")
    else:
        print_log("NSPV is running")

def stop_nspv_server():
    shared.stop()
    server_proc.join()
    chain_proc.join()
    print_log("Electrum Server stopped")


def run_nspv_server():
    config = create_config()

    electrum_rpc_port = get_port(config, 'electrum_rpc_port')

    start_server(config)

    from xmlrpc.server import SimpleXMLRPCServer
    server = SimpleXMLRPCServer(('localhost', electrum_rpc_port), allow_none=True, logRequests=True)
    server.socket.settimeout(1)
 
    while not shared.stopped():
        try:
            server.handle_request()
        except socket.timeout:
            continue
        except:
            stop_nspv_server()

def start_nspv_server_thread():
    t = threading.Thread(target = run_nspv_server)
    t.daemon = True
    t.start()