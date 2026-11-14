# Bounded operating window: proposal, not deployed

The preferred micro candidate remains unselected. Its forecast assumes **at most
360 compute hours per UTC billing month**, including provisioning, testing and
previous launches. The host-side guard adds no AWS services or credentials. It
cannot enforce a hard account-wide dollar cap. Public traffic, retained storage,
allocated IPv4, KMS, taxes and unrelated resources remain separate cost risks.

The conservative control allocates one fixed UTC window in one month. **Stopped
gaps consume the allocation too.** It deliberately trades availability for a
simple bound: 360 flexible running hours spread across a month are not offered.
The deadline is earlier than the allowance by an explicit shutdown margin.
The owner must approve the actual dates and unavailable periods before selection.

## Enforcement and accounting

`tools/aws_runtime_guard.py` validates a strict private policy, compares account,
region and instance type against IMDSv2's identity document, then atomically journals
observed uptime and a conservative elapsed allocation in root-owned SQLite.
It never reads role credentials or invokes an AWS start/stop API.

The allocation is the maximum of elapsed UTC window time, observed host uptime and
the previous recorded allocation, plus prior consumption. Unknown/stopped gaps
count as consumed. Reboots and manual starts retain the absolute deadline. Clock
rollback, invalid policy/state, changed policy, an unapproved month or an exhausted
window fail closed. A forward jump can stop early. On reboot the current boot's
uptime is added; this is conservative and **not an AWS billing meter**. The guard
does not automatically renew or start an instance next month.

CloudFormation embeds the exact reviewed Python guard in user data, before package
downloads. A root systemd service checks immediately and a timer rechecks every
30 seconds. STOP requests `systemctl poweroff`; a failed service also has
`FailureAction=poweroff`. EC2 explicitly sets `InstanceInitiatedShutdownBehavior`
to `stop`. Merely halting a guest is insufficient; see the
[EC2 shutdown documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_ChangingInstanceInitiatedShutdownBehavior.html).
The runtime installer and app start require the guard and persistent data mount.
The app UID cannot change the policy, timer, journal or host clock.

## Prepare a policy locally, without AWS operations

Copy `deploy/aws/runtime-policy.example.json` to ignored `tmp/runtime-policy.json`.
The example is intentionally invalid. Fill in the privately verified account,
approved plan SHA-256 reference, actual UTC dates and **all already-consumed
instance seconds**. A hash reference identifies owner approval; it is not itself
a signature or permission to provision. The existing explicit approval gate remains.

Window length + prior consumption + shutdown margin must be <= 1,296,000 seconds
for micro. A policy cannot cross a UTC month. No automatic allowance reset is allowed.
Use the real planned launch time as the start, including setup. If the host has
already been running, include those seconds conservatively and shorten the window.

```powershell
python -c "import json; from tools.aws_runtime_guard import validate; validate(json.load(open('tmp/runtime-policy.json'))); print('POLICY_VALID_NOT_APPROVED')"
$touchstoneRuntimePolicy = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path 'tmp/runtime-policy.json')))
```

Supply this value privately as `RuntimePolicyBase64` only in the separately approved
deployment. It contains account identity and approval terms, **no credentials**.
Do not commit real account parameters. To update the embedded guard after source
review: `python tools/render_aws_userdata.py`; validate with `--check` and rerun
Guard to bind exceptions to the new template hash.

## Required on-host acceptance after explicit provisioning approval

No on-host result is claimed yet. Before public use, in the approved cost window:

1. Verify the installed guard matches the reviewed source; policy/journal are
   root-only and the timer is enabled and active. Inspect the conservative counters
   with the guard's `--policy`/`--state` arguments **without** `--enforce`.
2. Verify startup cannot proceed without the data mount, valid policy or timer.
3. Exercise an owner-approved short deadline and observe EC2 reach **stopped**
   from a separate owner session. Verify service failure also stops the instance.
4. Within the same approved allocation, manually start and reboot once; confirm
   counters/deadline remain unchanged and the arithmetic job/audit persist.
5. Compare observed counters to the EC2 lifecycle and current billing evidence;
   include per-start minimum billing and any failed setup time conservatively.
6. Confirm a subsequent month/start outside the window stops again; no auto-start
   schedule or account upgrade exists. A new month requires fresh cost/approval review.

The 16 automated tests use temporary databases and controlled clocks. They do not
contact IMDS, shut down any host, or prove EC2 will stop under a real failure.
There is no independent off-host watchdog in this low-cost proposal. Kernel hangs,
clock tampering, root/SSM compromise, failed poweroff, or AWS control-plane delays
can defeat the host control. Initial boot failure before user data runs is also
outside it. An operator must monitor the validation window independently and stop
the instance if the guard fails. These risks and variable-usage costs prevent a
guaranteed $10 gross bound today; **provisioning remains BLOCKED** pending an
explicitly accepted cost envelope and successful approved host acceptance.
