import ctypes

libc = ctypes.CDLL(None, use_errno=True)
CLONE_NEWUSER, CLONE_NEWNET = 0x10000000, 0x40000000
if libc.unshare(CLONE_NEWUSER) == 0:
    print("ESCAPED:unshare user")
if libc.unshare(CLONE_NEWNET) == 0:
    print("ESCAPED:unshare net")
if libc.ptrace(0, 0, 0, 0) == 0:
    print("ESCAPED:ptrace")
if libc.mount(b"none", b"/tmp", b"tmpfs", 0, None) == 0:
    print("ESCAPED:mount")
if libc.chroot(b"/tmp") == 0:
    print("ESCAPED:chroot")
print("done")
