"""Multiple concurrent reporters running in separate threads."""
import threading
import time
from odin import Reporter


def run_job(name: str, steps: int, step_time: float) -> None:
    r = Reporter(name, total=steps)
    for i in range(steps):
        time.sleep(step_time)
        r.progress(i + 1)
    r.done()


jobs = [
    ("fast job",   50,  0.04),
    ("medium job", 80,  0.07),
    ("slow job",   30,  0.15),
]

threads = [threading.Thread(target=run_job, args=job) for job in jobs]
for t in threads:
    t.start()
for t in threads:
    t.join()
