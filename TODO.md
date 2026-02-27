# TODO — Renderer Alignment With Solver Contract

## Goal

Make **network-renderer-container-dev** a **pure projection layer** that consumes the solver output schema correctly and performs **no allocation or policy decisions**.

Renderer must strictly realize solver state.

* * *

## 1. Fix Solver Schema Consumption (BLOCKER)

### Problem

Renderer expects:

Codedata.site

but solver outputs:

Codedata.sites.<enterprise>.<site>

### Tasks

* Read solver JSON from:
    

Codesites → enterprise → site

* Add deterministic extraction:
    
    * Fail if:
        
        * no enterprises exist
            
        * more than one enterprise exists (temporary limitation)
            
        * more than one site exists (temporary limitation)
            
* Store extracted object as:
    

Codesite

* Replace all usages of:
    

Codedata["site"]

with:

Codesite

* * *

## 2. Enforce Required Routing Assumptions

### Required field

Codesite._routingMaps.assumptions

### Tasks

* Validate presence of:
    
    * `core`
        
    * `policy`
        
    * `singleAccess`
        
* Handle:
    

CodeupstreamSelector = null

as valid (single-WAN mode).

* Renderer must NOT crash when upstream selector is absent.
    

* * *

## 3. Remove Address Allocation From Renderer (CRITICAL)

### Problem

Renderer currently allocates P2P links independently.

This violates architecture:

Codesolver = allocation authority  
renderer = realization only

### Tasks

* Delete all logic that:
    
    * generates P2P subnets
        
    * assigns link addresses
        
    * computes adjacency topology
        
* Use only:
    

Codesite.links  
site.nodes[*].interfaces

as authoritative input.

Renderer must never invent network state.

* * *

## 4. Stop Hardcoding Routes

### Problem

Renderer injects default routes manually.

Solver already provides:

Codeinterfaces.routes4  
interfaces.routes6

### Tasks

* Remove hardcoded route generation.
    
* Emit routes strictly from solver interface definitions.
    

Single source of truth = solver output.

* * *

## 5. Deterministic Interface Ordering

### Problem

Interface numbering depends on unordered iteration.

### Tasks

* Sort deterministic inputs before rendering:
    
    * tenant domains (by name)
        
    * links (by key)
        
    * nodes (by name)
        

Goal:

Codesame solver input → identical topology output

(no diff churn).

* * *

## 6. Respect Unit Isolation Semantics

Solver provides:

Codeunits.<name>.isolated  
units.<name>.containers

Renderer currently ignores this.

### Tasks

* Prepare mapping layer:
    

Codeisolated unit → dedicated namespace / container / VRF  
non-isolated → default namespace

(implementation may be stubbed initially).

Renderer must not discard isolation metadata.

* * *

## 7. Add Schema Version Guard

### Tasks

* Read:
    

Codemeta.schemaVersion

* Implement version switch:
    

Codeif schemaVersion == 1:  
    legacy handling  
elif schemaVersion == 2:  
    enterprise-aware traversal  
else:  
    fail with clear error

Prevent silent contract breakage.

* * *

## 8. Security Hygiene

### Tasks

* Remove committed TLS private keys:
    
    Codeclab-fabric/.tls/**/*.key
    
* Add to `.gitignore`.
    
* Regenerate lab certificates.
    

* * *

## 9. Renderer Invariants (Add Validation)

Renderer must fail early if:

* `_routingMaps.assumptions` missing
    
* required roles missing
    
* nodes referenced by links do not exist
    
* interfaces reference unknown links
    

Errors must include attribute path.

* * *

## 10. Architectural Rule (MUST HOLD)

Renderer is **pure projection**:

Allowed:

* translate solver → containerlab YAML
    
* emit configs
    

Forbidden:

* allocate addresses
    
* infer topology
    
* inject routes
    
* invent roles
    

* * *

## Definition of Done

* Renderer runs successfully on multi-site solver output.
    
* No topology data is generated inside renderer.
    
* Re-running renderer produces identical output.
    
* Removing solver routes changes rendered routes automatically.
    
* Single-WAN and multi-WAN both render correctly.
    
