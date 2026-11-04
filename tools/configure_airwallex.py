"""Masked local sandbox setup. Never accepts credentials as command arguments."""
import argparse
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.airwallex_doctor import inspect
from touchstone.treasury import BASE_URL

KEYS = ('AIRWALLEX_CLIENT_ID', 'AIRWALLEX_API_KEY', 'AIRWALLEX_ACCOUNT_ID')


def save_status(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    pending.replace(path)


def check(values):
    if set(values) != set(KEYS) or any(not isinstance(v, str) or not v.strip() for v in values.values()):
        raise ValueError('All three scoped-key fields are required')
    for key, value in values.items():
        os.environ[key] = value.strip()
    os.environ['AIRWALLEX_BASE_URL'] = BASE_URL
    return inspect(probe_reads=True)


def remember():
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
        for key in (*KEYS, 'AIRWALLEX_BASE_URL'):
            winreg.SetValueEx(registry, key, 0, winreg.REG_SZ, os.environ[key])


def check_saved():
    import winreg
    values = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
        for key in KEYS:
            values[key] = winreg.QueryValueEx(registry, key)[0]
    report = check(values)
    report['configuration_source'] = 'WINDOWS_USER_ENVIRONMENT_VIA_PROCESS'
    return report


def publish_readiness(report):
    save_status({'mode': 'SANDBOX', 'authenticated': report['authenticated'],
        'observed_at': report['observed_at'], 'account_context_configured': report['account_context_valid'],
        'balance_read': report['reads'].get('balances', {}).get('allowed', False),
        'fx_conversions_read': report['reads'].get('conversions', {}).get('allowed', False),
        'global_accounts_read': False, 'checkout_sessions_read': False,
        'writes_performed': False, 'money_moved': False, 'source': 'SCOPED_KEY_READ_ONLY_SETUP'},
        ROOT/'data/airwallex-readiness.json')


def open_dashboard():
    with socket.socket() as sock:
        running = sock.connect_ex(('127.0.0.1', 8088)) == 0
    if not running:
        subprocess.Popen([sys.executable, '-m', 'touchstone', 'serve'], cwd=ROOT,
            env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    webbrowser.open('http://127.0.0.1:8088/')
    return running


def gui(status_path):
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('Touchstone — Airwallex sandbox setup')
    root.geometry('600x510')
    root.resizable(False, False)
    panel = ttk.Frame(root, padding=24)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Connect your existing scoped sandbox key', font=('Segoe UI', 15)).pack(anchor='w')
    ttk.Label(panel, text='Copy all three fields from the scoped key/account details.\nThe API key stays masked and is never written to project files.').pack(anchor='w', pady=(8,16))
    entries = {}
    for key, label in zip(KEYS, ('Client ID for the scoped key', 'Scoped API key (not the Client ID)', 'Sandbox account ID')):
        ttk.Label(panel, text=label).pack(anchor='w')
        entry = ttk.Entry(panel, show='*' if key == 'AIRWALLEX_API_KEY' else '', width=70)
        entry.pack(anchor='w', pady=(4,10))
        entries[key] = entry
    persist = tk.BooleanVar(value=True)
    ttk.Checkbutton(panel, text='Save in this Windows user’s environment after verification', variable=persist).pack(anchor='w', pady=6)
    status = tk.StringVar(value='Sandbox only. Authentication and reads; no financial operation.')
    ttk.Label(panel, textvariable=status, wraplength=540).pack(anchor='w', pady=12)
    messages = queue.Queue()

    def work(values, should_save):
        try:
            report = check(values)
            report['configuration_source'] = 'MASKED_LOCAL_FORM_PROCESS_ENVIRONMENT'
            report['user_environment_saved'] = False
            if report['read_probe'] == 'PASS':
                if should_save:
                    remember()
                    report['user_environment_saved'] = True
                publish_readiness(report)
            save_status(report, status_path)
            messages.put(report)
        except Exception as error:
            report = {'label': 'BLOCKED', 'error_type': type(error).__name__, 'money_moved': False,
                      'writes_performed': False, 'values_disclosed': False}
            save_status(report, status_path)
            messages.put(report)

    def connect():
        button.config(state='disabled')
        launch.config(state='disabled')
        status.set('Checking sandbox authentication and read scopes…')
        values = {key: entry.get() for key, entry in entries.items()}
        threading.Thread(target=work, args=(values, persist.get()), daemon=True).start()

    def show_dashboard():
        running = open_dashboard()
        status.set('Dashboard opened. '+('An existing server was kept running; restart it from a new terminal to load changed credentials.' if running else 'Started with the verified scoped-key environment.'))

    button = ttk.Button(panel, text='Verify and configure sandbox', command=connect)
    button.pack(anchor='w')
    launch = ttk.Button(panel, text='Open Touchstone dashboard', command=show_dashboard, state='disabled')
    launch.pack(anchor='w', pady=8)

    def poll():
        try:
            report = messages.get_nowait()
        except queue.Empty:
            pass
        else:
            button.config(state='normal')
            if report.get('read_probe') == 'PASS':
                entries['AIRWALLEX_API_KEY'].delete(0, 'end')
                status.set('Verified: authentication, balances, balance history and conversion reads. No money moved. You can open the dashboard.')
                launch.config(state='normal')
            elif 'CLIENT_ID_IS_NOT_AN_API_KEY' in report.get('blockers', []):
                status.set('Client ID and API key are identical. Enter the actual secret from your existing scoped key.')
            elif report.get('read_probe') == 'BLOCKED_AUTHENTICATION':
                status.set('Sandbox rejected authentication. Use the scoped key’s matching Client ID, secret and authorized account; the disabled admin key cannot be used.')
            else:
                status.set('Blocked: check account ID, Balances Read and Conversion Read/Write. No credentials or raw responses were logged.')
        root.after(150, poll)

    root.after(150, poll)
    entries['AIRWALLEX_CLIENT_ID'].focus_set()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-saved', action='store_true', help='Read Windows user environment; print only redacted sandbox checks')
    parser.add_argument('--open-dashboard', action='store_true', help='Open the dashboard after --check-saved passes')
    parser.add_argument('--status', default=str(ROOT/'tmp/airwallex-setup-status.json'))
    args = parser.parse_args()
    if args.open_dashboard and not args.check_saved:
        parser.error('--open-dashboard requires --check-saved')
    if args.check_saved:
        try:
            report = check_saved()
            if report.get('read_probe') == 'PASS':
                publish_readiness(report)
                if args.open_dashboard:
                    report['existing_dashboard_kept'] = open_dashboard()
                    report['dashboard_url'] = 'http://127.0.0.1:8088/'
            save_status(report, args.status)
            print(json.dumps(report, indent=2))
            return 0 if report.get('read_probe') == 'PASS' else 2
        except Exception as error:
            print(json.dumps({'label': 'BLOCKED', 'error_type': type(error).__name__, 'values_disclosed': False}))
            return 2
    gui(args.status)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
