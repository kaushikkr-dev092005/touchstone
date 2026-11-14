# AWS preparation â€” not provisioned

No AWS resource, account upgrade, budget subscription, inference purchase or bank
operation has been created. The existing Sites deployment remains unchanged.
The latest local preflight returns **AWS_ROOT_CREDENTIALS_FORBIDDEN** before
any AWS API call: the default profile points to a root login session. An explicitly
authorized browser login completed but returned root again. The owner confirmed
that no non-root identity exists yet. The owner must create/authorize a non-root
IAM user or role in the intended account before cloud checks can resume. No IAM
resource or account plan was changed. AWS CLI 2.40.3 is installed and discovered.
Earlier STS evidence returned AWS_ACCOUNT_MISMATCH; it does not establish the
intended account, Mumbai availability, current account plan or credit coverage.

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
  memory/process limits and a protected data mount. Caddy uses separate UID 10002,
  no capabilities and unprivileged internal ports 8080/8443, mapped to public 80/443.
  Images must be ARM64 and
  pinned by digest; the application revision label must match the approved source.
- No AWS, Airwallex, Claude or payment-wallet secrets are mounted in the app.
  The existing Node libraries support protected read-only quote validation.
  Remote financial dispatch remains disabled. This does not move a live payer
  into the public service or make Visa onboarding complete.
- The sandbox merchant remains the existing separate HTTPS service. Caddy redirects
  `/merchant` there; merchant OAuth/keys are not copied into AWS.

The host administrator and a fully compromised host remain outside the app's
signature-security boundary. This single-host prototype is not highly available.

## Cost review: verified public rates, account eligibility pending

The gross monthly ceiling remains **$10** and the cash target **$0**. No alternative
has been selected or authorized. The owner must establish a non-root identity and rerun the
read-only preflight; no cloud checks continued after root was detected.
Actual credit/tax/service eligibility and other account usage remain unverified.

Official Mumbai rates retrieved on 14 November 2026:

- Linux `t4g.micro`: $0.0056/hour; `t4g.nano`: $0.0028/hour, from the
  [AWS EC2 public feed](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20%28Mumbai%29/Linux/index.json).
- gp3 storage: **$0.0912 per GB-month**, confirmed in the
  [AWS Mumbai public catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-south-1/index.csv),
  SKU `D7RMW443YWTMZ4V5`, rate `D7RMW443YWTMZ4V5.JRTCKXETXF.6YS6EN2CT7`,
  effective 1 November 2026. This replaces the former unverified $0.12 allowance.
- One allocated public IPv4: $0.005/hour, including idle hours, per
  [AWS VPC pricing](https://aws.amazon.com/vpc/pricing/).

The compact source record is [`pricing.json`](../deploy/aws/pricing.json).
Reproduce every number using `python tools/aws_cost_review.py`; it is offline,
uses Decimal, cannot provision and never deducts credits from gross usage.
The 744-hour bound covers a 31-day month; both encrypted disks total 16 GiB.

| Proposal | Compute | Allocated IPv4 | Storage | Fixed subtotal | Total with reserves |
|---|---:|---:|---:|---:|---:|
| Current micro, 744 hours | $4.1664 | $3.7200 | $1.4592 | $9.3456 | **$11.71472: over cap** |
| Nano, 744 hours | $2.0832 | $3.7200 | $1.4592 | $7.2624 | **$9.21488: conditional** |
| Micro, at most 360 running hours | $2.0160 | $3.7200 | $1.4592 | $7.1952 | **$9.13424: conditional** |
| IPv6-only micro research, 744 hours | $4.1664 | $0 | $1.4592 | $5.6256 | **$7.25072: connectivity blocked** |

Totals add a 20% tax/planning reserve to the fixed subtotal and $0.50 variable-usage
reserve. This is not the account's verified tax rate or a hard network-cost cap.
Account-wide unrelated usage, chargeable key costs, taxes and traffic beyond the
reserve must be included before a final decision. Credits cannot repair a gross
estimate above $10. No option currently proves $0 out of pocket.

### Lower-cost alternatives and tradeoffs

All proposals preserve operator authentication, financial dispatch disabled,
SQLite on encrypted persistent storage, signed-approval controls and backups.
They change capacity, availability or connectivity; they are not silently applied.

1. **Always-on nano:** least disruptive to the current template, but only on an
   **already-paid** plan with verified credits. AWS's
   [eligible instance list](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-launch-parameters.html)
   includes micro, not nano, for the newer Free Plan. Never upgrade the account.
   Its 512 MiB capacity is untested; require memory/restart/load validation before
   accepting it. If inadequate, stop rather than resize automatically.
2. **Micro with a 360-hour monthly running limit:** keeps the Free Plan candidate
   type and all storage/auth controls, but the backend is offline outside agreed
   windows. Allocated IPv4 and both disks still bill for the full month, including
   stopped periods. The limit includes launch, setup and validation hours. A root-owned operating-window guard is implemented and locally tested, but
   not deployed or host-verified. Its absolute UTC deadline counts stopped gaps,
   prior use and a shutdown margin. See [runtime accounting and limitations](AWS_RUNTIME_GUARD.md).
   No automatic starts, monthly renewals or off-host watchdog are implemented.
   Selection requires explicit availability consent and on-host stop acceptance.
3. **IPv6-only micro:** a costed research option, not a supported replacement yet.
   IPv4-only clients cannot connect directly. Package/image registries, SSM,
   providers, temporary DNS and CA validation must all support the chosen IPv6
   design; otherwise egress translation/gateways could erase savings. No NAT,
   gateway or IPv6 resources have been added, and the current template is IPv4.

For a Free Plan, the bounded-hours micro proposal is the practical next candidate;
for an already-paid plan, nano is a candidate subject to capacity. Both remain
blocked until actual account usage, credits and costs are verified. The plan's
`approved_budget_satisfied` remains null; cost arithmetic alone cannot approve it.

Standard CPU credits avoid surplus-credit charges; exhaustion throttles the host.
Compilation remains off-host. Budgets are account-wide gross costs excluding
credits/refunds and including taxes, with alerts at $5/$8/$10. They are delayed
notifications, **not a hard cap**; see
[AWS Budgets limitations](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
`[MY AWS BILLING EMAIL]` is still a placeholder; supply the recipient privately.
No budget resource has been created.

## Authenticate and perform read-only checks

Install the [official AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
and authenticate locally using the account owner's existing supported login flow.
With a current CLI, `aws login --profile default` opens the existing browser console
sign-in flow and uses temporary credentials; see [AWS console-credential login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).
For an account already using IAM Identity Center, `aws configure sso --profile default`
and `aws sso login --profile default` are options. Do not create an IAM account or
upgrade a plan merely to enable this flow. Never paste access keys or tokens in chat.

The current owner action is to create/authorize a non-root IAM user or assumed
role in the intended account, then sign into that identity in the console. Do not
use root or create long-lived keys for this deployment. An administrator must allow
`SignInLocalDevelopmentAccess` and the read-only permissions listed below. Creating
IAM resources is a separate owner action, not a permitted deployment side effect.
After that identity exists, use the approved local sign-in flow:

```powershell
$touchstoneAwsCli = Join-Path $env:LOCALAPPDATA 'Programs\Amazon\AWSCLIV2\aws.exe'
& $touchstoneAwsCli login --profile default --region ap-south-1
```

This changes the local login profile only. Verify the browser identity before
accepting the change. Do not paste authentication codes, passwords or keys in chat.
From the repository root, run:

```powershell
$touchstoneAccountId = Read-Host 'Intended 12-digit AWS account ID'
python tools/aws_preflight.py --expected-account $touchstoneAccountId
```

This tool accepts only `default`, rejects a known root login before any API call,
rejects STS root identities, verifies the intended non-root identity, checks Mumbai opt-in and
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

A no-publication local ARM64 build is reproducible from committed files only:
`python tools/build_aws_image.py --ref FULL_REVIEWED_COMMIT`. Its git archive excludes
ignored local wallets, environment files, databases and Git credentials. The image
ID printed by a local build is **not** a published registry manifest digest.


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
aws cloudformation deploy --profile default --region ap-south-1 --stack-name touchstone --template-file deploy/aws/cloudformation.json --capabilities CAPABILITY_IAM --parameter-overrides ExpectedAccountId=APPROVED_ACCOUNT VerifiedAccountPlan=VERIFIED_EXISTING_PLAN ApplicationImage=APPROVED_PUBLIC_ARM64_IMAGE_DIGEST SourceRevision=APPROVED_FULL_COMMIT BudgetEmail=APPROVED_ALERT_EMAIL EbsKmsKeyArn=APPROVED_EXISTING_KEY_ARN RuntimePolicyBase64=PRIVATELY_APPROVED_MONTHLY_POLICY
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

Current results and the exact tested revision are recorded in
[AWS deployment verification](AWS_DEPLOYMENT_VERIFICATION.md). These are local/CI
results, not proof of an AWS deployment. No publication workflow or provisioning
operation has been executed. The latest complete GitHub matrix must be green on
the final source before release; a previous passing push does not erase a failing
PR run on the same source.

### Guard review: three fixes, five proposed exceptions

Guard 3.2.1 is installed locally under ignored `.tools/aws-guard/3.2.1/`, with
its official Windows release checksum verified. All 43 EC2/IAM rule files from
[AWS registry revision 7f7340c](https://github.com/aws-cloudformation/aws-guard-rules-registry/tree/7f7340c26ae5d5e8874651dbffeb12e0e9f505b6)
ran without suppressions. Results: **23 passed, 15 not applicable, 5 failed**.
Raw Guard still exits nonzero. These exception proposals require final-plan review;
none is a production compliance certificate or silently accepted waiver.

[`guard-review.json`](../deploy/aws/guard-review.json) binds the result to the
current template SHA-256 after CRLF-to-LF normalization and preserves the original
eight-finding baseline from `eaaba69` for comparison.

| Original finding | Disposition and remaining risk/check |
|---|---|
| `EBS_OPTIMIZED_INSTANCE` | **Fixed:** explicit `EbsOptimized:true`. T4g nano/micro are [optimized by default](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html); this makes the included feature explicit. |
| `EBS_VOLUME_ENCRYPTION_KEY_RULE` | **Fixed:** root and data disks require `EbsKmsKeyArn`, an existing same-account Mumbai key with no default override. Before approval, verify the actual account default/policy, enabled state, grants and cost. No key resource was added; do not weaken policy or create a paid key to pass Guard. AWS-managed keys have [no monthly key fee](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html), while request charges/coverage and customer-key fees need account review. |
| `SECURITY_GROUP_DESCRIPTION_RULE` | **Fixed:** every ingress/egress rule now explains its purpose. The group is referenced only by `Instance`; no port/CIDR was widened. |
| `EC2_INSTANCE_DETAILED_MONITORING_ENABLED` | **Proposed exception:** basic EC2 monitoring avoids adding unbudgeted detailed metrics. Mumbai first-tier metrics are $0.30/metric-month ([official regional catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/ap-south-1/index.json)); actual metric count, hourly proration and account allowances require verification. This is an additional unbudgeted line, not assumed free. Risk: coarser host failure/performance detection. Mitigations: container health checks, restart policy, bounded logs, basic host metrics and manual observation during the approved window. Verify alarm/log requirements and price additions before approval. |
| `EC2_SECURITY_GROUP_EGRESS_OPEN_TO_WORLD_RULE` | **Proposed exception:** TCP 80/443 internet egress supports packages, images, SSM, TLS and read-only provider checks without a paid NAT/proxy. Risks: outbound exfiltration/cost if the host is compromised. Mitigations: no financial secrets, minimal host role, unprivileged app, read-only containers, protocol limits. Destination allowlisting/private endpoints remain production hardening; do not claim least-privilege destinations. |
| `EC2_SECURITY_GROUP_INGRESS_OPEN_TO_WORLD_RULE` | **Proposed exception:** public 80/443 is intentional for HTTPS website access and ACME redirects/challenges. Risks: attacks, denial of service and traffic costs. Mitigations: authenticated private API, TLS, Host/Origin/CSRF checks, application rate/body limits, no public SSH/Python/database port. These limits do not provide a hard AWS bandwidth cap. |
| `NO_UNRESTRICTED_ROUTE_TO_IGW` | **Proposed exception:** this dedicated public subnet needs its default IGW route; a private-host gateway/load-balancer architecture exceeds this cost target. Risk: direct internet routing. Mitigations: only the dedicated host/group, IMDSv2, no application AWS credentials, limited network ports. Confirm there are no additional group attachments before deployment. |
| `SECURITY_GROUP_INGRESS_CIDR_NON_32_RULE` | **Proposed exception:** a public website must serve more than a single operator IP. Risk: internet-wide attack surface, overlapping the public-ingress finding. The operator API remains authenticated. Restricting to an owner CIDR is a different, private-access product choice, not silently applied. |

The encrypted data volume retains both deletion/replacement policies. The template
is below the inline size limit; metadata records financial/network/storage
constraints. Account-aware service validation, TLS and runtime checks are still
pending. No account, key policy or deployed security group was modified.

Reproduce Guard locally (no AWS call):

```powershell
& .tools/aws-guard/3.2.1/cfn-guard-v3-x86_64-windows-latest/cfn-guard.exe validate --data deploy/aws/cloudformation.json --rules .tools/aws-guard/rules-7f7340c/amazon_ec2 --rules .tools/aws-guard/rules-7f7340c/iam --output-format json --show-summary none
```

The exact phased release gates and expected results are in
[the acceptance checklist](AWS_ACCEPTANCE_CHECKLIST.md). The current source remains
unmerged; no image publication or infrastructure operation was performed.

Remaining: confirmation/correction of the default profile's intended account,
region/credit verification,
current month usage/tax/key costs, compliant cost review, image builds/digests,
resolution/review of the static security findings, budget recipient email,
exact final provisioning approval and explicit operator
initialization. **This is prepared infrastructure, not a successful AWS deployment.**
