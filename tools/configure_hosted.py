"""Masked local hosted setup. Verification retrieves model metadata; it never requests inference."""
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.config import KEYS, LOCAL_CONFIG
from touchstone.treasury import NoRedirect


def check_and_save(key, model, workspace='', credits=False, *, opener=None, path=None):
    key, model, workspace = key.strip(), model.strip(), workspace.strip()
    if (not key.startswith('sk-ant-') or not 20 <= len(key) <= 500 or any(c.isspace() for c in key)
            or not re.fullmatch(r'claude-[A-Za-z0-9._-]{1,100}', model)
            or workspace and not re.fullmatch(r'wrkspc_[A-Za-z0-9_-]{1,100}', workspace)):
        raise ValueError('A valid hosted key, model ID and optional workspace ID are required')
    if credits is not True:
        raise ValueError('Confirm the partner-credit source locally; this does not verify its balance')
    headers = {'x-api-key': key, 'anthropic-version': '2026-10-21'}
    if workspace:
        headers['anthropic-workspace-id'] = workspace
    request = urllib.request.Request('https://api.anthropic.com/v1/models/' + model, headers=headers, method='GET')
    try:
        with (opener or urllib.request.build_opener(NoRedirect()).open)(request, timeout=20) as response:
            body = response.read(200001)
        if len(body) > 200000:
            raise ValueError('Model metadata is too large')
        metadata = json.loads(body)
        if not isinstance(metadata, dict):
            raise ValueError('Model metadata must be an object')
        resolved = metadata.get('id', '')
        if metadata.get('type') != 'model' or not re.fullmatch(r'claude-[A-Za-z0-9._-]{1,100}', resolved):
            raise ValueError('Model metadata is invalid')
        capabilities = metadata.get('capabilities') or {}
        if not isinstance(capabilities, dict):
            raise ValueError('Model capability metadata is invalid')
        structured = capabilities.get('structured_outputs') or {}
        if not isinstance(structured, dict) or structured.get('supported') is False:
            raise ValueError('Model does not support the extraction schema')
    except urllib.error.HTTPError as error:
        raise ValueError(f'Hosted model verification rejected (HTTP {error.code}); no inference requested') from None
    except (OSError, ValueError, TypeError):
        raise ValueError('Hosted model metadata could not be verified; no inference requested') from None
    path = Path(path or LOCAL_CONFIG)
    raw = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(raw, dict) or any(k not in KEYS or not isinstance(v, str) for k, v in raw.items()):
        raise ValueError('Existing local configuration is invalid; preserved without changes')
    raw.update(ANTHROPIC_API_KEY=key, ANTHROPIC_MODEL=resolved, ANTHROPIC_WORKSPACE_ID=workspace,
               TOUCHSTONE_HOSTED_FUNDING_SOURCE='PARTNER_CREDITS')
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.pending')
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
        pending.chmod(0o600)
        file.write(json.dumps(raw, indent=2) + '\n')
    pending.replace(path)
    return {'label': 'MEASURED', 'model_metadata_verified': True, 'configuration_saved': True,
            'configured_model': resolved,
            'workspace_configured': bool(workspace), 'partner_credits': 'OPERATOR_DECLARED_NOT_BALANCE_VERIFIED',
            'model_inference_calls': 0, 'financial_transactions': 0}


def main():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title('Touchstone - private hosted provider setup')
    root.geometry('680x470')
    panel = ttk.Frame(root, padding=24)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Configure the existing hosted tier', font=('Segoe UI', 15)).pack(anchor='w')
    ttk.Label(panel, text='The key stays local. Verification reads model metadata only.\nNo inference, card, FX or token transaction is executed.').pack(anchor='w', pady=10)
    entries = []
    for title, masked in [('Hosted API key', True), ('Claude model ID', False), ('Workspace ID (optional for a workspace-scoped key)', True)]:
        ttk.Label(panel, text=title).pack(anchor='w')
        entry = ttk.Entry(panel, width=76, show='*' if masked else '')
        entry.pack(anchor='w', pady=(2, 9))
        entries.append(entry)
    credits = tk.BooleanVar(value=False)
    start = tk.BooleanVar(value=False)
    ttk.Checkbutton(panel, text='I confirm partner credits are available; paid validation still needs approval.', variable=credits).pack(anchor='w')
    ttk.Checkbutton(panel, text='After saving, start the local model and sellers (no purchases).', variable=start).pack(anchor='w')
    status = tk.StringVar(value='Enter credentials here, never in chat. The model ID must be available to your account.')
    ttk.Label(panel, textvariable=status, wraplength=625).pack(anchor='w', pady=12)
    messages = queue.Queue()

    def work(values, declared, launch):
        try:
            report = check_and_save(*values, credits=declared)
            if launch:
                os.environ.update(ANTHROPIC_API_KEY=values[0].strip(), ANTHROPIC_MODEL=report['configured_model'],
                    ANTHROPIC_WORKSPACE_ID=values[2].strip(), TOUCHSTONE_HOSTED_FUNDING_SOURCE='PARTNER_CREDITS')
                from tools.run_project import run
                runtime = run(start=True)
                report['services'] = {name: value['status'] for name, value in runtime['services'].items()}
        except Exception as error:
            report = {'label': 'BLOCKED', 'failure_type': type(error).__name__, 'financial_transactions': 0}
        from tools.configure_airwallex import save_status
        save_status(report, ROOT / 'tmp/hosted-setup-status.json')
        messages.put(report)

    def configure():
        button.config(state='disabled')
        status.set('Checking model metadata; no inference or purchase...')
        values = tuple(entry.get() for entry in entries)
        threading.Thread(target=work, args=(values, credits.get(), start.get()), daemon=True).start()

    def poll():
        try:
            report = messages.get_nowait()
        except queue.Empty:
            pass
        else:
            button.config(state='normal')
            if report.get('configuration_saved'):
                entries[0].delete(0, 'end')
                status.set('Verified and saved locally. ' + ('Services: ' + ', '.join(k + '=' + v for k, v in report['services'].items()) if report.get('services') else 'Start the local stack when ready.'))
            else:
                status.set('BLOCKED: check the key, accessible model, workspace and credit confirmation. No raw response or secret was logged.')
        root.after(150, poll)

    button = ttk.Button(panel, text='Verify and save configuration', command=configure)
    button.pack(anchor='w')
    root.after(150, poll)
    entries[0].focus_set()
    root.mainloop()


if __name__ == '__main__':
    main()
