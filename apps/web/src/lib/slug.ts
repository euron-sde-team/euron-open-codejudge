/** A problem slug from its title: lower case letters, digits and single hyphens, 3 to 64 long. */
export function slugify(title: string): string {
  return title
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64)
    .replace(/-+$/g, "");
}

/** The API's rule: starts and ends with a letter or digit, 3 to 64 characters. */
export const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/;

export function isSlug(value: string): boolean {
  return SLUG_PATTERN.test(value);
}
