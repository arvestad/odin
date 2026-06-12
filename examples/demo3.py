from odin import Reporter 
import time
import random

the_end = 123
raven = Reporter('Demo 3', total=the_end)
i = 0
while i < the_end:
    i += min(random.randint(-10, 15), the_end - i)
    time.sleep(0.1)
    raven.progress(i)
    if i % 10 == 0:
        raven.info(f'Yay {i}!')
        
raven.done()
