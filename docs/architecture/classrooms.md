# Classes and assignments

Classes with rosters, assignments with deadlines and a late policy, and a gradebook.
Code: `classrooms/`.

## Classes and roles

Staff create classes and become their first teacher. Students join with the class's join
code (eight characters without look-alikes such as `0`/`O` and `1`/`I`), which a teacher can
rotate. Teachers of a class (and admins) manage its roster and assignments; the last
teacher cannot be removed. Someone outside a class gets 404, not 403, so a class's
existence does not leak.

## Assignments

| Field | Meaning |
| --- | --- |
| Problems and points | Each problem's best mark is scaled to its points in this assignment |
| `opens_at` | Submissions before it are refused |
| `due_at` | Per student, unless an extension moves it |
| `late_policy` | `accept` (late work counts in full), `penalty` (late work loses `penalty_percent` of its mark) or `refuse` (no submissions after the due time) |

The `assignment` submission policy admits members of the class from the opening time; after
the due time it refuses (`assignment_closed`) or marks the submission late, per the policy.
Late submissions are kept and shown either way. Assignment problems can be private (not in
the practice list); members see them through the assignment.

A student's view lists their assignments with a status: `upcoming`, `open`, `late` (past
due, still accepted) or `closed`.

## The gradebook

For each student and problem, the best mark: the submission's score scaled to the
problem's points, with the late penalty applied to late submissions. Totals per student.
Computed with one query over the submissions, whatever the class size, so it always
reflects the current verdicts (a rejudge changes the gradebook at once).

`GET /api/v1/assignments/{id}/gradebook.csv` exports it. Cells that start with `=`, `+`,
`-` or `@` are neutralised so the file cannot run formulas when a spreadsheet opens it.
