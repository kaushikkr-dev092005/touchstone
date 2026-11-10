"""Bounded source-role checks. No dataset, task ID, answer map or model output repair."""
import re
import unicodedata

ALIASES = {
    'invoice_id': ('Invoice ID', 'Document reference'),
    'supplier_name': ('Supplier', 'Issued by'),
    'purchase_order_id': ('Purchase order', 'Procurement reference'),
    'currency': ('Currency', 'Settlement currency'),
    'subtotal_cents': ('Subtotal', 'Net goods'),
    'tax_cents': ('Tax', 'Sales tax'),
    'total_cents': ('Total due', 'Amount payable'),
}


def label_key(value):
    # Normalize label typography only. Never normalize invoice values or their offsets.
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


LABELS = {label_key(label): role for role, labels in ALIASES.items() for label in labels}
HEADERS = tuple(re.compile(pattern) for pattern in (
    r'\s*\|\s*(?P<label>[^|]{1,64}?)\s*\|\s*(?P<value>[^|]+?)\s*\|\s*',
    r'(?P<value>.+?)\s+\[(?P<label>[^\[\]]{1,64})\]\s*',
    r'(?P<label>.{1,64}?)\s*\.\.\.\s*\{(?P<value>[^{}]+)\}\s*',
    r'(?P<label>.{1,64}?)\s*(?:=>|:|\t+)\s*(?P<value>.+?)\s*',
))
MONEY = r'USD [0-9]+\.[0-9]{2}'
ITEMS = tuple(re.compile(pattern) for pattern in (
    rf'ITEM-[0-9]+\s*\|\s*quantity=(?P<quantity>[1-9][0-9]*)\s*\|\s*unit=(?P<unit_price_cents>{MONEY})\s*\|\s*amount=(?P<line_total_cents>{MONEY})',
    rf'ITEM-[0-9]+\s+extension (?P<line_total_cents>{MONEY});\s*(?P<quantity>[1-9][0-9]*) units @ (?P<unit_price_cents>{MONEY})',
    rf'ITEM-[0-9]+\s+(?P<unit_price_cents>{MONEY}) each / (?P<quantity>[1-9][0-9]*) pcs / extended (?P<line_total_cents>{MONEY})',
))


def citation(text, begin, end):
    while begin < end and text[begin].isspace(): begin += 1
    while end > begin and text[end-1].isspace(): end -= 1
    return {'value': text[begin:end], 'start': begin, 'end': end}


def header_bindings(text):
    bindings = {role: [] for role in ALIASES}
    for line in re.finditer(r'[^\r\n]+', text):
        for pattern in HEADERS:
            match = pattern.fullmatch(line[0])
            if not match: continue
            role = LABELS.get(label_key(match['label']))
            if role:
                value = citation(text, line.start()+match.start('value'), line.start()+match.end('value'))
                if value['value']: bindings[role].append(value)
                break
    return bindings


def item_bindings(text, row):
    for pattern in ITEMS:
        match = pattern.fullmatch(row[0])
        if match:
            return {role: citation(text, row.start()+match.start(role), row.start()+match.end(role))
                    for role in ('quantity', 'unit_price_cents', 'line_total_cents')}
    return None


def check_roles(text, fields, items, rows):
    """Known wrong roles reject; unsupported/ambiguous roles require review."""
    bindings = header_bindings(text)
    issues, reject = [], False
    for role, selected in fields.items():
        matches = bindings[role]
        if not matches:
            issues.append('UNSUPPORTED_HEADER_ROLE:'+role)
        elif len(matches) != 1:
            issues.append('AMBIGUOUS_HEADER_ROLE:'+role)
        elif selected != matches[0]:
            issues.append('FIELD_ROLE_MISMATCH:'+role); reject = True
    identifiers = [re.match(r'ITEM-[0-9]+', row[0])[0] for row in rows]
    if len(set(identifiers)) != len(identifiers): issues.append('DUPLICATE_LINE_IDENTIFIER')
    for row, selected in zip(rows, items):
        expected = item_bindings(text, row)
        if expected is None:
            issues.append('UNSUPPORTED_ITEM_ROLES')
        elif any(selected[role] != value for role, value in expected.items()):
            issues.append('ITEM_ROLE_MISMATCH'); reject = True
    for role in ('invoice_id', 'purchase_order_id'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/\-]{0,95}', fields[role]['value']):
            issues.append('INVALID_IDENTIFIER:'+role); reject = True
    return {'verified': not issues, 'decision': 'rejected' if reject else 'review' if issues else 'candidate',
            'issues': sorted(set(issues))}


def parse_supported(text, rows):
    """Tools share the same bounded grammar as validation; no artificial parser handicap."""
    headers = header_bindings(text)
    if not any(headers.values()): return None
    items = []
    for row in rows:
        fields = item_bindings(text, row)
        if fields is None: return None
        items.append({'line': citation(text, row.start(), row.end()), **fields})
    return {'fields': {role: values[0] if len(values)==1 else None for role, values in headers.items()}, 'items': items}
