"""Optional browser QA for the dashboard transactions explorer.

Usage: python tools/check_transactions.py [base_url]
Requires playwright + Chromium and a running dashboard that already holds transactions
(e.g. `python tools/run_mock.py`, then run the demo once).
"""
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088"


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (" - " + str(detail) if detail else ""))
    return ok


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(BASE + "/")
        page.wait_for_selector("#tx-rows tr[data-key]", timeout=15000)
        total = int(page.inner_text("#tx-count"))
        results.append(check("rows render", page.locator("#tx-rows tr[data-key]").count() > 0, total))
        results.append(check("summary spend", page.inner_text("#tx-spend").startswith("$")))

        page.click('.tx-chip[data-f="fail"]')
        fails = page.locator("#tx-rows tr[data-key]").count()
        results.append(check("rejected filter", fails == 0 or all("REJECTED" in t for t in page.locator("#tx-rows .pill").all_inner_texts()), fails))
        page.click('.tx-chip[data-f="all"]')

        page.fill("#tx-search", "zzz-no-match")
        results.append(check("search no match", page.locator("#tx-rows tr[data-key]").count() == 0))
        page.fill("#tx-search", "")
        first_provider = page.locator("#tx-rows tr[data-key] td").nth(2).inner_text().split()[0]
        page.fill("#tx-search", first_provider)
        results.append(check("search by provider", page.locator("#tx-rows tr[data-key]").count() > 0, first_provider))
        page.fill("#tx-search", "")

        before = page.locator("#tx-rows tr[data-key] td").first.inner_text()
        page.click('th[data-sort="seq"]')
        after = page.locator("#tx-rows tr[data-key] td").first.inner_text()
        results.append(check("sort toggles", before != after or total == 1, before + "->" + after))

        page.locator("#tx-rows tr[data-key]").first.click()
        results.append(check("detail drawer opens", page.locator("#tx-drawer").evaluate("d=>d.open")))
        results.append(check("detail has receipt", "Receipt" in page.inner_text("#tx-detail")))
        page.click("#tx-close")

        with page.expect_download() as dl:
            page.click("#tx-export")
        results.append(check("csv export", dl.value.suggested_filename == "touchstone-transactions.csv"))
        results.append(check("no console errors", not errors, errors[:3]))
        page.locator("#transactions").screenshot(path="tmp/transactions.png")
        browser.close()
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
