"""Authenticated operational HTTP service, separate from the private payer console.

Run behind the supplied TLS reverse proxy. Only deterministic jobs and unsigned
read-only quotes are exposed. No route can forward arbitrary private-console calls.
"""
import hashlib
import json
import mimetypes
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import socket
import threading
import time
from urllib.parse import urlsplit, unquote

from .ledger import PolicyError, canonical
from .operations import Operations
from .operator_auth import Sessions, load_config
from .procurement_approval import strict_json

ROOT=Path(__file__).resolve().parent.parent
CSP="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads=True

    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(32)
        super().__init__(*args,**kwargs)

    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()


def make_server(config_path, data_dir, *, bind='127.0.0.1',port=8089):
    config=load_config(config_path)
    ops=Operations(Path(data_dir)/'ledger.sqlite')
    sessions=Sessions(ops.ledger,config)
    streams=threading.BoundedSemaphore(8)
    allowed_host=urlsplit(config['origin']).netloc

    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self,*args):
            # Passwords, session cookies, CSRF, source text and URLs are never logged.
            pass

        def send(self,status,value,mime='application/json',cookie=None):
            body=(canonical(value).encode() if mime=='application/json' else value)
            self.send_response(status)
            for name,value in {'Content-Type':mime,'Content-Length':str(len(body)),
                'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                'Content-Security-Policy':(CSP.replace("frame-ancestors 'none'", "frame-ancestors 'self'")
                    if urlsplit(self.path).path == '/site/dashboard/index.html' else CSP),'Referrer-Policy':'no-referrer',
                'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
                'Connection':'close'}.items():self.send_header(name,value)
            if cookie:self.send_header('Set-Cookie',cookie)
            self.end_headers();self.wfile.write(body)
            self.close_connection=True

        def cookie(self,token,*,delete=False):
            secure='; Secure' if config['origin'].startswith('https:') else ''
            return f'{sessions.cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if delete else config["session_seconds"]}'+secure

        def boundary(self,mutating=False):
            if self.headers.get_all('Host')!=[allowed_host]:
                raise PolicyError('HOST_REJECTED')
            origin=self.headers.get('Origin')
            if (origin is not None and origin!=config['origin']) or (mutating and origin!=config['origin']):
                raise PolicyError('ORIGIN_REJECTED')
            if self.headers.get('Sec-Fetch-Site') in {'cross-site'}:
                raise PolicyError('ORIGIN_REJECTED')

        def identity(self,*,mutating=False):
            cookie=SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except Exception:raise PolicyError('AUTHENTICATION_REQUIRED') from None
            token=cookie[sessions.cookie_name].value if sessions.cookie_name in cookie else ''
            identity=sessions.inspect(token)
            if mutating:
                import hmac
                if not hmac.compare_digest(self.headers.get('X-Touchstone-CSRF',''),identity['csrf']):
                    raise PolicyError('CSRF_REJECTED')
            return token,identity

        def body(self):
            if self.headers.get('Transfer-Encoding') or self.headers.get_all('Content-Length') is None or len(self.headers.get_all('Content-Length'))!=1:
                raise ValueError('CONTENT_LENGTH_REQUIRED')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                raise ValueError('JSON_REQUIRED')
            length=int(self.headers['Content-Length'])
            if not 0<length<=32768:raise ValueError('REQUEST_TOO_LARGE')
            payload=self.rfile.read(length)
            if len(payload)!=length:raise ValueError('INCOMPLETE_BODY')
            value=strict_json(payload.decode('utf-8'))
            if type(value) is not dict:raise ValueError('JSON_OBJECT_REQUIRED')
            return value

        def error(self,error):
            known={'AUTHENTICATION_REQUIRED':401,'INVALID_CREDENTIALS':401,'RATE_LIMITED':429,
                   'HOST_REJECTED':403,'ORIGIN_REJECTED':403,'CSRF_REJECTED':403,
                   'JOB_NOT_FOUND':404,'IDEMPOTENCY_CONFLICT':409,'JOB_PAUSED':409}
            code=str(error.args[0]) if error.args else 'REQUEST_REJECTED'
            if not re.fullmatch(r'[A-Z0-9_]{1,100}',code):code='REQUEST_REJECTED'
            self.send(known.get(code,400),{'error':code})

        def do_GET(self):
            try:
                self.boundary()
                path=urlsplit(self.path).path
                if path=='/healthz':
                    return self.send(200,{'status':'ok','environment':config['environment'],
                        'service':'touchstone-operator','financial_dispatch_enabled':False,
                        'revision':revision()})
                if path.startswith('/operator-api/'):
                    token,identity=self.identity()
                    if path=='/operator-api/session':
                        return self.send(200,{'username':identity['username'],'csrf':identity['csrf'],
                            'expires_at':identity['expires_at'],'environment':config['environment'],
                            'financial_dispatch_enabled':False,'revision':revision()})
                    if path=='/operator-api/jobs':
                        return self.send(200,{'jobs':ops.jobs(identity['username']),'audit':ops.ledger.audit()})
                    if path=='/operator-api/transactions':
                        return self.send(200,{'transactions':ops.jobs(identity['username']),
                            'currencies':{'USD':0,'USDZ':0,'prepaid_credit_USD':0,'native_fees':'NONE'},
                            'mode':'OPERATIONAL_ZERO_CHARGE'})
                    if path=='/operator-api/integrations':
                        # A private operator performs checks separately. No financial
                        # credential or payer filesystem is mounted in this service.
                        try:
                            from datetime import datetime, timezone
                            file=Path(data_dir)/'readonly-integrations.json'
                            if file.stat().st_size>32768:raise ValueError('SNAPSHOT_TOO_LARGE')
                            raw=json.loads(file.read_text(encoding='utf-8'))
                            observed=datetime.fromisoformat(raw['observed_at'])
                            age=(datetime.now(timezone.utc)-observed).total_seconds()
                            if not 0<=age<=300 or raw.get('scope')!='READ_ONLY_INTEGRATION_CHECK':raise ValueError('STALE_SNAPSHOT')
                            fields={
                                'airwallex':('mode','authenticated','balance_read','global_accounts_read','checkout_sessions_read','fx_conversions_read','writes_performed'),
                                'issuing':('issuing_read','issuing_write_verified'),
                                'merchant':('configuration_read','new_payment_verified'),
                                'historical_capture':('account_matches','status','amount','currency','captured_amount','current_active_hold'),
                                'metal_rpc':('connected','chain_id','block_number','transactions_sent'),
                                'visa':('status','approval_verified'),
                                'airwallex_error':('http_status','code','status')}
                            safe={'observed_at':raw['observed_at']}
                            for group,allowed in fields.items():
                                value=raw.get(group,{})
                                if isinstance(value,dict):
                                    safe[group]={k:value[k] for k in allowed if k in value and type(value[k]) in (bool,int,float,str,type(None))}
                            return self.send(200,{'status':'CURRENT_READ_ONLY_SNAPSHOT','age_seconds':int(age),'checks':safe,'financial_authority_granted':False})
                        except (OSError,ValueError,TypeError,KeyError):
                            return self.send(200,{'status':'BLOCKED_FRESH_PRIVATE_READ_CHECK_REQUIRED',
                                'financial_authority_granted':False})
                    if path=='/operator-api/events':
                        return self.events(token,identity['username'])
                    return self.send(404,{'error':'NOT_FOUND'})
                # Serve only the public build, never /console, Python source, data, or payer assets.
                if path in {'/control-room','/control-room/','/','/site/','/dashboard','/ledger'}:
                    target=ROOT/'apps/web/dist/index.html'
                elif path.startswith('/site/'):
                    relative=unquote(path[len('/site/'):])
                    target=(ROOT/'apps/web/dist'/relative).resolve()
                    if not target.is_relative_to((ROOT/'apps/web/dist').resolve()):
                        return self.send(404,{'error':'NOT_FOUND'})
                elif path=='/api/site-context':
                    return self.send(200,{'operator_console':False,'operational_workspace':'/control-room'})
                else:return self.send(404,{'error':'NOT_FOUND'})
                if not target.is_file():return self.send(503,{'error':'FRONTEND_BUILD_REQUIRED'})
                mime=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                if target.suffix=='.js':mime='application/javascript'
                return self.send(200,target.read_bytes(),mime)
            except (ValueError,KeyError,PolicyError,TypeError) as error:self.error(error)
            except (ConnectionError,socket.timeout):pass
            except Exception:self.send(500,{'error':'INTERNAL_ERROR'})

        def do_POST(self):
            try:
                self.boundary(mutating=True)
                path=urlsplit(self.path).path
                if path=='/operator-api/login':
                    sessions.rate('login:'+self.client_address[0],5)
                    body=self.body()
                    if set(body)!={'username','password'}:raise ValueError('INVALID_LOGIN_SCHEMA')
                    token,csrf=sessions.login(body['username'],body['password'])
                    return self.send(200,{'csrf':csrf},cookie=self.cookie(token))
                token,identity=self.identity(mutating=True)
                sessions.rate('mutation:'+identity['username'],60)
                body=self.body()
                if path=='/operator-api/logout':
                    if body:raise ValueError('UNEXPECTED_FIELDS')
                    sessions.logout(token)
                    return self.send(200,{'logged_out':True},cookie=self.cookie('',delete=True))
                if path=='/operator-api/jobs':
                    return self.send(201,ops.create(identity['username'],self.headers.get('Idempotency-Key'),body))
                match=re.fullmatch(r'/operator-api/jobs/(op_[0-9a-f]{32})/(start|pause|resume|quotes)',path)
                if match:
                    if body:raise ValueError('UNEXPECTED_FIELDS')
                    job,action=match.groups()
                    if action=='quotes':
                        return self.send(200,ops.quotes(identity['username'],job,config['providers']))
                    return self.send(200,ops.action(identity['username'],job,action))
                return self.send(404,{'error':'NOT_FOUND'})
            except (ValueError,KeyError,PolicyError,TypeError) as error:self.error(error)
            except (ConnectionError,socket.timeout):pass
            except Exception:self.send(500,{'error':'INTERNAL_ERROR'})

        def events(self,token,owner):
            after=self.headers.get('Last-Event-ID','0')
            if not re.fullmatch(r'[0-9]{1,15}',after):raise ValueError('INVALID_EVENT_CURSOR')
            if not streams.acquire(blocking=False):raise PolicyError('RATE_LIMITED')
            try:
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Accel-Buffering','no')
                self.send_header('Connection','close')
                self.end_headers()
                cursor=int(after)
                deadline=time.monotonic()+25
                while time.monotonic()<deadline:
                    sessions.inspect(token,touch=False)
                    for event in ops.ledger.events(cursor,100):
                        cursor=event['id']
                        if event['payload'].get('owner')!=owner:continue
                        self.wfile.write(f'id: {cursor}\nevent: operation\ndata: {canonical(event)}\n\n'.encode())
                    self.wfile.write(b': keepalive\n\n');self.wfile.flush();time.sleep(.5)
            except (ConnectionError,socket.timeout,PolicyError):pass
            finally:
                streams.release();self.close_connection=True

    server=BoundedHTTPServer((bind,port),Handler)
    server.operations,server.sessions=ops,sessions
    return server


def revision():
    # Docker writes the source revision at build time; never execute git on a request.
    import os
    value=os.environ.get('TOUCHSTONE_SOURCE_REVISION','working-tree')
    return value if re.fullmatch(r'[A-Za-z0-9._-]{1,80}',value) else 'unknown'
