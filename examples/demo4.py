from odin import Reporter 
import time

raven = Reporter('Demo 4: this label is really unnecessarily long, but there are times when long labels are needed', total=123)
for i in range(123):
    time.sleep(0.05)
    raven.progress(i)
    if i % 10 == 0:
        raven.info(f'Yay {i}!')
        
raven.done()
