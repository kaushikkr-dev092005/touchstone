"""Durable, request-ID-bound Airwallex sandbox FX conversions."""
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3
import time

from .ledger import ClosingConnection, canonical


class ConversionOutcomeUnknown(RuntimeError):
    pass


class FxJournal:
    def __init__(self, path="data/airwallex-fx.sqlite"):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS conversions(
                request_id TEXT PRIMARY KEY, quote_id TEXT NOT NULL, terms TEXT NOT NULL,
                state TEXT NOT NULL, conversion TEXT, opening_balances TEXT, updated_at REAL NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def get(self, request_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM conversions WHERE request_id=?", (request_id,)).fetchone()
        return dict(row) if row else None

    def dispatch(self, request_id, quote, balances):
        terms = canonical({"quote_id": quote["quote_id"], "buy_currency": quote["buy_currency"],
                           "sell_currency": quote["sell_currency"], "dealt_currency": quote["dealt_currency"],
                           "buy_amount": str(quote["buy_amount"]), "sell_amount": str(quote["sell_amount"]),
                           "conversion_date": quote.get("conversion_date")})
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM conversions WHERE request_id=?", (request_id,)).fetchone()
            if row:
                if row["quote_id"] != quote["quote_id"] or row["terms"] != terms:
                    raise ValueError("request_id is already bound to different conversion terms")
                return dict(row), False
            db.execute("INSERT INTO conversions VALUES(?,?,?,?,?,?,?)",
                       (request_id, quote["quote_id"], terms, "DISPATCHING", None,
                        canonical(balances), time.time()))
        return self.get(request_id), True

    def update(self, request_id, state, conversion=None):
        with self.connect() as db:
            db.execute("UPDATE conversions SET state=?,conversion=?,updated_at=? WHERE request_id=?",
                       (state, canonical(conversion) if conversion is not None else None, time.time(), request_id))


def execute_conversion(client, journal, quote, request_id):
    """Post at most once; uncertain outcomes are looked up, never replayed."""
    if not isinstance(quote, dict) or not quote.get("quote_id") or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id or ""):
        raise ValueError("A saved Airwallex quote is required")
    prior = journal.get(request_id)
    if prior:
        journal.dispatch(request_id, quote, json.loads(prior["opening_balances"]))
        if prior["state"] in {"SCHEDULED", "SETTLED", "CANCELLED", "OVERDUE", "REJECTED"}:
            return json.loads(prior["conversion"]) if prior["conversion"] else {"request_id": request_id, "state": prior["state"]}
        existing = client.conversions_by_request_id(request_id)
        if len(existing) > 1:
            raise ValueError("Airwallex returned multiple conversions for one request_id")
        if existing:
            conversion = existing[0]
            journal.update(request_id, conversion.get("status", "UNKNOWN"), conversion)
            return conversion
        journal.update(request_id, "UNKNOWN")
        raise ConversionOutcomeUnknown("Conversion may have been submitted; request_id lookup found no record. Do not submit a new conversion.")

    opening = client.current_balances()
    _, created = journal.dispatch(request_id, quote, opening)
    if not created:
        raise ConversionOutcomeUnknown("Existing request_id must be reconciled before retry")
    try:
        conversion = client.create_conversion(quote, request_id)
    except Exception as error:
        try:
            existing = client.conversions_by_request_id(request_id)
        except Exception:
            existing = []
        if len(existing) == 1:
            conversion = existing[0]
        else:
            status = "REJECTED" if getattr(error, "status", None) in {400, 401, 403, 404, 422} else "UNKNOWN"
            journal.update(request_id, status)
            if status == "REJECTED":
                raise
            raise ConversionOutcomeUnknown("Conversion outcome is unresolved; request_id lookup found no record. Do not submit a new conversion.") from None
    if conversion.get("request_id") != request_id:
        journal.update(request_id, "UNKNOWN", conversion)
        raise ConversionOutcomeUnknown("Airwallex response did not echo the requested request_id")
    state = conversion.get("status")
    if state not in {"SCHEDULED", "SETTLED", "CANCELLED", "OVERDUE"}:
        journal.update(request_id, "UNKNOWN", conversion)
        raise ConversionOutcomeUnknown("Airwallex returned an unrecognized conversion status")
    journal.update(request_id, state, conversion)
    return conversion


def spend_report(client, journal, request_id):
    local = journal.get(request_id)
    conversions = client.conversions_by_request_id(request_id)
    history = client.conversion_balance_history(request_id)
    balances = client.current_balances()
    report = {"mode": "AIRWALLEX_SANDBOX", "request_id": request_id,
              "wallet_balances": _balance_summary(balances), "conversion": None,
              "balance_history": [], "local_state": local["state"] if local else "NO_LOCAL_OPERATION",
              "reconciliation": "NOT_RECONCILED"}
    if not conversions:
        report["reconciliation"] = "PENDING_OR_NOT_FOUND"
        return report
    if len(conversions) != 1:
        report["reconciliation"] = "MISMATCH_MULTIPLE_CONVERSIONS"
        return report
    conversion = conversions[0]
    report["conversion"] = {key: conversion.get(key) for key in
        ("conversion_id", "request_id", "status", "buy_currency", "buy_amount", "sell_currency", "sell_amount", "client_rate", "quote_id")}
    related = [row for row in history if row.get("source_type") == "CONVERSION"
               and row.get("source") == conversion.get("conversion_id")]
    report["balance_history"] = [{key: row.get(key) for key in
        ("id", "source", "source_type", "transaction_type", "currency", "amount", "balance", "posted_at")}
        for row in related]
    if conversion.get("status") != "SETTLED":
        report["reconciliation"] = "PENDING_SETTLEMENT" if conversion.get("status") == "SCHEDULED" else "NOT_SETTLED"
        return report
    if not local:
        report["reconciliation"] = "MISMATCH_NO_LOCAL_OPERATION"
        return report
    terms = json.loads(local["terms"])
    terms_match = (conversion.get("quote_id") == terms["quote_id"]
                   and conversion.get("sell_currency") == terms["sell_currency"]
                   and conversion.get("buy_currency") == terms["buy_currency"]
                   and _equal_amount(conversion.get("sell_amount"), terms["sell_amount"])
                   and _equal_amount(conversion.get("buy_amount"), terms["buy_amount"]))
    if not terms_match:
        report["reconciliation"] = "MISMATCH_LOCAL_TERMS"
        return report
    sell = [row for row in related if row.get("transaction_type") == "CONVERSION_SELL"]
    buy = [row for row in related if row.get("transaction_type") == "CONVERSION_BUY"]
    match = (len(sell) == 1 and len(buy) == 1
             and sell[0].get("currency") == conversion.get("sell_currency")
             and buy[0].get("currency") == conversion.get("buy_currency")
             and _equal_amount(sell[0].get("amount"), conversion.get("sell_amount"))
             and _equal_amount(buy[0].get("amount"), conversion.get("buy_amount")))
    report["reconciliation"] = "MATCHED_WALLET_HISTORY" if match else "MISMATCH_WALLET_HISTORY"
    return report


def _balance_summary(balances):
    return [{key: row.get(key) for key in
             ("account_type", "currency", "available_amount", "pending_amount", "reserved_amount", "total_amount")}
            for row in balances if row.get("account_type") == "cash"]


def _equal_amount(first, second):
    try:
        return abs(Decimal(str(first))) == abs(Decimal(str(second)))
    except (InvalidOperation, TypeError, ValueError):
        return False
