# TODO — Routing Renderer Corrections

- [ ] Renderer must preserve prefix lengths exactly as emitted by the solver (no default `/24` or `/64` substitutions).
- [ ] Treat `kind = "p2p"` links as strict point-to-point networks; never render them as LAN segments.
- [ ] Client/container interfaces must derive addressing from the solver interface definition, not from address pools or inferred subnet sizes.
- [ ] Remove all renderer-side subnet assumptions; topology generation must be a pure projection of solver JSON.
- [ ] Ensure WAN default routes are rendered deterministically (no implicit ECMP unless explicitly defined by solver).
- [ ] Add renderer validation step: fail generation if rendered interface prefix ≠ solver interface prefix.
