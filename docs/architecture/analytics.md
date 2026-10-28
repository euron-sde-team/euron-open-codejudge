# Analytics

Charts for staff and a progress page for students, read from a rollup that stays exact.
Code: `analytics/`.

## The rollup

`stats_daily` holds, per day, problem and language: submissions, accepted, and counts per
failure verdict (wrong answer, time limit, memory limit, runtime error, compilation error,
output limit, internal error), and distinct users.

When a submission is judged (or rejudged) a listener recomputes the bucket it belongs to
from the submissions themselves with one indexed query, under a Postgres advisory lock per
bucket. Recomputing instead of incrementing makes it idempotent: judging the same
submission twice changes nothing, and a rejudge that changes a verdict moves the counts
correctly. Only counted contexts are included (practice, contest, assignment, assessment;
never runs or reference solutions).

## The pages

| Endpoint | Who | Reads |
| --- | --- | --- |
| `GET /api/v1/analytics/overview` | staff | The rollup only: submissions and acceptance per day for 30 days, verdict mix, top problems, acceptance by difficulty, languages |
| `GET /api/v1/analytics/problems/{ref}` | staff | One problem's submissions, on its index: acceptance, verdict mix, median time, attempts to the first acceptance |
| `GET /api/v1/analytics/me` | anyone signed in | Their own progress: solved count, attempts, by difficulty, recent activity |
| `GET /api/v1/analytics/users/{id}` | staff, or the user themselves | The same for one user (a student asking for someone else gets 404) |

The overview never scans the raw submissions table, so it costs the same with a hundred
submissions or ten million.
