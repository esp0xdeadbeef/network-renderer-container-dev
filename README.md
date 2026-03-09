
# Disclaimer

This project exists primarily to support my own infrastructure.

If it happens to be useful to others, great - just make sure to pin
a specific version (see the Nix manual for how to do this).

If it does not fit your needs, feel free to fork it and adapt it.
Pull requests are welcome, but they are unlikely to be merged if they
conflict with the architectural model used here.

The internal model and schema may change between versions.
Backward compatibility is not guaranteed.


# Network Compiler → Solver → Containerlab Renderer

This project generates a Containerlab network topology from a high level
network model.

Pipeline:

network-compiler -> network-solver -> renderer


## Repositories

Clone the required repositories:

```bash
git clone https://github.com/esp0xdeadbeef/network-compiler
git clone https://github.com/esp0xdeadbeef/network-solver
git clone https://github.com/esp0xdeadbeef/network-renderer-containerlab-linux-backend
```


## Requirements

Nix with flakes enabled.


## Step 1 — Compile

```bash
cd network-compiler
nix run .#compile -- examples/multi-wan/inputs.nix
```

This produces:

output-compiler-signed.json


## Step 2 — Solve

```bash
cd ../network-solver
nix run .#compile-and-solve -- ../network-compiler/examples/multi-wan/inputs.nix
```

This produces:

output-solver-signed.json


## Step 3 — Render Containerlab topology

```bash
cd ../network-renderer-containerlab-linux-backend
./run-clab-generator.sh
```

This generates:

fabric.clab.yml
vm-bridges-generated.nix


## Step 4 — Start VM

```bash
# this will recompile all inputs with ./run-clab-generator (edit ./run-clab-generator.sh to change the inputs)
./start-vm.sh
```

Connect to the VM:

```bash
ssh -o "StrictHostKeyChecking no" -p2222 root@localhost
```


## Notes

Current routing: static routes

Router roles:

core  
policy  
access  
upstream-selector
