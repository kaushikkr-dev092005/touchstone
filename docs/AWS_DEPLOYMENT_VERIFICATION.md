# AWS deployment verification

Status: **BLOCKED, not deployed**. PR #3 stays draft and unmerged. No images have
been published, no AWS resources provisioned and no financial operations performed.

## Errors resolved locally

The Windows/Python 3.11 login failure was reproduced at a calendar-minute boundary:
five incorrect logins at 59.9 seconds returned 401, then a valid password at 60.1
incorrectly returned 200. Fixed-minute buckets were the cause. Durable rolling
60-second windows now use a monotonic elapsed clock, serialized SQLite updates
and conservative restart/migration handling. The failed-attempt limit stays five.
The original test forces this boundary deterministically; expiry still permits a
legitimate login. Eight repetitions of that test and 28 operator tests passed on
Windows/Python 3.11. A bounded unread-body drain also preserves 401/429 responses
on Windows instead of resetting a socket closed with an unread POST body.

The AWS helper now rejects root sessions before cloud access and rejects root or
unverifiable STS identities. An explicitly approved browser sign-in completed but
returned root again. The owner confirmed there is no non-root identity available.
The owner changed the intended target to account ending **0507**. The local
profile belongs to another account and remains root. STS identity and eligibility
for the intended account are **not verified**.
Required owner action: establish a non-root IAM user or role in that account with
console/CLI sign-in and the documented read-only permissions, then repeat login and
`tools/aws_preflight.py`. No root API call is permitted as a workaround.

## Source changes

- `touchstone/operator_auth.py`, `operator_server.py`: durable rolling throttles,
  controlled clocks, safe bounded rejection responses.
- `tools/aws_preflight.py`: credential-source metadata, root refusal and strict
  non-root identity verification before further read-only checks.
- `tools/aws_runtime_guard.py`, `render_aws_userdata.py`, `deploy/aws/bootstrap.sh`,
  `cloudformation.json`, `install-runtime.sh`, `runtime-policy.example.json`:
  embedded root-owned stopping window, durable counters and mount/start checks.
- `deploy/aws/compose.yaml`, `Caddyfile`, `deploy/operator/Dockerfile`: separate
  non-root proxy, capability removal, exact base digests, correct UID/GID,
  required Node runtime library and frontend Python command.
- `tools/run_operator.py`: graceful SIGTERM and removal of cloud/financial env vars.
- `tools/build_aws_image.py`, `check_aws_container.py`: committed-source local
  ARM64 build and isolated real-backend acceptance; no publication/provisioning.
- `tools/check_operator_workspace.py`, `validate_release.py`: strip AWS credentials
  from zero-spend validation children.
- `tests/test_operator_workspace.py`, `test_aws_deployment.py`,
  `test_aws_runtime_guard.py`: clock/migration/concurrency, identity and runtime coverage.
- AWS plan/pricing/Guard reports and deployment documentation: actual results,
  cost/approval blockers and exact owner acceptance steps. No financial evidence changed.

## Runtime changes

The existing single-host architecture is preserved. Caddy runs as a separate
unprivileged UID with all capabilities dropped; only proxy 80/443 are published.
Python remains private. Both containers have graceful stopping intervals. The
operator handles SIGTERM and strips AWS/financial environment credentials.

The preferred bounded-hours micro proposal has an embedded, root-owned operating
window guard with 16 controlled tests. It includes prior use, stopped gaps, restart
accounting, expiry, failure and month rollover. See [the precise limitations and
host acceptance steps](AWS_RUNTIME_GUARD.md). It is not an independent AWS billing
meter or hard account-wide spending cap. It has not been tested on EC2.

## Security and cost gates

Guard remains **FAIL: 23 pass, 15 skip, 5 fail**, unsuppressed. The three actionable
original findings stay fixed; five public-network/basic-monitoring exception
candidates require owner approval against the exact template hash in
[`guard-review.json`](../deploy/aws/guard-review.json). None is accepted implicitly.

The offline Mumbai forecasts remain $11.71472 always-on micro (**over budget**),
$9.13424 micro at most 360 hours, and $9.21488 always-on nano (conditional paid-plan
and capacity eligibility). These include full-month allocated IPv4 and both EBS
volumes, a planning tax reserve and variable reserve. Credits are never deducted
from gross costs. Actual account-wide usage, KMS/tax costs, promotional eligibility,
credit balance/expiry and $0 cash coverage remain **BLOCKED**. No architecture is
selected. Budget alerts at $5/$8/$10 are notifications, not a hard cap.

## Proposed resources (not provisioned)

The unchanged resource inventory is: Vpc, InternetGateway, GatewayAttachment,
Subnet, RouteTable, PublicRoute, RouteAssociation, SecurityGroup, HostRole,
HostProfile, Instance, PublicIp, IpAttachment, DataVolume, DataAttachment,
and UsageBudget. Root storage is attached to Instance; no KMS key, scheduler,
managed database, load balancer or paid networking resource is added.

## Executed local container proof

**PASS**, ARM64 image built from source `79287854c92258fe7eb7f4f2e83735602e974e65`.
The first build found Debian's existing `operator` group; the next exposed the
missing `python` alias in the frontend build stage. Both were fixed. The final
build compiles the frontend and verifies ARM64/OCI source identity. Its local-only
image identifier is `sha256:c291f5eea0d9234806f2122ae287055c416bfa45cfe8efa6225d2b0b6d8ccb41`;
**this is not a published registry digest or an approved deployment artifact**.

`tools/check_aws_container.py` passes with external networking disabled and no
published ports. The test drives actual HTTP over container loopback, verifies
all four public frontend routes, bad/correct login, 429 after five attempts,
CSRF rejection, arithmetic result 2000, genuine SSE, zero ledger charges, audit
integrity, retained SQLite/session history after real container restart, and the
absence of a payment API. Node 22 runs as the app user. Temporary test volumes and
containers are removed. An earlier harness attempted host publishing on an
internal Docker network; it was corrected to container-loopback testing instead
of allowing outbound access. This is local proof, not external AWS acceptance.

Caddy ARM64 configuration validation also passes as UID 10002, with dropped
capabilities, read-only root and network disabled. Candidate digest:
`caddy@sha256:4e2425f6009577e7c651010f16679c28f7d12df3e7b1914f941a7a3370746b3c`.
It is not owner-approved yet. Syntax validation is not public certificate issuance.

## Release gates

The public PR head remains `79287854c92258fe7eb7f4f2e83735602e974e65`.
GitHub PR workflow [43628947781](https://github.com/kaushikkr-dev092005/touchstone/actions/runs/43628947781)
and push workflow [43628943192](https://github.com/kaushikkr-dev092005/touchstone/actions/runs/43628943192)
both passed Ubuntu/Windows with Python 3.11 and 3.12. These results do not cover
subsequent local commits. Publishing those commits requires owner approval.

Local committed source `8734c162c8b1d4de955394cb15333131db2dc1bd` passed
518 Python tests on Windows/Python 3.12, 67 Node tests, frontend TypeScript/Vite
build, and all five controlled milestone proofs in a disposable source archive.
The controlled proof scripts now supply real ephemeral test-human signatures
through the existing test-only fixture. Their network fence remains enabled.
Canonical historical results under `bench/` were not regenerated or changed.

The first aggregate browser run failed because the existing dashboard QA helper
did not accept its caller's `label=` selection argument. The helper now forwards
that argument to Playwright without changing the UI or weakening an assertion.
The failed dashboard command and all subsequent browser commands were executed
again and passed: dashboard/128 transaction rows, signed-mandate three-state
proof, motion, release/reconnection, shared website and operator workspace.
Operator QA measured result 2000, real events, refresh/restart persistence and
valid audit history, with zero external requests or financial calls. These are
local controlled measurements, not public AWS acceptance.

The same committed source also passed a fresh ARM64 build and network-isolated
container acceptance. Its local image identifier is
`sha256:bed0752295d8ca205701486d371bc7303a60a861c1b138fe8d9debaf820f2054`.
It is not a published registry manifest. Caddy's candidate manifest was retrieved
anonymously, its digest verified and Linux/ARM64 support confirmed; an EC2 pull
has not been attempted. The image publication workflow is not present on the
default branch and has not been dispatched.

Public Mumbai micro/nano compute and gp3 rates were rechecked on 2026-11-15;
the offline forecasts above are unchanged. This verifies public rates only,
not account credits, taxation, unrelated consumption or cash coverage.

After committing fixes, rerun the complete isolated release gate:

```powershell
python tools/validate_release.py --ref HEAD --browser --frontend --output tmp/aws-release-current.json
```

The generated local report records the exact source SHA, archive/log hashes,
each stage's exit code and overall result. Do not treat a failed earlier report
as passing because an individual stage was subsequently repaired. No unrun
command is a pass. Public HTTPS, SSM, EBS retention, host shutdown and
outside-machine acceptance remain **NOT RUN** until an exact compliant plan is
explicitly approved.

The reproducible commands and complete resource/backup/teardown requirements are
in [the deployment guide](AWS_DEPLOYMENT.md) and [acceptance checklist](AWS_ACCEPTANCE_CHECKLIST.md).
Use `tools/build_aws_image.py` for a local committed-source ARM64 build and
`tools/check_aws_container.py --revision FULL_COMMIT` for isolated container acceptance.
Neither publishes an image or deploys AWS infrastructure.

## Safe rollback

Before any future update, stop the app, make and verify an offline SQLite backup,
and preserve the operator config/TLS state privately. Revert only to an approved
compatible image digest; do not downgrade schema without its compatible backup.
An exhausted operating policy cannot be bypassed to roll back: stop and obtain
a revised approved window. Host shutdown is `poweroff` with EC2 behavior `stop`.
Stopping compute retains full EBS/allocated-IP charges. Stack deletion retains the
data disk and its charges; remove it or release the IP only with separate deletion
approval after a verified backup. Retiring the hostname/session before releasing
its IP avoids takeover. No rollback or deletion has been executed.
