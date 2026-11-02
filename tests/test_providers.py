import io
import json
import os
import unittest
from unittest.mock import patch

from touchstone.providers import anthropic_inference, task_contract
from touchstone.workload import Task


class HostedProviderTests(unittest.TestCase):
    def test_structured_schema_uses_anthropic_supported_constraints(self):
        task = Task("invoice", "invoice", {"text": "Invoice X. ITEM QTY 1 PRICE 10"})
        _, schema = task_contract(task)
        self.assertEqual(schema["required"], ["invoice_id", "currency", "total_cents"])
        self.assertFalse(schema["additionalProperties"])

    def test_messages_api_request_records_model_usage_without_exposing_key(self):
        response = {"model": "claude-sonnet-5", "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": '{"total_cents": 2000}'}],
                    "usage": {"input_tokens": 34, "output_tokens": 9}}
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return io.BytesIO(json.dumps(response).encode())

        task = Task("arithmetic", "arithmetic", {"amounts_cents": [1250, 775], "discount_cents": 25})
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-secret", "ANTHROPIC_MODEL": "claude-sonnet-5"}):
            output, latency, metadata = anthropic_inference(task, opener)
        request = captured["request"]
        headers = {key.lower(): value for key, value in request.header_items()}
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], "test-secret")
        self.assertEqual(headers["anthropic-version"], "2026-10-21")
        self.assertEqual(captured["timeout"], 90)
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(output, {"total_cents": 2000})
        self.assertGreaterEqual(latency, 0)
        self.assertEqual(metadata["provider_type"], "ANTHROPIC_API")
        self.assertEqual(metadata["usage"]["input_tokens"], 34)
        self.assertNotIn("test-secret", json.dumps(metadata))

    def test_missing_api_key_fails_before_network(self):
        task = Task("arithmetic", "arithmetic", {"amounts_cents": [10], "discount_cents": 0})
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                anthropic_inference(task, lambda *args, **kwargs: self.fail("network must not be called"))


if __name__ == "__main__":
    unittest.main()
