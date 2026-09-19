# ADR standards

Applies when recording or editing an architecture decision in `docs/DECISION_LOG.md`.

Every technical decision worth remembering — framework/library choice, data model shape, testing
strategy, CI/CD or tooling pipeline, deployment/containerization approach, or a reversal of a
prior decision — must be recorded as an ADR before the code review that implements it lands.

## Format (MADR / Nygard hybrid)

Each entry uses exactly this structure:

```markdown
## ADR-[ID]: [Decision Name]

**Status:** Proposed | Accepted | Deprecated | Superseded
**Date:** YYYY-MM-DD

### Context and Problem

Short description of the challenge, technical constraints, or time limits (e.g. 4-6h box).

### Chosen Option and Justification

The option picked and the technical reason it won over the alternatives considered.

### Trade-offs and Consequences

- **Positive (+):** immediate and architectural benefits.
- **Negative (-):** limitations, technical debt accepted, or open follow-ups.
```

## Rules for the AI

- IDs are sequential and never reused: `ADR-001`, `ADR-002`, ... Find the highest existing ID in
  `docs/DECISION_LOG.md` before adding a new one.
- All entries live in `docs/DECISION_LOG.md`, appended in ID order. Never create per-decision
  files.
- `Date` is the date the decision was made/recorded, not the date of a later edit.
- Changing an accepted decision does not edit its entry in place: add a new ADR, set the old
  entry's `Status` to `Superseded`, and reference the new ADR's ID from it.
- Ground every ADR in what the codebase actually does — check current config/dependencies/CI
  state before writing "Accepted"; if something is planned but not implemented, say so in
  `Negative` or mark the ADR `Proposed`, don't claim it as delivered.
- Keep each section to a few sentences; this is a decision record, not a design doc.
