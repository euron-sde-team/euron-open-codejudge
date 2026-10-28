import threading
import time

started = 0
try:
    for _ in range(10000):
        threading.Thread(target=time.sleep, args=(5,), daemon=True).start()
        started += 1
except RuntimeError:
    pass
print("ESCAPED:threads" if started > 64 else "done")
