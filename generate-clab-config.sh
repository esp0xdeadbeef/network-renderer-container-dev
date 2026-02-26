#!/usr/bin/env bash
set -euo pipefail

DEFAULT_SOLVER_JSON="output-network-solver.json"
DEFAULT_TOPO_FILE="fabric.clab.yml"

SOLVER_JSON="${1:-$DEFAULT_SOLVER_JSON}"
TOPO_FILE="${2:-$DEFAULT_TOPO_FILE}"

if [ ! -f "$SOLVER_JSON" ]; then
  echo "ERROR: Solver JSON not found: $SOLVER_JSON" >&2
  exit 1
fi

jq_req() {
  local query="$1"
  local desc="$2"
  local val
  val="$(jq -er "$query" "$SOLVER_JSON")" || {
    echo "ERROR: Missing required solver field: $desc ($query)" >&2
    exit 1
  }
  printf '%s\n' "$val"
}

jq_req_args() {
  local desc="$1"
  shift
  local val
  val="$(jq -er "$@" "$SOLVER_JSON")" || {
    echo "ERROR: Missing required solver field: $desc" >&2
    exit 1
  }
  printf '%s\n' "$val"
}

# Properly indent generated exec lines (8 spaces + "- ")
indent_exec() {
  sed '/^[[:space:]]*$/d; s/^/        - /'
}

# -----------------------------------------------------------------------------
# Inputs from solver.json
# -----------------------------------------------------------------------------

CORE_NODE="$(jq_req '.site._routingMaps.assumptions.core' "assumptions.core")"
POLICY_NODE="$(jq_req '.site._routingMaps.assumptions.policy' "assumptions.policy")"
ACCESS_NODE="$(jq_req '.site._routingMaps.assumptions.singleAccess' "assumptions.singleAccess")"
UPSEL_NODE="$(jq_req '.site._routingMaps.assumptions.upstreamSelector' "assumptions.upstreamSelector")"

TENANTS_V4=($(jq -r '.site._routingMaps.tenants.ipv4[]' "$SOLVER_JSON"))
TENANTS_V6=($(jq -r '.site._routingMaps.tenants.ipv6[]' "$SOLVER_JSON"))

CLIENT_TENANT_V4="$(jq -r '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv4' "$SOLVER_JSON" | head -n1)"
CLIENT_TENANT_V6="$(jq -r '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv6' "$SOLVER_JSON" | head -n1)"

# -----------------------------------------------------------------------------
# Link addresses
# -----------------------------------------------------------------------------

ACCESS_POLICY_V4="$(jq_req_args "access-policy addr4" \
  --arg a "$ACCESS_NODE" \
  '.site.links["p2p-s-router-access-s-router-policy"].endpoints[$a].addr4')"

ACCESS_POLICY_V6="$(jq_req_args "access-policy addr6" \
  --arg a "$ACCESS_NODE" \
  '.site.links["p2p-s-router-access-s-router-policy"].endpoints[$a].addr6')"

POLICY_ACCESS_V4="$(jq_req_args "policy-access addr4" \
  --arg p "$POLICY_NODE" \
  '.site.links["p2p-s-router-access-s-router-policy"].endpoints[$p].addr4')"

POLICY_ACCESS_V6="$(jq_req_args "policy-access addr6" \
  --arg p "$POLICY_NODE" \
  '.site.links["p2p-s-router-access-s-router-policy"].endpoints[$p].addr6')"

CORE_UP_V4="$(jq_req_args "core-up addr4" \
  --arg c "$CORE_NODE" \
  '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints[$c].addr4')"

CORE_UP_V6="$(jq_req_args "core-up addr6" \
  --arg c "$CORE_NODE" \
  '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints[$c].addr6')"

UP_CORE_V4="$(jq_req_args "up-core addr4" \
  --arg u "$UPSEL_NODE" \
  '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints[$u].addr4')"

UP_CORE_V6="$(jq_req_args "up-core addr6" \
  --arg u "$UPSEL_NODE" \
  '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints[$u].addr6')"

POLICY_UP_V4="$(jq_req_args "policy-up addr4" \
  --arg p "$POLICY_NODE" \
  '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints[$p].addr4')"

POLICY_UP_V6="$(jq_req_args "policy-up addr6" \
  --arg p "$POLICY_NODE" \
  '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints[$p].addr6')"

UP_POLICY_V4="$(jq_req_args "up-policy addr4" \
  --arg u "$UPSEL_NODE" \
  '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints[$u].addr4')"

UP_POLICY_V6="$(jq_req_args "up-policy addr6" \
  --arg u "$UPSEL_NODE" \
  '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints[$u].addr6')"

# -----------------------------------------------------------------------------
# Route emitters (correctly indented)
# -----------------------------------------------------------------------------

emit_routes4() {
  local node="$1"
  local ifname="$2"
  jq -r --arg n "$node" --arg i "$ifname" '
    (.site.nodes[$n].interfaces[$i].routes4 // [])
    | map(select(.dst != "0.0.0.0/0"))
    | .[]
    | "ip route replace \(.dst) via \(.via4)"
  ' "$SOLVER_JSON" | indent_exec
}

emit_routes6() {
  local node="$1"
  local ifname="$2"
  jq -r --arg n "$node" --arg i "$ifname" '
    (.site.nodes[$n].interfaces[$i].routes6 // [])
    | map(select(.dst != "::/0"))
    | .[]
    | "ip -6 route replace \(.dst) via \(.via6)"
  ' "$SOLVER_JSON" | indent_exec
}

emit_default4() {
  local node="$1"
  local ifname="$2"
  jq -r --arg n "$node" --arg i "$ifname" '
    (.site.nodes[$n].interfaces[$i].routes4 // [])
    | map(select(.dst == "0.0.0.0/0"))
    | .[0].via4 // empty
  ' "$SOLVER_JSON"
}

emit_default6() {
  local node="$1"
  local ifname="$2"
  jq -r --arg n "$node" --arg i "$ifname" '
    (.site.nodes[$n].interfaces[$i].routes6 // [])
    | map(select(.dst == "::/0"))
    | .[0].via6 // empty
  ' "$SOLVER_JSON"
}

ACCESS_IF="p2p-s-router-access-s-router-policy"
POLICY_IF_ACCESS="p2p-s-router-access-s-router-policy"
POLICY_IF_UP="p2p-s-router-policy-s-router-upstream-selector"
UPSEL_IF_POLICY="p2p-s-router-policy-s-router-upstream-selector"
CORE_IF="p2p-s-router-core-s-router-upstream-selector"

ACCESS_DEF4="$(emit_default4 "$ACCESS_NODE" "$ACCESS_IF")"
ACCESS_DEF6="$(emit_default6 "$ACCESS_NODE" "$ACCESS_IF")"
POLICY_DEF4="$(emit_default4 "$POLICY_NODE" "$POLICY_IF_UP")"
POLICY_DEF6="$(emit_default6 "$POLICY_NODE" "$POLICY_IF_UP")"
UPSEL_DEF4="$(emit_default4 "$UPSEL_NODE" "$CORE_IF")"
UPSEL_DEF6="$(emit_default6 "$UPSEL_NODE" "$CORE_IF")"

# -----------------------------------------------------------------------------
# Static ISP + image
# -----------------------------------------------------------------------------

IMAGE="frrouting/frr:latest"
ISP_CORE_V4="203.0.113.1/30"
ISP_CORE_V6="2001:db8:ffff::1/48"
ISP_ISP_V4="203.0.113.2/30"
ISP_ISP_V6="2001:db8:ffff::2/48"

CLIENT_GW_V4="$(echo "$CLIENT_TENANT_V4" | awk -F'[./]' '{printf "%d.%d.%d.1\n",$1,$2,$3}')"
CLIENT_IP_V4="$(echo "$CLIENT_TENANT_V4" | awk -F'[./]' '{printf "%d.%d.%d.2/24\n",$1,$2,$3}')"
CLIENT_GW_V6="$(echo "$CLIENT_TENANT_V6" | sed 's|::/64|::1|')"
CLIENT_IP_V6="$(echo "$CLIENT_TENANT_V6" | sed 's|::/64|::2/64|')"

# -----------------------------------------------------------------------------
# Emit topology (valid YAML)
# -----------------------------------------------------------------------------

cat > "$TOPO_FILE" <<EOF
name: fabric

topology:
  defaults:
    kind: linux
    image: ${IMAGE}
    network-mode: none
    sysctls:
      net.ipv4.ip_forward: "1"
      net.ipv6.conf.all.forwarding: "1"
      net.ipv4.conf.default.rp_filter: "0"

  nodes:
    ${ACCESS_NODE}:
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip addr replace ${ACCESS_POLICY_V4} dev eth1
        - ip -6 addr replace ${ACCESS_POLICY_V6} dev eth1
        - ip link set eth2 up
        - ip addr replace ${CLIENT_GW_V4}/24 dev eth2
        - ip -6 addr replace ${CLIENT_GW_V6}/64 dev eth2
        - ip route replace default via ${ACCESS_DEF4}
        - ip -6 route replace default via ${ACCESS_DEF6}

    ${POLICY_NODE}:
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip link set eth2 up
        - ip addr replace ${POLICY_ACCESS_V4} dev eth1
        - ip -6 addr replace ${POLICY_ACCESS_V6} dev eth1
        - ip addr replace ${POLICY_UP_V4} dev eth2
        - ip -6 addr replace ${POLICY_UP_V6} dev eth2
EOF

emit_routes4 "$POLICY_NODE" "$POLICY_IF_ACCESS" >> "$TOPO_FILE"
emit_routes6 "$POLICY_NODE" "$POLICY_IF_ACCESS" >> "$TOPO_FILE"

cat >> "$TOPO_FILE" <<EOF
        - ip route replace default via ${POLICY_DEF4}
        - ip -6 route replace default via ${POLICY_DEF6}

    ${UPSEL_NODE}:
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip link set eth2 up
        - ip addr replace ${UP_CORE_V4} dev eth1
        - ip -6 addr replace ${UP_CORE_V6} dev eth1
        - ip addr replace ${UP_POLICY_V4} dev eth2
        - ip -6 addr replace ${UP_POLICY_V6} dev eth2
EOF

emit_routes4 "$UPSEL_NODE" "$UPSEL_IF_POLICY" >> "$TOPO_FILE"
emit_routes6 "$UPSEL_NODE" "$UPSEL_IF_POLICY" >> "$TOPO_FILE"

cat >> "$TOPO_FILE" <<EOF
        - ip route replace default via ${UPSEL_DEF4}
        - ip -6 route replace default via ${UPSEL_DEF6}

    ${CORE_NODE}:
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip addr replace ${CORE_UP_V4} dev eth1
        - ip -6 addr replace ${CORE_UP_V6} dev eth1
        - ip link set eth2 up
        - ip addr replace ${ISP_CORE_V4} dev eth2
        - ip -6 addr replace ${ISP_CORE_V6} dev eth2
EOF

emit_routes4 "$CORE_NODE" "$CORE_IF" >> "$TOPO_FILE"
emit_routes6 "$CORE_NODE" "$CORE_IF" >> "$TOPO_FILE"

cat >> "$TOPO_FILE" <<EOF
        - ip route replace default via 203.0.113.2
        - ip -6 route replace default via 2001:db8:ffff::2

    isp:
      exec:
        - sysctl -w net.ipv4.ip_forward=1
        - sysctl -w net.ipv6.conf.all.forwarding=1
        - ip link set eth1 up
        - ip addr replace ${ISP_ISP_V4} dev eth1
        - ip -6 addr replace ${ISP_ISP_V6} dev eth1
EOF

for v4 in "${TENANTS_V4[@]}"; do
  echo "        - ip route replace ${v4} via 203.0.113.1" >> "$TOPO_FILE"
done
for v6 in "${TENANTS_V6[@]}"; do
  echo "        - ip -6 route replace ${v6} via 2001:db8:ffff::1" >> "$TOPO_FILE"
done

cat >> "$TOPO_FILE" <<EOF

    client:
      exec:
        - ip link set eth1 up
        - ip addr replace ${CLIENT_IP_V4} dev eth1
        - ip -6 addr replace ${CLIENT_IP_V6} dev eth1
        - ip route replace default via ${CLIENT_GW_V4}
        - ip -6 route replace default via ${CLIENT_GW_V6}

  links:
    - endpoints: ["${ACCESS_NODE}:eth1", "${POLICY_NODE}:eth1"]
    - endpoints: ["${POLICY_NODE}:eth2", "${UPSEL_NODE}:eth2"]
    - endpoints: ["${CORE_NODE}:eth1", "${UPSEL_NODE}:eth1"]
    - endpoints: ["${CORE_NODE}:eth2", "isp:eth1"]
    - endpoints: ["${ACCESS_NODE}:eth2", "client:eth1"]
EOF
