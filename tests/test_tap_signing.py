import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from touchstone.config import ROOT
from touchstone.merchant import MerchantError, node_signer
from touchstone.metal import node_executable

GENERATE = ("import {generateKeyPairSync} from 'node:crypto';"
            "const k=generateKeyPairSync('ed25519');"
            "console.log(JSON.stringify({priv:k.privateKey.export({type:'pkcs8',format:'pem'}),pub:k.publicKey.export({type:'spki',format:'pem'})}));")
VERIFY = ("import {DatabaseSync} from 'node:sqlite';import {TapMerchant} from './integrations/metal/tap.mjs';"
          "const i=JSON.parse(process.argv[1]);const now=Math.floor(Date.now()/1000);"
          "const m=new TapMerchant(new DatabaseSync(':memory:'),new Map([[i.kid,{public_key:i.pub,expires_at:now+600,trust_source:'CONTROLLED_LOCAL_KEY'}]]));"
          "try{const r=m.verify({authority:i.authority,path:i.path,method:'POST',headers:i.headers,body:i.body},now);"
          "console.log(JSON.stringify({ok:true,visa:r.visa_approved_agent}));}catch(e){console.log(JSON.stringify({ok:false}));}")


def node(script, *args, **kwargs):
    return subprocess.run([node_executable(), '--input-type=module', '-e', script, *args], capture_output=True, text=True,
                          cwd=ROOT, timeout=30, **kwargs)


class TapSigningTests(unittest.TestCase):
    def test_python_signer_round_trips_through_the_node_merchant_verifier(self):
        keys = json.loads(node(GENERATE).stdout)
        with tempfile.TemporaryDirectory() as temp:
            key_file = Path(temp) / 'agent.pem'
            key_file.write_text(keys['priv'])
            body = json.dumps({'job_id': 'job', 'intent': 'purchase', 'currency': 'USD', 'amount_minor': 1}, separators=(',', ':'))
            headers = node_signer('127.0.0.1:9000', '/tap/intent', body, 'agent', key_file)
            check = {'kid': 'agent', 'pub': keys['pub'], 'authority': '127.0.0.1:9000', 'path': '/tap/intent', 'headers': headers, 'body': body}
            self.assertEqual(json.loads(node(VERIFY, json.dumps(check)).stdout), {'ok': True, 'visa': False})
            check['body'] = body.replace('"amount_minor":1', '"amount_minor":2')
            self.assertFalse(json.loads(node(VERIFY, json.dumps(check)).stdout)['ok'])
            with self.assertRaises(MerchantError):
                node_signer('127.0.0.1:9000', '/tap/intent', body, 'agent', Path(temp) / 'missing.pem')


if __name__ == '__main__':
    unittest.main()
