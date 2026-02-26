# FILE: ./generate-clab-config.sh
#!/usr/bin/env bash
set -euo pipefail

SOLVER_JSON="./output-network-solver.json"
TOPO_FILE="./fabric.clab.yml"

if [ ! -f "$SOLVER_JSON" ]; then
  echo "ERROR: Missing $SOLVER_JSON" >&2
  exit 1
fi

strip_cidr() {
  echo "$1" | cut -d/ -f1
}

jq_req() {
  local query="$1"
  local desc="$2"
  local val
  val="$(jq -er "$query" "$SOLVER_JSON" 2>/dev/null || true)"
  if [ -z "${val:-}" ] || [ "$val" = "null" ]; then
    echo "ERROR: Missing required solver field: $desc ($query)" >&2
    exit 1
  fi
  printf '%s\n' "$val"
}

indent_exec_block() {
  sed '/^[[:space:]]*$/d; s/^/        - /'
}

# Check if ANY non-default routes exist on an interface (IPv4)
iface_has_v4_routes() {
  local node="$1"
  local iface="$2"
  jq -e --arg n "$node" --arg i "$iface" '
    (.site.nodes[$n].interfaces[$i].routes4 // [])
    | map(select(.dst != "0.0.0.0/0"))
    | length > 0
  ' "$SOLVER_JSON" >/dev/null 2>&1
}

# Check if ANY non-default routes exist on an interface (IPv6)
iface_has_v6_routes() {
  local node="$1"
  local iface="$2"
  jq -e --arg n "$node" --arg i "$iface" '
    (.site.nodes[$n].interfaces[$i].routes6 // [])
    | map(select(.dst != "::/0"))
    | length > 0
  ' "$SOLVER_JSON" >/dev/null 2>&1
}

# Emit ALL non-default routes from solver for an interface
emit_solver_routes() {
  local node="$1"
  local iface="$2"

  jq -r --arg n "$node" --arg i "$iface" '
    (
      (.site.nodes[$n].interfaces[$i].routes4 // [])
      | map(select(.dst != "0.0.0.0/0"))
      | .[]
      | "ip route replace \(.dst) via \(.via4)"
    ),
    (
      (.site.nodes[$n].interfaces[$i].routes6 // [])
      | map(select(.dst != "::/0"))
      | .[]
      | "ip -6 route replace \(.dst) via \(.via6)"
    )
  ' "$SOLVER_JSON"
}

# -----------------------------
# Addresses from solver
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

CLIENT_SUBNET_V4="$(jq_req '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv4' "clients ipv4")"
CLIENT_SUBNET_V6="$(jq_req '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv6' "clients ipv6")"

CLIENT_GW_V4="$(echo "$CLIENT_SUBNET_V4" | awk -F'[./]' '{printf "%d.%d.%d.1\n",$1,$2,$3}')"
CLIENT_GW_V6="$(echo "$CLIENT_SUBNET_V6" | sed 's|::/64|::1|')"

CLIENT_IP_V4="$(echo "$CLIENT_SUBNET_V4" | awk -F'[./]' '{printf "%d.%d.%d.2/24\n",$1,$2,$3}')"
CLIENT_IP_V6="$(echo "$CLIENT_SUBNET_V6" | sed 's|::/64|::2/64|')"

ISP_CORE_V4="203.0.113.1/30"
ISP_CORE_V6="2001:db8:ffff::1/48"
ISP_ISP_V4="203.0.113.2/30"
ISP_ISP_V6="2001:db8:ffff::2/48"

# -----------------------------
# GAP ANALYSIS
# -----------------------------

POLICY_TO_ACCESS_ROUTES=""
UPSEL_TO_POLICY_ROUTES=""
CORE_TO_UPSEL_ROUTES=""
ISP_RETURN_ROUTES=""

# policy → access
if iface_has_v4_routes "s-router-policy" "p2p-s-router-access-s-router-policy" || \
   iface_has_v6_routes "s-router-policy" "p2p-s-router-access-s-router-policy"; then
  POLICY_TO_ACCESS_ROUTES="$(emit_solver_routes "s-router-policy" "p2p-s-router-access-s-router-policy")"
else
  echo "GAP: Solver missing tenant routes on s-router-policy → injecting client subnet only" >&2
  POLICY_TO_ACCESS_ROUTES+="ip route replace ${CLIENT_SUBNET_V4} via ${ACCESS_POLICY_V4%/*}"$'\n'
  POLICY_TO_ACCESS_ROUTES+="ip -6 route replace ${CLIENT_SUBNET_V6} via ${ACCESS_POLICY_V6%/*}"$'\n'
fi

# upstream-selector → policy
if iface_has_v4_routes "s-router-upstream-selector" "p2p-s-router-policy-s-router-upstream-selector" || \
   iface_has_v6_routes "s-router-upstream-selector" "p2p-s-router-policy-s-router-upstream-selector"; then
  UPSEL_TO_POLICY_ROUTES="$(emit_solver_routes "s-router-upstream-selector" "p2p-s-router-policy-s-router-upstream-selector")"
else
  echo "GAP: Solver missing tenant routes on s-router-upstream-selector → injecting client subnet only" >&2
  UPSEL_TO_POLICY_ROUTES+="ip route replace ${CLIENT_SUBNET_V4} via ${POLICY_UP_V4%/*}"$'\n'
  UPSEL_TO_POLICY_ROUTES+="ip -6 route replace ${CLIENT_SUBNET_V6} via ${POLICY_UP_V6%/*}"$'\n'
fi

# core → upstream-selector
if iface_has_v4_routes "s-router-core" "p2p-s-router-core-s-router-upstream-selector" || \
   iface_has_v6_routes "s-router-core" "p2p-s-router-core-s-router-upstream-selector"; then
  CORE_TO_UPSEL_ROUTES="$(emit_solver_routes "s-router-core" "p2p-s-router-core-s-router-upstream-selector")"
else
  echo "GAP: Solver missing tenant routes on s-router-core → injecting client subnet only" >&2
  CORE_TO_UPSEL_ROUTES+="ip route replace ${CLIENT_SUBNET_V4} via ${UP_CORE_V4%/*}"$'\n'
  CORE_TO_UPSEL_ROUTES+="ip -6 route replace ${CLIENT_SUBNET_V6} via ${UP_CORE_V6%/*}"$'\n'
fi

# ISP return (never in solver)
echo "GAP: ISP return routes not modeled in solver → injecting client subnet return" >&2
ISP_RETURN_ROUTES+="ip route replace ${CLIENT_SUBNET_V4} via 203.0.113.1"$'\n'
ISP_RETURN_ROUTES+="ip -6 route replace ${CLIENT_SUBNET_V6} via 2001:db8:ffff::1"$'\n'

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
$(printf '%s\n' "$POLICY_TO_ACCESS_ROUTES" | indent_exec_block)
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
$(printf '%s\n' "$CORE_TO_UPSEL_ROUTES" | indent_exec_block)
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
$(printf '%s\n' "$UPSEL_TO_POLICY_ROUTES" | indent_exec_block)
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
$(printf '%s\n' "$ISP_RETURN_ROUTES" | indent_exec_block)

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
