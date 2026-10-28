/**
 * Candidates typed or pasted one per line: "email", "Name, email" or "Name <email>".
 * Duplicates are dropped; lines that are not an email are reported back, not guessed.
 */
export interface Candidate {
  email: string;
  name: string;
}

const EMAIL = /^[^@\s,<>]+@[^@\s,<>]+\.[^@\s,<>]+$/;

export function parseCandidates(text: string): { candidates: Candidate[]; invalid: string[] } {
  const candidates: Candidate[] = [];
  const invalid: string[] = [];
  const seen = new Set<string>();
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    let name = "";
    let email = "";
    const angle = /^(.*)<([^>]+)>\s*$/.exec(line);
    if (angle) {
      name = (angle[1] ?? "").trim().replace(/,$/, "").trim();
      email = (angle[2] ?? "").trim();
    } else if (line.includes(",")) {
      const parts = line.split(",").map((p) => p.trim());
      const at = parts.findIndex((p) => p.includes("@"));
      email = at >= 0 ? (parts[at] ?? "") : "";
      name = parts.filter((_, i) => i !== at).join(" ").trim();
    } else {
      email = line;
    }
    email = email.toLowerCase();
    if (!EMAIL.test(email)) {
      invalid.push(line);
      continue;
    }
    if (seen.has(email)) continue;
    seen.add(email);
    candidates.push({ email, name: name.slice(0, 200) });
  }
  return { candidates, invalid };
}
