#!/bin/bash
# Run only on the explicitly approved EC2 instance, after CloudFormation completes.
set -euo pipefail
umask 077
[[ $EUID == 0 && $(uname -m) == aarch64 ]] || { echo 'ROOT_ON_APPROVED_ARM64_HOST_REQUIRED'; exit 1; }
[[ $# == 5 ]] || { echo 'Usage: install-runtime.sh DATA_VOLUME_ID APP_IMAGE CADDY_IMAGE SOURCE_COMMIT HTTPS_HOST'; exit 1; }
volume_id=$1; application_image=$2; caddy_image=$3; source_revision=$4; operator_domain=$5
[[ $volume_id =~ ^vol-[a-f0-9]{8,17}$ && $source_revision =~ ^[a-f0-9]{40}$ ]] || exit 1
[[ $application_image =~ ^ghcr\.io/kaushikkr-dev092005/touchstone@sha256:[a-f0-9]{64}$ ]] || exit 1
[[ $caddy_image =~ ^caddy@sha256:[a-f0-9]{64}$ ]] || exit 1
[[ $operator_domain =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && $operator_domain == *.sslip.io ]] || exit 1
[[ $(cat /opt/touchstone/application-image) == "$application_image" && $(cat /opt/touchstone/source-revision) == "$source_revision" ]] || { echo 'APPROVED_IMAGE_OR_SOURCE_MISMATCH'; exit 1; }

data_device=''
for serial_file in /sys/block/nvme*n1/device/serial; do
    [[ -f $serial_file ]] || continue
    serial=$(tr -d '[:space:]' < "$serial_file")
    if [[ $serial == "${volume_id//-/}" ]]; then
        [[ -z $data_device ]] || { echo 'AMBIGUOUS_VOLUME'; exit 1; }
        device_name=${serial_file#/sys/block/}; device_name=${device_name%%/*}
        data_device=/dev/$device_name
    fi
done
[[ -n $data_device && -b $data_device ]] || { echo 'APPROVED_DATA_VOLUME_NOT_FOUND'; exit 1; }
[[ $(lsblk -nr -o TYPE "$data_device" | wc -l) == 1 ]] || { echo 'PARTITIONED_VOLUME_REQUIRES_MANUAL_REVIEW'; exit 1; }
if ! mountpoint -q /var/lib/touchstone-aws; then
    [[ -z $(lsblk -nr -o MOUNTPOINTS "$data_device" | tr -d '[:space:]') ]] || { echo 'VOLUME_ALREADY_MOUNTED'; exit 1; }
    if [[ -z $(wipefs -n --noheadings "$data_device") ]]; then
        mkfs.ext4 -L touchstone-aws "$data_device"
    else
        [[ $(blkid -s TYPE -o value "$data_device") == ext4 && $(blkid -s LABEL -o value "$data_device") == touchstone-aws ]] || { echo 'UNKNOWN_EXISTING_VOLUME_REFUSED'; exit 1; }
    fi
    install -d -m 700 /var/lib/touchstone-aws
    mount "$data_device" /var/lib/touchstone-aws
else
    [[ $(findmnt -no UUID /var/lib/touchstone-aws) == $(blkid -s UUID -o value "$data_device") ]] || { echo 'MOUNTED_VOLUME_MISMATCH'; exit 1; }
fi
volume_uuid=$(blkid -s UUID -o value "$data_device")
if ! grep -Fq "UUID=$volume_uuid " /etc/fstab; then
    printf 'UUID=%s /var/lib/touchstone-aws ext4 defaults,nofail,x-systemd.device-timeout=30 0 2\n' "$volume_uuid" >> /etc/fstab
fi
install -d -m 700 -o 10001 -g 10001 /var/lib/touchstone-aws/operator
install -d -m 700 /var/lib/touchstone-aws/caddy-data /var/lib/touchstone-aws/caddy-config
# Small-host swap is on the encrypted retained volume. Never run model inference here.
if [[ ! -e /var/lib/touchstone-aws/swapfile ]]; then
    dd if=/dev/zero of=/var/lib/touchstone-aws/swapfile bs=1M count=512 status=none
    chmod 600 /var/lib/touchstone-aws/swapfile
    mkswap /var/lib/touchstone-aws/swapfile >/dev/null
fi
swapon --show=NAME --noheadings | grep -Fxq /var/lib/touchstone-aws/swapfile || swapon /var/lib/touchstone-aws/swapfile
grep -Fq '/var/lib/touchstone-aws/swapfile ' /etc/fstab || printf '/var/lib/touchstone-aws/swapfile none swap sw 0 0\n' >> /etc/fstab

install -d -m 755 /usr/local/lib/docker/cli-plugins
curl --fail --silent --show-error --location 'https://github.com/docker/compose/releases/download/v5.6.0/docker-compose-linux-aarch64' -o /opt/touchstone/docker-compose.pending
printf '%s  %s\n' '733ec76717ceb59052a9609b9dadfb523b2df8eab57a54212872d10a58078ea2' /opt/touchstone/docker-compose.pending | sha256sum --check --status
install -m 755 /opt/touchstone/docker-compose.pending /usr/local/lib/docker/cli-plugins/docker-compose
for name in compose.yaml Caddyfile; do
    curl --fail --silent --show-error --location "https://raw.githubusercontent.com/kaushikkr-dev092005/touchstone/$source_revision/deploy/aws/$name" -o "/opt/touchstone/$name"
done
printf 'APPLICATION_IMAGE=%s\nCADDY_IMAGE=%s\nSOURCE_REVISION=%s\nOPERATOR_DOMAIN=%s\n' "$application_image" "$caddy_image" "$source_revision" "$operator_domain" > /opt/touchstone/runtime.env

install -d /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/touchstone-data.conf <<'EOF'
[Unit]
RequiresMountsFor=/var/lib/touchstone-aws
[Service]
ExecStartPre=/usr/bin/mountpoint -q /var/lib/touchstone-aws
EOF
cat > /etc/systemd/system/touchstone.service <<'EOF'
[Unit]
Description=Touchstone authenticated zero-charge workspace
Requires=docker.service
After=docker.service network-online.target
RequiresMountsFor=/var/lib/touchstone-aws
ConditionPathExists=/var/lib/touchstone-aws/operator/operator-config.json
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/touchstone
ExecStart=/usr/bin/docker compose --env-file runtime.env -f compose.yaml up -d --no-build
ExecStop=/usr/bin/docker compose --env-file runtime.env -f compose.yaml stop
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable touchstone.service
cd /opt/touchstone
docker compose --env-file runtime.env -f compose.yaml config --quiet
docker compose --env-file runtime.env -f compose.yaml pull
[[ $(docker image inspect --format '{{.Architecture}}' "$application_image") == arm64 ]] || { echo 'ARM64_IMAGE_REQUIRED'; exit 1; }
[[ $(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$application_image") == "$source_revision" ]] || { echo 'IMAGE_SOURCE_REVISION_MISMATCH'; exit 1; }
echo 'Prepared. Operator identity NOT created and application NOT started. Initialize interactively, then start touchstone.service.'
