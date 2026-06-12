from odin import Reporter 
import time

raven = Reporter('Uneven times', total=123)
for i in range(1,123):
    if i < 20:
        time.sleep(1)
    else:
        time.sleep(0.1)
    raven.progress(i+1)
    if i % 10 == 0:
        raven.info(f'Yay {i}!')
        
raven.done()
