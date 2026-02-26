# FILE: ./generate-clab-config.sh
#!/usr/bin/env bash
set -euo pipefail

SOLVER_JSON="./output-network-solver.json"
TOPO_FILE="./fabric.clab.yml"

if [ ! -f "$SOLVER_JSON" ]; then
  echo "ERROR: Missing $SOLVER_JSON" >&2
  exit 1
fi

# -----------------------------
# jq helpers
# -----------------------------

jq_req() {
  local query="$1"
  local desc="$2"
  local val
  val="$(jq -er "$query" "$SOLVER_JSON" 2>/dev/null || true)"
  if [ -z "${val:-}" ] || [ "$val" = "null" ]; then
    echo "ERROR: Missing $desc in solver JSON ($query)" >&2
    exit 1
  fi
  printf '%s\n' "$val"
}

jq_opt() {
  local query="$1"
  local desc="$2"
  local val
  val="$(jq -er "$query" "$SOLVER_JSON" 2>/dev/null || true)"
  if [ -z "${val:-}" ] || [ "$val" = "null" ]; then
    echo "WARNING: Missing $desc in solver JSON ($query)" >&2
    printf '%s\n' ""
    return 0
  fi
  printf '%s\n' "$val"
}

indent_exec_block() {
  # Prefix each non-empty line with YAML exec list indentation.
  sed '/^[[:space:]]*$/d; s/^/        - /'
}

emit_routes_from_solver_iface() {
  # Emits "ip route replace ..." and "ip -6 route replace ..." derived from solver.
  # Also WARNs if the interface object or routes are missing/empty.
  local node="$1"
  local iface="$2"

  local iface_exists
  iface_exists="$(jq -r --arg n "$node" --arg i "$iface" \
    '.site.nodes[$n].interfaces[$i] != null' "$SOLVER_JSON" 2>/dev/null || echo "false")"

  if [ "$iface_exists" != "true" ]; then
    echo "WARNING: Missing solver interface object: .site.nodes[\"$node\"].interfaces[\"$iface\"]" >&2
    return 0
  fi

  local v4 v6
  v4="$(jq -r --arg n "$node" --arg i "$iface" '
    (.site.nodes[$n].interfaces[$i].routes4 // [])
    | map(select(.dst != "0.0.0.0/0"))
    | .[]
    | "ip route replace \(.dst) via \(.via4)"
  ' "$SOLVER_JSON")"

  v6="$(jq -r --arg n "$node" --arg i "$iface" '
    (.site.nodes[$n].interfaces[$i].routes6 // [])
    | map(select(.dst != "::/0"))
    | .[]
    | "ip -6 route replace \(.dst) via \(.via6)"
  ' "$SOLVER_JSON")"

  if [ -z "${v4//[[:space:]]/}" ] && [ -z "${v6//[[:space:]]/}" ]; then
    echo "WARNING: No non-default routes in solver for $node/$iface (routes4/routes6 empty or missing)" >&2
    return 0
  fi

  # Print v4 then v6 (each may be empty)
  if [ -n "${v4//[[:space:]]/}" ]; then
    printf '%s\n' "$v4"
  fi
  if [ -n "${v6//[[:space:]]/}" ]; then
    printf '%s\n' "$v6"
  fi
}

# Tenants list (for ISP return routes)
TENANT_SUBNETS_V4="$(jq_opt '.site._routingMaps.tenants.ipv4[]?' 'tenant ipv4 list')"
TENANT_SUBNETS_V6="$(jq_opt '.site._routingMaps.tenants.ipv6[]?' 'tenant ipv6 list')"

emit_isp_return_routes() {
  # These routes are NOT in solver (ISP is static), but are REQUIRED for return traffic.
  # We derive tenant subnets from solver and route them back to core.
  if [ -z "${TENANT_SUBNETS_V4//[[:space:]]/}" ] && [ -z "${TENANT_SUBNETS_V6//[[:space:]]/}" ]; then
    echo "WARNING: Missing tenant subnet lists in solver (.site._routingMaps.tenants.*). ISP will not get return routes." >&2
    return 0
  fi

  if [ -n "${TENANT_SUBNETS_V4//[[:space:]]/}" ]; then
    while IFS= read -r dst; do
      [ -z "${dst:-}" ] && continue
      printf 'ip route replace %s via %s\n' "$dst" "203.0.113.1"
    done <<<"$TENANT_SUBNETS_V4"
  else
    echo "WARNING: Missing .site._routingMaps.tenants.ipv4[] in solver; no ISP IPv4 return routes emitted" >&2
  fi

  if [ -n "${TENANT_SUBNETS_V6//[[:space:]]/}" ]; then
    while IFS= read -r dst; do
      [ -z "${dst:-}" ] && continue
      printf 'ip -6 route replace %s via %s\n' "$dst" "2001:db8:ffff::1"
    done <<<"$TENANT_SUBNETS_V6"
  else
    echo "WARNING: Missing .site._routingMaps.tenants.ipv6[] in solver; no ISP IPv6 return routes emitted" >&2
  fi
}

# -----------------------------
# P2P link addresses
# -----------------------------

ACCESS_POLICY_V4="$(jq_req '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-access"].addr4' "access-policy addr4")"
ACCESS_POLICY_V6="$(jq_req '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-access"].addr6' "access-policy addr6")"

POLICY_ACCESS_V4="$(jq_req '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-policy"].addr4' "policy-access addr4")"
POLICY_ACCESS_V6="$(jq_req '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-policy"].addr6' "policy-access addr6")"

POLICY_UP_V4="$(jq_req '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-policy"].addr4' "policy-up addr4")"
POLICY_UP_V6="$(jq_req '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-policy"].addr6' "policy-up addr6")"

UP_POLICY_V4="$(jq_req '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr4' "upstream-policy addr4")"
UP_POLICY_V6="$(jq_req '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr6' "upstream-policy addr6")"

CORE_UP_V4="$(jq_req '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-core"].addr4' "core-up addr4")"
CORE_UP_V6="$(jq_req '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-core"].addr6' "core-up addr6")"

UP_CORE_V4="$(jq_req '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr4' "up-core addr4")"
UP_CORE_V6="$(jq_req '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr6' "up-core addr6")"

# -----------------------------
# Client subnet
# -----------------------------

CLIENT_SUBNET_V4="$(jq_req '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv4' "clients ipv4")"
CLIENT_SUBNET_V6="$(jq_req '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv6' "clients ipv6")"

CLIENT_GW_V4="$(echo "$CLIENT_SUBNET_V4" | awk -F'[./]' '{printf "%d.%d.%d.1\n",$1,$2,$3}')"
CLIENT_GW_V6="$(echo "$CLIENT_SUBNET_V6" | sed 's|::/64|::1|')"

CLIENT_IP_V4="$(echo "$CLIENT_SUBNET_V4" | awk -F'[./]' '{printf "%d.%d.%d.2/24\n",$1,$2,$3}')"
CLIENT_IP_V6="$(echo "$CLIENT_SUBNET_V6" | sed 's|::/64|::2/64|')"

# -----------------------------
# Static ISP
# -----------------------------

ISP_CORE_V4="203.0.113.1/30"
ISP_CORE_V6="2001:db8:ffff::1/48"
ISP_ISP_V4="203.0.113.2/30"
ISP_ISP_V6="2001:db8:ffff::2/48"

# -----------------------------
# Routes REQUIRED for connectivity (derived from solver + static ISP)
#
# NOTE:
# - These non-default tenant routes are the "missing" pieces that make return traffic work:
#   policy -> access (tenants)
#   upstream-selector -> policy (tenants)
#   core -> upstream-selector (tenants)
# - ISP return routes are NOT in solver, injected here for all tenant subnets.
# -----------------------------

POLICY_TO_ACCESS_ROUTES="$(emit_routes_from_solver_iface "s-router-policy" "p2p-s-router-access-s-router-policy" || true)"
UPSEL_TO_POLICY_ROUTES="$(emit_routes_from_solver_iface "s-router-upstream-selector" "p2p-s-router-policy-s-router-upstream-selector" || true)"
CORE_TO_UPSEL_ROUTES="$(emit_routes_from_solver_iface "s-router-core" "p2p-s-router-core-s-router-upstream-selector" || true)"
ISP_RETURN_ROUTES="$(emit_isp_return_routes || true)"

# -----------------------------
# Emit topology
# -----------------------------

cat >"$TOPO_FILE" <<EOF
name: fabric

topology:
  defaults:
    kind: linux
    image: frrouting/frr:latest
    sysctls:
      net.ipv4.ip_forward: "1"
      net.ipv6.conf.all.forwarding: "1"
      net.ipv4.conf.all.rp_filter: "0"
      net.ipv4.conf.default.rp_filter: "0"

  nodes:
    s-router-access:
      network-mode: none
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip addr replace ${ACCESS_POLICY_V4} dev eth1
        - ip -6 addr replace ${ACCESS_POLICY_V6} dev eth1
        - ip link set eth2 up
        - ip addr replace ${CLIENT_GW_V4}/24 dev eth2
        - ip -6 addr replace ${CLIENT_GW_V6}/64 dev eth2
        - ip route replace default via ${POLICY_ACCESS_V4%/*}
        - ip -6 route replace default via ${POLICY_ACCESS_V6%/*}

    s-router-policy:
      network-mode: none
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip link set eth2 up
        - ip addr replace ${POLICY_ACCESS_V4} dev eth1
        - ip -6 addr replace ${POLICY_ACCESS_V6} dev eth1
        - ip addr replace ${POLICY_UP_V4} dev eth2
        - ip -6 addr replace ${POLICY_UP_V6} dev eth2
$(printf '%s\n' "${POLICY_TO_ACCESS_ROUTES:-}" | indent_exec_block)
        - ip route replace default via ${UP_POLICY_V4%/*}
        - ip -6 route replace default via ${UP_POLICY_V6%/*}

    s-router-core:
      network-mode: none
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip addr replace ${CORE_UP_V4} dev eth1
        - ip -6 addr replace ${CORE_UP_V6} dev eth1
        - ip link set eth2 up
        - ip addr replace ${ISP_CORE_V4} dev eth2
        - ip -6 addr replace ${ISP_CORE_V6} dev eth2
$(printf '%s\n' "${CORE_TO_UPSEL_ROUTES:-}" | indent_exec_block)
        - ip route replace default via 203.0.113.2
        - ip -6 route replace default via 2001:db8:ffff::2

    s-router-upstream-selector:
      network-mode: none
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip link set eth2 up
        - ip addr replace ${UP_CORE_V4} dev eth1
        - ip -6 addr replace ${UP_CORE_V6} dev eth1
        - ip addr replace ${UP_POLICY_V4} dev eth2
        - ip -6 addr replace ${UP_POLICY_V6} dev eth2
$(printf '%s\n' "${UPSEL_TO_POLICY_ROUTES:-}" | indent_exec_block)
        - ip route replace default via ${CORE_UP_V4%/*}
        - ip -6 route replace default via ${CORE_UP_V6%/*}

    isp:
      network-mode: none
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip addr replace ${ISP_ISP_V4} dev eth1
        - ip -6 addr replace ${ISP_ISP_V6} dev eth1
$(printf '%s\n' "${ISP_RETURN_ROUTES:-}" | indent_exec_block)

    client:
      network-mode: none
      exec:
        - ip link set eth1 up
        - ip addr replace ${CLIENT_IP_V4} dev eth1
        - ip -6 addr replace ${CLIENT_IP_V6} dev eth1
        - ip route replace default via ${CLIENT_GW_V4}
        - ip -6 route replace default via ${CLIENT_GW_V6}

  links:
    - endpoints: ["s-router-access:eth1", "s-router-policy:eth1"]
    - endpoints: ["s-router-policy:eth2", "s-router-upstream-selector:eth2"]
    - endpoints: ["s-router-core:eth1", "s-router-upstream-selector:eth1"]
    - endpoints: ["s-router-core:eth2", "isp:eth1"]
    - endpoints: ["s-router-access:eth2", "client:eth1"]
EOF
