# Building guides

This folder explains what we actually built in each phase, why we built it,
and how it works. These files describe finished work. They are not plans.

Each documentation area has one job:

- `docs/building_phases/` says what we plan to build and how we decide that a
  phase is complete.
- `docs/building_guides/` explains what we actually built.
- `docs/adr/` records important technical decisions and alternatives.
- `docs/project-status.md` says where the project is now and what comes next.

## Guides

- [Phase 2: environment and repository setup](phase-02-environment-and-repository-setup.md)
- [Phase 3: UI foundation and progress dashboard](phase-03-ui-foundation-and-progress-dashboard.md)
- [Phase 4: Wellcome discovery and ingestion client](phase-04-wellcome-discovery-and-ingestion-client.md)
- [Phase 5: Bronze data layer](phase-05-bronze-data-layer.md)
- [Phase 6: Silver normalization and OCR cleaning](phase-06-silver-normalization-and-ocr-cleaning.md)
- [Phase 7: Gold data layer and chunking experiments](phase-07-gold-data-layer-and-chunking-experiments.md)

## Update convention

At the end of each phase:

1. Read the finished code instead of copying the original plan.
2. List the files, tools, runtime flow, and commands that really exist.
3. Explain every important part in this order: what it does, why it exists, and
   how it works.
4. Keep technical names, but explain them in plain language before relying on
   them.
5. Record real test evidence without claiming results that were not measured.
6. State the current limits and when they should be addressed.
7. Link to official documentation when an external tool defines the behavior.

## Guide template

Use the same reading order for every phase guide:

1. **Phase at a glance** - the result, tools, and work deliberately left out.
2. **Repository structure** - the files and modules added or changed.
3. **Runtime flow** - what happens from the start of an operation to the end.
4. **Module reviews** - what each part does, why it exists, and how it works.
5. **Tool management** - dependencies, containers, data, or infrastructure.
6. **Verification** - the commands run and what each result proves.
7. **Review summary** - what should stay stable and what should change later.

Use short paragraphs, direct sentences, tables, and small examples. A reader
should not need to know a term before opening the guide.
