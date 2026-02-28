# TODO — Renderer

## projection
- [ ] renderer performs pure projection only
- [ ] no topology inference
- [ ] no policy decisions inside renderer

## allocation removal
- [ ] remove `clabgen/p2p_alloc.py`
- [ ] remove `clabgen/addressing.py`
- [ ] remove unused allocation helpers
- [ ] renderer cannot allocate IPs or subnets

## schema
- [ ] enforce `meta.schemaVersion` guard
- [ ] fail on unsupported schema versions
- [ ] keep enterprise-aware traversal only

## routing
- [ ] routes emitted only from solver interfaces
- [ ] no hardcoded routes
- [ ] no default-route injection

## ordering
- [ ] interface order provided by solver
- [ ] renderer stops deriving ordering from names
- [ ] identical input → identical YAML output

## isolation
- [ ] fail if `isolated == true` (until implemented)
- [ ] design isolation realization model
- [ ] implement namespace / VRF mapping

## node behavior
- [ ] remove global forwarding defaults
- [ ] forwarding controlled by solver metadata

## validation
- [ ] fail on missing routing assumptions
- [ ] fail on invalid links ↔ nodes references
- [ ] fail on unknown interface links
- [ ] errors include attribute path
