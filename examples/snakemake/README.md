# Snakemake example

A minimal workflow for trying out `odin snakemake` — no external tools or
input data required. Requires `snakemake` to be installed (`pip install
snakemake`).

Start the Odin server first:

```bash
odin serve
```

Then run the workflow with its progress piped into Odin:

```bash
cd examples/snakemake
snakemake -j1 --forceall 2>&1 | odin snakemake
```

Watch it on `http://localhost:6271` or with `odin watch` in another terminal —
you should see a `snakemake` session climb from 0 to 6 steps.

To see the error path instead, run the deliberately failing rule:

```bash
snakemake -j1 output/boom.txt 2>&1 | odin snakemake
```

Clean up generated output with `rm -rf output`.
