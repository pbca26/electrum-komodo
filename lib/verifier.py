# Electrum - Lightweight Bitcoin Client
# Copyright (c) 2012 Thomas Voegtlin
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
from .util import ThreadJob
from .bitcoin import *
from .blockchain import CHUNK_LEN, deserialize_header

class SPV(ThreadJob):
    """ Simple Payment Verification """

    def __init__(self, network, wallet):
        self.wallet = wallet
        self.network = network
        self.blockchain = network.blockchain()
        # Keyed by tx hash.  Value is None if the merkle branch was
        # requested, and the merkle root once it has been verified
        self.merkle_roots = {}
        self.headers = {}

    def run(self):
        # temp skip verifier in NSPV mode
        if self.network.config.get('nspv') == True:
            return
        else:
            interface = self.network.interface
            if not interface:
                return
            blockchain = interface.blockchain
            if not blockchain:
                return
            lh = self.network.get_local_height()
            if lh > 0 and interface.tip > 0:
                self.wallet.syncronizedPerc = (lh * 100) / interface.tip
            unverified = self.wallet.get_unverified_txs()
            for tx_hash, tx_height in unverified.items():
                if self.network.config.get('fast_verify'):
                    # NSPV TODO: verify merkle
                    if self.network.config.get('nspv') == True:
                        print('request header')
                        request = ('blockchain.block.header', [tx_hash])
                        self.network.send([request], self.NSPV_parse_header)
                        self.print_error('requested header for TXID', tx_height)
                        self.headers[tx_hash] = None
                    else:
                        if tx_height > 0:
                            if tx_height not in self.headers:
                                print('request header')
                                request = ('blockchain.block.header', [tx_height])
                                self.network.send([request], self.parse_header)
                                self.print_error('requested header', tx_height)
                                self.headers[tx_height] = None

                            if tx_hash not in self.merkle_roots and tx_height in self.headers and self.headers[tx_height] is not None:
                                request = ('blockchain.transaction.get_merkle',
                                            [tx_hash, tx_height])
                                self.network.send([request], self.verify_merkle)
                                self.print_error('requested merkle', tx_hash)
                                self.merkle_roots[tx_hash] = None
                else:
                    if (tx_height > 0) and (tx_height <= lh):
                        header = blockchain.read_header(tx_height)
                        if header is None:
                            index = tx_height // CHUNK_LEN
                            if index < len(blockchain.checkpoints):
                                self.network.request_chunk(interface, index)
                        else:
                            if tx_hash not in self.merkle_roots:
                                request = ('blockchain.transaction.get_merkle',
                                            [tx_hash, tx_height])
                                self.network.send([request], self.verify_merkle)
                                self.print_error('requested merkle', tx_hash)
                                self.merkle_roots[tx_hash] = None

            if self.network.config.get('fast_verify') == False:
                if self.network.blockchain() != self.blockchain:
                    self.blockchain = self.network.blockchain()
                    self.undo_verifications()
 
    def parse_header(self, header):
        self.headers[header['params'][0]] = deserialize_header(bfh(header['result']), header['params'][0])

    def NSPV_parse_header(self, header, tx_height, tx_hash):
        self.headers[header['params'][0]] = deserialize_header(bfh(header['result']), header['params'][0])
        #self.print_error("verified %s" % tx_hash)
        #self.wallet.add_verified_tx(tx_hash, (tx_height, header.get('timestamp'), pos))

    def verify_merkle(self, r):
        if self.wallet.verifier is None:
            return  # we have been killed, this was just an orphan callback
        if r.get('error'):
            self.print_error('received an error:', r)
            return
        params = r['params']
        merkle = r['result']
        # Verify the hash of the server-provided merkle branch to a
        # transaction matches the merkle root of its block
        tx_hash = params[0]
        tx_height = merkle.get('block_height')
        pos = merkle.get('pos')
        merkle_root = self.hash_merkle_root(merkle['merkle'], tx_hash, pos)
        header = None
    
        if self.network.config.get('fast_verify') == False:
            header = self.network.blockchain().read_header(tx_height)
        elif tx_height in self.headers and self.headers[tx_height] is not None:
            header = self.headers[tx_height]
        # FIXME: if verification fails below,
        # we should make a fresh connection to a server to
        # recover from this, as this TX will now never verify
        if not header:
            self.print_error(
                "merkle verification failed for {} (missing header {})"
                .format(tx_hash, tx_height))
            return
        if header.get('merkle_root') != merkle_root:
            self.print_error(
                "merkle verification failed for {} (merkle root mismatch {} != {})"
                .format(tx_hash, header, merkle_root))
            return
        # we passed all the tests
        self.merkle_roots[tx_hash] = merkle_root
        self.print_error("verified %s" % tx_hash)
        #self.wallet.add_verified_tx(tx_hash, (tx_height, header.get('timestamp'), pos))

    @classmethod
    def hash_merkle_root(cls, merkle_s, target_hash, pos):
        h = hash_decode(target_hash)
        for i in range(len(merkle_s)):
            item = merkle_s[i]
            h = Hash(hash_decode(item) + h) if ((pos >> i) & 1) else Hash(h + hash_decode(item))
        return hash_encode(h)

    def undo_verifications(self):
        height = self.blockchain.get_checkpoint()
        tx_hashes = self.wallet.undo_verifications(self.blockchain, height)
        for tx_hash in tx_hashes:
            self.print_error("redoing", tx_hash)
            self.merkle_roots.pop(tx_hash, None)
