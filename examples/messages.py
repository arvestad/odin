"""Showcases info, warning, and error messages during a computation."""
import time
from odin import Reporter

r = Reporter('data pipeline', total=100)

for i in range(100):
    time.sleep(0.1)
    r.progress(i + 1)

    if i  == 10:
        r.error('Oh no, i == 10!')
        time.sleep(0.2)
    elif i == 30:
        r.info('Phase 1 complete, starting phase 2')
    elif i == 49:
        r.warning('Disk usage above 80%, consider cleaning up')
        time.sleep(0.2)
    elif i == 74:
        r.info('Phase 2 complete, starting phase 3')
    elif i == 90:
        r.warning('Two input files had unexpected format, skipped')
        time.sleep(0.2)

r.done()
