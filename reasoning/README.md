# LLM Reasoning Layer — Defensive Use

Reasoning over the **structured event graph** (DSO) with an LLM: step-by-step explanations, mandatory citations to graph nodes, confidence score, **no autonomous action**.

**Design:** [LLM-REASONING-LAYER.md](../docs/LLM-REASONING-LAYER.md)

## Contents

| Item | Description |
|------|-------------|
| **schemas/explanation_output.json** | JSON schema for LLM response (explanation_steps, summary, confidence, confidence_justification). |
| **schemas/audit_log_entry.json** | JSON schema for audit log entry (request/response metadata, citation verification). |
| **README.md** | This file. |

## Constraints (enforced by design)

- LLM **cannot take autonomous action**; output is explanation only.
- Operates **only on structured event graph** (injected as context); no raw logs.
- **All outputs must cite graph nodes** (did:, evt:, clu:, risk id, etc.); guardrail validates citations against context.
- **Step-by-step explanation** and **confidence score** required; output must conform to `explanation_output.json`.

## Usage

- **Context:** Build a subgraph from the DSO (e.g. via graph API or Cypher); serialize to JSON node/edge list or triples; inject into prompt.
- **Prompt:** Use system + user templates from the design doc; include only the serialized graph in context.
- **Response:** Parse JSON; validate against `explanation_output.json`; run citation guardrail (every citation in context_node_ids or edges).
- **Audit:** Log every request/response per `audit_log_entry.json`; append-only; retain per policy.
