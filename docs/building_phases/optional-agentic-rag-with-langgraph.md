# Optional extension — Agentic RAG with LangGraph

This extension begins only after the deterministic baseline is complete and evaluated.

Potential graph:

```text
classify question
→ rewrite query
→ retrieve
→ judge evidence sufficiency
→ answer, abstain, or reformulate and retry
→ validate citations
```

The extension must be compared against the baseline using the same evaluation dataset. It is retained only if it produces a meaningful improvement that justifies additional latency, model calls, state, and operational complexity.

A separate ADR should be created if this extension is implemented.

---
