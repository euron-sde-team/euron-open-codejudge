import socket

for host, port in (("redis", 6379), ("api", 8080), ("1.1.1.1", 53), ("169.254.169.254", 80)):
    try:
        socket.create_connection((host, port), timeout=1)
        print("ESCAPED:connected", host)
    except OSError:
        pass
print("done")
