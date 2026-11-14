#!/bin/bash
# Rendered into cloudformation.json; never execute on a developer workstation.
set -euo pipefail
umask 077
trap '/usr/bin/systemctl --no-block poweroff' ERR
install -d -m 700 /opt/touchstone /etc/touchstone /var/lib/touchstone-runtime-guard
printf '%s' '${RuntimePolicyBase64}' | base64 --decode > /etc/touchstone/runtime-policy.json
chmod 600 /etc/touchstone/runtime-policy.json
python3 - <<'PY'
import base64,zlib
from pathlib import Path
Path('/opt/touchstone/aws_runtime_guard.py').write_bytes(zlib.decompress(base64.b64decode('@GUARD_PAYLOAD@')))
PY
chmod 700 /opt/touchstone/aws_runtime_guard.py
cat > /etc/systemd/system/touchstone-runtime-guard.service <<'EOF'
[Unit]
Description=Fail-closed approved Touchstone operating window
FailureAction=poweroff
[Service]
Type=oneshot
UMask=0077
TimeoutStartSec=15
ExecStart=/usr/bin/python3 /opt/touchstone/aws_runtime_guard.py --policy /etc/touchstone/runtime-policy.json --state /var/lib/touchstone-runtime-guard/state.sqlite --enforce
EOF
cat > /etc/systemd/system/touchstone-runtime-guard.timer <<'EOF'
[Unit]
Description=Recheck runtime allocation including restarts and manual starts
[Timer]
OnBootSec=15s
OnUnitActiveSec=30s
AccuracySec=1s
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
# Validate identity/window and arm the stop control before any network install.
systemctl start touchstone-runtime-guard.service
systemctl enable --now touchstone-runtime-guard.timer
# Wait for the explicitly allocated Elastic IP; never allocate a second public IP.
for n in $(seq 1 120); do if curl --silent --show-error --head --connect-timeout 3 https://cdn.amazonlinux.com/ >/dev/null; then break; fi; sleep 5; done
dnf install -y docker
systemctl enable --now docker amazon-ssm-agent
printf '%s\n' '${ApplicationImage}' > /opt/touchstone/application-image
printf '%s\n' '${SourceRevision}' > /opt/touchstone/source-revision
# No operator identity, payment key, financial operation or app launch is created here.
