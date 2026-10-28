import type { Role } from "./api/types";

export const ROLES: readonly Role[] = ["admin", "staff", "student"] as const;

const ROLE_LABEL: Record<Role, string> = { admin: "Admin", staff: "Staff", student: "Student" };

const ROLE_DESCRIPTION: Record<Role, string> = {
  admin: "Everything staff can do, plus users, roles and the audit log.",
  staff: "Writes and publishes problems, sees every submission and rejudges.",
  student: "Solves problems and sees their own submissions.",
};

export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

export function roleLabel(role: string | null | undefined): string {
  return isRole(role) ? ROLE_LABEL[role] : "Unknown";
}

export function roleDescription(role: string | null | undefined): string {
  return isRole(role) ? ROLE_DESCRIPTION[role] : "";
}

/** Staff and admins write problems, see every submission and rejudge. */
export function isStaff(role: string | null | undefined): boolean {
  return role === "staff" || role === "admin";
}

/** Only admins manage users, roles and the audit log. */
export function isAdmin(role: string | null | undefined): boolean {
  return role === "admin";
}
