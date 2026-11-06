"""Merchant payment adapters for the card rail. An adapter acknowledges a purchase; it never moves
funds by itself and never receives a card number (PAN/CVC) from this code."""
import json
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .config import ROOT
from .metal import node_executable


class MerchantError(RuntimeError):
    pass


class MerchantAdapter:
    name = 'abstract'

    def charge(self, *, job_id, card_id, amount_micro, currency):
        raise NotImplementedError

    def confirm(self, receipt):
        """Independent settlement evidence, or None when the adapter cannot provide any."""
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def node_signer(authority, path, body, key_id, key_file, tag='agent-payer-auth'):
    request = {'authority': authority, 'path': path, 'body': body, 'key_id': key_id, 'private_key_file': str(key_file), 'tag': tag}
    try:
        process = subprocess.run([node_executable(), str(ROOT / 'integrations/metal/tap-sign-cli.mjs')], input=json.dumps(request),
                                 capture_output=True, text=True, cwd=ROOT, timeout=20)
        parsed = json.loads(process.stdout)
        if process.returncode or not parsed.get('ok'):
            raise ValueError
        return parsed['result']['headers']
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise MerchantError('Could not sign the intent with the existing local key') from None


class SignedIntentMerchant(MerchantAdapter):
    """Posts one RFC 9421 Ed25519 signed intent to a merchant /tap/intent endpoint.

    This is the agent-recognition profile the project already verifies locally. It is not Visa
    onboarding: no Visa key trust, payment container or acquirer settlement is implied, so the
    receipt always reports settlement_verified=False unless `settlement_reader` supplies evidence.
    """
    name = 'signed-intent-merchant'

    def __init__(self, origin, key_id, key_file, *, signer=node_signer, opener=None, settlement_reader=None, timeout=15):
        parsed = urlparse(origin)
        loopback = parsed.hostname in {'127.0.0.1', 'localhost', '::1'}
        if parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or not parsed.hostname or \
                (parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback)):
            raise ValueError('Merchant origin must be HTTPS (or loopback HTTP) without credentials, path or query')
        self.origin, self.authority = f'{parsed.scheme}://{parsed.netloc}', parsed.netloc
        self.key_id, self.key_file, self.signer, self.timeout = key_id, key_file, signer, timeout
        self.opener = opener or urllib.request.build_opener(_NoRedirect()).open
        self.settlement_reader = settlement_reader

    def charge(self, *, job_id, card_id, amount_micro, currency):
        if amount_micro % 10000:
            raise ValueError('Merchant intents use whole minor units')
        intent = {'job_id': job_id, 'intent': 'purchase', 'currency': currency, 'amount_minor': amount_micro // 10000}
        body = json.dumps(intent, separators=(',', ':'))
        headers = self.signer(self.authority, '/tap/intent', body, self.key_id, self.key_file)
        request = urllib.request.Request(self.origin + '/tap/intent', body.encode(), {'Content-Type': 'application/json', **headers}, method='POST')
        try:
            with self.opener(request, timeout=self.timeout) as response:
                result = json.loads(response.read(20001))
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise MerchantError('Merchant response unavailable or refused') from error
        if (result.get('signature_verified') is not True or result.get('intent_verified') is not True
                or result.get('replay_protected') is not True or result.get('intent') != intent):
            raise MerchantError('Merchant acknowledgement does not match the signed intent')
        return {'adapter': self.name, 'merchant': self.authority, 'intent': intent, 'card_id': card_id,
                'merchant_acknowledged': True, 'identity_trust': result.get('identity_trust'),
                'merchant_payments_sent': result.get('payments_sent')}

    def confirm(self, receipt):
        return self.settlement_reader(receipt) if self.settlement_reader else None
