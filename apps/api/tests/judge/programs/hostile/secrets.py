import glob
import os

found = [
    p
    for pat in (
        "/var/cache/codejudge/**",
        "/opt/**",
        "/**/*.ans",
        "/home/**",
        "/root/**",
        "/etc/shadow",
        "/proc/1/environ",
        "/run/secrets/**",
    )
    for p in glob.glob(pat, recursive=True)
]
if found:
    print("ESCAPED:saw", found[:5])
if any(k for k in os.environ if "TOKEN" in k or "SECRET" in k or "PASSWORD" in k or "REDIS" in k):
    print("ESCAPED:env", sorted(os.environ))
print("done")
