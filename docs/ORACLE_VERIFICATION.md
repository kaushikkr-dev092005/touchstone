# Oracle deployment verification

Status: **IN PROGRESS; not deployed**. Working branch: `deploy/oracle-operator`,
based on `4507b4bb341241c3782902f4f4fffaa85ba036a2`. PR #3 remains draft/unmerged;
no Oracle changes have been pushed or merged. No financial operation was executed.

| Component | Status | Observed evidence |
|---|---|---|
| Browser account access | PASS | Official Oracle console accessed after owner sign-in |
| Home region | PASS | Console region menu identifies India West (Mumbai) as home |
| Plan | PASS, limited scope | Console banner identifies Free Tier / Free Trial; no upgrade selected |
| Tenancy-wide allocation/billing | IN PROGRESS | Read-only Cloud Shell inventory; no free-cost conclusion yet |
| OCI instance / SSH / host | NOT TESTED | No application compute instance provisioned |
| Terraform static schema | PASS | Terraform 1.17.2 + pinned OCI provider 9.13.0 validate successfully |
| Provider download recovery | PASS | GitHub transfer failed; official HashiCorp mirror ZIP matches registry SHA-256 |
| OCI-specific unit checks | PASS | 13 controlled tests; no cloud or financial calls |
| Complete source release gate | NOT RUN for Oracle revision | Previous source 4507b4b passed 518 Python, 67 Node and 17 release stages |
| ARM64 runtime | Prior local PASS only | Previous source passed actual isolated container auth, 2000, SSE and restart/audit checks; new revision must be retested |
| Public OCI domain / TLS | BLOCKED_DOMAIN | No owned operator domain confirmed; SSH tunnel is the fallback |
| Financial safety | DISABLED | No financial routes/credentials added; all historical evidence retained |
| Current OCI charges | NOT VERIFIED | No resource or $0 actual-bill claim made |

Local OCI CLI installation encountered large-package download timeouts. Oracle's
pre-authenticated Cloud Shell supplies the administrative CLI without exporting
its credentials. Terraform's Windows provider archive contains an executable
without an `.exe` suffix; preserving the canonical package filename fixes local
mirror discovery. The official archive hash is
`cb47b787f944732a895354b75500b28ed2598fa1a2d47b8902202448e25eb564`.
No provider checksum or version constraint was weakened.

Final results, full source revision, source/image archive hashes, actual OCI
resource state, costs and remaining acceptance gates must be recorded after
execution. Never describe this document or a passing local check as a completed
cloud deployment. See [setup, acceptance and rollback](ORACLE_DEPLOYMENT.md).
