"""Open-ended task: no total known upfront, just counting items processed."""
import time
from odin import Reporter

r = Reporter('stream processor')  # no total= argument
count = 0
for _ in range(120):
    time.sleep(0.05)
    count += 1
    r.progress(count)
    if count % 30 == 0:
        r.info(f'Processed {count} items so far')
r.done()
