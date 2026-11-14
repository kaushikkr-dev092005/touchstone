"""Single-operator server-side sessions; never grants financial dispatch authority."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit

from .ledger import PolicyError


def password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def make_config(origin, username, password, environment='DEMO'):
    if type(password) is not str or not 16 <= len(password) <= 256:
        raise ValueError('Use a unique password of 16 to 256 characters')
    salt = secrets.token_hex(16)
    result = {'origin':origin, 'username':username, 'password_salt':salt,
        'password_scrypt':password_hash(password,salt), 'environment':environment,
        'providers':[], 'session_seconds':3600, 'idle_seconds':900}
    validate_config(result)
    return result


def validate_config(config):
    expected={'origin','username','password_salt','password_scrypt','environment','providers','session_seconds','idle_seconds'}
    if type(config) is not dict or set(config)!=expected:
        raise ValueError('INVALID_OPERATOR_CONFIGURATION')
    origin=urlsplit(config['origin'])
    local=origin.hostname in {'127.0.0.1','localhost'}
    if (origin.scheme not in {'https','http'} or not origin.hostname or origin.username or origin.password
        or origin.path or origin.query or origin.fragment or (origin.scheme=='http' and not local)
        or config['origin']!=f'{origin.scheme}://{origin.netloc}'
        or config['environment'] not in {'DEMO','SANDBOX','TESTNET'}):
        raise ValueError('HTTPS_REQUIRED_OR_ENVIRONMENT_DISABLED')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',config['username']):
        raise ValueError('INVALID_OPERATOR_IDENTITY')
    if not re.fullmatch(r'[0-9a-f]{32}',config['password_salt']) or not re.fullmatch(r'[0-9a-f]{128}',config['password_scrypt']):
        raise ValueError('INVALID_PASSWORD_HASH')
    if any(type(config[k]) is not int for k in ('session_seconds','idle_seconds')) or not 60<=config['idle_seconds']<=config['session_seconds']<=3600:
        raise ValueError('INVALID_SESSION_EXPIRY')
    if type(config['providers']) is not list or len(config['providers'])>4:
        raise ValueError('INVALID_PROVIDER_ALLOWLIST')
    identities=set()
    for provider in config['providers']:
        if type(provider) is not dict or set(provider)!={'id','origin'} or provider['id'] not in {'local-gpu','hosted-premium','metal-provider'}:
            raise ValueError('INVALID_PROVIDER_ALLOWLIST')
        u=urlsplit(provider['origin'])
        if (u.scheme not in {'http','https'} or not u.hostname or u.username or u.password or u.path or u.query or u.fragment
            or (u.scheme=='http' and u.hostname not in {'localhost','127.0.0.1'}) or provider['id'] in identities):
            raise ValueError('INVALID_PROVIDER_ALLOWLIST')
        identities.add(provider['id'])
    return config


def load_config(path):
    config=validate_config(json.loads(Path(path).read_text(encoding='utf-8')))
    return config


class Sessions:
    def __init__(self, ledger, config):
        self.ledger,self.config=ledger,validate_config(config)
        # Password rotation or environment change invalidates existing sessions.
        self.epoch=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        with ledger.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS operator_sessions(
              token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, csrf TEXT NOT NULL,
              issued_at REAL NOT NULL, expires_at REAL NOT NULL, last_seen REAL NOT NULL, epoch TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operator_rates(
              rate_key TEXT NOT NULL, window INTEGER NOT NULL, count INTEGER NOT NULL,
              PRIMARY KEY(rate_key,window));
            ''')

    @property
    def cookie_name(self):
        return '__Host-touchstone' if self.config['origin'].startswith('https:') else 'touchstone-local'

    def rate(self,key,limit):
        now=int(time.time()//60)
        fingerprint=hashlib.sha256(key.encode()).hexdigest()
        with self.ledger.tx() as db:
            db.execute('DELETE FROM operator_rates WHERE window<?',(now-2,))
            db.execute('INSERT INTO operator_rates VALUES(?,?,1) ON CONFLICT(rate_key,window) DO UPDATE SET count=count+1',(fingerprint,now))
            count=db.execute('SELECT count FROM operator_rates WHERE rate_key=? AND window=?',(fingerprint,now)).fetchone()[0]
        if count>limit:
            raise PolicyError('RATE_LIMITED')

    def login(self,username,password):
        if type(username) is not str or type(password) is not str or len(password)>256:
            raise PolicyError('INVALID_CREDENTIALS')
        valid=hmac.compare_digest(password_hash(password,self.config['password_salt']),self.config['password_scrypt'])
        if not (valid and hmac.compare_digest(username,self.config['username'])):
            self.ledger.event('OPERATOR_LOGIN_REJECTED',{'credentials_disclosed':False})
            raise PolicyError('INVALID_CREDENTIALS')
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        now=time.time()
        with self.ledger.tx() as db:
            db.execute('DELETE FROM operator_sessions WHERE expires_at<=?',(now,))
            db.execute('INSERT INTO operator_sessions VALUES(?,?,?,?,?,?,?)',
                (hashlib.sha256(token.encode()).hexdigest(),username,csrf,now,now+self.config['session_seconds'],now,self.epoch))
            self.ledger._event(db,'OPERATOR_LOGIN',{'owner':username})
        return token,csrf

    def inspect(self,token,*,touch=True):
        if type(token) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
            raise PolicyError('AUTHENTICATION_REQUIRED')
        fingerprint=hashlib.sha256(token.encode()).hexdigest()
        now=time.time()
        with self.ledger.tx() as db:
            row=db.execute('SELECT * FROM operator_sessions WHERE token_hash=?',(fingerprint,)).fetchone()
            if not row or row['expires_at']<=now or row['last_seen']+self.config['idle_seconds']<=now or row['epoch']!=self.epoch:
                db.execute('DELETE FROM operator_sessions WHERE token_hash=?',(fingerprint,))
                raise PolicyError('AUTHENTICATION_REQUIRED')
            if touch:
                db.execute('UPDATE operator_sessions SET last_seen=? WHERE token_hash=?',(now,fingerprint))
        return dict(row)

    def logout(self,token):
        with self.ledger.tx() as db:
            db.execute('DELETE FROM operator_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
            self.ledger._event(db,'OPERATOR_LOGOUT',{'session_revoked':True})
