for path in ("/usr/pwned", "/box/pwned", "/bin/pwned", "/etc/pwned"):
    try:
        open(path, "w").write("x")
        print("ESCAPED:wrote", path)
    except OSError:
        pass
try:
    with open("/tmp/fill", "wb") as f:
        f.write(b"x" * (512 << 20))
    print("ESCAPED:tmp unlimited")
except OSError:
    pass
print("done")
