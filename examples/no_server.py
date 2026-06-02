"""Demonstrates graceful fallback when no Odin server is running.

Run this without starting 'odin serve' first. Progress updates fall back
to stderr so the script still works — it just loses the fancy viewer.
"""
import time
from odin import track

for item in track(range(20), label='fallback demo'):
    time.sleep(0.1)
