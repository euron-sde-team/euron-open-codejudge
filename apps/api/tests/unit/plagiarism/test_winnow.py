"""AC10: a disguised copy is flagged; an independent solution to the same problem is not."""

from __future__ import annotations

import pytest

from codejudge.plagiarism.tokens import tokenize
from codejudge.plagiarism.winnow import common, compare, fingerprint, merge

THRESHOLD = 0.5

ORIGINAL_PY = """
import sys

def read_graph():
    n, m = map(int, sys.stdin.readline().split())
    adjacency = [[] for _ in range(n + 1)]
    for _ in range(m):
        a, b = map(int, sys.stdin.readline().split())
        adjacency[a].append(b)
        adjacency[b].append(a)
    return n, adjacency

def count_components(n, adjacency):
    seen = [False] * (n + 1)
    components = 0
    for start in range(1, n + 1):
        if seen[start]:
            continue
        components += 1
        stack = [start]
        seen[start] = True
        while stack:
            node = stack.pop()
            for nxt in adjacency[node]:
                if not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
    return components

n, adjacency = read_graph()
print(count_components(n, adjacency))
"""

# Renamed every identifier, swapped the two functions, rewrote the comments and spacing.
DISGUISED_PY = """
import sys
# count how many islands there are


def islands(total, g):
    # visited flags
    vis = [False] * (total + 1)
    answer = 0
    for s in range(1, total + 1):
        if vis[s]:
            continue
        answer += 1
        todo = [s]
        vis[s] = True
        while todo:
            cur = todo.pop()
            for nb in g[cur]:
                if not vis[nb]:
                    vis[nb] = True
                    todo.append(nb)
    return answer


def load():
    total, edges = map(int, sys.stdin.readline().split())
    g = [[] for _ in range(total + 1)]
    for _ in range(edges):
        x, y = map(int, sys.stdin.readline().split())
        g[x].append(y)
        g[y].append(x)
    return total, g

total, g = load()
print(islands(total, g))
"""

# The same problem solved independently, with union-find instead of a search.
INDEPENDENT_PY = """
def find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def main():
    data = open(0).read().split()
    n, m = int(data[0]), int(data[1])
    parent = list(range(n + 1))
    groups = n
    idx = 2
    for _ in range(m):
        u, v = int(data[idx]), int(data[idx + 1])
        idx += 2
        ru, rv = find(parent, u), find(parent, v)
        if ru != rv:
            parent[ru] = rv
            groups -= 1
    print(groups)

main()
"""

ORIGINAL_CPP = """
#include <bits/stdc++.h>
using namespace std;
// longest increasing subsequence in n log n
int lis(const vector<int>& values) {
    vector<int> tails;
    for (int v : values) {
        auto it = lower_bound(tails.begin(), tails.end(), v);
        if (it == tails.end()) tails.push_back(v);
        else *it = v;
    }
    return (int)tails.size();
}
int main() {
    int n; cin >> n;
    vector<int> values(n);
    for (int i = 0; i < n; i++) cin >> values[i];
    cout << lis(values) << endl;
    return 0;
}
"""

DISGUISED_CPP = """
#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;

int solve(const vector<int>& arr)
{
    vector<int> best;   /* smallest tail of each length */
    for (int x : arr)
    {
        auto pos = lower_bound(best.begin(), best.end(), x);
        if (pos == best.end()) best.push_back(x);
        else *pos = x;
    }
    return (int)best.size();
}

int main()
{
    int count;
    cin >> count;
    vector<int> arr(count);
    for (int k = 0; k < count; k++) cin >> arr[k];
    cout << solve(arr) << endl;
    return 0;
}
"""

INDEPENDENT_CPP = """
#include <bits/stdc++.h>
using namespace std;
int main() {
    int n; scanf("%d", &n);
    vector<long long> a(n), dp(n, 1);
    for (auto& x : a) scanf("%lld", &x);
    int answer = 0;
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < i; ++j)
            if (a[j] < a[i] && dp[j] + 1 > dp[i]) dp[i] = dp[j] + 1;
        answer = max(answer, (int)dp[i]);
    }
    printf("%d\\n", answer);
}
"""


@pytest.mark.parametrize(
    ("language", "original", "disguised", "independent"),
    [
        ("python3", ORIGINAL_PY, DISGUISED_PY, INDEPENDENT_PY),
        ("cpp17", ORIGINAL_CPP, DISGUISED_CPP, INDEPENDENT_CPP),
    ],
)
def test_disguised_copy_is_flagged_and_independent_work_is_not(
    language: str, original: str, disguised: str, independent: str
) -> None:
    a = fingerprint("a", original, language)
    copy = compare(a, fingerprint("b", disguised, language))
    other = compare(a, fingerprint("c", independent, language))
    assert copy is not None and other is not None
    assert copy.similarity >= THRESHOLD, copy
    assert other.similarity < THRESHOLD, other
    assert copy.similarity > other.similarity + 0.3
    assert copy.ranges_a and copy.ranges_b


def test_identifiers_literals_and_comments_are_normalised() -> None:
    a = [t.text for t in tokenize("total = count + 42  # sum\n", "python3")]
    b = [t.text for t in tokenize("x = y + 7\n", "python3")]
    assert a == b == ["ID", "=", "ID", "+", "NUM"]
    c = [t.text for t in tokenize('int s = a /* x */ + "hi"; // done', "cpp17")]
    assert c == ["int", "ID", "=", "ID", "+", "STR", ";"]


def test_preprocessor_lines_and_broken_python_still_tokenize() -> None:
    assert [t.text for t in tokenize("#include <bits/stdc++.h>\nint x;", "cpp17")] == [
        "int",
        "ID",
        ";",
    ]
    assert tokenize("def broken(:\n  pass\n", "python3")


def test_tiny_programs_are_not_compared() -> None:
    a, b = fingerprint("a", "print(1)", "python3"), fingerprint("b", "print(2)", "python3")
    assert compare(a, b) is None


def test_merge_joins_overlapping_and_adjacent_ranges() -> None:
    assert merge([(5, 7), (1, 2), (3, 4), (10, 12), (11, 15)]) == [(1, 7), (10, 15)]


def test_common_fingerprints_need_enough_documents() -> None:
    docs = [fingerprint(str(i), ORIGINAL_PY, "python3") for i in range(3)]
    assert common(docs) == set()
    many = [fingerprint(str(i), ORIGINAL_PY, "python3") for i in range(6)]
    assert common(many) == many[0].hashes
