import {
  ActivityIcon,
  BarChart3Icon,
  BriefcaseIcon,
  CopyCheckIcon,
  FileCode2Icon,
  GraduationCapIcon,
  ListChecksIcon,
  PencilRulerIcon,
  ScrollTextIcon,
  SettingsIcon,
  TrendingUpIcon,
  TrophyIcon,
  UsersIcon,
  type LucideIcon,
} from "lucide-react";

export type Audience = "everyone" | "signedIn" | "student" | "staff" | "admin";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  audience: Audience;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: "Practice",
    items: [
      { href: "/problems", label: "Problems", icon: FileCode2Icon, audience: "everyone" },
      { href: "/contests", label: "Contests", icon: TrophyIcon, audience: "everyone" },
      { href: "/classes", label: "Classes", icon: GraduationCapIcon, audience: "signedIn" },
      { href: "/submissions", label: "Submissions", icon: ListChecksIcon, audience: "signedIn" },
      { href: "/progress", label: "My progress", icon: TrendingUpIcon, audience: "student" },
    ],
  },
  {
    label: "Staff",
    items: [
      { href: "/manage/problems", label: "Problem editor", icon: PencilRulerIcon, audience: "staff" },
      { href: "/assessments", label: "Assessments", icon: BriefcaseIcon, audience: "staff" },
      { href: "/plagiarism", label: "Plagiarism", icon: CopyCheckIcon, audience: "staff" },
      { href: "/analytics", label: "Analytics", icon: BarChart3Icon, audience: "staff" },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/admin/users", label: "Users", icon: UsersIcon, audience: "admin" },
      { href: "/admin/system", label: "System", icon: ActivityIcon, audience: "admin" },
      { href: "/admin/audit", label: "Audit log", icon: ScrollTextIcon, audience: "admin" },
      { href: "/admin/settings", label: "Settings", icon: SettingsIcon, audience: "admin" },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

/** Whether someone with this role (null: signed out) sees an item. */
export function visibleTo(item: NavItem, role: string | null | undefined): boolean {
  switch (item.audience) {
    case "everyone":
      return true;
    case "signedIn":
      return !!role;
    case "student":
      return role === "student";
    case "staff":
      return role === "staff" || role === "admin";
    case "admin":
      return role === "admin";
  }
}

/** The nav item a path belongs to: the longest matching prefix. */
export function activeNavItem(pathname: string): NavItem | undefined {
  const path = pathname.replace(/\/+$/, "") || "/";
  return NAV_ITEMS.filter((i) => path === i.href || path.startsWith(`${i.href}/`)).sort(
    (a, b) => b.href.length - a.href.length,
  )[0];
}

export function isActive(item: NavItem, pathname: string): boolean {
  return activeNavItem(pathname)?.href === item.href;
}
