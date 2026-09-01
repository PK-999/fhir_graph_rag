# Gemini / Antigravity Agent Workflow

## Goal
Maximize correctness while minimizing repeated context and token use.

## Context strategy

### Always loaded
Keep `GEMINI.md` short. It contains only project-wide invariants.

### Load on demand
Use individual documents for the current task:
- synthetic data -> `DATA_GENERATION_SPEC.md`
- graph -> `GRAPH_SCHEMA.md`
- API -> `API_CONTRACT.md`
- UI/product -> `PRODUCT_SPEC.md`
- coding/testing -> `ENGINEERING_STANDARDS.md`

Do not ask the agent to reread all specs on every turn.

## Task size
Give the agent one vertical milestone or one bounded issue at a time.

Good:
"Implement deterministic Patient + Encounter generation and tests according to DATA_GENERATION_SPEC.md."

Bad:
"Build the entire product."

## Required agent loop
For each task:
1. inspect relevant specs;
2. inspect existing implementation;
3. propose a short plan;
4. implement the smallest complete slice;
5. run targeted tests;
6. fix failures;
7. summarize changed files and verification.

## Token-saving conventions
- Ask for patches, not pasted full files, when interacting in chat.
- Keep terminal output truncated to failures/relevant summaries.
- Prefer scripts for deterministic checks.
- Put large schemas/catalogs under `references/` or project files, not agent instructions.
- Use stable interfaces so later tasks do not need whole-codebase context.
- Commit after each milestone.
- Start fresh agent sessions for unrelated milestones.
- Reference paths directly instead of pasting their contents.
- Do not ask the agent to narrate routine reasoning.

## Model strategy
Use the strongest reasoning model for:
- ontology changes
- architecture
- difficult debugging
- cross-service refactors

Use a faster/lower-cost model for:
- boilerplate
- tests derived from an existing contract
- CRUD endpoints
- simple UI implementation
- formatting/refactoring with clear constraints

## Git strategy
Before each milestone:
- working tree clean;
- create focused branch;
- make one coherent commit after tests pass.

Never combine architecture rewrites with UI polish in one task.

## MCP/plugins
Install only tools that remove a real manual bottleneck.

High-value:
- GitHub MCP/plugin: issues, PRs, code review
- browser automation: UI/E2E verification
- PostgreSQL/Neo4j tooling only if read-limited and necessary
- official documentation lookup where available

Avoid:
- multiple overlapping coding-agent plugins
- broad filesystem/shell plugins when built-in tools already suffice
- loading huge documentation MCP contexts by default

## Antigravity/Gemini skills
Workspace skills are stored under `.gemini/skills/`.
Use skills for specialized procedures that should activate only on relevant tasks.
Keep the root `GEMINI.md` for persistent invariants.

Recommended workspace skills:
- `fhir-data`
- `graph-modeling`
- `quality-gate`

Do not create a skill for ordinary React/Python coding unless the project has a special workflow requiring it.
