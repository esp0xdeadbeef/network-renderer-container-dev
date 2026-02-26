#!/usr/bin/env bash
set -euo pipefail

SOLVER_JSON="./output-network-solver.json"
TOPO_FILE="./fabric.clab.yml"

if [ ! -f "$SOLVER_JSON" ]; then
  echo "Missing $SOLVER_JSON"
  exit 1
fi

indent_exec_block() {
  sed 's/^/        - /'
}

strip_cidr() {
  echo "$1" | cut -d/ -f1
}

# -----------------------------
# P2P addressing (from solver)
# -----------------------------

ACCESS_POLICY_V4=$(jq -r '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-access"].addr4' "$SOLVER_JSON")
ACCESS_POLICY_V6=$(jq -r '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-access"].addr6' "$SOLVER_JSON")

POLICY_ACCESS_V4=$(jq -r '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-policy"].addr4' "$SOLVER_JSON")
POLICY_ACCESS_V6=$(jq -r '.site.links["p2p-s-router-access-s-router-policy"].endpoints["s-router-policy"].addr6' "$SOLVER_JSON")

CORE_UP_V4=$(jq -r '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-core"].addr4' "$SOLVER_JSON")
CORE_UP_V6=$(jq -r '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-core"].addr6' "$SOLVER_JSON")

UP_CORE_V4=$(jq -r '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr4' "$SOLVER_JSON")
UP_CORE_V6=$(jq -r '.site.links["p2p-s-router-core-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr6' "$SOLVER_JSON")

POLICY_UP_V4=$(jq -r '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-policy"].addr4' "$SOLVER_JSON")
POLICY_UP_V6=$(jq -r '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-policy"].addr6' "$SOLVER_JSON")

UP_POLICY_V4=$(jq -r '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr4' "$SOLVER_JSON")
UP_POLICY_V6=$(jq -r '.site.links["p2p-s-router-policy-s-router-upstream-selector"].endpoints["s-router-upstream-selector"].addr6' "$SOLVER_JSON")

CORE_P2P_IP_V4=$(strip_cidr "$CORE_UP_V4")
CORE_P2P_IP_V6=$(strip_cidr "$CORE_UP_V6")

# -----------------------------
# Defaults/routes (from solver)
# -----------------------------

ACCESS_DEFAULT_V4=$(jq -r '.site.nodes["s-router-access"].interfaces[] | .routes4[]? | select(.dst=="0.0.0.0/0") | .via4' "$SOLVER_JSON")
ACCESS_DEFAULT_V6=$(jq -r '.site.nodes["s-router-access"].interfaces[] | .routes6[]? | select(.dst=="::/0") | .via6' "$SOLVER_JSON")

POLICY_DEFAULT_V4=$(jq -r '.site.nodes["s-router-policy"].interfaces[] | .routes4[]? | select(.dst=="0.0.0.0/0") | .via4' "$SOLVER_JSON")
POLICY_DEFAULT_V6=$(jq -r '.site.nodes["s-router-policy"].interfaces[] | .routes6[]? | select(.dst=="::/0") | .via6' "$SOLVER_JSON")

POLICY_TENANT_ROUTES_V4=$(jq -r '
  .site.nodes["s-router-policy"].interfaces[]
  | .routes4[]?
  | select(.dst!="0.0.0.0/0")
  | "ip route replace \(.dst) via \(.via4)"
' "$SOLVER_JSON")

POLICY_TENANT_ROUTES_V6=$(jq -r '
  .site.nodes["s-router-policy"].interfaces[]
  | .routes6[]?
  | select(.dst!="::/0")
  | "ip -6 route replace \(.dst) via \(.via6)"
' "$SOLVER_JSON")

CORE_TENANT_ROUTES_V4=$(jq -r '
  .site.nodes["s-router-core"].interfaces[]
  | .routes4[]?
  | "ip route replace \(.dst) via \(.via4)"
' "$SOLVER_JSON")

CORE_TENANT_ROUTES_V6=$(jq -r '
  .site.nodes["s-router-core"].interfaces[]
  | .routes6[]?
  | "ip -6 route replace \(.dst) via \(.via6)"
' "$SOLVER_JSON")

# -----------------------------
# Client subnet (from solver)
# -----------------------------

CLIENT_SUBNET_V4=$(jq -r '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv4' "$SOLVER_JSON")
CLIENT_SUBNET_V6=$(jq -r '.site.compilerIR.domains.tenants[] | select(.name=="clients") | .ipv6' "$SOLVER_JSON")

CLIENT_V4=$(echo "$CLIENT_SUBNET_V4" | awk -F'[./]' '{printf "%d.%d.%d.2/24\n",$1,$2,$3}')
CLIENT_V6=$(echo "$CLIENT_SUBNET_V6" | sed 's|::/64|::2/64|')

CLIENT_GW_V4=$(echo "$CLIENT_SUBNET_V4" | awk -F'[./]' '{printf "%d.%d.%d.1\n",$1,$2,$3}')
CLIENT_GW_V6=$(echo "$CLIENT_SUBNET_V6" | sed 's|::/64|::1|')

# -----------------------------
# Transit aggregate back to core (derived from solver p2p pool base)
#   - IPv4: take pool base X.Y.Z.0 -> X.Y.Z.0/29
#   - IPv6: take pool base prefix -> <prefix>::/124
# -----------------------------

P2P_POOL_V4=$(jq -r '.site.compilerIR.addressPools.p2p.ipv4' "$SOLVER_JSON")   # e.g. 10.10.0.0/24
P2P_POOL_V6=$(jq -r '.site.compilerIR.addressPools.p2p.ipv6' "$SOLVER_JSON")   # e.g. fd42:dead:beef:1000::/118

P2P_AGG_V4=$(echo "$P2P_POOL_V4" | awk -F'[./]' '{printf "%d.%d.%d.0/29\n",$1,$2,$3}')
P2P_AGG_V6="$(echo "$P2P_POOL_V6" | cut -d/ -f1 | sed 's/::*$/::/')/124"

# -----------------------------
# Static ISP (not in solver)
# -----------------------------

ISP_CORE_V4="203.0.113.1/30"
ISP_ISP_V4="203.0.113.2/30"
ISP_CORE_V6="2001:db8:ffff::1/48"
ISP_ISP_V6="2001:db8:ffff::2/48"

cat > "$TOPO_FILE" <<EOF
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
        - ip link set eth1 up
        - ip addr replace ${ACCESS_POLICY_V4} dev eth1
        - ip -6 addr replace ${ACCESS_POLICY_V6} dev eth1
        - ip link set eth2 up
        - ip addr replace ${CLIENT_GW_V4}/24 dev eth2
        - ip -6 addr replace ${CLIENT_GW_V6}/64 dev eth2
        - ip route replace default via ${ACCESS_DEFAULT_V4}
        - ip -6 route replace default via ${ACCESS_DEFAULT_V6}

    s-router-policy:
      network-mode: none
      exec:
        - ip link set eth1 up
        - ip link set eth2 up
        - ip addr replace ${POLICY_ACCESS_V4} dev eth1
        - ip -6 addr replace ${POLICY_ACCESS_V6} dev eth1
        - ip addr replace ${POLICY_UP_V4} dev eth2
        - ip -6 addr replace ${POLICY_UP_V6} dev eth2
$(echo "$POLICY_TENANT_ROUTES_V4" | indent_exec_block)
$(echo "$POLICY_TENANT_ROUTES_V6" | indent_exec_block)
        - ip route replace default via ${POLICY_DEFAULT_V4}
        - ip -6 route replace default via ${POLICY_DEFAULT_V6}

    s-router-core:
      network-mode: none
      exec:
        - ip link set eth1 up
        - ip addr replace ${CORE_UP_V4} dev eth1
        - ip -6 addr replace ${CORE_UP_V6} dev eth1
        - ip link set eth2 up
        - ip addr replace ${ISP_CORE_V4} dev eth2
        - ip -6 addr replace ${ISP_CORE_V6} dev eth2
$(echo "$CORE_TENANT_ROUTES_V4" | indent_exec_block)
$(echo "$CORE_TENANT_ROUTES_V6" | indent_exec_block)
        - ip route replace default via 203.0.113.2
        - ip -6 route replace default via 2001:db8:ffff::2

    s-router-upstream-selector:
      network-mode: none
      exec:
        - ip link set eth1 up
        - ip link set eth2 up
        - ip addr replace ${UP_CORE_V4} dev eth1
        - ip -6 addr replace ${UP_CORE_V6} dev eth1
        - ip addr replace ${UP_POLICY_V4} dev eth2
        - ip -6 addr replace ${UP_POLICY_V6} dev eth2
        - ip route replace default via ${CORE_P2P_IP_V4}
        - ip -6 route replace default via ${CORE_P2P_IP_V6}

    isp:
      network-mode: none
      exec:
        - ip link set eth1 up
        - ip addr replace ${ISP_ISP_V4} dev eth1
        - ip -6 addr replace ${ISP_ISP_V6} dev eth1
        - ip route replace ${CLIENT_SUBNET_V4} via 203.0.113.1
        - ip -6 route replace ${CLIENT_SUBNET_V6} via 2001:db8:ffff::1
        - ip route replace ${P2P_AGG_V4} via 203.0.113.1
        - ip -6 route replace ${P2P_AGG_V6} via 2001:db8:ffff::1

    client:
      network-mode: none
      exec:
        - ip link set eth1 up
        - ip addr replace ${CLIENT_V4} dev eth1
        - ip -6 addr replace ${CLIENT_V6} dev eth1
        - ip route replace default via ${CLIENT_GW_V4}
        - ip -6 route replace default via ${CLIENT_GW_V6}

  links:
    - endpoints: ["s-router-access:eth1", "s-router-policy:eth1"]
    - endpoints: ["s-router-policy:eth2", "s-router-upstream-selector:eth2"]
    - endpoints: ["s-router-core:eth1", "s-router-upstream-selector:eth1"]
    - endpoints: ["s-router-core:eth2", "isp:eth1"]
    - endpoints: ["s-router-access:eth2", "client:eth1"]
EOF
