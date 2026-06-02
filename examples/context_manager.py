"""Context manager usage: the error is automatically reported if the job crashes."""
import time
import random
from odin import Reporter

# Run this a few times — it will randomly crash partway through.
# Watch the viewer: a clean finish shows "done", a crash shows "error" then "died".

with Reporter('risky job', total=60) as r:
    r.info('An error will probably occur after 40+ iterations, randomly decided.')
    for i in range(60):
        time.sleep(0.05)
        r.progress(i + 1)
        if i > 40 and random.random() < 0.02:
            raise RuntimeError("Something went wrong at step 40")
