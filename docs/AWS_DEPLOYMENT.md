# AWS preparation â€” not provisioned

No AWS resource, account upgrade, budget subscription, inference purchase or bank
operation has been created. The existing Sites deployment remains unchanged.
The latest local preflight (14 November 2026) returns **AWS_ACCOUNT_MISMATCH**.
AWS CLI 2.40.3 is installed outside `PATH`; the helper now discovers its standard
Windows installation location. A real read-only STS request succeeded, but
`default` did not match the account in the operator's earlier console link.
The helper stopped before region, instance-offering or credit queries. Do not
silently switch accounts or change `default`; confirm the intended identity first.
The supplied Cost Explorer URL alone is not an authenticated CLI session.

## Approved preparation scope

Use only the existing `default` profile after verifying the intended account.
Deployment region: `ap-south-1`. Monthly gross AWS usage ceiling: **$10**;
out-of-pocket target: **$0**, subject to verified credit eligibility. No automatic
account upgrade, provisioning, payment, funding, card creation or paid inference.
The previous $4.50 Claude cap is separate and remains unchanged.

`deploy/aws/plan.json` records the current **unapproved** plan and missing gates.
Do not execute the CloudFormation deployment until identity, credits, actual
account costs, final artifact digests and a compliant estimate are verified and
the operator explicitly approves that exact final plan.

## Architecture and security boundary

- One small ARM64 EC2 host in a dedicated VPC/public subnet. No load balancer,
  NAT gateway, ECS/EKS, RDS, CloudFront, Route 53 zone or GPU instance.
- Caddy exposes only 80/443. Python port 8089, SQLite and Docker are not public.
  The public website/dashboard and authenticated `/control-room` use one origin.
- SSM manages the host; no SSH port/key pair. The instance role has only the AWS
  managed SSM core policy. IMDSv2 and hop limit 1 restrict container metadata access.
- Encrypted 8 GiB root disk and separate encrypted 8 GiB retained data volume.
  SQLite, operator configuration and TLS state persist. Data is never formatted
  unless the exact approved EBS volume is blank; unknown filesystems are refused.
- The application runs as UID 10001, with read-only root, dropped capabilities,
  memory/process limits and a protected data mount. Images must be ARM64 and
  pinned by digest; the application revision label must match the approved source.
- No AWS, Airwallex, Claude or payment-wallet secrets are mounted in the app.
  The existing Node libraries support protected read-only quote validation.
  Remote financial dispatch remains disabled. This does not move a live payer
  into the public service or make Visa onboarding complete.
- The sandbox merchant remains the existing separate HTTPS service. Caddy redirects
  `/merchant` there; merchant OAuth/keys are not copied into AWS.

The host administrator and a fully compromised host remain outside the app's
signature-security boundary. This single-host prototype is not highly available.

## Cost review: a gate, not a promise of free hosting

Observed public Mumbai Linux prices on 14 November 2026 are $0.0056/hour for
`t4g.micro` and $0.0028/hour for `t4g.nano` from the
[AWS public EC2 pricing feed](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20%28Mumbai%29/Linux/index.json).
One public IPv4 address costs $0.005/hour per
[AWS VPC pricing](https://aws.amazon.com/vpc/pricing/).

| Planning item, 744-hour month | Free Plan candidate: micro | Conditional nano alternative |
|---|---:|---:|
| Compute | $4.1664 | $2.0832 |
| One public IPv4 | $3.7200 | $3.7200 |
| 16 GiB storage allowance at $0.12/GiB-month | $1.9200 | $1.9200 |
| Fixed subtotal before reserves | $9.8064 | $7.7232 |
| 20% tax/planning reserve plus $0.50 other-usage reserve | $2.46128 | $2.04464 |
| Conservative planning total | **$12.26768 â€” over cap** | **$9.76784 â€” conditional** |

Storage uses a conservative allowance, **not a verified regional gp3 quote**.
The tax reserve is not a determination of the account's actual tax treatment.
Actual Free Tier entitlements, current month usage, egress, retained storage,
credit-covered services and tax coverage require account-level verification.
No credit deduction is assumed in this table. Neither option guarantees a $0 bill.

AWS currently lists `t4g.micro` among the instance types available under the newer
Free Tier plan, not `t4g.nano`; see the
[EC2 launch parameters](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-launch-parameters.html).
The template defaults to micro. Nano is only a conditional alternative for an
**already paid** account whose credits and permissions are verified. Never upgrade
the account to use it. If the account is on the Free Plan, reprice its actual
entitlements and resolve the conservative over-cap estimate before requesting
final approval. Never silently resize or shorten uptime to fit the budget.

CPU credit mode is `standard`, preventing surplus CPU-credit billing; exhausted
credits reduce performance. All compilation occurs off-host. The tiny-host capacity
and memory limits remain unverified until an approved runtime smoke check.

The CloudFormation budget is account-wide **gross usage**, with credits/refunds
excluded and taxes included, so promotional credits do not hide consumption.
Alerts are configured at 50%, 80%, 100% ($5/$8/$10); the operator must provide the
recipient email and confirm delivery. **Budget alerts do not enforce a hard cap**,
and billing notifications may lag usage. See
[AWS Budgets limitations](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
Existing unrelated account usage can consume this budget. No budget is created now.
`[MY AWS BILLING EMAIL]` is a placeholder, not a configured recipient; replace it
privately with a real email in the approved deployment parameters. The template
requires a valid email and does not commit the recipient to source control.

## Authenticate and perform read-only checks

Install the [official AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
and authenticate locally using the account owner's existing supported login flow.
With a current CLI, `aws login --profile default` opens the existing browser console
sign-in flow and uses temporary credentials; see [AWS console-credential login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).
For an account already using IAM Identity Center, `aws configure sso --profile default`
and `aws sso login --profile default` are options. Do not create an IAM account or
upgrade a plan merely to enable this flow. Never paste access keys or tokens in chat.

From the repository root in PowerShell, after the official CLI is available:

```powershell
$touchstoneAccountId = Read-Host 'Intended 12-digit AWS account ID'
python tools/aws_preflight.py --expected-account $touchstoneAccountId
```

This tool accepts only `default`, verifies STS identity, checks Mumbai opt-in and
instance offerings, then calls the read-only Free Tier account-plan API in
`us-east-1` (billing endpoint). It ignores environment credentials and endpoint
overrides. It never calls Cost Explorer's billed API or any provisioning/write API.
Missing authentication/permissions remain explicit blockers. The resulting report
is ignored at `tmp/aws-preflight.json` and contains no credential values.
Exit `0` means only that all supported read checks completed for the intended
account and an active plan. `provisioning_authorized` remains `false`, and credit
eligibility and final approval remain blocked. Exit `2` means a check is missing,
failed or ineligible, including an account mismatch discovered by the billing API.
Missing `default` authentication returns `AWS_PROFILE_NOT_CONFIGURED`; an installed
profile with no CLI returns `AWS_CLI_NOT_INSTALLED`. Neither is a successful check.
The helper checks `PATH` and standard Windows CLI v2 installation directories;
it does not install software, alter your profile or persistently change `PATH`.

The equivalent individual read-only CLI checks are below. Use the helper above
for account/environment isolation: unlike these raw commands, it strips inherited
AWS credential and endpoint overrides and stops if identity does not match. If
running them manually, first remove such overrides in your local shell and verify
the STS account before continuing. Do not share credentials or full debug output.
If `aws` is not on `PATH`, replace it with the full path to your installed `aws.exe`.

```powershell
aws sts get-caller-identity --profile default --region ap-south-1 --no-cli-pager --output json
aws ec2 describe-regions --profile default --region ap-south-1 --region-names ap-south-1 --no-cli-pager --output json
aws ec2 describe-instance-type-offerings --profile default --region ap-south-1 --location-type region --filters Name=instance-type,Values=t4g.micro --no-cli-pager --output json
aws freetier get-account-plan-state --profile default --region us-east-1 --no-cli-pager --output json
```

The [Free Tier account-plan API](https://docs.aws.amazon.com/cli/latest/reference/freetier/get-account-plan-state.html)
can return plan status, remaining credits and expiration. A balance does not prove
that every deployment service or tax is credit-covered. The owner must check the
current [Billing credits](https://console.aws.amazon.com/billing/home#/credits)
and current month Bills pages, including applicable service restrictions and
expiration. The provided Cost Explorer link ends in October 2026 and does not
establish current November usage. This has not been independently verified.

Read-only permissions needed: STS caller identity, `ec2:DescribeRegions`,
`ec2:DescribeInstanceTypeOfferings`, and `freetier:GetAccountPlanState`.
CloudFormation/IAM/EC2/Budgets provisioning permissions have not been verified.

## Build and freeze the artifact before final approval

The manual `.github/workflows/aws-image.yml` accepts a full reviewed commit already
merged into master. It builds ARM64 with the existing Dockerfile and publishes an
image to GHCR using GitHub's scoped workflow token, not AWS credentials.
**The workflow has not been dispatched.** No image digest is fabricated.

After source review and authorization to publish that image, run the workflow,
review its scan/build output, verify the image is publicly pullable without an
account key, and record its immutable digest and OCI source revision in the plan.
Resolve and review a Caddy ARM64 image digest too. Do not store a GHCR token on EC2.

The source, image digests, account plan, alert email, expected monthly gross cost,
credit coverage and exact proposed resources must be included in final approval.

## Provision only after the final explicit approval

The following are **future execution instructions**, not commands run during
preparation. Keep `ExpectedAccountId`, `VerifiedAccountPlan`, image digest and
source commit equal to the approved plan. The template itself is not a cost limiter.

```text
aws cloudformation validate-template --profile default --region ap-south-1 --template-body file://deploy/aws/cloudformation.json
aws cloudformation deploy --profile default --region ap-south-1 --stack-name touchstone --template-file deploy/aws/cloudformation.json --capabilities CAPABILITY_IAM --parameter-overrides ExpectedAccountId=APPROVED_ACCOUNT VerifiedAccountPlan=VERIFIED_EXISTING_PLAN ApplicationImage=APPROVED_PUBLIC_ARM64_IMAGE_DIGEST SourceRevision=APPROVED_FULL_COMMIT BudgetEmail=APPROVED_ALERT_EMAIL
aws cloudformation describe-stacks --profile default --region ap-south-1 --stack-name touchstone
```

No instance/account upgrade, transfer, new wallet or financial API call is part of
these instructions. CloudFormation completion proves infrastructure provisioning,
not application readiness. Check cloud-init and SSM readiness separately.

## Temporary HTTPS and explicit operator setup

The allocated Elastic IP yields `https://PUBLIC_IP.sslip.io`. This shared public
DNS service maps the embedded IP without buying a domain; see
[sslip.io documentation](https://sslip.io/). It is a temporary third-party dependency,
not an owned production domain. TLS issuance and DNS have not been tested here.
If DNS or CA validation fails, stop; do not provision a paid fallback automatically.

Open the approved instance using Session Manager. Download the reviewed
`install-runtime.sh` from the approved commit, verify its SHA-256 against the
reviewed local file, and run it as root with the stack's exact data-volume ID,
application image, Caddy digest, source commit and temporary hostname. It refuses
unknown volumes and sets up encrypted-volume persistence, bounded swap, Compose,
and a systemd unit. It **does not create an operator identity or start the app**.
Docker Compose 5.6.0 ARM64 is checksum-pinned in the installer.

From `/opt/touchstone`, initialize the operator interactively:

```text
sudo docker compose --env-file runtime.env -f compose.yaml run --rm -it --no-deps operator python tools/run_operator.py init --config /var/lib/touchstone/operator-config.json --origin https://PUBLIC_IP.sslip.io --username operator --environment DEMO
sudo systemctl start touchstone.service
```

The initializer uses a masked password prompt. Never place passwords in SSM Run
Command payloads, shell arguments, environment variables, build arguments or logs.
The runtime volume contains only the operational database, operator password
hash/configuration and audit; never copy a private payer wallet into it.

## Required external acceptance checks

Before announcing deployment:

1. HTTPS landing, dashboard, ledger and `/control-room` return successful pages.
2. `/healthz` identifies the reviewed source and `financial_dispatch_enabled:false`.
3. Anonymous `/operator-api/jobs` returns 401; legacy `/console` and private
   procurement routes remain unavailable.
4. Browser login uses Secure/HttpOnly/SameSite cookies and rejects bad CSRF/Origin.
5. Create the arithmetic task `[1250,900] - 150`; verify actual result 2000, zero
   external charges, real SSE and persisted history after refresh.
6. Restart the service and host; verify audit/history persist and the data-volume
   mount is required before Docker starts. Do not expose private data in logs.
7. Check memory, swap and CPU-credit behavior; no model or GPU process runs here.
   If capacity is inadequate, stop and obtain a revised cost plan before resizing.
8. Missing/tampered approval tests remain no-spend; no live financial proof is run.
9. Verify the budget recipient and all three alert thresholds in AWS Billing.

## Backup, rollback and teardown

Stop the operator before using its existing backup tool so its owner lease is
released. The image now includes `tools/operator_backup.py`; back up `jobs` into a
new file outside that subdirectory, protect it, export it securely and test restore
into an empty directory. See [the operational backup guide](LIVE_DEPLOYMENT.md).
Back up operator configuration and Caddy TLS state separately with appropriate
access protection. No S3 bucket or automatic snapshot charge is provisioned here.

Rollback uses the previous approved image digest; never downgrade a database schema
without a compatible backup. The data volume is retained on stack deletion and
**continues to cost money**. Release the Elastic IP and delete retained storage only
after explicit deletion approval and a verified backup. Stopping EC2 alone does not
stop EBS or Elastic IP charges. Retire the temporary hostname/session credentials
before releasing its IP. No teardown command has been executed.

## Local validation and remaining blockers

Latest local validation on 14 November 2026:

| Check | Result |
|---|---|
| `python -m unittest discover -s tests -p test_aws_deployment.py -v` | 22 passed; controlled AWS responses only |
| `cfn-lint -t deploy/aws/cloudformation.json -r ap-south-1` | Passed with installed cfn-lint 1.60.1 |
| `docker compose -f deploy/aws/compose.yaml config --quiet` | Passed with dummy public artifact identifiers; no containers started |
| `bash -n deploy/aws/install-runtime.sh` | Passed; installer not executed |
| Read-only account preflight | Real STS request returned `AWS_ACCOUNT_MISMATCH`; region/credit checks stopped |
| cfn-guard 3.2.1, pinned AWS EC2/IAM registry rules | FAIL: 8 failed, 20 passed, 15 not applicable; details below |
| Image/container/TLS/EC2 smoke checks | Unrun: Docker engine unavailable and intended AWS account not verified |

The preceding preparation revision `50324146a162aef0060b4b4d6f1d0cb7b88aa9a3`
passed GitHub CI on Ubuntu/Windows with Python 3.11/3.12. Its existing 22 operational
tests passed locally on repeat; the first local run had one Windows socket-abort
error (`WinError 10053`) without an application change or relaxed test. These are
local/CI results, not proof of an AWS deployment. No image workflow was executed
and no resource was created.

### Guard review: unresolved findings

With explicit installation approval, Guard 3.2.1 was installed under ignored
`.tools/aws-guard/3.2.1/`. The official Windows archive was checked against its
published SHA-256 before execution. Rules came from the
[AWS registry at pinned commit 7f7340c](https://github.com/aws-cloudformation/aws-guard-rules-registry/tree/7f7340c26ae5d5e8874651dbffeb12e0e9f505b6).
All 43 EC2/IAM rule files were evaluated without suppressions. The template was
not modified to hide findings. The hash-bound summary (SHA-256 after CRLF-to-LF
normalization, supporting Windows and Linux checkouts) is
[`deploy/aws/guard-review.json`](../deploy/aws/guard-review.json).

| Failed rule | Resource and disposition before deployment |
|---|---|
| `EBS_OPTIMIZED_INSTANCE` | `Instance`: `EbsOptimized` is not explicit. Verify the selected type's default/support and price before making the setting explicit. |
| `EBS_VOLUME_ENCRYPTION_KEY_RULE` | `DataVolume`: encrypted, but no explicit `KmsKeyId`. Review default EBS encryption and key access; do not create a paid customer key automatically. |
| `EC2_INSTANCE_DETAILED_MONITORING_ENABLED` | `Instance`: detailed monitoring is disabled for the cost plan. Review basic monitoring coverage and price any additional monitoring before approval. |
| `EC2_SECURITY_GROUP_EGRESS_OPEN_TO_WORLD_RULE` | `SecurityGroup`: outbound TCP 80/443 is internet-wide for bootstrapping and read-only provider queries. Destination restrictions remain a deployment security review. |
| `EC2_SECURITY_GROUP_INGRESS_OPEN_TO_WORLD_RULE` | `SecurityGroup`: public TCP 80/443 serves the website/TLS challenge. No SSH or Python port is open; public exposure still requires explicit review. |
| `NO_UNRESTRICTED_ROUTE_TO_IGW` | `PublicRoute`: the default internet route is required by the proposed public single-host topology. Review that topology before deployment. |
| `SECURITY_GROUP_DESCRIPTION_RULE` | `SecurityGroup`: individual ingress/egress rules lack descriptions, despite a group description. Add precise rule descriptions in a reviewed template revision. |
| `SECURITY_GROUP_INGRESS_CIDR_NON_32_RULE` | `SecurityGroup`: public website ingress is wider than a single IPv4 address. A private operator-only alternative would change accessibility; do not change silently. |

On this Windows workspace, reproduce the static review after the approved local
installation and pinned registry download (these commands do not contact AWS):

```powershell
& .tools/aws-guard/3.2.1/cfn-guard-v3-x86_64-windows-latest/cfn-guard.exe validate --data deploy/aws/cloudformation.json --rules .tools/aws-guard/rules-7f7340c/amazon_ec2 --rules .tools/aws-guard/rules-7f7340c/iam --output-format json --show-summary none
```

The full local output is ignored at `tmp/aws-guard-review.json`; the command exits
nonzero while findings remain. These checks do not establish runtime security,
credit eligibility, account permissions, HTTPS issuance or readiness to provision.

Remaining: confirmation/correction of the default profile's intended account,
region/credit verification,
current month usage/tax/gp3 pricing, compliant cost review, image builds/digests,
resolution/review of the static security findings, budget recipient email,
exact final provisioning approval and explicit operator
initialization. **This is prepared infrastructure, not a successful AWS deployment.**
