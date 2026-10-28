# Contests

Timed contests with ICPC or IOI scoring, a scoreboard with a freeze, and clarifications.
Code: `contests/` (`scoring.py` holds the rules as pure functions, `service.py` the policy,
the board and the lifecycle).

## A contest

| Field | Meaning |
| --- | --- |
| `format` | `icpc` (solved count, then penalty minutes) or `ioi` (sum of best scores per problem) |
| `starts_at`, `ends_at` | The window; submissions outside it are refused |
| `freeze_at` | Optional. From this moment contestants see later attempts as pending until staff unfreeze |
| `visibility` | `public` (listed for everyone) or `private` |
| `registration` | `open` (anyone registers) or `invite` (with the contest's join code) |
| `penalty_minutes` | ICPC: added per rejected attempt before the first acceptance (20 by default) |
| Problems | Labelled A, B, C in order; IOI gives each problem its contest points. Reordering relabels them |

A contest can use published problems and **private** ones, which are not in the practice
list: the contest problem endpoint shows a private problem's statement to registered
participants once the contest has started, through the same view as practice (samples
only, never hidden tests). The problem set and the board stay hidden from non-staff until
the start.

## Who may submit

The `contest` submission policy admits a submission when the person is a registered
participant, the contest is running, and the problem belongs to the contest. Staff may
always submit (to test the set). Interview candidates never can. A contestant's code is
readable by its author and staff only, during and after the contest.

In ICPC contests a contestant's own submissions show the overall verdict and the sample
results, not how many hidden tests passed: per-test results would turn the judge into an
oracle for the hidden data. IOI contests show the per-group results, since partial scores
are the point.

## Scoring

**ICPC.** Rank by problems solved, then penalty, then the time of the last accepted
attempt. The penalty is, for every solved problem, the minutes from the start to its first
accepted attempt plus `penalty_minutes` for every rejected attempt before it. A compilation
error is not an attempt (it costs nothing), attempts after the first acceptance are
ignored, and an internal error is the judge's fault, so it is ignored too. The first solver
of each problem is marked.

**IOI.** For each problem the best score of any attempt, scaled to the problem's contest
points; the total is the sum; ties go to whoever reached their total first.

Tied rows share a rank. Unjudged attempts show as pending in every view.

## The freeze

In the frozen view every attempt made at or after `freeze_at` is shown as pending: it is
counted (a team sees that a rival tried), but its verdict and score are hidden. Contestants
get the frozen view from the freeze until staff press **Unfreeze**; staff always see the
live board. A contestant always sees their own verdicts on their own submissions.

## The scoreboard

Computed from the contest's submissions with a fixed number of queries (problems,
participants with their names, and one query over the submissions), however many people
take part, then cached per contest and view. Every change that can move the board (a
verdict, a rejudge, an edited window or freeze, a problem added or removed) bumps the
contest's version number, which is part of the cache key, so a stale board is never
served; the short TTL only bounds memory.

## Clarifications

Participants ask questions, optionally about one problem. Staff answer them privately or
publicly, and post announcements (public answers without a question). Contestants see their
own questions and every public answer.
