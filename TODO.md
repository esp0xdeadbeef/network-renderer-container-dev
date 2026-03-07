# TODO — Fix tenant interface projection

Tenant networks are currently rendered as dummy interfaces when only one node participates, causing eth2 to never appear in Containerlab. Instead, always project tenant interfaces as Containerlab bridge links, even if there is only a single member, so the dataplane interface (e.g. eth2) is created deterministically. Bridge names must be truncated or hashed to <=15 characters (Linux bridge name limit) to ensure interfaces are created correctly.
