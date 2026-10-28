# Writing problems

A problem is a statement, limits, tests and at least one reference solution. CodeJudge
publishes it only when the reference solutions get the verdicts they should, which catches
the mistakes that make judges unfair.

## 1. Create it

**Manage problems**, **New problem**: a slug (`two-sum`, used in URLs), a title, the
difficulty, tags, and limits:

| Limit | Default | Advice |
| --- | --- | --- |
| Time | 2000 ms | CPU time, not wall clock. Set it at 2 to 3 times your reference solution's slowest test in the slowest language you want to pass |
| Memory | 256 MB | Java and Node get their heap set to this; leave headroom for the runtime |
| Output | 64 MB | Rarely needs changing |

**Visibility**: `public` problems appear in the practice list once published; `private` ones
only through a contest, an assignment or an assessment.

## 2. Write the statement

Markdown with `$inline$` and `$$display$$` math (KaTeX). Use `## Input`, `## Output` and,
for partial scoring, `## Subtasks`. The samples are shown from the tests: do not paste them
into the statement.

## 3. Add tests

In the **Tests** tab, add tests by name:

- `sample/1`, `sample/2`: shown in the statement, judged first, worth no points.
- `secret/01` ...: hidden, one group worth 100 points.
- `secret/small/01`, `secret/large/01` ...: hidden groups (subtasks). Give each group its
  points; a group scores when every test in it passes.

Large tests come as a package: build a zip in the Kattis layout
([problem-format.md](../architecture/problem-format.md)) and upload it in the same tab, or
import a whole problem from **Import**. Generate big inputs with a script and compute the
answers with a trusted solution.

Good tests include the smallest input, the largest input (to catch slow solutions), every
edge the statement allows (zero, negative numbers, equal values, one element) and inputs
that break the obvious wrong idea (a greedy that fails, an overflow).

## 4. Choose a checker

| Checker | When |
| --- | --- |
| Tokens (default) | One right answer; spacing and line breaks do not matter |
| Float | Real numbers: set absolute and relative tolerances |
| Exact | Formatting matters (rare) |
| Custom | Several right answers ("print any valid pair"). Write a program in any judge language; use the Kattis convention (exit 42 accepts, 43 rejects; write a message to `<feedback dir>/judgemessage.txt`) or testlib's (exit 0 accepts) |

## 5. Add reference solutions

Add your correct solution (expected `AC`), ideally in two languages. Add a deliberately slow
one with expected `TLE` to prove the limit separates them, and a wrong one with `WA` if you
want to prove a test catches a common mistake. Press **Judge references**; the problem lists
what still blocks publishing until every reference gets its expected verdict on the current
tests.

## 6. Publish

**Publish** is enabled when nothing blocks it. Unpublishing hides it from the practice list
but keeps its submissions.

## Fixing a test later

Change the tests (a new version is created), judge the references again, then **Rejudge
all** on the problem: every submission is judged on the current tests, and scoreboards,
gradebooks and analytics follow. Submissions always record the version they were judged
against.
