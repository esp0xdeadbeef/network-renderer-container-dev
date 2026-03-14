TODO — Renderer: derive policy externals from solved overlay realization

Problem
The renderer currently assumes that every external referenced by
communicationContract must correspond to a local interface tag on the
policy node.

This assumption is incorrect.

In the solved operational model an external domain may be realized through
a transport overlay that terminates on another Unit while still requiring
policy traversal.

The renderer must therefore resolve externals from the solved fabric
model rather than only from policy-node interfaces.

Required behavior

When an external appears in:

    site.communicationContract.allowedRelations[].to

and the external is listed in:

    site.domains.externals[]

the renderer must determine how that external is realized in the solved
network.

Resolution algorithm

1. Look for a local policy-node interface tagged with that external.
   If present, use it.

2. Otherwise resolve the external via overlay realization:

   - inspect site.transport.overlays[]
   - find overlay where overlay.name == external.name
   - determine termination node from overlay.terminateOn

3. Verify that policy traversal is required:

       "policy" ∈ overlay.mustTraverse

4. Locate the overlay interface on the termination node:

       site.nodes[overlay.terminateOn].interfaces.*
           where kind == "overlay"
           and overlay == external.name

5. Treat that overlay interface as the operational realization of the
   external domain.

Failure condition

Only fail if:

    external ∈ communicationContract
    AND
    external ∉ site.domains.externals
    OR
    no overlay realization exists
    OR
    traversal does not include policy

Rationale

The solver already provides a complete operational model including:

    domains.externals
    transport.overlays
    overlay interfaces on nodes

The renderer must use this information to resolve policy externals instead
of requiring them to be locally attached to the policy node.
