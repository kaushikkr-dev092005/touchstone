# Oracle Always Free deployment

Status: **preparing and verifying; not deployed**. Actual results are in
[ORACLE_VERIFICATION.md](ORACLE_VERIFICATION.md). Financial dispatch stays disabled.
The current public saved-evidence website remains independent until migration
passes acceptance. No replacement URL or domain is invented.

## Verified application architecture

The shared ARM64 Dockerfile builds `apps/web` with its lockfile and regenerates
the public dashboard from `apps/dashboard/index.html`. The operator HTTP service
serves that public frontend and a separately authenticated `/control-room` API.
Public `/dashboard` and `/ledger` display projected saved evidence. They cannot
forward requests to the private loopback console on 8088. The authenticated
workspace on container port 8089 runs bounded deterministic jobs, SQLite audit
and SSE. It has no payment, wallet, signing-proxy or bank-write endpoint.

`deploy/operator/compose.yaml` is the single shared runtime: UIDs 10001/10002,
read-only filesystems, capability removal, resource/log limits and persistent
bind directories under `/var/lib/touchstone-data`. Python is not publicly
published. The optional Caddy HTTPS profile publishes only 80/443. The tunnel
override publishes 8089 on **host loopback only**. Cloud credentials never enter
the application container. No local GPU or inference server is installed.

## Account, allocation and approval gates

Verify the actual tenancy and **home region**, account plan, current-month usage,
all compartments' existing compute, boot/block storage, networking, limits and
quotas before creating resources. A trial credit balance is not free eligibility.
Do not upgrade, select a paid Marketplace image or use a paid capacity fallback.

The candidate is one `touchstone-oracle` **VM.Standard.A1.Flex**, 2 OCPUs, 12 GB,
official **Ubuntu 24.04 ARM64**, and a 50 GB boot disk. SQLite/TLS data persist on
this encrypted boot storage; no additional block volume or backup policy is
created. Preserve the boot volume on termination and use independent private
backups. Terraform prevents instance destruction until separately reviewed.

Oracle currently documents 1,500 OCPU-hours / 9,000 GB-hours monthly A1 allowance
(2 OCPUs / 12 GB equivalent), combined 200 GB boot/block storage, in the home
region. A 31-day 2/12 projection is 1,488 OCPU-hours / 8,928 GB-hours, **before
existing consumption**. Check actual account eligibility and remaining allowance,
including past usage and retained volumes. Source:
[Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

If there is no free A1 capacity, try only eligible availability domains with the
same reviewed configuration, inspect leftovers, then report
`BLOCKED_FREE_CAPACITY`. No endless retry, shape upgrade or paid fallback.
Idle Always Free instances can be reclaimed; do not run artificial workloads
to defeat reclamation. Backups and service availability need ongoing attention.

Infrastructure uses a dedicated VCN/subnet/Internet Gateway, empty security list
and dedicated NSG. SSH 22 is restricted to the authorized owner's IPv4 `/32`;
80/443 serve the optional proxy. DNS/NTP use OCI's resolver, package/image/TLS
egress uses 80/443. There is no NAT, load balancer, database, paid key, instance
principal, IAM policy or reserved IP resource. Public IP is the VNIC's ephemeral
address. All resource eligibility and egress allowances still require review.

## Authentication and read-only preparation

Use your official browser session and temporary CLI authentication; enter
password/MFA privately. Never paste signing keys, tokens or cookies into chat.
Cloud Shell provides a pre-authenticated CLI within its published free limits:
[Oracle Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cloudshellintro.htm).
It is an administration environment, not the application host. Do not copy its
credentials into a build, Terraform variables, the server or container.

For a desktop OCI CLI, use the official browser flow:

```powershell
oci session authenticate --region VERIFIED_HOME_REGION --profile-name TOUCHSTONE --session-expiration-in-minutes 60
```

The Windows local installation may be `.tools/oci/Scripts/oci.exe`. This writes
a temporary private local session, not an IAM grant. See
[token-based CLI authentication](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/clitoken.htm).

Create ignored `tmp/oracle-settings.json` privately with exactly `profile`,
`region`, `tenancy_ocid`, `compartment_ocid`, `image_ocid`. Then:

```text
python tools/oracle_preflight.py --settings tmp/oracle-settings.json
```

The tool rejects tenancy mismatch and non-home regions, requires temporary
authentication, reads all listed compartments and checks image/A1 compatibility.
Partial inventory fails closed. Its report omits OCIDs and credentials. A passing
read check does **not** approve provisioning or verify bills/month-to-date usage.

## Infrastructure review

`deploy/oracle` pins the OCI Terraform provider. It creates no resources on init,
fmt or validate. Copy `terraform.example.tfvars` to ignored `tmp/oracle.tfvars`;
fill actual identifiers, official image, owner SSH **public** key and `/32`.
Set `free_capacity_verified` only after real account review. This validation flag
is not an authorization protocol. Keep Terraform state private: it contains
identifiers and bootstrap metadata. Do not upload it to GitHub.

```text
terraform -chdir=deploy/oracle init -backend=false
terraform -chdir=deploy/oracle fmt -check -recursive
terraform -chdir=deploy/oracle validate
terraform -chdir=deploy/oracle plan -var-file=../../tmp/oracle.tfvars -out=../../tmp/oracle.tfplan
```

Review the exact plan, selected image's Always Free label, remaining aggregate
allocation and network exposure before applying. Do not deploy unreviewed source.
No apply, publication, account upgrade or IAM grant is implied by passing tests.
The bootstrap uses the official signed Docker Ubuntu ARM64 repository, enables
key-only SSH/UFW/security updates, and prepares protected directories. It does
not format disks, initialize an operator or launch the app. Source:
[Docker Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/).

## Artifact and host installation

Build from the reviewed committed source off-host, without cloud/financial keys:

```text
python tools/build_operator_image.py --ref FULL_REVIEWED_COMMIT
python tools/check_operator_container.py --revision FULL_REVIEWED_COMMIT
```

The output local image ID is **not** a published registry manifest. Save that
verified image, hash the archive, transfer it by `scp` using the dedicated private
SSH key, verify the archive hash on the host, and `docker load` it. Verify image
architecture, ID and OCI source label match. No GHCR publication is necessary.
Transfer only the reviewed source archive and image; exclude `.oci`, `.ssh`,
`.env`, private SQLite, wallet and financial-provider configuration.

On the approved host check `uname -m`, `/etc/os-release`, `free -h`, `df -h`,
`lscpu`, `cloud-init status --wait`, Docker/Compose versions and the NSG/UFW rules.
Run the reviewed installer as root with source directory, full commit, exact local
app image ID, reviewed Caddy digest and `tunnel` or `https VERIFIED_OWNED_DOMAIN`.
The installer validates image identity and refuses an existing runtime config.
It neither starts the application nor asks for a password.

For tunnel mode, open a private administrator shell and initialize interactively:

```bash
cd /opt/touchstone
sudo docker compose --env-file runtime.env -f compose.yaml -f compose.tunnel.yaml run --rm --no-deps -it operator python tools/run_operator.py init --config /var/lib/touchstone/operator-config.json --origin http://127.0.0.1:8089 --environment DEMO
sudo systemctl start touchstone.service
```

Enter the operator password yourself in masked input. From the owner's desktop:

```text
ssh -i PRIVATE_KEY_PATH -N -L 8089:127.0.0.1:8089 ubuntu@VERIFIED_INSTANCE_IP
```

Open `http://127.0.0.1:8089/control-room`. HTTP is confined to loopback and the
encrypted SSH tunnel. Do not publish 8089 or use public raw HTTP for login.
For HTTPS use the owned, verified DNS name, HTTPS profile and matching HTTPS
origin during interactive initialization; inspect an existing config before any
origin migration because session invalidation is deliberate. Never overwrite it.

## Acceptance and maintenance

Confirm `/healthz` identifies the reviewed revision and
`financial_dispatch_enabled:false`; anonymous `/operator-api/jobs` returns 401.
Sign in, submit amounts 1250/900 with discount 150, verify 2000, actual SSE,
refresh, restart and audit persistence, and zero external charges. Check current
dashboard/ledger, mobile layouts, Host/Origin/CSRF and login throttles. With an
owned domain verify DNS, real TLS, redirects, secure cookies and proxy SSE
externally. A local build is not public acceptance.

On the host, these commands apply to the reviewed installation:

```bash
sudo systemctl status touchstone.service
sudo docker ps
sudo docker stats --no-stream
sudo journalctl -u touchstone.service -n 40 --no-pager
df -h
free -h
sudo systemctl restart touchstone.service
sudo systemctl stop touchstone.service
```

For Compose logs include the installation's `runtime.env` and selected compose
files; inspect privately and redact source data, cookies and credentials.
Updates require a newly tested source/image, backup and explicit configuration
review; the installer deliberately refuses silent overwrite. Never resize to
fix a failed build or capacity issue.

Offline backup after stopping the service uses the existing backup tool:

```bash
sudo docker run --rm --network none --mount type=bind,source=/var/lib/touchstone-data/operator,target=/var/lib/touchstone --entrypoint python REVIEWED_APP_IMAGE_ID tools/operator_backup.py backup --data-dir /var/lib/touchstone/jobs --archive /var/lib/touchstone/backup-UNIQUE.sqlite
```

Copy the private archive and separate operator config to owner-controlled,
encrypted storage over SSH. Never commit them. Restore with the tool's `restore`
action into a **new empty directory**, verify audit and revoked sessions, then
review the replacement mount. Do not restore over active or financial databases.
Stopping containers or the VM does not delete storage. Termination, removal of
`prevent_destroy`, deletion of retained boot volumes and any other irreversible
cleanup require separate owner approval and a verified backup first.

## Removed AWS deployment

The AWS CloudFormation, bootstrap/hour guard, pricing/plan files, AWS-specific
checks and obsolete AWS guides were removed at the owner's request. Generic
ARM64 build/smoke tooling and the manual image workflow were renamed and retained.
The prior preparation is recoverable from branch `deploy/aws-operator`, commit
`4507b4bb341241c3782902f4f4fffaa85ba036a2`; Git history was not rewritten. Core
authentication, signed mandates, financial tests, benchmarks and historical
transaction evidence were preserved. `AWS_` secret rejection remains a security
deny rule, not deployment configuration.
