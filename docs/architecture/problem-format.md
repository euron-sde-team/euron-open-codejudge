# Problem format

CodeJudge stores, imports and exports problems in the
[Kattis problem package format](https://www.kattis.com/problem-package-format/), the format
DOMjudge and Kattis use ([ADR-0004](adr/0004-kattis-problem-package-format.md)). The zip a
problem is judged with is the zip it exports, so moving a problem between installs, or
from another judge into CodeJudge, is an upload. Code: `problems/packages.py`.

## Layout

```text
problem.yaml                          name, limits, validation, license, source
problem_statement/problem.md          the statement, Markdown with $math$
data/sample/1.in   data/sample/1.ans  public samples (shown in the statement)
data/secret/1.in   data/secret/1.ans  hidden tests in one group named "secret"
data/secret/<group>/07.in, 07.ans     or hidden tests in named groups (subtasks)
data/secret/<group>/test_group.yaml   score: 40   (the group's points)
output_validators/<name>/<file>       a custom checker's source
submissions/accepted/<file>           reference solutions (imported as expected AC)
```

Accepted on import, as other tools write them:

- one top-level folder around everything (`myproblem/problem.yaml` and so on);
- `problem_statement/problem.en.md`, `statement/problem.md` or `statement/problem.en.md`
  for the statement;
- `testdata.yaml` (the older name) as well as `test_group.yaml` for group scores;
- `name` as a string or as a map of languages (`en` is used).

## problem.yaml

| Key | Read as |
| --- | --- |
| `name` | The title |
| `source`, `license` | Shown on the problem page |
| `limits.time_limit` | Seconds; lowered to the server's maximum (`MAX_TIME_LIMIT_MS`) with a warning |
| `limits.memory` | MB |
| `type: scoring` | Groups get the points their `test_group.yaml` gives; groups without one score 0 |
| `validation: custom` | Use the first source in `output_validators/` in a supported language as a Kattis checker |
| `validator_flags` | `case_insensitive`; `float_tolerance`, `float_absolute_tolerance`, `float_relative_tolerance` with a value (switches to the float checker) |

Without `type: scoring`, the points are split evenly between the hidden groups (100 in
total), and samples score 0.

## Tests and groups

- A test is a pair `<name>.in` and `<name>.ans` under `data/sample/` or `data/secret/`;
  its name is its path below `data/` without the extension (`sample/1`, `secret/large/03`).
- Tests are judged samples first, then hidden tests in natural order (`2` before `10`).
- Hidden tests directly under `data/secret/` form the group `secret`; tests in
  `data/secret/<group>/` form `<group>`. Group names may use letters, digits, `_` and `-`.
- A group's points are earned when every test in it is accepted. Hidden groups stop at
  the first failure (the rest are `SKIPPED`); samples always all run.
- A problem must have at least one hidden test to be published: samples alone cannot judge.

## Checkers

Built-in checkers need no code: `tokens` (the default), `float` with tolerances, `exact`.
A custom checker is a program in one of the four judge languages, run in its own sandbox:

| Convention | Called as | Accepts | Rejects | Anything else |
| --- | --- | --- | --- | --- |
| `kattis` (imports) | `checker input answer feedback_dir/ < output` | exit 42 | exit 43 | internal error |
| `testlib` | `checker input output answer` | exit 0 | exit 1 or 2 | internal error |

A Kattis checker may write a message to `feedback_dir/judgemessage.txt`; it is shown for
sample tests. A checker that crashes or exits with another code is an internal error, so a
broken checker never turns into wrong answers for students.

## Export

`GET /api/v1/problems/{id}/export` (staff) returns the current version's tests and checker
with today's statement, limits, title and the reference solutions expected to be accepted,
as a zip in the layout above. Builds are deterministic (sorted entries, fixed timestamps),
so the same tests always give the same SHA-256 and re-uploading identical data does not
create a new version. Reference solutions are kept in their own table and go into the
package only on export; the package the judge runs holds tests and the checker only.

## Safety on import

An upload is refused when it is not a zip, has more than 20,000 entries, contains an
absolute path or `..`, or has no tests. On the judge, a package is unpacked only after its
SHA-256 matches the job, symlinks and devices are refused, and the unpacked size is capped.
