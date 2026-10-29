/**
 * Named aliases over the generated OpenAPI types (`pnpm gen:api`). Nothing here is
 * hand-written: every shape comes from `schema.d.ts`, which is generated from
 * docs/api/openapi.yaml.
 */
import type { components, paths } from "./schema";

type S = components["schemas"];
/** The JSON body of a POST route, for schemas whose generated name is not stable. */
type PostBody<P extends keyof paths> = paths[P] extends { post: { requestBody?: { content: { "application/json": infer B } } } } ? B : never;

export type User = S["UserOut"];
export type UserCreate = S["UserCreate"];
export type UserUpdate = S["UserUpdate"];
export type SignIn = S["SignInOut"];
export type AuditEntry = S["AuditOut"];
export type SystemInfo = S["SystemInfo"];

export type QueueStatus = S["QueueStatus"];

export type Language = S["LanguageOut"];
export type ProblemSummary = S["ProblemSummary"];
export type ProblemPage = S["ProblemPage"];
export type Problem = S["ProblemOut"];
export type ProblemAdmin = S["ProblemAdmin"];
export type ProblemCreate = S["ProblemCreate"];
export type ProblemUpdate = S["ProblemUpdate"];
export type Sample = S["Sample"];
export type TagCount = S["TagCount"];
export type CheckerSpec = S["CheckerSpec"];
export type GroupSpec = S["GroupSpec"];
export type TestIn = S["TestIn"];
export type TestMeta = S["TestMeta"];
export type Version = S["VersionOut"];
export type VersionCreate = S["VersionCreate"];
export type Reference = S["ReferenceOut"];
export type ReferenceIn = S["ReferenceIn"];
export type ImportResult = S["ImportResult"];

export type Submission = S["SubmissionOut"];
export type SubmissionPage = S["SubmissionPage"];
export type SubmissionCreate = S["SubmissionCreate"];
export type RunCreate = PostBody<"/api/v1/runs">;
export type TestOutcome = S["TestOut"];

export type Role = NonNullable<UserCreate["role"]>;
export type Difficulty = NonNullable<ProblemCreate["difficulty"]>;

export type PublicSettings = S["PublicSettings"];
export type AdminSettings = S["AdminSettings"];
export type SettingsUpdate = S["SettingsUpdate"];

export type ContestSummary = S["ContestSummary"];
export type Contest = S["ContestOut"];
export type ContestCreate = S["ContestCreate"];
export type ContestUpdate = S["ContestUpdate"];
export type ContestProblem = S["ContestProblemOut"];
export type ContestFormat = Contest["format"];
export type ContestPhase = Contest["phase"];
export type Scoreboard = S["Scoreboard"];
export type ScoreRow = S["RowOut"];
export type ScoreCell = S["CellOut"];
export type ContestStatus = S["MyStatus"];
export type Clarification = S["ClarificationOut"];

export type ClassRoom = S["ClassOut"];
export type ClassMember = S["MemberOut"];
export type Assignment = S["AssignmentOut"];
export type AssignmentCreate = S["AssignmentCreate"];
export type AssignmentUpdate = S["AssignmentUpdate"];
export type AssignmentProblem = S["AssignmentProblemOut"];
export type LatePolicy = Assignment["late_policy"];
export type Gradebook = S["Gradebook"];

export type Assessment = S["AssessmentOut"];
export type AssessmentCreate = S["AssessmentCreate"];
export type AssessmentUpdate = S["AssessmentUpdate"];
export type Invitation = S["InvitationOut"];
export type InviteResult = S["InviteResult"];
export type CandidateView = S["CandidateView"];
export type CandidatePreview = S["CandidatePreview"];
export type CandidateReport = S["Report"];

export type PlagiarismRun = S["RunOut"];
export type PlagiarismRunDetail = S["RunDetail"];
export type PlagiarismPair = S["PairOut"];
export type PlagiarismPairDetail = S["PairDetail"];
export type PlagiarismScope = PlagiarismRun["scope"];

export type AnalyticsOverview = S["Overview"];
export type ProblemStats = S["ProblemStats"];
export type UserProgress = S["UserProgress"];
export type DayPoint = S["DayPoint"];
export type VerdictMix = S["VerdictMix"];

export type HintStatus = S["HintStatus"];
export type Hint = S["HintOut"];
