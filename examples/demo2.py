from odin import Reporter 
import time

raven = Reporter('Demo 2', total=123)
for i in range(123):
    time.sleep(0.05)
    raven.progress(i + 1)
    if i % 10 == 0:
        raven.info(f'Yay {i}!')
        
raven.done()
