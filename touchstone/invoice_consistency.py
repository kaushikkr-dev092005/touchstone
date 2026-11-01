"""Source-cited invoice consistency checks and a deliberately noisy spot-check."""
import random
import re

from .workload import Task

ITEM_RE = re.compile(r"(?im)^ITEM-[A-Z0-9-]+\b.*$")
QTY_RE = re.compile(r"\bQty\s*:\s*([0-9]{1,6})\b", re.I)
UNIT_RE = re.compile(r"\bunit price\s*:\s*(USD\s*[0-9,]+\.[0-9]{2})\b", re.I)
LINE_TOTAL_RE = re.compile(r"\bline extension\s*:\s*(USD\s*[0-9,]+\.[0-9]{2})\b", re.I)
TOTAL_RE = re.compile(r"\b(?:Grand total due|Balance due after credit)\s*:\s*(USD\s*[0-9,]+\.[0-9]{2})\b", re.I)
MONEY_RE = re.compile(r"USD\s*([0-9,]+)\.([0-9]{2})", re.I)


def make_invoice_consistency_case(seed=42, line_count=10, inconsistent=False):
    if type(line_count) is not int or not 2 <= line_count <= 100:
        raise ValueError("Invoice consistency cases need 2 to 100 line items")
    rng = random.Random(seed)
    descriptions = ["ceramic washers", "pump seals", "copper couplings", "valve kits", "steel clips",
                    "service labels", "filter housings", "mounting brackets", "gasket sheets", "hose clamps"]
    records = []
    lines = [f"Forwarded invoice INV-{seed}: receiving notes follow; quantities confirmed against the packing slip.",
             "Please ignore the old draft total in the email thread; use the final amount due below."]
    for index in range(line_count):
        quantity = rng.randint(1, 8)
        unit_cents = rng.randint(75, 15000)
        line_cents = quantity * unit_cents
        description = descriptions[index % len(descriptions)]
        line = (f"ITEM-{index + 1:02d} / {description} | Qty: {quantity}; "
                f"unit price: USD {unit_cents // 100}.{unit_cents % 100:02d} each; "
                f"line extension: USD {line_cents // 100}.{line_cents % 100:02d}; "
                f"{rng.choice(['packing note attached', 'backorder cleared', 'delivery confirmed'])}.")
        lines.append(line)
        records.append((line, quantity, unit_cents, line_cents))
    total_cents = sum(record[3] for record in records) + (137 if inconsistent else 0)
    lines.extend(["The supplier confirmed that the credit memo is already applied.",
                  f"Balance due after credit: USD {total_cents // 100}.{total_cents % 100:02d}"])
    text = "\n".join(lines)
    output = {"line_items": [], "total_cents": total_cents,
              "total_evidence": _citation(text, f"USD {total_cents // 100}.{total_cents % 100:02d}",
                                          text.rfind("Balance due after credit:")),
              "finding": "INCONSISTENT" if inconsistent else "CONSISTENT"}
    for line, quantity, unit_cents, line_cents in records:
        line_start = text.index(line)
        line_end = line_start + len(line)
        quantity_start = line_start + line.index("Qty: ") + len("Qty: ")
        unit_start = line_start + line.index("unit price: ") + len("unit price: ")
        line_total_start = line_start + line.index("line extension: ") + len("line extension: ")
        output["line_items"].append({
            "line": _citation(text, line), "quantity": quantity,
            "quantity_evidence": _citation(text, str(quantity), quantity_start, line_end),
            "unit_price_cents": unit_cents,
            "unit_price_evidence": _citation(text, f"USD {unit_cents // 100}.{unit_cents % 100:02d}", unit_start, line_end),
            "line_total_cents": line_cents,
            "line_total_evidence": _citation(text, f"USD {line_cents // 100}.{line_cents % 100:02d}",
                                             line_total_start, line_end),
        })
    task = Task(f"invoice-consistency-{seed}", "invoice_consistency", {"text": text})
    return task, output


def check_invoice_consistency(task, output):
    structure = _structure(task, output)
    if structure is None:
        return _failure("Invoice fields lack complete, exact source citations", retryable=False)
    rows, total_cents = structure
    consistent = True
    for row in rows:
        parsed = _parse_row(task.source["text"], row)
        if parsed is None:
            return _failure("A cited line item cannot be independently checked", retryable=False)
        quantity, unit_cents, line_cents = parsed
        if (row["quantity"] != quantity or row["unit_price_cents"] != unit_cents
                or row["line_total_cents"] != line_cents or quantity * unit_cents != line_cents):
            consistent = False
    consistent = consistent and sum(row["line_total_cents"] for row in rows) == total_cents
    expected = "CONSISTENT" if consistent else "INCONSISTENT"
    passed = output["finding"] == expected
    return {"score": float(passed), "passed": passed, "retryable": True,
            "method": "cited-invoice-arithmetic-v1",
            "reason": "Cited invoice arithmetic is consistent" if passed else "Finding contradicts cited invoice arithmetic"}


def noisy_invoice_check(task, output, seed, sample_size=1):
    """Verify all cited rows and totals, but sample only some row arithmetic checks."""
    structure = _structure(task, output)
    if structure is None or type(sample_size) is not int or sample_size < 1:
        return _failure("Invoice fields lack complete, exact source citations", retryable=False)
    rows, total_cents = structure
    if sum(row["line_total_cents"] for row in rows) != total_cents or output["finding"] != "CONSISTENT":
        return _failure("Cited line totals do not equal the stated total", retryable=True)
    selected = random.Random(seed).sample(range(len(rows)), min(sample_size, len(rows)))
    for index in selected:
        row = rows[index]
        parsed = _parse_row(task.source["text"], row)
        if parsed is None:
            return _failure("A sampled line item cannot be checked", retryable=True)
        quantity, unit_cents, line_cents = parsed
        if (row["quantity"] != quantity or row["unit_price_cents"] != unit_cents
                or row["line_total_cents"] != line_cents or quantity * unit_cents != line_cents):
            return _failure("Sampled line-item arithmetic failed", retryable=True)
    return {"score": 1.0, "passed": True, "retryable": True,
            "method": "noisy-invoice-spot-check-v1", "sampled_rows": selected,
            "reason": "Aggregate matched and sampled arithmetic passed; unsampled rows remain unverified"}


def _structure(task, output):
    if (not isinstance(task.source, dict) or set(task.source) != {"text"}
            or not isinstance(task.source["text"], str) or not isinstance(output, dict)
            or set(output) != {"line_items", "total_cents", "total_evidence", "finding"}
            or not isinstance(output["line_items"], list)
            or type(output["total_cents"]) is not int
            or output["finding"] not in {"CONSISTENT", "INCONSISTENT"}):
        return None
    text = task.source["text"]
    expected_lines = [match.group() for match in ITEM_RE.finditer(text)]
    rows = output["line_items"]
    if len(rows) != len(expected_lines) or not rows:
        return None
    seen = []
    fields = ("line", "quantity_evidence", "unit_price_evidence", "line_total_evidence")
    for row, expected_line in zip(rows, expected_lines):
        if (not isinstance(row, dict) or set(row) != {"line", "quantity", "quantity_evidence", "unit_price_cents",
                    "unit_price_evidence", "line_total_cents", "line_total_evidence"}
                or any(type(row[key]) is not int or row[key] < 0 for key in
                       ("quantity", "unit_price_cents", "line_total_cents"))):
            return None
        citations = {key: _read_citation(text, row[key]) for key in fields}
        if any(value is None for value in citations.values()) or citations["line"][0] != expected_line:
            return None
        line_span = row["line"]
        if any(not line_span["start"] <= row[key]["start"] < row[key]["end"] <= line_span["end"]
               for key in fields[1:]):
            return None
        seen.append(citations["line"][0])
    if len(set(seen)) != len(expected_lines):
        return None
    total_citation = _read_citation(text, output["total_evidence"])
    totals = list(TOTAL_RE.finditer(text))
    if (total_citation is None or len(totals) != 1 or total_citation[0] != totals[0].group(1)
            or total_citation[1:] != totals[0].span(1)
            or output["total_cents"] != _money_cents(total_citation[0])):
        return None
    return rows, output["total_cents"]


def _parse_row(text, row):
    line = _read_citation(text, row["line"])
    quantity_citation = _read_citation(text, row["quantity_evidence"])
    unit_citation = _read_citation(text, row["unit_price_evidence"])
    total_citation = _read_citation(text, row["line_total_evidence"])
    if any(value is None for value in (line, quantity_citation, unit_citation, total_citation)):
        return None
    quantity_match = QTY_RE.search(line[0])
    unit_match = UNIT_RE.search(line[0])
    total_match = LINE_TOTAL_RE.search(line[0])
    if not quantity_match or not unit_match or not total_match:
        return None
    if (quantity_citation[0] != quantity_match.group(1)
            or unit_citation[0] != unit_match.group(1)
            or total_citation[0] != total_match.group(1)
            or quantity_citation[1:] != (line[1] + quantity_match.start(1), line[1] + quantity_match.end(1))
            or unit_citation[1:] != (line[1] + unit_match.start(1), line[1] + unit_match.end(1))
            or total_citation[1:] != (line[1] + total_match.start(1), line[1] + total_match.end(1))):
        return None
    return int(quantity_match.group(1)), _money_cents(unit_match.group(1)), _money_cents(total_match.group(1))


def _citation(text, value, start=0, end=None):
    start = text.find(value, start, end)
    if start < 0:
        raise ValueError("Invoice evidence span was not found")
    return {"value": value, "start": start, "end": start + len(value)}


def _read_citation(text, citation):
    if (not isinstance(citation, dict) or set(citation) != {"value", "start", "end"}
            or not isinstance(citation["value"], str) or type(citation["start"]) is not int
            or type(citation["end"]) is not int or citation["start"] < 0
            or citation["end"] <= citation["start"] or citation["end"] > len(text)
            or text[citation["start"]:citation["end"]] != citation["value"]):
        return None
    return citation["value"], citation["start"], citation["end"]


def _money_cents(value):
    match = MONEY_RE.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError("Unsupported invoice money value")
    whole, cents = match.groups()
    return int(whole.replace(",", "")) * 100 + int(cents)


def _failure(reason, retryable):
    return {"score": 0.0, "passed": False, "retryable": retryable,
            "method": "cited-invoice-arithmetic-v1", "reason": reason}
