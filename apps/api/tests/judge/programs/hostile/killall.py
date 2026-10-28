import os
import signal

try:
    os.kill(-1, signal.SIGKILL)
except OSError:
    pass
print("done")
