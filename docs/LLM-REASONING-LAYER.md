# LLM-Based Reasoning Layer for Defensive Use

**Purpose:** Use an LLM to reason over the **structured event graph** (DSO) and produce step-by-step explanations with citations and confidence—**without any autonomous action**.

**Constraints:** LLM cannot take autonomous action; operates only on structured event graph; all outputs must cite graph nodes; step-by-step explanation required; confidence score required.

---

## Table of contents

| § | Topic |
|---|--------|
| 1 | [Prompt design](#1-prompt-design) |
| 2 | [Structured context injection method](#2-structured-context-injection-method) |
| 3 | [Guardrails to prevent hallucination](#3-guardrails-to-prevent-hallucination) |
| 4 | [Audit logging schema](#4-audit-logging-schema) |
| 5 | [Explanation outputs](#5-explanation-outputs) |

---

## 1. Prompt Design

### 1.1 System prompt (fixed, versioned)

The system prompt establishes role, constraints, and output format. It is **immutable per deployment** and versioned for audit.

```
You are a defensive analyst assistant. You reason ONLY over the structured event graph provided in the context below.

RULES:
- You MUST NOT take any action, execute commands, or suggest specific remediation steps that change system state.
- You MUST base every factual claim on the provided graph. Every claim MUST cite at least one graph node or edge by its canonical ID (e.g. did:..., evt:..., clu:..., RiskScore id).
- You MUST output a step-by-step explanation. Each step MUST include a "citations" array listing the graph node/edge IDs that support that step.
- You MUST output a confidence score between 0.0 and 1.0 for your overall assessment, with a brief justification.
- If the graph does not contain information needed to answer the query, say so and do not infer. Do not invent nodes, events, or relationships.
- Output ONLY valid JSON conforming to the required schema (explanation_steps, summary, confidence, confidence_justification). No markdown, no code blocks, no text outside the schema.
```

### 1.2 Context block (graph only)

- **Single source of truth:** The only factual input to the LLM is the **structured context** block, which is a serialized subset of the graph (nodes and edges) retrieved for the current query. No free-form user narrative as “facts”; user input is treated as **query intent** only.
- **Format:** JSON or JSON Lines: list of nodes (with label and properties) and list of edges (source_id, target_id, type). Node IDs are the canonical DSO IDs (e.g. `did:uuid`, `evt:uuid`, `clu:...`). See §2.

### 1.3 User prompt template

- **Query (user):** Natural language question or task, e.g. “Explain why device did:abc is high risk” or “What might link the spike in cluster clu:123 to device did:xyz?”
- **Injected template:**

```
Context (event graph subset — this is the ONLY source of facts; you must cite from this):

<structured_context>

Query: <user_query>

Respond with a step-by-step explanation. Every step must cite graph node/edge IDs from the context above. Include a confidence score and justification. Output valid JSON only.
```

### 1.4 Prompt versioning

- System prompt and user template are stored with a **version id** (e.g. `prompt_v1`). Version is logged in the audit record (§4) so that outputs can be interpreted and re-run with the same prompt set.

---

## 2. Structured Context Injection Method

### 2.1 Principle

- **Graph-only:** The LLM receives no unstructured text as “context” other than the serialized graph. All narrative context (e.g. “Device X had high risk”) must be derivable from the graph structure and properties in the context block.
- **Subgraph selection:** For each request, the **reasoning service** runs one or more graph queries (e.g. Cypher) to extract a **subgraph** relevant to the query (e.g. devices and events in a time range, clusters containing a device, risk scores for a node). The result is serialized and injected into the prompt.

### 2.2 Serialization format (graph context)

Two options; the service uses one consistently.

**Option A — Node/edge lists (JSON):**

```json
{
  "nodes": [
    { "id": "did:abc-123", "label": "Device", "properties": { "platform": "windows", "last_seen": "2025-02-26T12:00:00Z" } },
    { "id": "evt:e1", "label": "Event", "properties": { "kind": "process", "ts": "2025-02-26T11:55:00Z", "device_id": "did:abc-123" } },
    { "id": "risk-1", "label": "RiskScore", "properties": { "score": 0.82, "level": "high", "source": "did:abc-123", "window_start": "...", "window_end": "..." } }
  ],
  "edges": [
    { "source": "did:abc-123", "target": "evt:e1", "type": "REPORTS" },
    { "source": "did:abc-123", "target": "risk-1", "type": "HAS_RISK_IN" }
  ]
}
```

**Option B — Triples (compact):**

```
did:abc-123  label  Device
did:abc-123  platform  windows
did:abc-123  REPORTS  evt:e1
evt:e1  kind  process
did:abc-123  HAS_RISK_IN  risk-1
risk-1  score  0.82
risk-1  level  high
```

- **Injection:** The chosen serialization is placed in `<structured_context>` in the user prompt. **Maximum context size** (e.g. 16K tokens) is enforced; if the subgraph is too large, the service truncates or re-queries with a narrower scope (e.g. fewer hops, shorter time window).

### 2.3 Subgraph query strategy

- **Query-driven:** Parse or map the user query to graph parameters (e.g. node_id, time range, cluster_id). Run parameterized Cypher (or equivalent) to fetch:
  - Nodes: Devices, Events, RiskScores, TimeWindows, Clusters, SurveillanceSubjects that match.
  - Edges: REPORTS, HAS_RISK_IN, MEMBER_OF, COMMUNICATES_WITH, etc., between those nodes.
- **Bounded:** Limit depth (e.g. 2 hops from seed node) and node count (e.g. 500 nodes) so that the serialized context stays within the model’s context window and reduces noise.
- **No raw logs:** Only graph nodes and edges are included; no free-text logs or payloads. This keeps the LLM on the structured event graph and avoids hallucination from unstructured content.

---

## 3. Guardrails to Prevent Hallucination

### 3.1 No autonomous action

- **Design:** The LLM is **read-only**. Its output is an **explanation** (and optionally a list of suggested **human-reviewed** actions). There is no API or path by which the LLM output is parsed to trigger commands, config changes, or alerts automatically.
- **Enforcement:** No “tool use” or “function calling” that executes state-changing operations. If the product later adds “suggested actions,” they are presented to an operator and executed only after explicit approval.

### 3.2 Graph-only facts; mandatory citations

- **Input:** Only the structured graph context is provided as factual input. The model is instructed to cite a node or edge ID for every factual claim.
- **Output validation (post-processing):**  
  - Parse the LLM response as JSON (§5).  
  - For each `explanation_steps[].citations[]`, check that every cited ID appears in the **injected context** (nodes or edge endpoints).  
  - If any citation references an ID not in the context, **reject the response** (or strip that step / return a safe fallback: “Unable to verify citations”) and log the incident.
- **No citation → no claim:** If the model makes a claim without a citation, the guardrail treats it as invalid for that step; either request a rewrite (with strict instructions) or omit that step and lower the overall confidence.

### 3.3 Output schema enforcement

- **Structured output:** Require the model to respond with **only** the JSON object defined in §5 (explanation_steps, summary, confidence, confidence_justification). Use one of:
  - **Structured output mode** (e.g. OpenAI JSON mode, or response_format: { type: "json_schema", schema: ... }).
  - **Grammar / constrained decoding** so that only valid JSON conforming to the schema can be generated.
- **Validation:** After generation, validate the JSON against the schema. If invalid, do not return the raw text to the caller; return an error and log. Optionally retry once with a stricter prompt.

### 3.4 Refusal and out-of-scope

- **Explicit instruction:** If the graph does not contain information needed to answer the query, the model must say so and not infer. No “guessing” node IDs or relationships.
- **Refusal path:** If the user query asks for action, access to raw data, or information outside the graph, the model must refuse and explain that it only reasons over the provided graph and does not take action. These refusals are logged in the audit log with query and response type “refused.”

### 3.5 Confidence and low-confidence handling

- **Confidence score:** Every response includes a confidence score in [0, 1]. Low confidence (e.g. &lt; 0.5) can trigger:
  - A warning in the UI.
  - Optional automatic escalation or “needs human review” flag in the audit log.
- The model must not present low-confidence conclusions as certain; the confidence_justification field is used to explain why confidence is low (e.g. “Only one device in context; no cluster link”).

---

## 4. Audit Logging Schema

Every LLM request and response is logged for compliance and debugging. No raw PII or full graph dumps are required; node IDs and query metadata are sufficient.

### 4.1 Audit log entry (schema)

| Field | Type | Description |
|--------|------|-------------|
| **id** | string | Unique log entry id (e.g. UUID). |
| **ts** | string (ISO 8601) | Timestamp of the request. |
| **request_id** | string | Idempotency or correlation id from client. |
| **prompt_version** | string | Version of system + user template (e.g. `prompt_v1`). |
| **query** | string | User query (natural language). |
| **context_node_count** | integer | Number of nodes in the injected graph context. |
| **context_edge_count** | integer | Number of edges in the injected graph context. |
| **context_node_ids** | array of string | List of node IDs included in context (for citation verification). |
| **model** | string | Model identifier (e.g. `gpt-4`, `claude-3-sonnet`). |
| **response_type** | string | `explanation` \| `refused` \| `error` \| `invalid_output`. |
| **explanation_summary** | string (optional) | Short summary from the response (if type = explanation). |
| **confidence** | number (optional) | Confidence score from response (if type = explanation). |
| **citation_count** | integer (optional) | Total number of citations in the response. |
| **citation_ids** | array of string (optional) | All cited node/edge IDs (for verification). |
| **all_citations_in_context** | boolean (optional) | Result of guardrail check: true if every citation was in context. |
| **error_message** | string (optional) | If response_type = error or invalid_output. |
| **latency_ms** | integer (optional) | Time to produce response. |

### 4.2 Storage and retention

- **Immutable:** Append-only store (e.g. log file, object store, or audit table). No updates or deletes.
- **Retention:** Per policy (e.g. 90 days); redact or hash `query` if it might contain sensitive free text.
- **Access:** Restricted; only authorized roles can search or export. Used for compliance, incident review, and improving prompts/guardrails.

### 4.3 Example (JSON)

```json
{
  "id": "log-a1b2c3",
  "ts": "2025-02-26T14:00:00Z",
  "request_id": "req-xyz",
  "prompt_version": "prompt_v1",
  "query": "Why is device did:abc-123 high risk?",
  "context_node_count": 12,
  "context_edge_count": 18,
  "context_node_ids": ["did:abc-123", "evt:e1", "evt:e2", "risk-1", "risk-2", "win:1:3600"],
  "model": "gpt-4",
  "response_type": "explanation",
  "explanation_summary": "Device did:abc-123 has two high risk scores in the same window; process and privilege events are cited.",
  "confidence": 0.85,
  "citation_count": 4,
  "citation_ids": ["did:abc-123", "risk-1", "risk-2", "evt:e1"],
  "all_citations_in_context": true,
  "latency_ms": 1200
}
```

---

## 5. Explanation Outputs

### 5.1 Required JSON schema

The LLM must return **only** a JSON object of the following form. All factual claims must be tied to steps that cite graph nodes/edges from the injected context.

```json
{
  "explanation_steps": [
    {
      "step_number": 1,
      "claim": "Device did:abc-123 has a high risk score in the given time window.",
      "citations": ["did:abc-123", "risk-1"]
    },
    {
      "step_number": 2,
      "claim": "The risk score risk-1 is associated with process event evt:e1 on the same device.",
      "citations": ["risk-1", "evt:e1", "did:abc-123"]
    }
  ],
  "summary": "One- or two-sentence overall explanation.",
  "confidence": 0.85,
  "confidence_justification": "Brief reason for the confidence (e.g. multiple corroborating nodes vs. single edge)."
}
```

### 5.2 Field rules

| Field | Rule |
|-------|------|
| **explanation_steps** | At least one step. Each step has step_number (integer), claim (string), citations (array of strings). Citations must be node IDs or edge identifiers (e.g. source_id:target_id:type) from the context. |
| **summary** | Short narrative tying the steps together. No new facts without citations; summary should reflect only what the steps support. |
| **confidence** | Float in [0.0, 1.0]. |
| **confidence_justification** | Free text but short; explains why confidence is high or low (e.g. “Multiple devices and risk scores in context” vs. “Only one event; no cluster link”). |

### 5.3 Citation format

- **Nodes:** Use the canonical ID from the graph (e.g. `did:abc-123`, `evt:e1`, `clu:123:hash`, `risk-1`).
- **Edges:** Either reference by endpoint nodes (so the claim cites both nodes) or use a triple format in citations, e.g. `did:abc-123:REPORTS:evt:e1`, if the schema allows. The guardrail checks that every cited value appears in the injected context (as node id or as source/target/type of an edge).

### 5.4 Example response

```json
{
  "explanation_steps": [
    {
      "step_number": 1,
      "claim": "Device did:abc-123 has risk score 0.82 (high) in window win:1730000000:3600.",
      "citations": ["did:abc-123", "risk-1"]
    },
    {
      "step_number": 2,
      "claim": "Device did:abc-123 reports process event evt:e1 and privilege event evt:e2 in the same period.",
      "citations": ["did:abc-123", "evt:e1", "evt:e2"]
    },
    {
      "step_number": 3,
      "claim": "did:abc-123 is in cluster clu:1730000000:xyz with device did:def-456; both have high risk in the same window, suggesting coordinated activity.",
      "citations": ["did:abc-123", "did:def-456", "clu:1730000000:xyz", "risk-1", "risk-2"]
    }
  ],
  "summary": "Device did:abc-123 shows high risk due to process and privilege events and shares a risk cluster with did:def-456, indicating possible coordinated anomaly.",
  "confidence": 0.82,
  "confidence_justification": "Multiple events and cluster membership support the assessment; confidence is not 1.0 because we do not have payload details, only graph structure."
}
```

---

## Document Control

- **Created:** 2025-02-26  
- **Status:** Design approved  
- **Dependencies:** DSO event graph ([DSO-ONTOLOGY.md](DSO-ONTOLOGY.md)); no autonomous action by design.  
- **Implementation:** Use this doc for prompt templates, context serialization, guardrail logic, audit schema, and explanation JSON schema in a reasoning service (e.g. `reasoning/` or integration in `graph/` or fusion).
