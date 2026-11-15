"""Read-only OCI identity/inventory checks. Never provisions or treats credits as free eligibility."""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from decimal import Decimal, InvalidOperation

ROOT = Path(__file__).resolve().parent.parent
READS = {('iam', 'tenancy', 'get'), ('iam', 'region-subscription', 'list'),
         ('iam', 'availability-domain', 'list'), ('iam', 'compartment', 'list'),
         ('compute', 'instance', 'list'), ('compute', 'image', 'get'),
         ('compute', 'shape', 'list'), ('bv', 'volume', 'list'),
         ('bv', 'boot-volume', 'list'), ('network', 'vcn', 'list'),
         ('network', 'public-ip', 'list')}


def number(value):
    if isinstance(value, bool):
        raise ValueError('INVALID_CAPACITY')
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('INVALID_CAPACITY') from None
    if not n.is_finite() or n < 0:
        raise ValueError('INVALID_CAPACITY')
    return n


def capacity(ocpus, memory_gb, storage_gb):
    """Existing non-terminated allocation + proposed 2/12/50, tenancy-wide.

    Conservative 31-day projection; not a billing or historic-usage measurement.
    """
    cpu, memory, storage = number(ocpus) + 2, number(memory_gb) + 12, number(storage_gb) + 50
    fits = cpu <= 2 and memory <= 12 and storage <= 200 and cpu * 744 <= 1500 and memory * 744 <= 9000
    return {'projected_a1_ocpus': str(cpu), 'projected_a1_memory_gb': str(memory),
            'projected_storage_gb': str(storage), 'projected_ocpu_hours': str(cpu * 744),
            'projected_memory_gb_hours': str(memory * 744), 'fits_published_allocation': fits,
            'actual_month_to_date_usage_verified': False, 'always_free_eligibility_verified': False}


def find_cli():
    local = ROOT / '.tools/oci/Scripts/oci.exe'
    return shutil.which('oci') or (str(local) if local.is_file() else None)


def read_oci(command, args, *, cli, profile, region, config_file):
    if tuple(command) not in READS:
        raise ValueError('OCI_WRITE_FORBIDDEN')
    env = {k: v for k, v in os.environ.items() if not k.startswith(
        ('OCI_', 'ORACLE_', 'AWS_', 'AIRWALLEX_', 'METAL_', 'CLAUDE_', 'ANTHROPIC_')) and k != 'AGENT_PRIVATE_KEY'}
    result = subprocess.run([cli, '--config-file', str(config_file), '--profile', profile,
        '--cli-rc-file', os.devnull, '--query', '@',
        '--auth', 'security_token', '--region', region, '--output', 'json', *command, *args],
        env=env, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError('OCI_READ_DENIED_OR_SESSION_EXPIRED')
    # OCI CLI 3.95.1 cli_util.render() emits nothing for an empty list.
    # Force whole-response query/default isolation above; never apply this to GET.
    # https://github.com/oracle/oci-cli/blob/v3.95.1/src/oci_cli/cli_util.py
    if command[-1] == 'list' and not result.stdout.strip() and 'Query returned empty' not in result.stderr:
        return []
    try:
        return json.loads(result.stdout)['data']
    except (ValueError, KeyError):
        raise RuntimeError('OCI_INVALID_READ_RESPONSE') from None


def inspect(settings, *, config_file=None, reader=None):
    required = {'profile', 'region', 'tenancy_ocid', 'compartment_ocid', 'image_ocid'}
    if set(settings) != required:
        raise ValueError('INVALID_SETTINGS_FIELDS')
    if not all(isinstance(v, str) and v for v in settings.values()):
        raise ValueError('INVALID_SETTINGS_VALUES')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', settings['profile']):
        raise ValueError('INVALID_PROFILE')
    config_file = Path(config_file or Path.home() / '.oci/config')
    result = {'status': 'OCI_PROFILE_NOT_CONFIGURED', 'region': settings['region'],
              'read_only_checks_passed': False, 'identity_verified': False,
              'always_free_eligibility_verified': False, 'billing_verified': False,
              'provisioning_authorized': False, 'resources_created': 0, 'financial_operations': 0}
    cli = find_cli()
    if not cli and reader is None:
        result['status'] = 'OCI_CLI_NOT_INSTALLED'
        return result
    conf = configparser.ConfigParser(interpolation=None)
    conf.read(config_file, encoding='utf-8')
    if settings['profile'] not in conf:
        return result
    profile = conf[settings['profile']]
    if profile.get('tenancy') != settings['tenancy_ocid']:
        result['status'] = 'OCI_TENANCY_MISMATCH'
        return result
    if not profile.get('security_token_file'):
        result['status'] = 'OCI_TEMPORARY_SESSION_REQUIRED'
        return result
    if reader is None:
        def reader(command, args):
            return read_oci(command, args, cli=cli, profile=settings['profile'],
                            region=settings['region'], config_file=config_file)
    try:
        tenancy = reader(('iam', 'tenancy', 'get'), ['--tenancy-id', settings['tenancy_ocid']])
        if tenancy.get('id') != settings['tenancy_ocid']:
            result['status'] = 'OCI_TENANCY_MISMATCH'
            return result
        result['identity_verified'] = True
        result['tenancy_fingerprint'] = hashlib.sha256(tenancy['id'].encode()).hexdigest()[:16]
        regions = reader(('iam', 'region-subscription', 'list'), ['--tenancy-id', tenancy['id'], '--all'])
        if not any(r.get('is-home-region') and r.get('region-name') == settings['region']
                   and r.get('status') == 'READY' for r in regions):
            result['status'] = 'OCI_HOME_REGION_REQUIRED'
            return result
        ads = reader(('iam', 'availability-domain', 'list'), ['--compartment-id', tenancy['id'], '--all'])
        image = reader(('compute', 'image', 'get'), ['--image-id', settings['image_ocid']])
        if image.get('operating-system') != 'Canonical Ubuntu' or image.get('operating-system-version') != '24.04':
            result['status'] = 'OCI_UBUNTU_24_04_IMAGE_REQUIRED'
            return result
        shapes = reader(('compute', 'shape', 'list'), ['--compartment-id', settings['compartment_ocid'],
                        '--image-id', settings['image_ocid'], '--all'])
        if not any(s.get('shape') == 'VM.Standard.A1.Flex' for s in shapes):
            result['status'] = 'OCI_ARM64_IMAGE_OR_SHAPE_UNAVAILABLE'
            return result
        children = reader(('iam', 'compartment', 'list'), ['--compartment-id', tenancy['id'],
                          '--compartment-id-in-subtree', 'true', '--access-level', 'ANY', '--all'])
        compartments = {tenancy['id']} | {c['id'] for c in children if c.get('lifecycle-state') == 'ACTIVE'}
        if settings['compartment_ocid'] not in compartments:
            result['status'] = 'OCI_COMPARTMENT_NOT_IN_TENANCY'
            return result
        cpu = memory = storage = Decimal(0)
        instance_count = volume_count = networks = public_ips = 0
        for compartment in sorted(compartments):
            args = ['--compartment-id', compartment, '--all']
            instances = reader(('compute', 'instance', 'list'), args)
            for instance in instances:
                if instance.get('lifecycle-state') == 'TERMINATED':
                    continue
                instance_count += 1
                if instance.get('shape') == 'VM.Standard.A1.Flex':
                    cpu += number(instance['shape-config']['ocpus'])
                    memory += number(instance['shape-config']['memory-in-gbs'])
            volumes = list(reader(('bv', 'volume', 'list'), args))
            for ad in ads:
                volumes.extend(reader(('bv', 'boot-volume', 'list'), args + ['--availability-domain', ad['name']]))
                public_ips += len(reader(('network', 'public-ip', 'list'), args + [
                    '--scope', 'AVAILABILITY_DOMAIN', '--availability-domain', ad['name']]))
            for volume in volumes:
                if volume.get('lifecycle-state') != 'TERMINATED':
                    storage += number(volume['size-in-gbs'])
                    volume_count += 1
            networks += len(reader(('network', 'vcn', 'list'), args))
            public_ips += len(reader(('network', 'public-ip', 'list'), args + ['--scope', 'REGION']))
        result['inventory'] = {'compartments_read': len(compartments), 'instances': instance_count,
                               'volumes': volume_count, 'vcns': networks, 'public_ips': public_ips}
        result['capacity'] = capacity(cpu, memory, storage)
        result['read_only_checks_passed'] = True
        result['status'] = ('READ_CHECKS_PASSED_BILLING_AND_APPROVAL_STILL_REQUIRED'
                            if result['capacity']['fits_published_allocation'] else 'BLOCKED_FREE_ALLOCATION')
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        result['status'] = 'OCI_READ_FAILED_OR_INCOMPLETE_INVENTORY'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True, help='Private ignored JSON; see deployment guide')
    parser.add_argument('--output', default='tmp/oracle-preflight.json')
    args = parser.parse_args()
    target = (ROOT / args.output).resolve()
    if not target.is_relative_to(ROOT / 'tmp'):
        raise ValueError('REPORT_MUST_REMAIN_IN_IGNORED_TMP')
    result = inspect(json.loads(Path(args.settings).read_text(encoding='utf-8')))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'READ_CHECKS_PASSED_BILLING_AND_APPROVAL_STILL_REQUIRED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
