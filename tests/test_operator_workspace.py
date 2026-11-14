import concurrent.futures
import http.client
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from touchstone.ledger import PolicyError
from touchstone.operations import Operations
from touchstone.operator_auth import Sessions, make_config, validate_config
from touchstone.operator_server import make_server


def proposal(**changes):
    return {'kind':'arithmetic','source':{'amounts_cents':[1250,900],'discount_cents':150},
        'policy':'tools-only','budget_micro_usdz':0,'max_call_micro_usdz':0,**changes}


class OperationalJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'ledger.sqlite'
        self.ops=Operations(self.path)

    def create(self,**changes):
        return self.ops.create('operator','request-one',proposal(**changes))

    def test_real_tool_verifier_zero_cost_and_persistence(self):
        job=self.create()
        with patch('touchstone.metal.MetalRail.pay',side_effect=AssertionError('Financial call forbidden')):
            result=self.ops.action('operator',job['id'],'start')
        self.assertEqual(result['state'],'COMPLETED')
        self.assertEqual(result['output'],{'total_cents':2000})
        self.assertTrue(result['verdict']['passed'])
        self.assertEqual(result['charged_micro_usdz'],0)
        reopened=Operations(self.path)
        self.assertEqual(reopened.get('operator',job['id']),result)
        self.assertTrue(reopened.ledger.audit()['valid'])
        self.assertEqual([e['kind'] for e in reopened.ledger.events()],
            ['JOB_CREATED','PLANNING_STARTED','LOCAL_TOOL_SELECTED','VERIFICATION_PASSED','JOB_COMPLETED'])

    def test_unsupported_sources_block_without_fabricated_result(self):
        job=self.create(source={'amounts_cents':[True],'discount_cents':0})
        result=self.ops.action('operator',job['id'],'start')
        self.assertEqual(result['state'],'BLOCKED')
        self.assertIsNone(result['output'])

    def test_signed_or_approved_boolean_cannot_grant_remote_spend(self):
        for field in ('approved','signature','provider_url','owner','api_credit_micro_usd'):
            with self.assertRaises(ValueError):self.create(**{field:True})
        job=self.create(policy='real-touchstone',source={'text':'ambiguous invoice'},kind='invoice_extraction',
            budget_micro_usdz=10000,max_call_micro_usdz=10000)
        result=self.ops.action('operator',job['id'],'start')
        self.assertEqual(result['state'],'BLOCKED')
        self.assertIn('SIGNED_APPROVAL_REQUIRED',result['reason'])
        self.assertFalse(result['financial_dispatch_enabled'])

    def test_malformed_budget_types_and_missing_fields(self):
        for value in (True,-1,0.1,'1',10**20):
            with self.assertRaises(ValueError):self.create(budget_micro_usdz=value)
        with self.assertRaises(ValueError):self.create(max_call_micro_usdz=1)

    def test_idempotency_and_conflicts(self):
        first=self.create()
        self.assertEqual(self.create()['id'],first['id'])
        with self.assertRaises(PolicyError):self.create(source={'amounts_cents':[3],'discount_cents':0})

    def test_concurrent_start_runs_once(self):
        job=self.create()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            rows=list(pool.map(lambda _:self.ops.action('operator',job['id'],'start'),range(4)))
        self.assertEqual({r['state'] for r in rows},{'COMPLETED'})
        self.assertEqual(sum(e['kind']=='LOCAL_TOOL_SELECTED' for e in self.ops.ledger.events()),1)

    def test_pause_and_resume_do_not_execute(self):
        job=self.create()
        self.assertEqual(self.ops.action('operator',job['id'],'pause')['state'],'PAUSED')
        with self.assertRaises(PolicyError):self.ops.action('operator',job['id'],'start')
        self.assertEqual(self.ops.action('operator',job['id'],'resume')['state'],'QUEUED')
        self.assertIsNone(self.ops.get('operator',job['id'])['output'])

    def test_other_operator_cannot_view_or_start_job(self):
        job=self.create()
        self.assertEqual(self.ops.jobs('other'),[])
        with self.assertRaises(KeyError):self.ops.action('other',job['id'],'start')

    def test_quoted_source_is_backend_generated_and_never_paid(self):
        job=self.create(policy='real-touchstone',budget_micro_usdz=10000,max_call_micro_usdz=10000)
        seen=[]
        def probe(terms):
            seen.append(terms)
            return {'url':terms['url'],'provider_id':'local-gpu','expires_at':time.time()*1000+30000,
                    'offer':{'amount':'10000000000000000','network':'eip155:63825'}}
        result=self.ops.quotes('operator',job['id'],[{'id':'local-gpu','origin':'http://127.0.0.1:8092'}],probe=probe)
        self.assertEqual(result['payments_dispatched'],0)
        self.assertEqual(result['providers'][0]['status'],'QUOTE_RECEIVED')
        self.assertEqual(result['providers'][0]['approval'],'APPROVAL_REQUIRED')
        self.assertIn('/inference/',seen[0]['url'])
        self.assertTrue(self.ops.ledger.audit()['valid'])

    def test_expired_or_wrong_provider_quote_is_blocked(self):
        job=self.create(policy='real-touchstone',budget_micro_usdz=10000,max_call_micro_usdz=10000)
        for provider,expiry in [('evil',time.time()*1000+30000),('local-gpu',0)]:
            result=self.ops.quotes('operator',job['id'],[{'id':'local-gpu','origin':'http://127.0.0.1:8092'}],
                probe=lambda t:{'url':t['url'],'provider_id':provider,'expires_at':expiry})
            self.assertEqual(result['providers'][0]['status'],'BLOCKED')

    def test_backup_restore_keeps_jobs_and_audit_but_revokes_sessions(self):
        from tools.operator_backup import backup_or_restore
        folder=Path(self.tmp.name)
        password=secrets.token_urlsafe(24)
        config=make_config('http://127.0.0.1:8089','operator',password)
        sessions=Sessions(self.ops.ledger,config)
        token,_=sessions.login('operator',password)
        job=self.create()
        self.ops.action('operator',job['id'],'start')
        # The primary fixture's database is directly in folder, so use a separate archive parent.
        with tempfile.TemporaryDirectory() as location:
            archive=Path(location)/'backup.sqlite'
            backup_or_restore('backup',folder,archive)
            restored=folder/'restored'
            backup_or_restore('restore',restored,archive)
            self.assertEqual(Operations(restored/'ledger.sqlite').get('operator',job['id'])['state'],'COMPLETED')
            self.assertTrue(Operations(restored/'ledger.sqlite').ledger.audit()['valid'])
            with self.assertRaises(PolicyError):Sessions(Operations(restored/'ledger.sqlite').ledger,config).inspect(token)
            with self.assertRaises(ValueError):backup_or_restore('restore',restored,archive)


class OperatorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        self.origin='http://127.0.0.1:'+str(port)
        self.password=secrets.token_urlsafe(24)
        self.config=make_config(self.origin,'operator',self.password)
        path=Path(self.tmp.name)/'config.json'
        path.write_text(json.dumps(self.config))
        self.server=make_server(path,self.tmp.name,port=port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.port=port
        self.cookie='';self.csrf=''

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def request(self,path,body=None,headers=None,raw=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        all_headers={'Origin':self.origin,'Cookie':self.cookie,'X-Touchstone-CSRF':self.csrf}
        if body is not None or raw is not None:all_headers['Content-Type']='application/json'
        all_headers.update(headers or {})
        conn.request('GET' if body is None and raw is None else 'POST',path,
            raw if raw is not None else json.dumps(body) if body is not None else None,all_headers)
        response=conn.getresponse();payload=response.read()
        result=(response.status,json.loads(payload),dict(response.getheaders()))
        conn.close();return result

    def login(self):
        status,body,headers=self.request('/operator-api/login',{'username':'operator','password':self.password})
        self.assertEqual(status,200)
        self.cookie=headers['Set-Cookie'].split(';')[0];self.csrf=body['csrf']

    def test_auth_required_for_every_operational_read_and_write(self):
        for path in ('jobs','events','transactions','session'):
            self.assertEqual(self.request('/operator-api/'+path)[0],401)
        self.assertEqual(self.request('/operator-api/jobs',proposal())[0],401)
        self.assertEqual(self.request('/console')[0],404)
        self.assertEqual(self.request('/api/state')[0],404)

    def test_login_session_cookie_csrf_origin_host_and_logout(self):
        self.login()
        status,value,headers=self.request('/operator-api/session')
        self.assertEqual(status,200)
        self.assertEqual(value['username'],'operator')
        for changed in ({'Origin':'https://evil.invalid'},{'Host':'evil.invalid'},{'X-Touchstone-CSRF':'fake'}):
            self.assertEqual(self.request('/operator-api/jobs',proposal(),changed)[0],403)
        self.assertEqual(self.request('/operator-api/logout',{})[0],200)
        self.assertEqual(self.request('/operator-api/jobs')[0],401)

    def test_create_execute_refresh_and_transactions(self):
        self.login()
        status,job,_=self.request('/operator-api/jobs',proposal(),{'Idempotency-Key':'request-123'})
        self.assertEqual(status,201)
        self.assertEqual(self.request('/operator-api/jobs/'+job['id']+'/start',{})[1]['output'],{'total_cents':2000})
        self.assertEqual(self.request('/operator-api/jobs')[1]['jobs'][0]['state'],'COMPLETED')
        tx=self.request('/operator-api/transactions')[1]
        self.assertEqual(tx['currencies'],{'USD':0,'USDZ':0,'prepaid_credit_USD':0,'native_fees':'NONE'})

    def test_duplicate_json_fields_and_fake_approval_rejected(self):
        self.login()
        self.assertEqual(self.request('/operator-api/jobs',raw='{"kind":"arithmetic","kind":"invoice"}')[0],400)
        self.assertEqual(self.request('/operator-api/jobs',{**proposal(),'approved':True})[0],400)

    def test_wrong_password_rate_limit_and_safe_errors(self):
        for _ in range(5):self.assertEqual(self.request('/operator-api/login',{'username':'operator','password':'wrong'})[0],401)
        self.assertEqual(self.request('/operator-api/login',{'username':'operator','password':self.password})[0],429)

    def test_expired_revoked_and_rotated_sessions(self):
        self.login()
        with self.server.operations.ledger.tx() as db:db.execute('UPDATE operator_sessions SET expires_at=0')
        self.assertEqual(self.request('/operator-api/session')[0],401)
        self.login()
        with self.server.operations.ledger.tx() as db:db.execute('UPDATE operator_sessions SET epoch=?',('old',))
        self.assertEqual(self.request('/operator-api/session')[0],401)

    def test_sse_reports_durable_events_and_resume_cursor(self):
        self.login()
        _,job,_=self.request('/operator-api/jobs',proposal(),{'Idempotency-Key':'event-test'})
        self.request('/operator-api/jobs/'+job['id']+'/start',{})
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        conn.request('GET','/operator-api/events',headers={'Cookie':self.cookie,'Last-Event-ID':'1'})
        response=conn.getresponse()
        self.assertEqual(response.status,200)
        lines=[response.readline().decode() for _ in range(4)]
        self.assertTrue(any('JOB_CREATED' in line for line in lines))
        self.assertFalse(any(line=='id: 1\n' for line in lines))
        conn.close()

    def test_session_restart_preserves_and_idle_expiry_rejects(self):
        self.login()
        sessions=Sessions(self.server.operations.ledger,self.config)
        token=self.cookie.split('=',1)[1]
        self.assertEqual(sessions.inspect(token)['username'],'operator')
        with self.server.operations.ledger.tx() as db:db.execute('UPDATE operator_sessions SET last_seen=0')
        with self.assertRaises(PolicyError):sessions.inspect(token)

    def test_https_cookie_and_production_refused(self):
        config=make_config('https://operator.example.com','operator',self.password,'TESTNET')
        self.assertEqual(Sessions(self.server.operations.ledger,config).cookie_name,'__Host-touchstone')
        config['environment']='PRODUCTION'
        with self.assertRaises(ValueError):validate_config(config)
        with self.assertRaises(ValueError):make_config('http://public.example.com','operator',self.password)

    def test_readiness_cache_is_authenticated_and_expires(self):
        self.assertEqual(self.request('/operator-api/integrations')[0],401)
        self.login()
        self.assertEqual(self.request('/operator-api/integrations')[1]['status'],'BLOCKED_FRESH_PRIVATE_READ_CHECK_REQUIRED')
        from datetime import datetime,timezone,timedelta
        path=Path(self.tmp.name)/'readonly-integrations.json'
        raw={'scope':'READ_ONLY_INTEGRATION_CHECK','observed_at':datetime.now(timezone.utc).isoformat(),
             'airwallex':{'authenticated':True,'api_key':'must-not-be-returned'},'unexpected_private_field':'must not be returned'}
        path.write_text(json.dumps(raw))
        status,value,_=self.request('/operator-api/integrations')
        self.assertEqual(value['status'],'CURRENT_READ_ONLY_SNAPSHOT')
        self.assertNotIn('unexpected_private_field',json.dumps(value))
        self.assertNotIn('api_key',json.dumps(value))
        raw['observed_at']=(datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat()
        path.write_text(json.dumps(raw))
        self.assertEqual(self.request('/operator-api/integrations')[1]['status'],'BLOCKED_FRESH_PRIVATE_READ_CHECK_REQUIRED')

    def test_no_remote_financial_or_approval_proxy_routes_exist(self):
        self.login()
        for path in ('/api/live/run','/api/procurement/submit-signature','/operator-api/pay','/operator-api/capture'):
            self.assertEqual(self.request(path,{'approved':True})[0],404)


if __name__=='__main__':unittest.main()
