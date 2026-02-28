# ./todo.md

# TODO – Fix ISP Core / WAN Rendering

## Critical: WAN Links Not Rendered

- [ ] Stop skipping `kind == "wan"` links in generator
- [ ] Render WAN links even if only 1 endpoint exists in solver
- [ ] Introduce synthetic ISP nodes (`isp-a`, `isp-b`)
- [ ] Attach core WAN interfaces to synthetic ISP nodes
- [ ] Ensure exactly 2 endpoints per containerlab link (always)

## Topology Logic Corrections

- [ ] Do not silently `continue` on malformed links
- [ ] Fail fast if:
  - [ ] Endpoint count is invalid
  - [ ] Referenced unit does not exist
  - [ ] Container is missing
  - [ ] Interface mapping fails
- [ ] Remove any logic that drops links implicitly

## ISP Node Modeling

- [ ] Create one containerlab node per upstream ISP per site
- [ ] Deterministic naming:
  `esp0xdeadbeef-site-a-isp-a`
  `esp0xdeadbeef-site-a-isp-b`
- [ ] Each WAN link must produce:
  - core ↔ isp-a
  - core ↔ isp-b
- [ ] No single-endpoint links ever

## Verification

- [ ] `fabric.clab.yml` must contain:
  - [ ] ISP nodes
  - [ ] 2 WAN links per site
- [ ] `grep isp fabric.clab.yml` shows node + link entries
- [ ] containerlab deploy succeeds without endpoint errors
- [ ] No WAN links silently missing

---

Status: Broken  
Requirement: It must deterministically render all solver WAN links into valid 2-endpoint containerlab links.
