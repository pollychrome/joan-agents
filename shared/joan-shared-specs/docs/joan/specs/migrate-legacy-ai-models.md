# Spec: Migrate Legacy AI Providers to Unified Models

Status: Draft
Owner: TBD

## Summary
Migrate all AI entry points (ceremonies, resources, global chat) to the unified AI model system based on `api_keys` and `ai_models`, and retire the legacy `ceremony_ai_providers` and `ai-context-builder` paths.

## Goals
- Use `api_keys` + `ai_models` as the single source of truth for provider selection and model configuration.
- Route all AI calls through a shared client with consistent retries, response parsing, and usage tracking.
- Use `AIContextService` as the primary context builder for all AI features.
- Eliminate legacy provider tables and code paths from runtime usage.

## Non-goals
- Redesigning prompt content or ceremony flows.
- Changing external API behavior or response formats from endpoints.
- Reworking the admin UI beyond wiring it to the unified model system.

## Current State (Key Divergences)
- Ceremonies use `ceremony_ai_providers` and inline API calls. `workers/src/routes/ceremonies.ts`
- Resources use `ai-context-builder` and inline API calls with partial use of `AIProviderService`. `workers/src/routes/ai-resources.ts`
- Global chat uses `AIContextService` and `AIToolRegistry`. `workers/src/services/global-chat-handler.ts`
- Legacy `ceremony_ai_requests.provider_id` expects `ceremony_ai_providers` but is already written inconsistently. `migrations/017_ceremony_tables.sql`

## Target State
- All AI features select models via `AIProviderService` (reads `api_keys` and `ai_models`).
- All AI calls go through a shared `AIClient` with a consistent request/response shape.
- `AIContextService` is used for global chat, ceremonies, and resources.
- Usage tracking is recorded against `ai_models` and `ai_model_usage`.
- `ceremony_ai_providers` is deprecated and no longer referenced at runtime.

## Proposed Changes

### 1) Data model alignment
- Add `ai_model_id` to `ceremony_ai_requests` and use it for new writes.
- Keep `ceremony_ai_requests` for ceremony-specific analytics, but stop writing `provider_id`.
- Continue to keep `ceremony_ai_providers` table for rollback only.

### 2) Data migration
- One-time script or migration that:
  - Converts `ceremony_ai_providers` rows into `api_keys` + `ai_models`.
  - Maps `ceremony_components.ai_provider_id` to `ceremony_components.ai_model_id`.
  - Leaves old fields intact for rollback.

Mapping rules:
- `ceremony_ai_providers.provider_type` -> `api_keys.provider`
- `ceremony_ai_providers.api_key` -> `api_keys.api_key_encrypted` (ensure existing encryption rules apply)
- `ceremony_ai_providers.model_name` -> `ai_models.model_id`
- `is_default` and `priority` carry over to `ai_models`

### 3) Shared AI client
Create `workers/src/services/ai/ai-client.ts` with:
- `call(provider: AIProvider, messages, options) -> { content, tokens, model }`
- Provider-specific request formatting (OpenAI, Anthropic, Groq, Ollama)
- Standard error handling and response normalization
- Optional tool call support (already implemented in handlers, but normalize responses)

### 4) Handler updates
- Ceremonies: replace `ceremony_ai_providers` selection and inline calls with `AIProviderService` + `AIClient`. `workers/src/routes/ceremonies.ts`
- Resources: use `AIProviderService` + `AIClient` and move context to `AIContextService` (or extend it for resource context). `workers/src/routes/ai-resources.ts`
- Ceremony chat: move from `ai-context-builder` to `AIContextService`, and align tool validation with `AIToolRegistry`. `workers/src/services/ceremony-chat-handler.ts`

### 5) Context unification
Extend `AIContextService` to cover:
- Resource finder context (task, project, user goals, related tasks)
- Ceremony-specific context (daily planning summary, session metadata)

Deprecate `workers/src/services/ai-context-builder.ts` once all callers are migrated.

### 6) Usage tracking
Ensure all AI calls record:
- `ai_models.total_*` counters
- `ai_model_usage` daily aggregates
- Optional: keep `ceremony_ai_requests` for ceremony-specific diagnostics

## Migration Plan

Phase 0: Preparation
- Add new columns/migrations (`ai_model_id` on `ceremony_ai_requests`).
- Add `AIClient` and integration tests for response normalization.

Phase 1: Data migration
- Backfill `api_keys` and `ai_models` from `ceremony_ai_providers`.
- Map `ceremony_components.ai_provider_id` to `ai_model_id`.
- Validate that default model selection matches existing behavior.

Phase 2: Code migration
- Update ceremonies and resources to use `AIProviderService` + `AIClient`.
- Update ceremony chat to use `AIContextService`.
- Start dual-write of usage stats if needed for validation.

Phase 3: Cutover
- Remove reads from `ceremony_ai_providers`.
- Remove `ai-context-builder` usage.
- Update docs to reflect the unified system.

Phase 4: Cleanup (optional)
- Remove legacy tables in a later migration after stability window.

## Rollout and Backout
- Feature flag: `USE_UNIFIED_AI_MODELS=true` to gate new selection logic.
- Backout: flip the flag and keep legacy reads as long as the table remains.
- Keep legacy tables for at least one release after cutover.

## Testing and Validation
- Unit tests for `AIClient` request/response normalization.
- Integration tests for:
  - ceremony AI query endpoint
  - resource finder endpoint
  - global chat tool calls
- Data validation:
  - `api_keys` and `ai_models` counts match legacy provider count.
  - Default model selection matches current settings.

## Risks and Mitigations
- Risk: legacy provider has no matching model in `ai_models`.
  - Mitigation: create model row during migration or default to provider default model.
- Risk: key encryption mismatch during migration.
  - Mitigation: reuse existing encryption helpers used by admin API keys.
- Risk: behavior drift due to different prompt/context builders.
  - Mitigation: keep prompts stable and add parity tests around context output shape.

## Open Questions
- Should `ceremony_ai_requests` be replaced by a unified `ai_requests` table?
- Do we need a short-term adapter that mirrors `ai-context-builder` outputs for resources?
