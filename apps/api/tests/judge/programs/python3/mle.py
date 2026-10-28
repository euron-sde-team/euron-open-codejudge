x = bytearray(512 << 20)
for i in range(0, len(x), 4096):
    x[i] = 1
print(len(x))
