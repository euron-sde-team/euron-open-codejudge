# Plagiarism checks

Token-based similarity between submissions, the MOSS approach. Code: `plagiarism/`
(`tokens.py` normalises source, `winnow.py` fingerprints and compares, `service.py` runs
checks in the background).

## What is compared

A run has a scope: one problem, one contest or one assignment. It takes one program per
author and problem in the scope (their latest accepted submission, or else their best
scoring one), groups them by problem and language, and compares every pair in a group.

## How

1. **Normalise.** Identifiers become `ID`, numbers `NUM`, string and character literals
   `STR`; keywords and operators stay; comments, whitespace and preprocessor lines (the
   `#include` boilerplate every C++ program shares) are dropped. Python uses the standard
   `tokenize` module; C++, Java and JavaScript share one small lexer with a keyword set per
   language. Code that does not tokenize falls back to the generic lexer instead of being
   skipped. Renaming variables or reformatting therefore changes nothing.
2. **Fingerprint (winnowing).** Every run of 5 consecutive tokens is hashed; in each window
   of 4 consecutive hashes the smallest is kept. Any match of at least 8 tokens is then
   guaranteed to share a fingerprint, while noise shorter than 5 tokens never does.
   Fingerprints form a set, so moving whole functions around does not lower the score.
3. **Ignore the obvious.** Fingerprints shared by more than 60% of a group (given template
   code, the canonical idiom for the problem) are ignored once a group has at least six
   programs, so two students who both wrote the textbook loop are not flagged for it.
4. **Score.** Similarity is the Jaccard index of the two fingerprint sets. Coverage per side
   is the share of that side's fingerprints found in the other, so a short program copied
   into a long one shows high coverage on the short side.
5. **Report.** Pairs at or above the threshold (0.5 by default, settable per run) are
   stored, most similar first, with the matched line ranges for the side-by-side view.

In the unit tests a copy with renamed identifiers, reordered functions and changed comments
scores far above the threshold, and an independent solution to the same problem with a
different algorithm scores far below it.

## Running

Starting a run queues it. The background worker claims queued runs with
`FOR UPDATE SKIP LOCKED` (several workers never take the same run), reclaims a run left
`running` for 30 minutes (its worker died), and does the comparing in a thread so the event
loop stays free. Groups are capped at 1,500 programs (newest first) and a run stores at
most 500 pairs, so one huge problem cannot stall the worker.

## A signal, not a verdict

A similarity score says two programs share structure. Short problems have few ways to be
solved; a class may have been shown the same example. The pair view puts both programs side
by side so a person decides. Plagiarism checks are staff only.
