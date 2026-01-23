# Alignment Gaps and Decisions

## Decisions (spec)
- Human inbox actions add follow-on tags without removing pending tags; BA/Architect clear pending tags after verification.
- Ops merges only when `Review-Approved` + `Ops-Ready` are present (explicit human gate).
- Inbox excludes items with `Review-Approved` + `Ops-Ready`.
- Staleness uses task last update time (`updated_at`).
- Frontend inbox filtering uses system tags, with a fallback trigger list if `/system-tags` fails.

## Resolved Gaps
- Inbox trigger source uses system_tag_id with tag-name fallback; frontend filters use system tags plus fallback list.
- Inbox actions and ALS templates use canonical action IDs and align tags.add/tags.remove.
- Inbox tag mutations keep pending tags; follow-on tags drive agent pickup.
- Ops merge gating requires `Review-Approved` + `Ops-Ready` in coordinator/ops logic.
- Workflow tags exist in system_tags seed data (see migrations/037 + 039).
- Inbox UI surfaces task resources (PR/branch links) when present.

## Open Items
None.
