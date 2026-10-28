# AI hints

Optional hints from a language model, through any OpenAI-compatible endpoint: a local model
(Ollama, vLLM, llama.cpp server) or a hosted one. Code: `hints/`, settings in `org/`.

## Off by default

With `ai_enabled` false (the default) no request is ever made: the hint endpoint refuses
before it builds anything. The integration test proves it by counting the requests the mock
model receives: zero. Judging never uses a model either; compiling and running a submission
consumes no tokens.

## When a hint is allowed

| Context | Allowed |
| --- | --- |
| Practice | When the admin enables AI and `ai_allowed_in_practice` (on by default) |
| Assignments | Only when `ai_allowed_in_assignments` is on (off by default) |
| Contests | Never |
| Assessments | Never |

Each person may ask for `ai_max_hints_per_problem` hints per problem (3 by default). The cap
is checked and a slot reserved under an advisory lock, so parallel requests cannot exceed
it; a failed provider call does not use a slot. `GET /api/v1/hints/status` tells the editor
whether to show the button and how many hints are left.

## What the model sees

The statement (at most 8,000 characters), the public samples, the person's own code (at
most 12,000 characters), and the verdict of their last submission with the **name** of the
first failing test. Hidden test inputs and answers never enter the prompt: the hint service
does not even read them, only the sample content stored on the problem version. A failing
hidden test is named (`secret/3`), never shown. The system prompt asks for a hint, not a
solution.

The request uses a 30 second timeout, at most 400 tokens and temperature 0.2. A provider
error comes back as a message that says what to check in Settings.

## Settings

| Setting | Meaning |
| --- | --- |
| `ai_enabled` | The master switch |
| `ai_base_url` | An OpenAI-compatible base URL (the request goes to `<base>/chat/completions`) |
| `ai_model` | The model name |
| `ai_api_key` | Sealed with the same sealer as every secret (AES-GCM locally, KMS on AWS); never returned, only whether one is set |
| `ai_max_hints_per_problem`, `ai_allowed_in_practice`, `ai_allowed_in_assignments` | Above |

`AI_ALLOW_PRIVATE_ENDPOINTS` (environment, default true) lets the base URL be a private
address, which a local model needs. Set it to false when only hosted providers are allowed;
instance metadata addresses are refused either way.
