# TODO — Policy Firewall (Renderer)

## Goal
Implement deterministic policy enforcement on the policy router using nftables.
Policy decisions must be based on topology (interfaces / tenants), not subnets.

## Policy Location
- Firewall runs only on `policyNodeName`
- Other routers must not install policy rules

## Renderer Tasks
- Read `policy.rules` from solver output
- Map tenants → policy-router ingress interfaces
- Map `external` → upstream interface
- Translate policy rules into interface-to-interface nftables rules
- Preserve rule ordering and priorities

## Interface Zones
Derive zones from policy-router links:

- access-admin  → admin zone
- access-client → client zone
- access-mgmt   → mgmt zone
- upstream-selector → wan zone

Rules operate on:

    iifname (source zone)
    oifname (destination zone)

Do not match IP subnets.

## nftables Model
- table: `inet policy`
- hook: `forward`
- default policy: `drop`
- allow established/related
- apply rules generated from policy.rules

## Runtime Integration
- Write nft rules to `output/nftables/<site>.nft`
- Mount rules into the policy container
- Load rules during container startup

## Management Interface Safety
- Disable forwarding on containerlab `eth0`
- Exception: fake ISP peer container

## Validation
Verify policy behavior:

- client → mgmt DNS blocked
- admin → mgmt DNS allowed
- client → mgmt blocked
- client → WAN allowed
