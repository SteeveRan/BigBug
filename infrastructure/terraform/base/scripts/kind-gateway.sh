#!/usr/bin/env bash
# Resolves the IPv4 gateway of the docker network that hosts the kind cluster
# (the host address pods reach as "the workstation"). Prints JSON for the
# tofu `external` data source.
set -euo pipefail
net="${KIND_DOCKER_NETWORK:-kind}"
gw="$(docker network inspect "$net" \
  | jq -r '.[0].IPAM.Config[] | select(.Gateway | test("\\.")) | .Gateway' \
  | head -1)"
if [ -z "$gw" ]; then
  echo "no IPv4 gateway on docker network '$net'" >&2
  exit 1
fi
jq -n --arg gw "$gw" '{"gateway": $gw}'
