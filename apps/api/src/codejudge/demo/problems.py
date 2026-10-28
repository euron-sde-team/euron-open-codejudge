"""The demo problem set: real statements, generated hidden tests, solvers that produce the
answers, and reference solutions that must be accepted before a problem is published.

Every hidden test is generated from a fixed seed and answered by the Python solver here,
so the set is reproducible and every answer is right by construction. Solutions in other
languages are real programs: the judge compiles and runs them like any submission.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DemoProblem:
    slug: str
    title: str
    difficulty: str
    tags: list[str]
    statement: str
    samples: list[str]
    generate: Callable[[random.Random], list[str]]
    solve: Callable[[str], str]
    references: dict[str, str]
    # Wrong solutions the demo students submit (language, source, what they get).
    wrong: list[tuple[str, str]] = field(default_factory=list)
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    # Hidden groups: name -> (points, generator). Empty means one group "secret".
    groups: dict[str, tuple[float, Callable[[random.Random], list[str]]]] = field(
        default_factory=dict
    )
    checker: dict[str, Any] | None = None
    checker_source: str | None = None


# ── 1. Sum of two ────────────────────────────────────────────────────────────────────
def _sum_gen(r: random.Random) -> list[str]:
    big = 10**18
    cases = [f"{r.randint(-big, big)} {r.randint(-big, big)}\n" for _ in range(6)]
    return [*cases, f"{big} {big}\n", f"{-big} {-big}\n", "0 0\n"]


def _sum_solve(i: str) -> str:
    a, b = map(int, i.split())
    return f"{a + b}\n"


# ── 2. Second largest ────────────────────────────────────────────────────────────────
def _second_gen(r: random.Random) -> list[str]:
    out = []
    for n in (2, 3, 10, 1000, 200000):
        xs = [r.randint(-(10**9), 10**9) for _ in range(n)]
        out.append(f"{n}\n{' '.join(map(str, xs))}\n")
    out.append("4\n7 7 7 3\n")
    out.append("3\n5 5 5\n")
    return out


def _second_solve(i: str) -> str:
    xs = list(map(int, i.split()[1:]))
    distinct = sorted(set(xs), reverse=True)
    return f"{distinct[1] if len(distinct) > 1 else 'NONE'}\n"


# ── 3. Balanced brackets ─────────────────────────────────────────────────────────────
def _brackets_gen(r: random.Random) -> list[str]:
    out = []
    for n in (1, 2, 10, 1000, 100000):
        s = "".join(r.choice("()[]{}") for _ in range(n))
        out.append(s + "\n")
    good = []
    for _ in range(50000):
        good.append(r.choice(["()", "[]", "{}"]))
    out.append("".join(good) + "\n")
    out.append("([{}])" * 10000 + "\n")
    return out


def _brackets_solve(i: str) -> str:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in i.strip():
        if ch in "([{":
            stack.append(ch)
        elif not stack or stack.pop() != pairs[ch]:
            return "NO\n"
    return "YES\n" if not stack else "NO\n"


# ── 4. Grid shortest path (BFS) ──────────────────────────────────────────────────────
def _grid_gen(r: random.Random) -> list[str]:
    out = []
    for n, m, wall in (
        (3, 3, 0.0),
        (5, 7, 0.2),
        (50, 50, 0.3),
        (500, 500, 0.25),
        (1000, 1000, 0.1),
    ):
        rows = []
        for y in range(n):
            row = ["#" if r.random() < wall else "." for _ in range(m)]
            if y == 0:
                row[0] = "."
            if y == n - 1:
                row[-1] = "."
            rows.append("".join(row))
        out.append(f"{n} {m}\n" + "\n".join(rows) + "\n")
    return out


def _grid_solve(i: str) -> str:
    lines = i.split()
    n, m = int(lines[0]), int(lines[1])
    grid = lines[2 : 2 + n]
    from collections import deque

    dist = [[-1] * m for _ in range(n)]
    dist[0][0] = 0
    q = deque([(0, 0)])
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < n and 0 <= nx < m and grid[ny][nx] == "." and dist[ny][nx] < 0:
                dist[ny][nx] = dist[y][x] + 1
                q.append((ny, nx))
    return f"{dist[n - 1][m - 1]}\n"


# ── 5. Range sum queries (prefix sums; subtasks) ─────────────────────────────────────
def _rsq_case(r: random.Random, n: int, q: int) -> str:
    xs = [r.randint(-(10**9), 10**9) for _ in range(n)]
    qs = []
    for _ in range(q):
        a = r.randint(1, n)
        b = r.randint(a, n)
        qs.append(f"{a} {b}")
    return f"{n} {q}\n{' '.join(map(str, xs))}\n" + "\n".join(qs) + "\n"


def _rsq_small(r: random.Random) -> list[str]:
    return [_rsq_case(r, n, q) for n, q in ((1, 1), (10, 10), (1000, 1000))]


def _rsq_large(r: random.Random) -> list[str]:
    return [_rsq_case(r, n, q) for n, q in ((100000, 100000), (200000, 200000))]


def _rsq_solve(i: str) -> str:
    it = iter(i.split())
    n, q = int(next(it)), int(next(it))
    pre = [0]
    for _ in range(n):
        pre.append(pre[-1] + int(next(it)))
    out = []
    for _ in range(q):
        a, b = int(next(it)), int(next(it))
        out.append(str(pre[b] - pre[a - 1]))
    return "\n".join(out) + "\n"


# ── 6. Circle area (float tolerance) ─────────────────────────────────────────────────
def _circle_gen(r: random.Random) -> list[str]:
    return [f"{r.uniform(0.001, 10000):.6f}\n" for _ in range(8)] + ["1\n", "0.5\n"]


def _circle_solve(i: str) -> str:
    import math

    return f"{math.pi * float(i) ** 2:.9f}\n"


# ── 7. Any pair with a given sum (custom checker: many correct answers) ──────────────
def _pair_gen(r: random.Random) -> list[str]:
    out = []
    for n in (2, 5, 1000, 100000):
        xs = [r.randint(1, 10**6) for _ in range(n)]
        i, j = r.sample(range(n), 2)
        out.append(f"{n} {xs[i] + xs[j]}\n{' '.join(map(str, xs))}\n")
    out.append("3 100\n1 2 3\n")
    return out


def _pair_solve(i: str) -> str:
    it = iter(i.split())
    n, target = int(next(it)), int(next(it))
    xs = [int(next(it)) for _ in range(n)]
    seen: dict[int, int] = {}
    for idx, x in enumerate(xs, start=1):
        if target - x in seen:
            return f"{seen[target - x]} {idx}\n"
        seen.setdefault(x, idx)
    return "-1\n"


PAIR_CHECKER = """import sys

# Kattis output validator: exit 42 accepts, 43 rejects.
inp = open(sys.argv[1]).read().split()
ans = open(sys.argv[2]).read().split()
out = sys.stdin.read().split()
n, target = int(inp[0]), int(inp[1])
xs = [int(v) for v in inp[2:2 + n]]


def reject(msg):
    open(sys.argv[3] + "judgemessage.txt", "w").write(msg)
    sys.exit(43)


if ans == ["-1"]:
    if out != ["-1"]:
        reject("no pair exists, expected -1")
    sys.exit(42)
if len(out) != 2:
    reject("print two indices")
try:
    i, j = int(out[0]), int(out[1])
except ValueError:
    reject("indices must be integers")
if not (1 <= i <= n and 1 <= j <= n) or i == j:
    reject("indices out of range or equal")
if xs[i - 1] + xs[j - 1] != target:
    reject("the two numbers do not add up to the target")
sys.exit(42)
"""


# ── 8. Longest increasing subsequence ────────────────────────────────────────────────
def _lis_gen(r: random.Random) -> list[str]:
    out = []
    for n in (1, 8, 1000, 100000, 200000):
        xs = [r.randint(1, 10**9) for _ in range(n)]
        out.append(f"{n}\n{' '.join(map(str, xs))}\n")
    out.append("5\n5 4 3 2 1\n")
    return out


def _lis_solve(i: str) -> str:
    import bisect

    xs = list(map(int, i.split()[1:]))
    tails: list[int] = []
    for x in xs:
        k = bisect.bisect_left(tails, x)
        if k == len(tails):
            tails.append(x)
        else:
            tails[k] = x
    return f"{len(tails)}\n"


# ── 9. Count islands ─────────────────────────────────────────────────────────────────
def _islands_gen(r: random.Random) -> list[str]:
    out = []
    for n, m, land in ((1, 1, 1.0), (4, 5, 0.4), (100, 100, 0.45), (800, 800, 0.4)):
        rows = ["".join("1" if r.random() < land else "0" for _ in range(m)) for _ in range(n)]
        out.append(f"{n} {m}\n" + "\n".join(rows) + "\n")
    return out


def _islands_solve(i: str) -> str:
    parts = i.split()
    n, m = int(parts[0]), int(parts[1])
    grid = [list(row) for row in parts[2 : 2 + n]]
    count = 0
    for sy in range(n):
        for sx in range(m):
            if grid[sy][sx] != "1":
                continue
            count += 1
            stack = [(sy, sx)]
            grid[sy][sx] = "0"
            while stack:
                y, x = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < n and 0 <= nx < m and grid[ny][nx] == "1":
                        grid[ny][nx] = "0"
                        stack.append((ny, nx))
    return f"{count}\n"


# ── 10. Word frequency ───────────────────────────────────────────────────────────────
WORDS = [
    "judge",
    "code",
    "test",
    "array",
    "graph",
    "tree",
    "heap",
    "stack",
    "queue",
    "sort",
    "search",
    "path",
    "node",
    "edge",
]


def _freq_gen(r: random.Random) -> list[str]:
    out = []
    for n in (1, 6, 1000, 100000):
        words = [r.choice(WORDS) for _ in range(n)]
        out.append(f"{n}\n{' '.join(words)}\n")
    return out


def _freq_solve(i: str) -> str:
    from collections import Counter

    words = i.split()[1:]
    counts = Counter(words)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return "".join(f"{w} {c}\n" for w, c in ranked)


# ── 11. Coin change (DP) ─────────────────────────────────────────────────────────────
def _coins_gen(r: random.Random) -> list[str]:
    out = []
    for k, target in ((1, 7), (3, 11), (5, 1000), (10, 100000), (20, 1000000)):
        coins = sorted(r.sample(range(1, 200), k))
        out.append(f"{k} {target}\n{' '.join(map(str, coins))}\n")
    out.append("1 7\n2\n")
    return out


def _coins_solve(i: str) -> str:
    it = iter(i.split())
    k, target = int(next(it)), int(next(it))
    coins = [int(next(it)) for _ in range(k)]
    inf = 1 << 30
    best = [0] + [inf] * target
    for value in range(1, target + 1):
        for c in coins:
            if c <= value and best[value - c] + 1 < best[value]:
                best[value] = best[value - c] + 1
    return f"{best[target] if best[target] < inf else -1}\n"


# ── 12. Matrix rotation ──────────────────────────────────────────────────────────────
def _rotate_gen(r: random.Random) -> list[str]:
    out = []
    for n in (1, 2, 3, 50, 500):
        rows = [" ".join(str(r.randint(0, 99)) for _ in range(n)) for _ in range(n)]
        out.append(f"{n}\n" + "\n".join(rows) + "\n")
    return out


def _rotate_solve(i: str) -> str:
    parts = i.split()
    n = int(parts[0])
    vals = parts[1:]
    rows = [vals[k * n : (k + 1) * n] for k in range(n)]
    rotated = [[rows[n - 1 - c][r] for c in range(n)] for r in range(n)]
    return "".join(" ".join(row) + "\n" for row in rotated)


PROBLEMS: list[DemoProblem] = [
    DemoProblem(
        slug="sum-of-two",
        title="Sum of Two",
        difficulty="easy",
        tags=["math", "warm-up"],
        statement=(
            "Read two integers $a$ and $b$ and print $a + b$.\n\n"
            "## Input\n\nOne line with two integers $a$ and $b$ ($-10^{18} \\le a, b \\le 10^{18}$).\n\n"
            "## Output\n\nPrint $a + b$.\n\n"
            "> The sum can exceed 64 bits only at the extremes: think about which type holds it."
        ),
        samples=["1 2\n", "-7 10\n"],
        generate=_sum_gen,
        solve=_sum_solve,
        references={
            "python3": "a, b = map(int, input().split())\nprint(a + b)\n",
            "cpp17": "#include <iostream>\nint main() { __int128 a, b; long long x, y; std::cin >> x >> y; a = x; b = y; __int128 s = a + b;\n"
            "  if (s == 0) { std::cout << 0 << '\\n'; return 0; }\n  bool neg = s < 0; if (neg) s = -s; std::string d; while (s > 0) { d += char('0' + int(s % 10)); s /= 10; }\n"
            "  if (neg) d += '-'; std::cout << std::string(d.rbegin(), d.rend()) << '\\n'; }\n",
            "java21": "import java.math.BigInteger;\nimport java.util.Scanner;\npublic class Main { public static void main(String[] a) { Scanner s = new Scanner(System.in); System.out.println(new BigInteger(s.next()).add(new BigInteger(s.next()))); } }\n",
            "javascript": "const [a, b] = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/).map(BigInt);\nconsole.log((a + b).toString());\n",
        },
        wrong=[
            (
                "cpp17",
                "#include <iostream>\nint main() { long long a, b; std::cin >> a >> b; std::cout << a + b << '\\n'; }\n",
            )
        ],
    ),
    DemoProblem(
        slug="second-largest",
        title="Second Largest",
        difficulty="easy",
        tags=["arrays", "sorting"],
        statement=(
            "Given $n$ integers, print the second largest **distinct** value, or `NONE` when all "
            "values are equal.\n\n## Input\n\n$n$ ($2 \\le n \\le 2 \\cdot 10^5$), then $n$ integers "
            "$|x_i| \\le 10^9$.\n\n## Output\n\nThe second largest distinct value, or `NONE`."
        ),
        samples=["5\n4 1 9 9 3\n", "3\n5 5 5\n"],
        generate=_second_gen,
        solve=_second_solve,
        references={
            "python3": "n, *xs = map(int, open(0).read().split())\nd = sorted(set(xs), reverse=True)\nprint(d[1] if len(d) > 1 else 'NONE')\n",
            "cpp17": '#include <bits/stdc++.h>\nusing namespace std;\nint main(){int n;cin>>n;set<long long> s;for(int i=0;i<n;i++){long long x;cin>>x;s.insert(x);}\nif(s.size()<2){puts("NONE");return 0;}auto it=s.rbegin();++it;cout<<*it<<"\\n";}\n',
        },
        wrong=[
            ("python3", "n, *xs = map(int, open(0).read().split())\nxs.sort()\nprint(xs[-2])\n")
        ],
    ),
    DemoProblem(
        slug="balanced-brackets",
        title="Balanced Brackets",
        difficulty="easy",
        tags=["stack", "strings"],
        statement=(
            "A string of `()[]{}` is balanced when every bracket closes the most recent unclosed "
            "one of the same kind. Print `YES` or `NO`.\n\n## Input\n\nOne line, length up to "
            "$10^5$ (the large tests use longer lines).\n\n## Output\n\n`YES` or `NO`."
        ),
        samples=["([]{})\n", "([)]\n"],
        generate=_brackets_gen,
        solve=_brackets_solve,
        references={
            "python3": "s = input().strip()\np = {')': '(', ']': '[', '}': '{'}\nst = []\nok = True\nfor c in s:\n    if c in '([{':\n        st.append(c)\n    elif not st or st.pop() != p[c]:\n        ok = False\n        break\nprint('YES' if ok and not st else 'NO')\n",
            "javascript": "const s = require('fs').readFileSync(0, 'utf8').trim();\nconst p = { ')': '(', ']': '[', '}': '{' };\nconst st = [];\nlet ok = true;\nfor (const c of s) { if ('([{'.includes(c)) st.push(c); else if (st.pop() !== p[c]) { ok = false; break; } }\nconsole.log(ok && st.length === 0 ? 'YES' : 'NO');\n",
        },
        wrong=[
            ("python3", "s = input()\nprint('YES' if s.count('(') == s.count(')') else 'NO')\n")
        ],
    ),
    DemoProblem(
        slug="grid-escape",
        title="Grid Escape",
        difficulty="medium",
        tags=["graphs", "bfs"],
        statement=(
            "A grid has open cells `.` and walls `#`. Moving up, down, left or right, find the "
            "fewest moves from the top-left to the bottom-right corner, or $-1$ if it cannot be "
            "reached.\n\n## Input\n\n$n$ and $m$ ($1 \\le n, m \\le 1000$), then $n$ rows.\n\n"
            "## Output\n\nThe number of moves, or $-1$."
        ),
        samples=["3 3\n...\n.#.\n...\n", "2 2\n.#\n#.\n"],
        generate=_grid_gen,
        solve=_grid_solve,
        references={
            "cpp17": "#include <bits/stdc++.h>\nusing namespace std;\nint main(){int n,m;cin>>n>>m;vector<string> g(n);for(auto&r:g)cin>>r;vector<int> d(n*m,-1);deque<int> q;d[0]=0;q.push_back(0);\nint dy[]={1,-1,0,0},dx[]={0,0,1,-1};while(!q.empty()){int c=q.front();q.pop_front();int y=c/m,x=c%m;for(int k=0;k<4;k++){int ny=y+dy[k],nx=x+dx[k];if(ny<0||nx<0||ny>=n||nx>=m||g[ny][nx]=='#'||d[ny*m+nx]>=0)continue;d[ny*m+nx]=d[c]+1;q.push_back(ny*m+nx);}}\ncout<<d[n*m-1]<<\"\\n\";}\n",
            "python3": "import sys\nfrom collections import deque\nd = sys.stdin.read().split()\nn, m = int(d[0]), int(d[1])\ng = d[2:2 + n]\ndist = [-1] * (n * m)\ndist[0] = 0\nq = deque([0])\nwhile q:\n    c = q.popleft()\n    y, x = divmod(c, m)\n    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):\n        if 0 <= ny < n and 0 <= nx < m and g[ny][nx] == '.' and dist[ny * m + nx] < 0:\n            dist[ny * m + nx] = dist[c] + 1\n            q.append(ny * m + nx)\nprint(dist[n * m - 1])\n",
        },
        wrong=[
            (
                "python3",
                "import sys\nd = sys.stdin.read().split()\nn, m = int(d[0]), int(d[1])\nprint(n + m - 2)\n",
            )
        ],
    ),
    DemoProblem(
        slug="range-sums",
        title="Range Sums",
        difficulty="medium",
        tags=["prefix-sums", "subtasks"],
        statement=(
            "Answer $q$ queries: the sum of $x_a \\ldots x_b$.\n\n## Input\n\n$n$ and $q$, then "
            "the $n$ values ($|x_i| \\le 10^9$), then $q$ lines $a$ $b$ ($1 \\le a \\le b \\le n$).\n\n"
            "## Subtasks\n\n1. (40 points) $n, q \\le 1000$\n2. (60 points) $n, q \\le 2 \\cdot 10^5$\n\n"
            "## Output\n\nOne sum per line."
        ),
        samples=["5 3\n1 2 3 4 5\n1 5\n2 3\n4 4\n"],
        generate=_rsq_small,
        solve=_rsq_solve,
        groups={"small": (40, _rsq_small), "large": (60, _rsq_large)},
        references={
            "cpp17": "#include <bits/stdc++.h>\nusing namespace std;\nint main(){ios::sync_with_stdio(false);cin.tie(nullptr);int n,q;cin>>n>>q;vector<long long> p(n+1,0);for(int i=1;i<=n;i++){long long x;cin>>x;p[i]=p[i-1]+x;}\nwhile(q--){int a,b;cin>>a>>b;cout<<p[b]-p[a-1]<<'\\n';}}\n",
            "python3": "import sys\nd = sys.stdin.buffer.read().split()\nn, q = int(d[0]), int(d[1])\np = [0] * (n + 1)\nfor i in range(n):\n    p[i + 1] = p[i] + int(d[2 + i])\no = []\nk = 2 + n\nfor _ in range(q):\n    a, b = int(d[k]), int(d[k + 1])\n    k += 2\n    o.append(p[b] - p[a - 1])\nsys.stdout.write('\\n'.join(map(str, o)) + '\\n')\n",
        },
        # Correct but quadratic: full marks on the small subtask, too slow on the large one.
        wrong=[
            (
                "python3",
                "import sys\nd = sys.stdin.read().split()\nn, q = int(d[0]), int(d[1])\nx = list(map(int, d[2:2 + n]))\nk = 2 + n\nfor _ in range(q):\n    a, b = int(d[k]), int(d[k + 1])\n    k += 2\n    print(sum(x[a - 1:b]))\n",
            )
        ],
    ),
    DemoProblem(
        slug="circle-area",
        title="Circle Area",
        difficulty="easy",
        tags=["math", "floating-point"],
        statement=(
            "Print the area of a circle with radius $r$. Answers within $10^{-6}$ (absolute or "
            "relative) are accepted.\n\n## Input\n\nOne real number $r$ ($0 < r \\le 10^4$).\n\n"
            "## Output\n\nThe area $\\pi r^2$."
        ),
        samples=["1\n", "2.5\n"],
        generate=_circle_gen,
        solve=_circle_solve,
        checker={"kind": "float", "float_abs": 1e-6, "float_rel": 1e-6},
        references={
            "python3": "import math\nr = float(input())\nprint(f'{math.pi * r * r:.6f}')\n",
            "java21": 'import java.util.Scanner;\npublic class Main { public static void main(String[] a) { double r = new Scanner(System.in).nextDouble(); System.out.printf("%.9f%n", Math.PI * r * r); } }\n',
        },
        wrong=[("python3", "r = float(input())\nprint(3.14 * r * r)\n")],
    ),
    DemoProblem(
        slug="pair-sum",
        title="Pair With Sum",
        difficulty="medium",
        tags=["hashing", "custom-checker"],
        statement=(
            "Find two different positions $i \\ne j$ with $x_i + x_j = t$ and print them "
            "(1-based, any valid pair is accepted), or $-1$ if there is none.\n\n## Input\n\n$n$ "
            "and $t$, then $n$ integers.\n\n## Output\n\nTwo indices, or $-1$."
        ),
        samples=["4 9\n2 7 11 15\n"],
        generate=_pair_gen,
        solve=_pair_solve,
        checker={
            "kind": "custom",
            "language": "python3",
            "path": "output_validators/pair/validate.py",
            "protocol": "kattis",
        },
        checker_source=PAIR_CHECKER,
        references={
            "python3": "n, t, *xs = map(int, open(0).read().split())\nseen = {}\nfor i, x in enumerate(xs, 1):\n    if t - x in seen:\n        print(seen[t - x], i)\n        break\n    seen.setdefault(x, i)\nelse:\n    print(-1)\n",
            "cpp17": '#include <bits/stdc++.h>\nusing namespace std;\nint main(){int n;long long t;cin>>n>>t;unordered_map<long long,int> s;for(int i=1;i<=n;i++){long long x;cin>>x;auto it=s.find(t-x);if(it!=s.end()){cout<<it->second<<\' \'<<i<<"\\n";return 0;}s.emplace(x,i);}cout<<-1<<"\\n";}\n',
        },
        wrong=[("python3", "n, t, *xs = map(int, open(0).read().split())\nprint(1, 2)\n")],
    ),
    DemoProblem(
        slug="longest-increasing",
        title="Longest Increasing Subsequence",
        difficulty="hard",
        tags=["dp", "binary-search"],
        statement=(
            "Print the length of the longest strictly increasing subsequence.\n\n## Input\n\n$n$ "
            "($1 \\le n \\le 2 \\cdot 10^5$), then $n$ integers.\n\n## Output\n\nThe length. "
            "An $O(n^2)$ solution is too slow for the largest tests."
        ),
        samples=["8\n10 9 2 5 3 7 101 18\n"],
        generate=_lis_gen,
        solve=_lis_solve,
        time_limit_ms=1000,
        references={
            "cpp17": '#include <bits/stdc++.h>\nusing namespace std;\nint main(){int n;cin>>n;vector<long long> t;for(int i=0;i<n;i++){long long x;cin>>x;auto it=lower_bound(t.begin(),t.end(),x);if(it==t.end())t.push_back(x);else *it=x;}cout<<t.size()<<"\\n";}\n',
            "python3": "import sys, bisect\nd = sys.stdin.buffer.read().split()\nt = []\nfor x in map(int, d[1:]):\n    k = bisect.bisect_left(t, x)\n    if k == len(t):\n        t.append(x)\n    else:\n        t[k] = x\nprint(len(t))\n",
        },
        wrong=[
            (
                "cpp17",
                '#include <bits/stdc++.h>\nusing namespace std;\nint main(){int n;cin>>n;vector<long long> a(n);for(auto&x:a)cin>>x;vector<int> d(n,1);int b=1;for(int i=0;i<n;i++)for(int j=0;j<i;j++)if(a[j]<a[i])d[i]=max(d[i],d[j]+1),b=max(b,d[i]);cout<<b<<"\\n";}\n',
            )
        ],
    ),
    DemoProblem(
        slug="count-islands",
        title="Count Islands",
        difficulty="medium",
        tags=["graphs", "dfs"],
        statement=(
            "Count the islands: groups of `1` cells connected up, down, left or right.\n\n"
            "## Input\n\n$n$ and $m$ ($1 \\le n, m \\le 800$), then $n$ rows of `0` and `1`.\n\n"
            "## Output\n\nThe number of islands."
        ),
        samples=["4 5\n11000\n11000\n00100\n00011\n"],
        generate=_islands_gen,
        solve=_islands_solve,
        references={
            "cpp17": "#include <bits/stdc++.h>\nusing namespace std;\nint main(){int n,m;cin>>n>>m;vector<string> g(n);for(auto&r:g)cin>>r;int c=0;vector<pair<int,int>> st;for(int y=0;y<n;y++)for(int x=0;x<m;x++){if(g[y][x]!='1')continue;c++;g[y][x]='0';st.push_back({y,x});\nwhile(!st.empty()){auto [cy,cx]=st.back();st.pop_back();int dy[]={1,-1,0,0},dx[]={0,0,1,-1};for(int k=0;k<4;k++){int ny=cy+dy[k],nx=cx+dx[k];if(ny>=0&&nx>=0&&ny<n&&nx<m&&g[ny][nx]=='1'){g[ny][nx]='0';st.push_back({ny,nx});}}}}cout<<c<<\"\\n\";}\n",
        },
    ),
    DemoProblem(
        slug="word-frequency",
        title="Top Three Words",
        difficulty="easy",
        tags=["hashing", "sorting"],
        statement=(
            "Print the three most frequent words with their counts, most frequent first; ties "
            "in alphabetical order. Print fewer lines if there are fewer distinct words.\n\n"
            "## Input\n\n$n$, then $n$ lowercase words.\n\n## Output\n\nUp to three lines `word count`."
        ),
        samples=["6\ncode test code judge test code\n"],
        generate=_freq_gen,
        solve=_freq_solve,
        references={
            "python3": "from collections import Counter\nw = open(0).read().split()[1:]\nfor word, c in sorted(Counter(w).items(), key=lambda kv: (-kv[1], kv[0]))[:3]:\n    print(word, c)\n",
            "javascript": "const w = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/).slice(1);\nconst c = new Map();\nfor (const x of w) c.set(x, (c.get(x) || 0) + 1);\nconst r = [...c].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, 3);\nconsole.log(r.map(([k, v]) => `${k} ${v}`).join('\\n'));\n",
        },
        wrong=[
            (
                "python3",
                "from collections import Counter\nw = open(0).read().split()[1:]\nfor word, c in Counter(w).most_common(3):\n    print(word, c)\n",
            )
        ],
    ),
    DemoProblem(
        slug="coin-change",
        title="Coin Change",
        difficulty="hard",
        tags=["dp"],
        statement=(
            "With unlimited coins of $k$ values, make exactly $t$ with as few coins as possible; "
            "print the count or $-1$.\n\n## Input\n\n$k$ and $t$ ($t \\le 10^6$), then the $k$ "
            "coin values.\n\n## Output\n\nThe fewest coins, or $-1$."
        ),
        samples=["3 11\n1 2 5\n", "1 7\n2\n"],
        generate=_coins_gen,
        solve=_coins_solve,
        time_limit_ms=3000,
        references={
            "cpp17": '#include <bits/stdc++.h>\nusing namespace std;\nint main(){int k,t;cin>>k>>t;vector<int> c(k);for(auto&x:c)cin>>x;const int INF=1<<30;vector<int> b(t+1,INF);b[0]=0;for(int v=1;v<=t;v++)for(int x:c)if(x<=v&&b[v-x]+1<b[v])b[v]=b[v-x]+1;cout<<(b[t]<INF?b[t]:-1)<<"\\n";}\n',
            "java21": "import java.io.*;\nimport java.util.*;\npublic class Main { public static void main(String[] a) throws IOException { StreamTokenizer s = new StreamTokenizer(new BufferedInputStream(System.in)); s.nextToken(); int k = (int) s.nval; s.nextToken(); int t = (int) s.nval; int[] c = new int[k]; for (int i = 0; i < k; i++) { s.nextToken(); c[i] = (int) s.nval; }\n int INF = 1 << 30; int[] b = new int[t + 1]; Arrays.fill(b, INF); b[0] = 0; for (int v = 1; v <= t; v++) for (int x : c) if (x <= v && b[v - x] + 1 < b[v]) b[v] = b[v - x] + 1; System.out.println(b[t] < INF ? b[t] : -1); } }\n",
        },
        # Greedy is wrong for coin systems like {1, 3, 4} and target 6.
        wrong=[
            (
                "python3",
                "k, t, *c = map(int, open(0).read().split())\nc.sort(reverse=True)\nn = 0\nfor x in c:\n    n += t // x\n    t %= x\nprint(n if t == 0 else -1)\n",
            )
        ],
    ),
    DemoProblem(
        slug="rotate-matrix",
        title="Rotate the Matrix",
        difficulty="easy",
        tags=["arrays", "implementation"],
        statement=(
            "Rotate an $n \\times n$ matrix 90 degrees clockwise.\n\n## Input\n\n$n$ "
            "($1 \\le n \\le 500$), then $n$ rows of $n$ integers.\n\n## Output\n\nThe rotated matrix."
        ),
        samples=["3\n1 2 3\n4 5 6\n7 8 9\n"],
        generate=_rotate_gen,
        solve=_rotate_solve,
        references={
            "python3": "import sys\nd = sys.stdin.read().split()\nn = int(d[0])\nm = [d[1 + i * n:1 + (i + 1) * n] for i in range(n)]\nprint('\\n'.join(' '.join(m[n - 1 - c][r] for c in range(n)) for r in range(n)))\n",
            "javascript": "const d = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/);\nconst n = +d[0];\nconst out = [];\nfor (let r = 0; r < n; r++) { const row = []; for (let c = 0; c < n; c++) row.push(d[1 + (n - 1 - c) * n + r]); out.push(row.join(' ')); }\nconsole.log(out.join('\\n'));\n",
        },
        wrong=[
            (
                "python3",
                "import sys\nd = sys.stdin.read().split()\nn = int(d[0])\nm = [d[1 + i * n:1 + (i + 1) * n] for i in range(n)]\nprint('\\n'.join(' '.join(m[c][r] for c in range(n)) for r in range(n)))\n",
            )
        ],
    ),
]


def tests_for(p: DemoProblem) -> list[dict[str, str]]:
    """The problem's tests as the versions endpoint takes them: samples then hidden groups."""
    r = random.Random(f"codejudge-demo-{p.slug}")
    tests = [
        {"name": f"sample/{k}", "input": s, "answer": p.solve(s)}
        for k, s in enumerate(p.samples, start=1)
    ]
    if p.groups:
        for group, (_points, gen) in p.groups.items():
            for k, inp in enumerate(gen(r), start=1):
                tests.append(
                    {"name": f"secret/{group}/{k:02d}", "input": inp, "answer": p.solve(inp)}
                )
    else:
        for k, inp in enumerate(p.generate(r), start=1):
            tests.append({"name": f"secret/{k:02d}", "input": inp, "answer": p.solve(inp)})
    return tests


def groups_for(p: DemoProblem) -> list[dict[str, Any]]:
    return [{"name": g, "points": pts} for g, (pts, _gen) in p.groups.items()]
