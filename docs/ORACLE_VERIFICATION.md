# Oracle deployment verification

**BLOCKED_FREE_CAPACITY — not deployed.** Observed on 2026-11-15 in the
owner-authenticated Oracle console and its pre-authenticated Cloud Shell.
Changes remain on local branch `deploy/oracle-operator`; nothing was pushed,
published or merged. The earlier AWS PR #3 remains draft/unmerged.

## Source and artifact

Tested application/runtime source: `503ee58c992fd2e7a7673dc08293ae9804002713`.
This report may be committed separately without changing that artifact.

- Local image: `touchstone-operator-local:503ee58c992fd2e7a7673dc08293ae9804002713`.
- Local ARM64 image ID: `sha256:19a8e8cc971d82bedc540b53463e2c625986ec5c488440a97a5f9f72b4abb919`.
  This is a local Docker identity, **not a published registry digest**.
- Optional proxy: `caddy@sha256:4e2425f6009577e7c651010f16679c28f7d12df3e7b1914f941a7a3370746b3c`.
  Caddy has not run on OCI.
- Requested host: official Ubuntu 24.04 ARM64, A1 Flex 2 OCPUs / 12 GB,
  50 GB encrypted boot storage. No host or operating system was provisioned.

## Actual Oracle observations

| Check | Status | Evidence and limit |
|---|---|---|
| Account access | PASS | Official console and Cloud Shell CLI 3.95.1; credentials not exported |
| Home region | PASS | Console home badge and region-subscription API identify `ap-mumbai-1` |
| Plan | PASS, limited scope | Actual banner identifies Free Tier / Free Trial; no upgrade selected |
| Complete resource inventory | PASS | All active compartments inspected: one compartment, zero nonterminated instances, zero boot/block GB, zero reserved public IPs and zero VCNs |
| Image compatibility | PASS | Three official Ubuntu 24.04 images returned for A1 Flex |
| Proposed free allocation | PASS, allocation only | 31 days at 2/12 = 1,488 OCPU-hours / 8,928 GB-hours, within current 1,500 / 9,000 allowance; 50 GB within 200 GB |
| Month-to-date cost query | PASS, reporting scope only | DAILY cost API returned zero entries through the start of the current UTC day; delayed usage and the current day are not covered |
| Month-to-date metered usage | PASS, reporting scope only | DAILY USAGE API returned zero entries, no next page, for 2026-11-01T00:00Z through 2026-11-15T00:00Z; reporting delay/current-day usage remain outside this observation |
| A1 capacity, 2 OCPUs / 12 GB | BLOCKED | Actual capacity report: `OUT_OF_HOST_CAPACITY` |
| A1 capacity, 1 OCPU / 6 GB | BLOCKED | Smaller eligible configuration also returned `OUT_OF_HOST_CAPACITY` |
| Alternative availability domain | BLOCKED | Tenancy exposes only one Mumbai availability domain |
| OCI instance / SSH / Docker | BLOCKED | No instance exists; host checks cannot pass |
| OCI app / restart / persistence | NOT TESTED | Local tests below are not cloud acceptance |
| Owned operator domain / TLS | BLOCKED_DOMAIN | No owned domain confirmed; use SSH tunnel until available |
| Financial safety | PASS, local/source scope | Dispatch disabled; no payer/bank/model credentials deployed; no financial operations |

The final informational capacity check was at **2026-11-15T10:26:24Z**.
It created no instance or capacity reservation. No paid fallback, other region,
account upgrade, VCN, volume, instance, load balancer, database, NAT or IAM grant
was created. **No Touchstone cloud resources were allocated by this deployment.**
No instance-launch request was submitted after Oracle reported unavailable
capacity; creating unused networking would not resolve that condition.

Oracle's [Always Free documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
describes the allowance and capacity error. Trial credits were not treated as
free eligibility. Cost observations do not guarantee zero future billing.

## Zero-spend validation

| Command/check | Status | Actual result |
|---|---|---|
| `python -m unittest discover -s tests -p test_oracle_deployment.py -v` | PASS | 15 controlled checks on the final runtime revision |
| Terraform 1.17.2 `validate` / `fmt -check -recursive` | PASS | Pinned OCI provider 9.13.0; no apply or cloud writes |
| `bash -n` on Oracle bootstrap and installer | PASS | Both parse; actual Ubuntu cloud-init NOT TESTED |
| Docker Compose tunnel configuration | PASS | Only host loopback 8089 published; proxy opt-in; no financial credentials |
| `python tools/build_operator_image.py --ref 503ee58c992fd2e7a7673dc08293ae9804002713` | PASS | Actual ARM64 build, source label and image ID; confirmed process exit 0 |
| `python tools/check_operator_container.py --revision 503ee58c992fd2e7a7673dc08293ae9804002713` | PASS | Network-isolated ARM64 container: frontend routes, auth/throttle, CSRF, arithmetic 2000, genuine SSE, restart/audit persistence, zero external charges, payment route absent |
| `python tools/scan_secrets.py --json` | PASS, heuristic scope | 1,861 text blobs/files, zero findings; nine oversized and 133 binary skips; full local history |
| Windows / Python 3.11 focused authentication | PASS | Seven tests: controlled-clock sliding window, concurrent/persistent limits, and actual incorrect-login/429 HTTP test |
| `python tools/validate_release.py --ref 503ee58c992fd2e7a7673dc08293ae9804002713 --browser --frontend --output tmp/oracle-final-release.json` | PASS | All 17 stages; 485 Python tests, 67 Node tests, frozen frontend build, five controlled milestone proofs and actual browser checks including dashboard/mobile, signatures, operator auth/2000/SSE/restart; zero external financial transactions |
| Remote GitHub CI on Oracle branch | NOT RUN | Branch not pushed; no GitHub write performed |
| Cloud host / TLS / external backend acceptance | BLOCKED | No free host capacity or owned operator domain |

Logs and machine-readable reports are under ignored `tmp/`. Regression tests
use controlled financial adapters and temporary test signers. They are not live
financial evidence. Earlier source `3be2ac05d6182fbe74ca18d8da9df05f1c3e9972`
separately passed 483 Python, 67 Node tests and all 17 release stages. The final
revision above was independently rebuilt and all 17 stages rerun successfully.

## Existing public website

The existing [public dashboard](https://touchstone-sandbox-merchant.sublimeoak1.chatgpt.site/dashboard)
responded in the real browser. Its iframe rendered 103 transaction rows and a
SIMULATED label, with no alert. This is the retained Sites deployment, **not an
Oracle deployment**. Hosted-source parity and a new Oracle public website/TLS
have not been established. No website was republished during this work.

## Corrections and remaining gates

- Reused the shared Docker runtime and removed AWS deployment files at the
  owner's request. Old branch/history, benchmarks and financial evidence remain.
- Fixed successful empty OCI list reads: CLI 3.95.1 emits no JSON for empty lists.
  Whole-response query/default isolation prevents filtered results being treated
  as a complete inventory. GET, failed and partial reads still fail closed.
- Added a Docker pre-start metadata firewall and fail-closed installer check.
  IMDSv2's constant header does not isolate containers. Host behavior remains
  untested until a host is available.
- Recovered Docker Desktop, rebuilt and tested ARM64. An initial PowerShell
  stderr-redirection wrapper falsely reported failure; captured subprocess
  execution confirmed build exit 0.
- Recovered provider download using the official HashiCorp mirror and verified
  registry hash plus upstream PGP-signed platform checksums. Preserved the
  canonical Windows binary filename; no dependency pin/checksum was weakened.

The exact 45-path implementation diff is reproducible with:

```text
git diff --stat 4507b4bb341241c3782902f4f4fffaa85ba036a2 503ee58c992fd2e7a7673dc08293ae9804002713
git diff --name-status 4507b4bb341241c3782902f4f4fffaa85ba036a2 503ee58c992fd2e7a7673dc08293ae9804002713
```

`deploy/oracle/*` implements the reviewed infrastructure/bootstrap/installer;
`deploy/operator/*` remains the single hardened application runtime;
`tools/oracle_preflight.py` and `tests/test_oracle_deployment.py` implement/test
read-only account/allocation checks. Shared build/container tools and the manual
image workflow were renamed; environment cleanup also rejects OCI variables.
README and deployment/navigation documents explain the separation and blockers.
The later report/feature-matrix commit contains documentation only. No changes
were made under `bench/`, `apps/dashboard/`, `apps/web/src/`, or to ledger/signed
mandate source relative to the preserved AWS branch.

**Next required event:** Always Free A1 capacity becomes available in Mumbai.
Reauthenticate if necessary and repeat inventory/usage/capacity review before
provisioning the same eligible configuration. Do not retry indefinitely or use
paid infrastructure. Then validate bootstrap/SSH/firewalls, transfer the tested
image, initialize the operator with owner-entered masked password in DEMO mode,
and complete the [acceptance and maintenance runbook](ORACLE_DEPLOYMENT.md).

No cloud rollback/deletion is currently required. For a later host, stopping
services retains storage; termination and retained-data deletion need separate
approval and verified backups. Keep local SSH keys, CLI identity, private cache
and Terraform state outside Git.
