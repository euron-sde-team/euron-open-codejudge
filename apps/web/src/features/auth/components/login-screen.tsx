"use client";

import { ArrowRightIcon, EyeIcon, EyeOffIcon, FileArchiveIcon, LockKeyholeIcon, ServerIcon, TrophyIcon } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { BrandLogo, BrandMark } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FieldError, Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/errors";
import { safeNext } from "@/lib/auth-redirect";

import { useLogin, usePublicSettings, useSignup } from "../api";

const PITCH = [
  {
    icon: LockKeyholeIcon,
    title: "A sandbox with no privileges",
    body: "Every submission runs in its own namespaces with no network, as nobody, in a worker that holds no database access.",
  },
  {
    icon: ServerIcon,
    title: "Yours to run",
    body: "One command starts it on your machine. No per-submission fee, and code never leaves your servers.",
  },
  {
    icon: FileArchiveIcon,
    title: "Portable problems",
    body: "Import and export in the open Kattis package format, the one DOMjudge and Kattis use.",
  },
  {
    icon: TrophyIcon,
    title: "Trustworthy verdicts",
    body: "CPU time, not wall time; hidden tests stay hidden; a problem cannot go live until its own solution passes.",
  },
];

const DEMO_TESTS = [
  { name: "Sample 1", verdict: "AC", time: "12 ms" },
  { name: "Hidden 1", verdict: "AC", time: "31 ms" },
  { name: "Hidden 2", verdict: "AC", time: "28 ms" },
  { name: "Hidden 3", verdict: "TLE", time: "2.00 s" },
];

type Mode = "login" | "signup";

export function LoginScreen({ mode = "login" }: { mode?: Mode }) {
  const router = useRouter();
  const params = useSearchParams();
  const login = useLogin();
  const signup = useSignup();
  const settings = usePublicSettings();
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [show, setShow] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const expired = params.get("reason") === "expired";
  const signupOpen = settings.data?.allow_signup === true;
  const pending = login.isPending || signup.isPending;
  const next = params.get("next");
  const otherHref = (target: Mode) => `/${target}${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password || (mode === "signup" && !name.trim())) {
      setError(mode === "signup" ? "Enter your name, email and a password." : "Enter your email and password.");
      return;
    }
    if (mode === "signup" && password.length < 10) {
      setError("Use at least 10 characters, with upper and lower case letters and a digit.");
      return;
    }
    setError(null);
    const done = {
      onSuccess: (session: { user: { name: string } }) => {
        toast.success(mode === "signup" ? `Welcome, ${session.user.name.split(" ")[0]}.` : `Welcome back, ${session.user.name.split(" ")[0]}.`);
        router.replace(safeNext(next));
      },
      onError: (err: unknown) => setError(errorMessage(err)),
    };
    if (mode === "signup") signup.mutate({ name: name.trim(), email: email.trim(), password }, done);
    else login.mutate({ email: email.trim(), password }, done);
  }

  return (
    <div className="grid min-h-dvh bg-background lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <div className="relative flex flex-col px-6 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Link href="/problems" className="rounded-lg focus-visible:outline-2 focus-visible:outline-ring" aria-label="CodeJudge problems">
            <BrandLogo />
          </Link>
          <ThemeToggle />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[360px]">
            <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.025em]">
              {mode === "signup" ? "Create your account" : "Sign in to CodeJudge"}
            </h1>
            <p className="mt-1.5 text-[13.5px] text-muted-foreground">
              {mode === "signup"
                ? "Solve problems, keep your submissions, and join classes and contests."
                : "Pick up your problems, submissions and contests where you left them."}
            </p>
            {expired && mode === "login" && (
              <div role="status" className="mt-5 rounded-lg bg-warning-soft px-3.5 py-2.5 text-[13px] text-warning">
                Your session expired. Sign in again to pick up where you left off.
              </div>
            )}
            {mode === "signup" && settings.isSuccess && !signupOpen && (
              <div role="status" className="mt-5 rounded-lg bg-warning-soft px-3.5 py-2.5 text-[13px] text-warning">
                Sign-up is closed on this server. Ask an admin to create your account.
              </div>
            )}
            <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
              {mode === "signup" && (
                <div className="space-y-1.5">
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" autoComplete="name" autoFocus className="h-10" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  autoFocus={mode === "login"}
                  placeholder="you@school.edu"
                  className="h-10"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  aria-invalid={!!error || undefined}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={show ? "text" : "password"}
                    autoComplete={mode === "signup" ? "new-password" : "current-password"}
                    className="h-10 pr-10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    aria-invalid={!!error || undefined}
                  />
                  <button
                    type="button"
                    onClick={() => setShow((s) => !s)}
                    aria-label={show ? "Hide password" : "Show password"}
                    className="absolute top-1/2 right-2 flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-subtle hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    {show ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                  </button>
                </div>
              </div>
              {error && <FieldError>{error}</FieldError>}
              <Button type="submit" size="lg" className="w-full" disabled={pending || (mode === "signup" && !signupOpen)}>
                {pending ? (mode === "signup" ? "Creating your account..." : "Signing in...") : mode === "signup" ? "Create account" : "Sign in"}
                {!pending && <ArrowRightIcon />}
              </Button>
            </form>
            <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
              {mode === "signup" ? (
                <>
                  Already have an account?{" "}
                  <Link href={otherHref("login")} className="font-medium text-primary underline-offset-2 hover:underline">
                    Sign in
                  </Link>
                  .
                </>
              ) : signupOpen ? (
                <>
                  New here?{" "}
                  <Link href={otherHref("signup")} className="font-medium text-primary underline-offset-2 hover:underline">
                    Create an account
                  </Link>
                  . Forgot your password? Ask an admin to reset it.
                </>
              ) : (
                <>
                  Accounts are created by an admin. Forgot your password? Ask an admin to reset it, or run{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">codejudge create-admin</code> on the server.
                </>
              )}
            </p>
            <p className="mt-3 text-xs text-muted-foreground">
              Just browsing?{" "}
              <Link href="/problems" className="font-medium text-primary underline-offset-2 hover:underline">
                See the problems
              </Link>{" "}
              without an account.
            </p>
          </div>
        </div>
        <p className="text-[11.5px] text-faint">Self-hosted. Submissions and test data stay on your infrastructure.</p>
      </div>

      <aside className="relative hidden overflow-hidden bg-[var(--panel)] p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-90"
          style={{
            background:
              "radial-gradient(60% 50% at 80% 10%, var(--panel-glow), transparent 70%), radial-gradient(50% 45% at 10% 90%, var(--panel-glow-2), transparent 70%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage: "linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)",
            backgroundSize: "36px 36px",
          }}
        />
        <div className="relative flex items-center gap-2 text-[13px] font-medium text-white/70">
          <BrandMark className="size-6" />
          Open-source coding assessments
        </div>

        <div className="relative max-w-lg">
          <h2 className="text-[34px] leading-[1.12] font-semibold tracking-[-0.03em]">
            Your own coding judge,
            <br />
            <span className="text-[var(--panel-accent)]">verdicts you can trust.</span>
          </h2>
          <p className="mt-3 text-[14.5px] leading-relaxed text-white/65">
            Write a problem, solve it in the browser in Python, C++, Java or JavaScript, and get a verdict in seconds from a
            sandbox that hostile code cannot escape.
          </p>

          <div className="mt-8 rounded-2xl bg-white/[0.06] p-4 shadow-[0_20px_60px_rgba(0,0,0,0.35)] ring-1 ring-white/10 backdrop-blur">
            <div className="flex items-center justify-between text-[12px] text-white/55">
              <span>Every test, measured</span>
              <span className="rounded-full bg-[var(--panel-accent-soft)] px-2 py-0.5 font-semibold text-[var(--panel-accent)]">
                CPU time, peak memory
              </span>
            </div>
            <ul className="mt-3 space-y-1.5 font-mono text-[12px]">
              {DEMO_TESTS.map((t) => (
                <li key={t.name} className="flex items-center justify-between rounded-lg bg-white/[0.04] px-3 py-1.5">
                  <span className="text-white/70">{t.name}</span>
                  <span className="flex items-center gap-3">
                    <span className="text-white/45">{t.time}</span>
                    <span
                      className={
                        t.verdict === "AC"
                          ? "rounded-full bg-emerald-400/15 px-2 py-0.5 font-semibold text-emerald-300"
                          : "rounded-full bg-amber-400/15 px-2 py-0.5 font-semibold text-amber-300"
                      }
                    >
                      {t.verdict}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <ul className="mt-8 grid gap-5 sm:grid-cols-2">
            {PITCH.map((p) => (
              <li key={p.title} className="flex gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-[var(--panel-accent)]">
                  <p.icon className="size-4" />
                </span>
                <div>
                  <div className="text-[13px] font-semibold">{p.title}</div>
                  <div className="mt-0.5 text-[12.5px] leading-relaxed text-white/55">{p.body}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="relative text-[11.5px] text-white/40">MIT licensed. Part of the Euron open-source initiative.</div>
      </aside>
    </div>
  );
}
