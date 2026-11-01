import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from touchstone.fx import ConversionOutcomeUnknown, FxJournal, execute_conversion, spend_report
from touchstone.treasury import AirwallexSandbox


QUOTE = {"quote_id": "quote-1", "sell_currency": "USD", "buy_currency": "EUR",
         "sell_amount": 1.0, "buy_amount": 0.92, "dealt_currency": "USD",
         "client_rate": 0.92, "conversion_date": "2026-11-01"}


class FakeAirwallex:
    def __init__(self):
        self.create_count = 0
        self.conversions = []
        self.history = []

    def current_balances(self):
        return [{"account_type": "cash", "currency": "USD", "available_amount": 8.0,
                 "pending_amount": 0, "reserved_amount": 0, "total_amount": 8.0}]

    def create_conversion(self, quote, request_id):
        self.create_count += 1
        conversion = {"conversion_id": "conversion-1", "request_id": request_id, "quote_id": quote["quote_id"],
                      "status": "SETTLED", "sell_currency": "USD", "sell_amount": "1.00",
                      "buy_currency": "EUR", "buy_amount": "0.92", "client_rate": 0.92}
        self.conversions = [conversion]
        self.history = [
            {"source_type": "CONVERSION", "source": "conversion-1", "transaction_type": "CONVERSION_SELL",
             "currency": "USD", "amount": -1.0},
            {"source_type": "CONVERSION", "source": "conversion-1", "transaction_type": "CONVERSION_BUY",
             "currency": "EUR", "amount": 0.92},
        ]
        return conversion

    def conversions_by_request_id(self, request_id):
        return [item for item in self.conversions if item["request_id"] == request_id]

    def conversion_balance_history(self, request_id):
        return self.history


class FxWorkflow(unittest.TestCase):
    def test_conversion_is_journaled_and_not_created_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            client, journal = FakeAirwallex(), FxJournal(Path(temp) / "fx.sqlite")
            result = execute_conversion(client, journal, QUOTE, "demo-request-001")
            retry = execute_conversion(client, journal, QUOTE, "demo-request-001")
            self.assertEqual(result, retry)
            self.assertEqual(client.create_count, 1)
            self.assertEqual(journal.get("demo-request-001")["state"], "SETTLED")
            report = spend_report(client, journal, "demo-request-001")
            self.assertEqual(report["reconciliation"], "MATCHED_WALLET_HISTORY")
            self.assertEqual(report["wallet_balances"][0]["currency"], "USD")

    def test_unknown_conversion_is_never_replayed(self):
        class Uncertain(FakeAirwallex):
            def create_conversion(self, quote, request_id):
                self.create_count += 1
                raise TimeoutError("response lost")

        with tempfile.TemporaryDirectory() as temp:
            client, journal = Uncertain(), FxJournal(Path(temp) / "fx.sqlite")
            for _ in range(2):
                with self.assertRaises(ConversionOutcomeUnknown):
                    execute_conversion(client, journal, QUOTE, "demo-request-002")
            self.assertEqual(client.create_count, 1)
            self.assertEqual(journal.get("demo-request-002")["state"], "UNKNOWN")

    def test_spend_report_detects_mismatch_between_conversion_and_wallet_history(self):
        with tempfile.TemporaryDirectory() as temp:
            client, journal = FakeAirwallex(), FxJournal(Path(temp) / "fx.sqlite")
            execute_conversion(client, journal, QUOTE, "demo-request-003")
            client.history[0]["amount"] = -0.99
            self.assertEqual(spend_report(client, journal, "demo-request-003")["reconciliation"],
                             "MISMATCH_WALLET_HISTORY")

    def test_spend_report_detects_remote_conversion_different_from_journaled_quote(self):
        with tempfile.TemporaryDirectory() as temp:
            client, journal = FakeAirwallex(), FxJournal(Path(temp) / "fx.sqlite")
            execute_conversion(client, journal, QUOTE, "demo-request-004")
            client.conversions[0]["buy_amount"] = 0.99
            self.assertEqual(spend_report(client, journal, "demo-request-004")["reconciliation"],
                             "MISMATCH_LOCAL_TERMS")

    def test_scoped_fx_methods_use_quote_and_conversion_endpoints(self):
        with patch.dict("os.environ", {"AIRWALLEX_CLIENT_ID": "client", "AIRWALLEX_API_KEY": "key",
                                       "AIRWALLEX_ACCOUNT_ID": "account"}):
            client = AirwallexSandbox()
        requests = []
        def request(method, path, body=None):
            requests.append((method, path, body))
            if path.endswith("/quotes/create"):
                return {**QUOTE, "sell_amount": 1.0, "buy_amount": 0.92}
            return {"request_id": "request-123", "status": "SCHEDULED"}
        client.request = request
        quote = client.create_fx_quote("USD", "EUR", "1.00")
        conversion = client.create_conversion(quote, "request-123")
        self.assertEqual(conversion["request_id"], "request-123")
        self.assertEqual(requests[0][1], "/api/v1/fx/quotes/create")
        self.assertEqual(requests[1][1], "/api/v1/fx/conversions/create")
        self.assertEqual(requests[1][2]["request_id"], "request-123")
        self.assertEqual(requests[1][2]["sell_amount"], "1.0")
        self.assertNotIn("buy_amount", requests[1][2])
        with self.assertRaisesRegex(ValueError, "represented exactly"):
            client.create_fx_quote("USD", "EUR", "0.123456789012345678")

    def test_account_context_is_required_before_treasury_reads_or_writes(self):
        with patch.dict("os.environ", {"AIRWALLEX_CLIENT_ID": "client", "AIRWALLEX_API_KEY": "key",
                                       "AIRWALLEX_ACCOUNT_ID": ""}):
            client = AirwallexSandbox()
        with self.assertRaisesRegex(ValueError, "AIRWALLEX_ACCOUNT_ID"):
            client.current_balances()
        with self.assertRaisesRegex(ValueError, "AIRWALLEX_ACCOUNT_ID"):
            client.create_fx_quote("USD", "EUR", "1.00")


if __name__ == "__main__":
    unittest.main()
