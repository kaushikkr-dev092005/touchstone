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
The intended account is owner-confirmed; identity and eligibility are **not verified**.
Required owner action: establish a non-root IAM user or role in that account with
console/CLI sign-in and the documented read-only permissions, then repeat login and
`tools/aws_preflight.py`. No root API call is permitted as a workaround.

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

## Release gates

Full final-source validation and image runtime results will be recorded here after
execution. No unrun command is a pass. A local image identifier is not a published
registry digest. Public HTTPS, SSM, EBS retention, host shutdown and outside-machine
acceptance remain **NOT RUN** until an exact compliant plan is explicitly approved.

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
