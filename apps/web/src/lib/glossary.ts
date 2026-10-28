/** Plain-words explanations for judging vocabulary, shown as inline hints. */
export const GLOSSARY = {
  timeLimit:
    "CPU time your program may use per test. Time spent waiting (sleeping, reading slowly) is not counted, but a program that never finishes is stopped.",
  memoryLimit: "The most memory your program may use per test, counted at its peak.",
  hiddenTests:
    "Tests you cannot see. Samples are shown in the statement; the hidden tests decide the verdict, so handle every case the statement allows.",
  groups:
    "Tests are grouped into subtasks. A group's points are earned when every test in it passes.",
  checker:
    "How your output is compared: by default whitespace does not matter, only the tokens; some problems accept numbers within a tolerance or use a custom checker.",
  reference:
    "A setter's own solution and the verdict it must get. A problem can be published only when every reference solution gets its expected verdict on the current tests.",
  version:
    "Each change to the tests creates a new version. Submissions remember the version they were judged on, so a rejudge can use the original tests or the latest ones.",
  acceptance: "Accepted submissions out of all judged submissions for this problem.",
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
