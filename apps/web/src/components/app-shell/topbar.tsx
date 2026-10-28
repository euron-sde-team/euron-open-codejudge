"use client";

import { LogInIcon, MenuIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { BrandLogo } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants, Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { usePermissions } from "@/features/auth/api";
import { useQueueStatus } from "@/features/admin/api";
import { loginUrl } from "@/lib/auth-redirect";
import { cn } from "@/lib/cn";

import { SidebarNav } from "./sidebar";
import { UserMenu } from "./user-menu";

/** Staff see whether the judges are keeping up: workers online and jobs waiting. */
function JudgeStatus() {
  const { data, isError } = useQueueStatus();
  const healthy = !isError && !!data && data.workers > 0;
  const label = !data && !isError
    ? "Checking judges"
    : !data
      ? "Judge status unknown"
      : data.workers === 0
        ? "No judge online"
        : `${data.workers} judge${data.workers === 1 ? "" : "s"} online`;
  return (
    <Link
      href="/admin/system"
      className="hidden items-center gap-2 rounded-full bg-muted px-3 py-1 text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring md:inline-flex"
    >
      <span className="relative flex size-2">
        {healthy && <span className="absolute inline-flex size-full animate-ping rounded-full bg-savings opacity-40" />}
        <span className={cn("relative inline-flex size-2 rounded-full", healthy ? "bg-savings" : data || isError ? "bg-warning" : "bg-faint")} />
      </span>
      {label}
      {data && data.waiting > 0 && <span className="text-faint">{data.waiting} waiting</span>}
    </Link>
  );
}

export function Topbar() {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const { signedIn, staff } = usePermissions();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
      <div className="flex h-14 items-center gap-2 px-4 sm:px-6 lg:px-8">
        <Button variant="subtle" size="icon" className="-ml-2 lg:hidden" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>
          <MenuIcon />
        </Button>
        <Link href="/problems" className="rounded-lg lg:hidden" aria-label="CodeJudge home">
          <BrandLogo />
        </Link>
        {staff && <JudgeStatus />}
        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          {signedIn ? (
            <UserMenu />
          ) : (
            <Link href={loginUrl(pathname)} className={buttonVariants({ size: "sm", className: "ml-1" })}>
              <LogInIcon />
              Sign in
            </Link>
          )}
        </div>
      </div>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="bg-sidebar">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex h-14 items-center px-4">
            <BrandLogo />
          </div>
          <div className="overflow-y-auto px-3 pb-6">
            <SidebarNav onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </header>
  );
}
