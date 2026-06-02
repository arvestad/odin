#!/bin/bash
# Shell script showing Odin's one-shot CLI commands.
# Each command connects, sends its message, and exits immediately.

LABEL="shell pipeline"

odin progress "$LABEL" 0 5

echo "Step 1: downloading data..."
sleep 1
odin progress "$LABEL" 1 5

echo "Step 2: validating..."
sleep 1
odin progress "$LABEL" 2 5
odin info "$LABEL" "Validation passed"

echo "Step 3: processing..."
sleep 1
odin progress "$LABEL" 3 5

echo "Step 4: writing output..."
sleep 1
odin progress "$LABEL" 4 5

echo "Step 5: cleaning up..."
sleep 1
odin progress "$LABEL" 5 5

echo "Done!"
