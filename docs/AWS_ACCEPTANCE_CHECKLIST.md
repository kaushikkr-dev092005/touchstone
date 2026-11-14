# AWS deployment acceptance checklist

Status: **preparation only; nothing is provisioned or approved to provision**.
The account owner is correcting `default` and will rerun the read-only preflight.
Keep PR #3 draft/unmerged. Image publication and infrastructure deployment each
require explicit approval; a green test or merged source is not that approval.

## Gate 1: account and eligibility, before requesting provisioning approval

- [ ] Owner confirms the intended account; STS identity matches it. Keep account
  identifiers and raw billing evidence private, outside Git.
- [ ] Run `python tools/aws_preflight.py --expected-account YOUR_ACCOUNT_ID`.
  Require `read_only_checks_passed:true`, Mumbai available, chosen instance offered,
  and an active existing plan. Its successful result still says provisioning is
  blocked. Never upgrade an account or try another account automatically.
- [ ] Verify promotional credit balance, expiration, eligible services and tax
  treatment in current Billing pages. Check EC2, EBS, IPv4 and KMS separately.
  A dollar balance or the word "Free Tier" is insufficient evidence.
- [ ] Verify current-month account-wide gross usage and projected unrelated costs.
  Do not use billed Cost Explorer APIs during zero-spend preparation.
- [ ] Verify the existing EBS default encryption key and organizational policy.
  After identity confirmation, read-only examples are
  `aws ec2 get-ebs-default-kms-key-id --profile default --region ap-south-1` and
  `aws kms describe-key --profile default --region ap-south-1 --key-id VERIFIED_KEY_ARN`.
  Require a same-account Mumbai enabled encryption key, permitted EBS use and
  owner-approved policy. Record its ARN privately for `EbsKmsKeyArn`.
  Do not create keys or replace a stronger account default. Count any existing
  customer-key fees/requests in the gross account forecast.
- [ ] Owner provides an actual budget email privately. Confirm the placeholder is
  not used and alerts are $5/$8/$10 on gross costs excluding credits/refunds.

## Gate 2: strict cost decision and proposed exceptions

- [ ] Recheck the dated official rates in `deploy/aws/pricing.json`; run
  `python tools/aws_cost_review.py` for reproducible Decimal arithmetic.
- [ ] Select an explicit architecture/availability window. The current always-on
  micro estimate exceeds $10 and **must not be provisioned**. Nano requires an
  already-paid plan and capacity evidence; no plan upgrade is authorized.
  The 360-hour micro proposal has no implemented scheduler: an approved stopping
  procedure, running-hour accounting and contingency are required before selection.
  IPv6-only is research, not a validated replacement.
- [ ] Forecast gross account-wide usage <= $10 including all storage, allocated
  IPs while stopped, variable usage, taxes, key costs and unrelated resources.
  Credits cannot make an over-$10 gross forecast compliant.
- [ ] Independently establish $0 out-of-pocket coverage for the full forecast and
  validity period. If taxes/services are uncovered, remain BLOCKED.
- [ ] Review the five **unsuppressed** Guard exceptions in the deployment guide:
  public web ingress, non-/32 ingress, default IGW route, HTTP(S) internet egress,
  and basic rather than detailed monitoring. Record the final decision with the
  exact template hash. No proposed exception is silently accepted.
- [ ] Review variable-traffic cost risk: reserves and AWS Budget alerts are not a
  hard billing cap. Agree on a bounded validation window/traffic exposure,
  monitoring and a stop decision before authorizing any resources.

## Gate 3: artifact and exact plan, still before provisioning

- [ ] All source changes reviewed; PR remains unmerged until separately approved.
- [ ] Run the local checks below with no live financial credentials. Record full
  source revision and template SHA-256 (CRLF normalized to LF).
- [ ] Reproduce Guard against all 43 EC2/IAM files at registry revision
  `7f7340c26ae5d5e8874651dbffeb12e0e9f505b6`. Expect only the five documented
  exception candidates; any new failure is a blocker. Raw Guard must still fail
  while exceptions are unsuppressed. Do not describe this as full compliance.
- [ ] Obtain explicit image publication approval before dispatching the manual
  workflow. No publication was performed during preparation.
- [ ] After approved publication, verify ARM64 architecture, source/OCI revision,
  exact application and Caddy digests, and anonymous image pullability. Never
  place a registry token on the host.
- [ ] Resolve the actual AL2023 ARM64 AMI, offered instance type, key permissions,
  SSM availability and capacity in the correct account. Keep changeset/resource
  creation outside zero-spend checks.
- [ ] Freeze account, region, existing plan, resource list, image digests, source
  revision, encryption key, cost calculation, credit coverage, email and exception
  decisions into the exact plan. Obtain **explicit final provisioning approval**.

```text
python -m unittest discover -s tests
python tools/check_dashboard.py
python tools/metal.py test
cfn-lint -t deploy/aws/cloudformation.json -r ap-south-1
bash -n deploy/aws/install-runtime.sh
python tools/aws_cost_review.py
python tools/scan_secrets.py
```

Resolve `deploy/aws/compose.yaml` using dummy public digests/hostname with
`docker compose -f deploy/aws/compose.yaml config --quiet`; this starts nothing.
See the deployment guide for Guard paths. Build/check the React frontend locally
when its source changes; do not confuse that with publishing a container image.

## Gate 4: execute only after that explicit approval

- [ ] Provision only the approved template and parameters, including the existing
  `EbsKmsKeyArn`. No extra wallets, models, cards, FX, API purchases or account upgrades.
- [ ] Validate resource count, encrypted disks/key, retained data policy,
  standard CPU credits, IMDSv2/hop limit 1 and ingress 80/443 only.
- [ ] Review cloud-init and SSM status. Run only the reviewed installer against
  the exact blank/known retained volume; unknown filesystems must be refused.
- [ ] Initialize the operator interactively with a masked password; no password
  in shell arguments, SSM payloads or logs. Do not mount financial credentials.
- [ ] Start the approved app explicitly. Verify the service refuses to start
  without the persistent mount/config and does not expose Python port 8089.

## Gate 5: external acceptance, no financial operations

- [ ] From outside the host, HTTPS landing, `/dashboard`, `/ledger` and
  `/control-room` load on the approved temporary hostname with a valid certificate.
- [ ] `/healthz` identifies the approved revision and
  `financial_dispatch_enabled:false`. Anonymous `/operator-api/jobs` returns 401;
  legacy `/console` and procurement mutation routes remain unavailable.
- [ ] Sign in with the operator. Confirm Secure/HttpOnly/SameSite cookies,
  expiration, rate limits, and rejection of bad Origin/Host/CSRF requests.
- [ ] Submit the supported arithmetic task `[1250,900] - 150`; result is 2000,
  verification succeeds, real SSE arrives, and external charges remain zero.
- [ ] Refresh/reconnect SSE: history remains; duplicate events do not duplicate
  work. Pause/resume and transaction inspection reflect durable backend records.
- [ ] Restart service and host; verify the same SQLite history and audit chain.
  Test offline backup/restore to a new empty directory, protecting its contents.
- [ ] Confirm missing/tampered/reused signed approvals fail using controlled local
  tests only; public deployment has no financial-dispatch capability or keys.
- [ ] Inspect memory, swap, CPU credits, bounded logs and disk growth during the
  approved window. No GPU/model process. Failed capacity checks do not authorize resizing.
- [ ] Confirm budget recipient/thresholds and gross forecast against actual billing.
  Stop validation if the approved exposure is threatened; stopping EC2 does not
  stop EBS/allocated-IP charges. Any deletion requires its own approval and backup.

Announce deployment only after every applicable gate is satisfied. Unchecked
items are pending, not passing. No new real Airwallex or Metal proof is part of
this checklist; historical evidence remains separate and unchanged.
