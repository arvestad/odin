from odin import Reporter 
import time
import random

raven = Reporter('Demo 3', total=123)
i = 0
while i < 123:
    i += random.randint(-10, 15)
    time.sleep(0.05)
    raven.progress(i)
    if i % 10 == 0:
        raven.info(f'Yay {i}!')
        
raven.done()
