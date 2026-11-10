"""Read sandbox issuing and merchant setup; never create a card or onboard a merchant."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from touchstone.card_rail import CardRail
from touchstone.holds import OperationJournal
from touchstone.treasury import AirwallexSandbox, AirwallexHTTPError
from tools.run_project import environment


def inspect_merchant(client):
    """Only return permission status. Config can contain private URLs and credentials."""
    result = {'configuration_read': False, 'onboarding_verified': False,
              'writes_performed': False, 'payment_submitted': False}
    try:
        raw = client.request('GET', '/api/v1/pa/agentic_commerce/config')
        valid = isinstance(raw, dict) and bool(raw)
        result.update(configuration_read=valid, status='READABLE_UNVERIFIED' if valid else 'INVALID_RESPONSE')
    except AirwallexHTTPError as error:
        status = ('NOT_CONFIGURED' if error.status == 404 and error.code == 'MERCHANT_CONFIG_NOT_FOUND'
                  else 'ACCESS_DENIED' if error.status in {401, 403} else 'UNAVAILABLE')
        result.update(status=status,
                      http_status=error.status, code=error.code)
    except (OSError, ValueError, RuntimeError):
        result['status'] = 'UNAVAILABLE'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='bench/results/completion-20261110/external-access.json')
    args = parser.parse_args()
    environment()
    client = AirwallexSandbox()
    report = {'label': 'MEASURED', 'observed_at': datetime.now(timezone.utc).isoformat(),
              'mode': 'SANDBOX', 'financial_transactions': 0, 'cards_created': 0,
              'hosted_inference_calls': 0,
              'issuing': CardRail(client, OperationJournal(ROOT/'data/issuing.sqlite')).doctor(diagnose=True),
              'merchant': inspect_merchant(client),
              'visa': {'status': 'APPROVAL_NOT_VERIFIED', 'registered_agent_verified': False,
                       'registration_submitted': False, 'source': 'NO_VISA_ONBOARDING_EVIDENCE'},
              'references': {
                  'scopes': 'https://www.airwallex.com/docs/developer-tools/api/api-key-scopes',
                  'issuing': 'https://www.airwallex.com/docs/issuing/test-and-go-live/integration-checklist',
                  'merchant': 'https://airwallexdev.com/agentic-commerce/',
                  'enablement': 'https://airwallexdev.com/guide',
                  'visa': 'https://developer.visa.com/docs/trusted-agent-protocol'}}
    path = ROOT/args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
