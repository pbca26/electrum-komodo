from lib import transaction, bitcoin, util
from lib.util import bfh, bh2u
from lib.transaction import Transaction

kmd_unsigned_tx_serialized = 'put unsigned kmd raw tx here'
wif = 'put your wif key here'

txin_type, privkey, compressed = bitcoin.deserialize_privkey(wif)
pubkey = bitcoin.public_key_from_private_key(privkey, compressed)

jsontx = transaction.deserialize(kmd_unsigned_tx_serialized)
inputs = jsontx.get('inputs')
outputs = jsontx.get('outputs')
locktime = jsontx.get('lockTime', 0)
outputs_formatted = []

for txout in outputs:
  outputs_formatted.append([txout['type'], txout['address'], txout['value']])

for txin in inputs:
  txin['type'] = txin_type
  txin['x_pubkeys'] = [pubkey]
  txin['pubkeys'] = [pubkey]
  txin['signatures'] = [None]
  txin['num_sig'] = 1
  txin['address'] = bitcoin.address_from_private_key(wif)
  txin['value'] = 100000000 # required for preimage calc

tx = Transaction.from_io(inputs, outputs_formatted, locktime=locktime)
tx.sign({pubkey:(privkey, compressed)})

print(tx.serialize())