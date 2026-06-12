from odin import Reporter 
import time
import random

raven = Reporter('Demo 4: this label is really unnecessarily long, but there are times when long labels are needed', total=99)
for i in range(99):
    time.sleep(0.05)
    raven.progress(i+1)
    if i % 10 == 0:
        if random.random() < 0.5:
            raven.info(f'Yay {i}!')
        else:
            raven.warning(f'Oh, {i=}')
        
raven.done()
