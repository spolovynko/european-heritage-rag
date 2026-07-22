# Building guides

This folder records what was actually built in each development phase and how
the resulting system works. It is a living implementation guide, not a plan.

The documentation areas have different responsibilities:

- `docs/building_phases/` defines the planned scope and exit criteria for each
  phase.
- `docs/building_guides/` reviews the implementation produced by each phase.
- `docs/adr/` records durable architecture decisions and their alternatives.
- `docs/project-status.md` records the current project state and next handoff.

## Guides

- [Phase 2: environment and repository setup](phase-02-environment-and-repository-setup.md)
- [Phase 3: UI foundation and progress dashboard](phase-03-ui-foundation-and-progress-dashboard.md)
- [Phase 4: Wellcome discovery and ingestion client](phase-04-wellcome-discovery-and-ingestion-client.md)

## Update convention

At the end of each phase:

1. Review the committed implementation rather than copying the phase plan.
2. Record the modules, frameworks, runtime flow, and operational commands.
3. Explain how the important code works and why its boundaries exist.
4. Record tests and verification evidence without claiming unmeasured results.
5. Identify current limitations and the phase in which they should change.
6. Prefer links to official framework documentation for behavior maintained by
   an external tool or library.

## Guide template

Use the same reading order for every phase guide:

1. **Phase at a glance** — result, technologies, and deliberate exclusions.
2. **Repository structure** — files and modules added or changed.
3. **Runtime flow** — how the parts interact when the system runs.
4. **Module reviews** — purpose, main pieces, behavior, design, limits, tests.
5. **Tool management** — dependencies, containers, data, or infrastructure.
6. **Verification** — commands and the property proved by each command.
7. **Review summary** — what is stable and what should be revisited later.

Prefer short paragraphs, comparison tables, and small code examples. Explain a
term before using it as part of a design argument.
