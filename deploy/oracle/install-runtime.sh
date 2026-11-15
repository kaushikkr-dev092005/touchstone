#!/bin/bash
# Only on the reviewed OCI Ubuntu host. No disk formatting, account creation or app start.
set -euo pipefail
umask 077
[[ $EUID == 0 && $(uname -m) == aarch64 ]] || { echo ROOT_ON_ARM64_REQUIRED; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo UBUNTU_24_04_REQUIRED; exit 1; }
[[ $# == 5 || $# == 6 ]] || { echo 'Usage: install-runtime.sh SOURCE_DIR COMMIT APP_IMAGE_ID CADDY_DIGEST tunnel|https [VERIFIED_DOMAIN]'; exit 1; }
source_dir=$1; revision=$2; app_image=$3; caddy_image=$4; mode=$5; domain=${6:-}
[[ $revision =~ ^[a-f0-9]{40}$ && $app_image =~ ^sha256:[a-f0-9]{64}$ ]] || exit 1
[[ $caddy_image =~ ^caddy@sha256:[a-f0-9]{64}$ ]] || exit 1
[[ -f $source_dir/deploy/operator/compose.yaml && -f $source_dir/deploy/operator/compose.tunnel.yaml ]] || exit 1
case $mode in
  tunnel) [[ -z $domain ]] || exit 1; operator_host=127.0.0.1:8089; origin=http://127.0.0.1:8089 ;;
  https) [[ $domain =~ ^[a-z0-9][a-z0-9.-]*\.[a-z][a-z0-9-]+$ ]] || { echo VERIFIED_DOMAIN_REQUIRED; exit 1; }; operator_host=$domain; origin=https://$domain ;;
  *) exit 1 ;;
esac
[[ $(docker image inspect --format '{{.Architecture}}' "$app_image") == arm64 ]] || exit 1
[[ $(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$app_image") == "$revision" ]] || { echo IMAGE_REVISION_MISMATCH; exit 1; }
docker compose version >/dev/null
[[ -f /etc/systemd/system/docker.service.d/touchstone-boundary.conf ]] || { echo CONTAINER_BOUNDARY_REQUIRED; exit 1; }
iptables -C DOCKER-USER -d 169.254.0.0/16 -j REJECT || { echo CONTAINER_METADATA_BLOCK_REQUIRED; exit 1; }
install -d -m 700 /opt/touchstone /var/lib/touchstone-data
install -d -m 700 -o 10001 -g 10001 /var/lib/touchstone-data/operator
install -d -m 700 -o 10002 -g 10002 /var/lib/touchstone-data/caddy-data /var/lib/touchstone-data/caddy-config
for name in compose.yaml compose.tunnel.yaml Caddyfile; do
    install -m 644 "$source_dir/deploy/operator/$name" "/opt/touchstone/$name"
done
[[ ! -e /opt/touchstone/runtime.env ]] || { echo EXISTING_RUNTIME_REQUIRES_REVIEWED_UPDATE; exit 1; }
printf 'APPLICATION_IMAGE=%s\nCADDY_IMAGE=%s\nSOURCE_REVISION=%s\nOPERATOR_HOST=%s\nOPERATOR_DOMAIN=%s\n' "$app_image" "$caddy_image" "$revision" "$operator_host" "$domain" > /opt/touchstone/runtime.env
if [[ $mode == https ]]; then
    docker pull "$caddy_image"
    [[ $(docker image inspect --format '{{.Architecture}}' "$caddy_image") == arm64 ]] || exit 1
    compose_args='--env-file runtime.env -f compose.yaml --profile https'
else
    compose_args='--env-file runtime.env -f compose.yaml -f compose.tunnel.yaml'
fi
cat > /etc/systemd/system/touchstone.service <<EOF
[Unit]
Description=Touchstone zero-charge authenticated workspace
Requires=docker.service
After=docker.service network-online.target
RequiresMountsFor=/var/lib/touchstone-data
ConditionPathExists=/var/lib/touchstone-data/operator/operator-config.json
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/touchstone
ExecStartPre=/usr/bin/test -f /var/lib/touchstone-data/operator/operator-config.json
ExecStart=/usr/bin/docker compose $compose_args up -d --pull never --no-build
ExecStop=/usr/bin/docker compose $compose_args stop
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable touchstone.service
echo "Runtime prepared; app not started. Initialize interactively in DEMO mode with origin $origin, then start touchstone.service."
