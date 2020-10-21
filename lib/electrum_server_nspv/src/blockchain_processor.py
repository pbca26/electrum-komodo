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

import hashlib
from json import dumps, load
import os
from queue import Queue
import random
import sys
import time
import threading
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import json
from decimal import Decimal
import string

from .processor import Processor, print_log
from .utils import logger, ProfiledThread

def randomString(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

class BlockchainProcessor(Processor):

    def __init__(self, config, shared):
        Processor.__init__(self)

        # monitoring
        self.avg_time = 0,0,0
        self.time_ref = time.time()

        self.shared = shared
        self.config = config

        self.watch_lock = threading.Lock()
        self.watch_blocks = []
        self.watch_headers = []
        self.watched_addresses = {}
        self.mempool_txs = {}
        self.mempool_lock = threading.Lock()
        self.tip = 0

        self.address_queue = Queue()

        self.blockchain_thread = threading.Thread(target = self.do_catch_up)
        self.blockchain_thread.start()

    def test(self):
        self.start_catchup_height = 10
        self.up_to_date = True
        print_log("self_shared_stop")
        print_log(self.shared.stopped())

    def do_catch_up(self):
        while not self.shared.stopped():
            self.main_iteration()
            if self.shared.paused():
                print_log("bitcoind is responding")
                self.shared.unpause()
            time.sleep(10)

    def add_request(self, session, request):
        # see if we can get if from cache. if not, add request to queue
        message_id = request.get('id')
        try:
            result = self.process(request, cache_only=True)
        except BaseException as e:
            self.push_response(session, {'id': message_id, 'error': str(e)})
            return 

        if result == -1:
            self.queue.put((session, request))
        else:
            self.push_response(session, {'id': message_id, 'result': result})


    def do_subscribe(self, method, params, session):
        with self.watch_lock:
            if method == 'blockchain.numblocks.subscribe':
                if session not in self.watch_blocks:
                    self.watch_blocks.append(session)

            elif method == 'blockchain.headers.subscribe':
                if session not in self.watch_headers:
                    self.watch_headers.append(session)

            elif method == 'blockchain.address.subscribe':
                address = params[0]
                l = self.watched_addresses.get(address)
                if l is None:
                    self.watched_addresses[address] = [session]
                elif session not in l:
                    l.append(session)

            elif method == 'blockchain.scripthash.subscribe':
                print_log('subscribe')
                address = params[0]
                l = self.watched_addresses.get(address)
                if l is None:
                    self.watched_addresses[address] = [session]
                elif session not in l:
                    l.append(session)


    def do_unsubscribe(self, method, params, session):
        with self.watch_lock:
            if method == 'blockchain.numblocks.subscribe':
                if session in self.watch_blocks:
                    self.watch_blocks.remove(session)
            elif method == 'blockchain.headers.subscribe':
                if session in self.watch_headers:
                    self.watch_headers.remove(session)
            elif method == "blockchain.address.subscribe":
                addr = params[0]
                l = self.watched_addresses.get(addr)
                if not l:
                    return
                if session in l:
                    l.remove(session)
                if session in l:
                    print_log("error rc!!")
                    self.shared.stop()
                if l == []:
                    del self.watched_addresses[addr]


    def nspv_request(self, method, params):
        # python 2
        #body = {"jsonrpc": "2.0", "method": method, "params": params}  
        #req = urllib.request.Request('http://127.0.0.1:7771')
        #req.add_header('Content-Type', 'application/json')
        #response = urllib.request.urlopen(req, json.dumps(body))
        #data = json.loads(response.read())
        #print_log('[NSPV daemon request]', body)
        #print_log('[NSPV daemon response]', data)
        #return data

        # python 3
        body = {"jsonrpc": "2.0", "method": method, "params": params}  
        myurl = 'http://127.0.0.1:7771'
        req = urllib.request.Request(myurl)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        jsondata = json.dumps(body)
        jsondataasbytes = jsondata.encode('utf-8')   # needs to be bytes
        req.add_header('Content-Length', len(jsondataasbytes))
        print_log(jsondataasbytes)
        response = urllib.request.urlopen(req, jsondataasbytes)
        data = json.loads(response.read())
        print_log('[NSPV daemon request]', body)
        print_log('[NSPV daemon response]', data)
        return data

    def pushtx_insight_kmd(self, rawtx):
        # python 2
        #try:
        #    body = {"rawtx": rawtx}  
        #    req = urllib.request.Request('https://www.kmdexplorer.io/insight-api-komodo/tx/send')
        #    req.add_header('Content-Type', 'application/json')
        #    response = urllib.request.urlopen(req, json.dumps(body))
        #    data = json.loads(response.read())
        #    print_log('[KMD Insight push tx request]', body)
        #    print_log('[KMD Insight push tx response]', data)
        #    return data
        #except:
        #    return {}
        
        # python 3
        try:
            body = {"rawtx": rawtx} 
            myurl = 'https://www.kmdexplorer.io/insight-api-komodo/tx/send'
            req = urllib.request.Request(myurl)
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            jsondata = json.dumps(body)
            jsondataasbytes = jsondata.encode('utf-8')   # needs to be bytes
            req.add_header('Content-Length', len(jsondataasbytes))
            print_log(jsondataasbytes)
            response = urllib.request.urlopen(req, jsondataasbytes)
            data = json.loads(response.read())
            print_log('[KMD Insight push tx request]', body)
            print_log('[KMD Insight push tx response]', data)
            return data
        except:
            return {}

    def satoshi(self, value):
        return int(float("{0:.8f}".format(value)) * 100000000)

    def nspv_normalize_listtransactions(self, data):
        result = []
        txids = []

        for tx in data['txids']:
            if tx['txid'] not in txids:
                result.append({
                    "tx_hash": tx['txid'],
                    "height": tx['height']
                })
                txids.append(tx['txid'])
            if tx['txid'] in self.mempool_txs:
                print_log('tx is already in history, remove ' + tx['txid'])
                del self.mempool_txs[tx['txid']]

        for tx in self.mempool_txs:
            if tx not in txids   :
                print_log('tx is not in history, append ' + tx)
                result.append({
                    "tx_hash": tx,
                    "height": 0
                })
                txids.append(tx[0])
        return result

    def nspv_normalize_listunspent(self, data):
        result = []

        for utxo in data['utxos']:
            result.append({
                "tx_hash": utxo['txid'],
                "height": utxo['height'],
                "tx_pos": utxo['vout'],
                "value": self.satoshi(utxo['value'])
            })

        return result

    def set_tip(self, height):
        if height > self.tip:
            self.tip = height
            print_log('new tip', self.tip)

    def sync_chaintip(self):
        nspv_res = self.nspv_request('getinfo', [])
        if nspv_res['result'] == 'error':
            print_log('unable to update chaintip')
        else:
            self.set_tip(nspv_res['height'])
            # send notification
        time.sleep(5)

    # TODO: check mempool, compare diff with tx_history, if new tx found set height to 0 and append to tx_history 
    def process(self, request, cache_only=False):
        
        message_id = request['id']
        method = request['method']
        params = request.get('params', ())
        result = None
        error = None

        # {"jsonrpc": "2.0", "error": {"code": 1, "message": "RGJ1zdFS1G2eSJGJDE1UPEHrHg9jhRMLJL is not a valid script hash"}, "id": 1}

        if method == 'blockchain.scripthash.subscribe':
            # stub method
            result = '2cd76590e904e447289967fb84b132be2b9f90b4ca8b39cb077f9b4a0ca624de'

        elif method == 'blockchain.numblocks.subscribe':
            # TODO notifier
            if self.tip == 0:
                nspv_res = self.nspv_request('getinfo', [])
                if nspv_res['result'] == 'error':
                    raise BaseException(nspv_res['error'])
                else:
                    self.set_tip(nspv_res['height'])
                    result = nspv_res['height']
            else:
                result = self.tip

        elif method == 'blockchain.scripthash.get_history':
            address = str(params[0])
            nspv_res = self.nspv_request('listtransactions', [address])
            if nspv_res['result'] == 'error':
                raise BaseException(nspv_res['error'])
            else:
                result = self.nspv_normalize_listtransactions(nspv_res)

        elif method == 'blockchain.scripthash.listunspent':
            address = str(params[0])
            nspv_res = self.nspv_request('listunspent', [address])
            if nspv_res['result'] == 'error':
                raise BaseException(nspv_res['error'])
            else:
                result = self.nspv_normalize_listunspent(nspv_res)

        elif method == 'blockchain.transaction.get':
            tx_hash = params[0]
            nspv_res = self.nspv_request('gettransaction', [tx_hash])
            if nspv_res['retcode'] == -2006:
                result = nspv_res['hex']
            else:
                raise BaseException('unable to get transaction hex')

        elif method == 'blockchain.headers.subscribe':
            nspv_res = self.nspv_request('getinfo', [])
            if nspv_res['result'] == 'error':
                raise BaseException(nspv_res['error'])
            else:
                result = {"hex": "", "height": nspv_res['height']}

        elif method == 'blockchain.transaction.broadcast':
            rawtx = params[0]
            # temp workaround until NSPV broadcast method is fixed
            pushtx_insight_kmd_res = self.pushtx_insight_kmd(rawtx)
            print_log(pushtx_insight_kmd_res)
            if 'txid' not in pushtx_insight_kmd_res:
                raise BaseException('unable to broadcast transaction')
            else:
                if pushtx_insight_kmd_res['txid'] not in self.mempool_txs:
                    self.mempool_txs[pushtx_insight_kmd_res['txid']] = True
                    print_log('added tx to mempool' + pushtx_insight_kmd_res['txid'])
                    print_log('current mempool', self.mempool_txs)
                    self.address_notifier()
                result = pushtx_insight_kmd_res['txid']

            #nspv_res = self.nspv_request('broadcast', [rawtx])
            #if nspv_res['expected'] == nspv_res['broadcast']:
            #    result = nspv_res['expected']
            #else:
            #    raise BaseException(nspv_res['type'])

        else:
            raise BaseException("unknown method:%s" % method)

        return result
    
    def close(self):
        self.blockchain_thread.join()


    def address_notifier(self):
        # time based history update
        if self.watched_addresses is not None:
            for addr in self.watched_addresses:
                print_log('watched address', addr)
                print_log('session', self.watched_addresses[addr])

                print('[NSPV server] total watched addresses', len(self.watched_addresses))
                for session in self.watched_addresses[addr]:
                    self.push_response(session, {
                        'id': None,
                        'method': 'blockchain.scripthash.subscribe',
                        'params': (addr, randomString(64)),
                    })
                    if (len(self.watched_addresses) > 1):
                        time.sleep(3)
        if len(self.watched_addresses) > 1:
            time.sleep(60)
        else:
            time.sleep(10)

    def main_iteration(self):
        if self.shared.stopped():
            print_log("Stopping timer")
            return

        while True:
            self.address_notifier()
            #self.sync_chaintip()
            
            try:
                addr, sessions = self.address_queue.get(False)
            except:
                break

            status = self.get_status(addr)
            for session in sessions:
                self.push_response(session, {
                        'id': None,
                        'method': 'blockchain.address.subscribe',
                        'params': (addr, status),
                        })
