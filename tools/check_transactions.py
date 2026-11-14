"""Optional browser QA for the dashboard transactions explorer.

Usage: python tools/check_transactions.py [base_url]
Requires playwright + Chromium and a running dashboard that already holds transactions
(e.g. `python tools/run_mock.py`, then run the demo once).
"""
import csv
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

def check_page(page, base, artifacts):
    """Check the real API, filters, drawer, pagination and exported charge totals."""
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    if page.locator('[data-nav="transactions"]').count():
        page.locator('[data-nav="transactions"]').click()
    transactions = page.request.get(base + '/api/transactions').json()['transactions']
    assert transactions, 'Run the simulated demo before checking transactions'
    page.wait_for_function('(n) => Number(document.getElementById("tx-count").textContent)===n', arg=len(transactions))
    expected_spend = sum(t['charged_provider'] + t['charged_verification'] for t in transactions)
    assert page.inner_text('#tx-spend') == f'${expected_spend/1e6:.4f}'
    page.click('.tx-chip[data-f="fail"]')
    rejected = [t for t in transactions if t['state'] == 'VERIFIED_FAIL']
    assert page.locator('#tx-rows tr[data-key]').count() == min(50, len(rejected))
    assert all('REJECTED' in text for text in page.locator('#tx-rows .pill').all_inner_texts())
    page.click('.tx-chip[data-f="all"]')
    page.fill('#tx-search', 'zzz-no-match')
    assert page.locator('#tx-rows tr[data-key]').count() == 0
    provider = transactions[0]['provider']
    page.fill('#tx-search', provider)
    assert page.locator('#tx-rows tr[data-key]').count() > 0
    page.fill('#tx-search', '')
    run_ids = {t['run_id'] for t in transactions}
    selected = transactions[0]['run_id']
    page.select_option('#tx-run', selected)
    assert page.locator('#tx-rows tr[data-key]').count() == min(50, sum(t['run_id'] == selected for t in transactions))
    page.select_option('#tx-run', '')
    before = page.locator('#tx-rows tr[data-key] td').first.inner_text()
    page.click('th[data-sort="seq"]')
    after = page.locator('#tx-rows tr[data-key] td').first.inner_text()
    assert before != after or len(transactions) == 1
    page.locator('#tx-rows tr[data-key]').first.focus()
    page.keyboard.press('Enter')
    assert page.locator('#tx-drawer').evaluate('d=>d.open')
    assert 'Receipt' in page.inner_text('#tx-detail')
    assert 'Total charged' in page.inner_text('#tx-detail')
    page.click('#tx-close')
    if len(transactions) > 50:
        page.click('#tx-more')
        assert page.locator('#tx-rows tr[data-key]').count() == min(100, len(transactions))
    with page.expect_download() as download:
        page.click('#tx-export')
    assert download.value.suggested_filename == 'touchstone-transactions.csv'
    with open(download.value.path(), newline='', encoding='utf-8') as stream:
        exported = list(csv.DictReader(stream))
    assert len(exported) == len(transactions)
    assert round(sum(float(row['total_charged_usd']) for row in exported)*1e6) == expected_spend
    page.locator('#v-transactions' if page.locator('#v-transactions').count() else '#transactions').screenshot(path=str(artifacts/'transactions.png'))
    return {'rows': len(transactions), 'runs': len(run_ids), 'confirmed_spend_micro_usd': expected_spend,
        'search_filters_sort_pagination': 'passed', 'keyboard_drawer': 'passed', 'csv_totals': 'passed'}


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8088'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(base + '/')
        print(check_page(page, base, Path(__file__).resolve().parent.parent/'tmp'))
        assert not errors, errors
        browser.close()


if __name__ == "__main__":
    main()
