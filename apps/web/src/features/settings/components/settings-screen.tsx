"use client";

import { KeyRoundIcon, LockIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { AdminOnly } from "@/components/admin-only";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { usePermissions } from "@/features/auth/api";
import { useLanguages } from "@/features/problems/api";
import { errorMessage } from "@/lib/api/errors";
import type { AdminSettings, SettingsUpdate } from "@/lib/api/types";

import { useOrgSettings, useUpdateOrgSettings } from "../api";

function Toggle({ label, hint, checked, onChange, disabled }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <label className="flex items-start gap-3 py-1">
      <Switch checked={checked} onCheckedChange={onChange} disabled={disabled} aria-label={label} className="mt-0.5" />
      <span>
        <span className="block text-[13px] font-medium">{label}</span>
        {hint && <span className="block text-[12px] text-muted-foreground">{hint}</span>}
      </span>
    </label>
  );
}

export function SettingsScreen() {
  const { user, admin } = usePermissions();
  const q = useOrgSettings();
  if (user && !admin) return <AdminOnly what="Settings" />;
  return (
    <>
      <PageHeader title="Settings" description="How this CodeJudge server presents itself, who can sign up, and the optional AI hints." />
      {q.isError ? (
        <ErrorState error={q.error} title="Settings could not be loaded" onRetry={() => void q.refetch()} />
      ) : !q.data ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <SettingsForm settings={q.data} />
      )}
    </>
  );
}

function SettingsForm({ settings: s }: { settings: AdminSettings }) {
  const update = useUpdateOrgSettings();
  const languages = useLanguages();
  const [siteName, setSiteName] = React.useState(s.site_name);
  const [signup, setSignup] = React.useState(s.allow_signup);
  const [language, setLanguage] = React.useState(s.default_language);
  const [aiEnabled, setAiEnabled] = React.useState(s.ai_enabled);
  const [baseUrl, setBaseUrl] = React.useState(s.ai_base_url ?? "");
  const [model, setModel] = React.useState(s.ai_model ?? "");
  const [newKey, setNewKey] = React.useState("");
  const [maxHints, setMaxHints] = React.useState(String(s.ai_max_hints_per_problem));
  const [practice, setPractice] = React.useState(s.ai_allowed_in_practice);
  const [assignments, setAssignments] = React.useState(s.ai_allowed_in_assignments);
  const [error, setError] = React.useState<string | null>(null);

  function save(extra: SettingsUpdate = {}) {
    const hints = Number(maxHints);
    if (!siteName.trim()) return setError("The site name cannot be empty.");
    if (!Number.isInteger(hints) || hints < 0 || hints > 50) return setError("Hints per problem must be 0 to 50.");
    if (aiEnabled && !baseUrl.trim()) return setError("Hints need the address of an OpenAI-compatible endpoint (for example a local Ollama at http://ollama:11434/v1).");
    setError(null);
    const body: SettingsUpdate = {
      site_name: siteName.trim(),
      allow_signup: signup,
      default_language: language,
      ai_enabled: aiEnabled,
      ai_base_url: baseUrl.trim(),
      ai_model: model.trim() || null,
      ai_max_hints_per_problem: hints,
      ai_allowed_in_practice: practice,
      ai_allowed_in_assignments: assignments,
      ...(newKey ? { ai_api_key: newKey } : {}),
      ...extra,
    };
    update.mutate(body, {
      onSuccess: () => {
        setNewKey("");
        toast.success("Settings saved.");
      },
      onError: (e) => setError(errorMessage(e)),
    });
  }

  return (
    <div className="max-w-3xl space-y-4">
      <Surface>
        <SurfaceHeader title="General" />
        <div className="grid gap-4 px-5 pb-5">
          <Field label="Site name" htmlFor="st-name" hint="Shown on the sign-in page and in invitation emails.">
            <Input id="st-name" value={siteName} onChange={(e) => setSiteName(e.target.value)} />
          </Field>
          <Field label="Default language" htmlFor="st-lang" hint="Preselected in the editor for people who have not picked one.">
            <SimpleSelect id="st-lang" value={language} onValueChange={setLanguage} options={(languages.data ?? []).map((l) => ({ value: l.id, label: l.name }))} />
          </Field>
          <Toggle
            label="Anyone can create an account"
            hint={signup ? "The sign-in page offers sign-up. New accounts are students." : "Only admins create accounts (Users page)."}
            checked={signup}
            onChange={setSignup}
          />
        </div>
      </Surface>

      <Surface>
        <SurfaceHeader
          title="AI hints"
          description="Optional. When on, students can ask a model for a nudge on a problem. Judging never uses AI. The model sees the statement, the code and the last result, never hidden tests."
        />
        <div className="grid gap-4 px-5 pb-5">
          <Toggle label="Offer AI hints" hint={aiEnabled ? "On where allowed below." : "Off: no request is ever sent to a model."} checked={aiEnabled} onChange={setAiEnabled} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Endpoint (OpenAI-compatible)" htmlFor="st-url" hint="A local model (Ollama, vLLM) keeps code on your servers.">
              <Input id="st-url" placeholder="http://ollama:11434/v1" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </Field>
            <Field label="Model" htmlFor="st-model">
              <Input id="st-model" placeholder="llama3.1:8b" value={model} onChange={(e) => setModel(e.target.value)} />
            </Field>
          </div>
          <Field
            label="API key"
            htmlFor="st-key"
            labelExtra={s.ai_has_key ? <Chip tone="success" className="ml-2">A key is stored</Chip> : <Chip tone="neutral" className="ml-2">No key</Chip>}
            hint="Stored sealed and never shown again. Type a new one to replace it; leave empty to keep the current one."
          >
            <div className="flex gap-2">
              <Input id="st-key" type="password" autoComplete="off" placeholder={s.ai_has_key ? "Replace the stored key" : "Only if the endpoint needs one"} value={newKey} onChange={(e) => setNewKey(e.target.value)} />
              {s.ai_has_key && (
                <Button variant="destructive-soft" onClick={() => save({ ai_api_key: "" })} disabled={update.isPending}>
                  <KeyRoundIcon />
                  Remove key
                </Button>
              )}
            </div>
          </Field>
          <Field label="Hints per person per problem" htmlFor="st-max" hint="0 turns hints off without losing the endpoint settings.">
            <Input id="st-max" inputMode="numeric" className="w-28" value={maxHints} onChange={(e) => setMaxHints(e.target.value)} />
          </Field>
          <div className="grid gap-1 sm:grid-cols-2">
            <Toggle label="In practice" checked={practice} onChange={setPractice} />
            <Toggle label="In class assignments" checked={assignments} onChange={setAssignments} />
            <span className="flex items-center gap-2 py-1 text-[13px] text-muted-foreground">
              <LockIcon className="size-3.5" aria-hidden />
              Never in contests
            </span>
            <span className="flex items-center gap-2 py-1 text-[13px] text-muted-foreground">
              <LockIcon className="size-3.5" aria-hidden />
              Never in interview assessments
            </span>
          </div>
        </div>
      </Surface>
      {error && <FieldError>{error}</FieldError>}
      <Button disabled={update.isPending} onClick={() => save()}>
        {update.isPending ? "Saving..." : "Save settings"}
      </Button>
    </div>
  );
}
