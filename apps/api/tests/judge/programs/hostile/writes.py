for path in ("/usr/pwned", "/box/pwned", "/bin/pwned", "/etc/pwned"):
    try:
        with open(path, "w") as f:
            f.write("x")
        print("ESCAPED:wrote", path)
    except OSError:
        pass
# The private /tmp is a small tmpfs: filling it in 1 MB chunks must stop well short of 512 MB.
chunk = b"x" * (1 << 20)
written = 0
try:
    with open("/tmp/fill", "wb") as f:
        for _ in range(512):
            f.write(chunk)
            f.flush()
            written += 1
    print("ESCAPED:tmp unlimited")
except OSError:
    pass
print("done")
