"""Optional browser QA. Requires playwright and its headless Chromium shell."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "tmp/browser"
BASE = "http://127.0.0.1:8091"


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qa-", dir=ARTIFACTS) as data:
        env={k:v for k,v in os.environ.items() if not k.startswith(('AIRWALLEX_','ANTHROPIC_','METAL_')) and k!='AGENT_PRIVATE_KEY'}
        env['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'
        process = subprocess.Popen([sys.executable, "-m", "touchstone", "serve", "--port", "8091", "--data-dir", data], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("QA server exited: " + process.communicate()[1])
                try:
                    urllib.request.urlopen(BASE + "/api/state", timeout=1).close()
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(.1)
            else:
                raise RuntimeError("QA server did not start")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
                def wait_state(predicate, timeout=60):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        current = page.request.get(BASE + "/api/state").json()
                        if predicate(current):
                            return current
                        page.wait_for_timeout(200)
                    raise AssertionError("Backend state did not reach expected condition")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(BASE, wait_until="domcontentloaded")
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                assert page.locator(".disclosure").inner_text().startswith("SIMULATION")
                page.wait_for_function("() => !document.getElementById('planning-case').disabled")
                assert "1000/1000" in page.locator("#planning-summary").inner_text()
                assert page.locator("#eligibility-rows tr").count() == 6
                assert page.locator("#planning-decision").inner_text() == "Use a local tool"
                page.select_option("#planning-case", label="foreign currency")
                assert page.locator("#planning-decision").inner_text() == "Pause for review"
                assert page.locator("#planning-output").inner_text() == "No answer accepted."
                page.select_option("#planning-case", label="sum discount")
                assert "2000" in page.locator("#planning-output").inner_text()
                page.wait_for_function("() => !document.getElementById('testnet-proof-summary').textContent.includes('Checking')")
                proof = page.request.get(BASE + '/api/readiness').json()['metal']['paid_proof']
                if proof:
                    assert '1 paid inference call' in page.locator('#testnet-proof-summary').inner_text()
                    assert 'rejected the answer' in page.locator('#testnet-proof-detail').inner_text()
                page.screenshot(path=str(ARTIFACTS / "desktop-ready.png"), full_page=True)
                refused = page.request.post(BASE + "/api/demo", data={})
                assert refused.status == 403
                token = page.locator('meta[name="touchstone-token"]').get_attribute("content")
                page.wait_for_function("() => document.getElementById('fault-summary').textContent.includes('1250')")
                assert '2000' in page.locator('#fault-summary').inner_text()
                assert 'UNSIGNED_HISTORICAL_DELIVERY' in page.locator('#fault-limits').text_content()
                assert 'No card created' in page.locator('#card-status').inner_text()
                assert 'MOCK identity' in page.locator('#tap-status').inner_text()
                assert page.request.post(BASE+'/api/fx-quote',data={}).status==403
                with page.expect_response(BASE+'/api/fx-quote') as quote_response:
                    page.click('#refresh-fx')
                assert quote_response.value.status==503
                page.wait_for_function("() => document.getElementById('fx-status').textContent.startsWith('BLOCKED')")
                refused = page.request.post(BASE + "/api/demo", headers={"X-Touchstone-Token": token, "Origin": "https://untrusted.example"}, data={})
                assert refused.status == 403
                request = urllib.request.Request(BASE + "/api/state", headers={"Host": "untrusted.example"})
                try:
                    urllib.request.urlopen(request, timeout=3)
                    raise AssertionError("Invalid Host accepted")
                except urllib.error.HTTPError as e:
                    assert e.code == 403
                page.click("#start")
                page.wait_for_function("() => document.querySelectorAll('#payment-rows tr').length >= 3")
                page.click("#halt")
                page.wait_for_function("() => document.getElementById('notice').textContent.includes('Kill switch active')")
                wait_state(lambda s: not s["worker_running"])
                page.click("#resume")
                wait_state(lambda s: not s["halted"] and not s["worker_running"] and len(s["jobs"]) == 3 and all(j["status"] != "RUNNING" for j in s["jobs"]))
                page.wait_for_function("() => !document.getElementById('close').disabled")
                page.screenshot(path=str(ARTIFACTS / "desktop-paused.png"), full_page=True)
                with page.expect_response(BASE + "/api/close") as close_response:
                    page.click("#close")
                assert close_response.value.status == 200, close_response.value.text()
                state = wait_state(lambda s: len(s["jobs"]) == 3 and all(j["status"] == "COMPLETED" for j in s["jobs"]))
                assert all(j["captured"] == j["spent"] and j["captured"] + j["released"] == j["hold"] for j in state["jobs"]), json.dumps(state["jobs"], indent=2)
                assert state["reconciliation"]["matched"]
                assert state["audit"]["valid"]
                page.select_option('#failed-call-policy','MERCHANT_ABSORBS')
                page.click('#start')
                state=wait_state(lambda s: not s['worker_running'] and len(s['runs'])==2)
                page.wait_for_function("() => !document.getElementById('close').disabled")
                page.click('#close')
                state=wait_state(lambda s: all(j['status']=='COMPLETED' for j in s['jobs']))
                latest=state['runs'][0]['id']
                financial=next(row for row in state['financials']['by_run'] if row['run_id']==latest)
                assert financial['failed_call_policy']=='MERCHANT_ABSORBS'
                assert financial['absorbed_failures_micro_usd']>0
                assert financial['customer_captured_micro_usd']<financial['provider_spend_micro_usd']+financial['check_fees_micro_usd']
                page.wait_for_function("() => document.getElementById('pnl-values').textContent.includes('MERCHANT_ABSORBS')")
                page.wait_for_timeout(1000)
                page.screenshot(path=str(ARTIFACTS / "desktop-completed.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.reload(wait_until="domcontentloaded")
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"), "Mobile overflow"
                page.screenshot(path=str(ARTIFACTS / "mobile-completed.png"), full_page=True)
                assert not errors, errors
                result = {"desktop": "passed", "mobile_width": 390, "horizontal_overflow": False,
                          "browser_errors": errors, "start_halt_resume_close": "passed",
                          "host_origin_session_controls": "passed", "reconciliation": state["reconciliation"],
                          "planning_tool_and_review_cases": "passed", "provider_evidence_rows": 6,
                          "testnet_proof_disclosure": "passed",
                          "fault_fx_telemetry_rail_panels": "passed",
                          "credential_isolation_and_blocked_fx": "passed",
                          "merchant_absorbs_sse_and_capture": "passed",
                          "screenshots": ["desktop-ready.png", "desktop-paused.png", "desktop-completed.png", "mobile-completed.png"]}
                (ARTIFACTS / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(result, indent=2))
                browser.close()
        finally:
            process.terminate()
            process.communicate(timeout=10)


if __name__ == "__main__":
    main()
