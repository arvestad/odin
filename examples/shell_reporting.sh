#!/bin/bash
# Shell script reporting examples.
# Each odin command connects, sends one message, and exits immediately.
# If no server is running the commands are silent no-ops (exit cleanly).

LABEL="shell demo"

# --- Progress reporting ---

# Report a single value out of a known total
odin progress "$LABEL" 0 10

# Simulate a 10-step pipeline
for step in $(seq 1 10); do
    echo "Working on step $step..."
    sleep 0.5
    odin progress "$LABEL" "$step" 10
done

# --- Messages ---

odin info    "$LABEL" "All steps complete"
odin warning "$LABEL" "Disk usage above 80%"
odin error   "$LABEL" "Config file missing — using defaults"

# --- Open-ended counting (no total) ---

COUNT_LABEL="log scanner"
count=0
while IFS= read -r line; do
    # Process the line ...
    (( count++ ))
    odin progress "$COUNT_LABEL" "$count"
done < /var/log/system.log 2>/dev/null || true

# --- Wrapping an external command ---

WRAP_LABEL="external tool"
odin progress "$WRAP_LABEL" 0 3

odin info "$WRAP_LABEL" "Compressing archive"
tar czf /tmp/odin_example.tar.gz /usr/share/doc 2>/dev/null || true
odin progress "$WRAP_LABEL" 1 3

odin info "$WRAP_LABEL" "Checking integrity"
tar tzf /tmp/odin_example.tar.gz > /dev/null 2>&1 \
    && odin progress "$WRAP_LABEL" 2 3 \
    || odin error "$WRAP_LABEL" "Archive integrity check failed"

odin info "$WRAP_LABEL" "Cleaning up"
rm -f /tmp/odin_example.tar.gz
odin progress "$WRAP_LABEL" 3 3

echo "Done."
