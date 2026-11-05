"""Masked local repair for an existing Metal testnet RPC credential. No wallet actions."""
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.config import save_rpc
from touchstone.rpc import inspect_rpc
from tools.configure_airwallex import save_status


def check(url):
    url = url.strip()
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'rpc-testnet.metalntwx.com'
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError('Use the full HTTPS Metal testnet RPC URL from your console')
    os.environ['METAL_RPC_URL'] = url
    report = inspect_rpc()
    save_rpc(url)
    save_status({**report, 'observed_at': time.time(),
        'endpoint_fingerprint': hashlib.sha256(url.encode()).hexdigest()}, ROOT/'data/rpc-readiness.json')
    return {**report, 'label': 'MEASURED', 'configuration_saved': True,
        'money_moved': False, 'wallet_generated': False}


def main():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('Touchstone - Metal TESTNET RPC setup')
    root.geometry('620x320')
    panel = ttk.Frame(root, padding=24)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Repair the existing Metal RPC connection', font=('Segoe UI', 15)).pack(anchor='w')
    ttk.Label(panel, text='Paste the full authenticated TESTNET RPC URL from your Metal console.\nThe URL is masked. No wallet is generated and no transaction is sent.').pack(anchor='w', pady=12)
    entry = ttk.Entry(panel, show='*', width=75)
    entry.pack(anchor='w', pady=8)
    status = tk.StringVar(value='Checks chain 63825 before saving the configuration locally.')
    ttk.Label(panel, textvariable=status, wraplength=560).pack(anchor='w', pady=12)
    messages = queue.Queue()

    def worker(value):
        try:
            report = check(value)
        except Exception as error:
            report = {'label': 'BLOCKED', 'failure_type': type(error).__name__, 'transactions_sent': 0,
                'endpoint_disclosed': False, 'money_moved': False}
        save_status(report, ROOT/'tmp/metal-rpc-setup-status.json')
        messages.put(report)

    def connect():
        button.config(state='disabled')
        status.set('Checking the testnet RPC; no payment or inference request...')
        threading.Thread(target=worker, args=(entry.get(),), daemon=True).start()

    def poll():
        try:
            report = messages.get_nowait()
        except queue.Empty:
            pass
        else:
            button.config(state='normal')
            if report.get('connected'):
                entry.delete(0, 'end')
                status.set('Verified chain 63825 and saved locally. No money moved. You can close this window.')
            else:
                status.set('Blocked: check that this is the current full testnet RPC URL. No secret or raw response was logged.')
        root.after(150, poll)

    button = ttk.Button(panel, text='Verify and save testnet RPC', command=connect)
    button.pack(anchor='w')
    root.after(150, poll)
    entry.focus_set()
    root.mainloop()


if __name__ == '__main__':
    main()
