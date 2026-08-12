# PInSight — Agentic Payment Incident Investigation Platform

### Project Guidelines, Roadmap, Implementation Details & Software Requirements Specification (SRS)

**Working name:** PInSight (rename freely — doesn't affect any design decision below)
**Author:** [Your name]
**Version:** 1.0
**Last updated:** [fill in]

---

## 1. Project Guidelines

### 1.1 Positioning

PInSight is a backend-first payment processing and incident-investigation system. The payment domain (transactions, webhooks, settlements, concurrency correctness) is the primary engineering surface. An agentic RCA (root-cause-analysis) module sits on top as a well-isolated service that uses tool-calling over the structured domain data — it is a *feature* of a real backend, not a wrapper around an LLM.

This dual structure is intentional: it lets the same codebase support two honest resume narratives —

- **SDE / backend-systems narrative:** idempotent transaction processing, webhook deduplication, concurrency correctness under load, async ingestion pipeline, API design, observability.
- **AI Engineer narrative:** tool-calling agent architecture, retrieval design (pgvector), eval harness with real accuracy/hallucination metrics, LLM reliability engineering (timeouts/retries/circuit breaker/fallback).

### 1.2 Design principles

1. **Correctness before cleverness.** Idempotency and concurrency bugs must be *actually* prevented (DB constraints, locking), not just handled in happy-path code.
2. **The LLM is an unreliable external dependency**, engineered around like any third-party API — never a single point of failure for the whole request.
3. **Everything the agent claims must be traceable** to a specific tool call and stored evidence. No un-cited claims in RCA output.
4. **Every claim in your resume bullets must be a claim you can reproduce on demand** — this document exists so nothing you say in an interview is unverifiable.
5. **No frameworks as a substitute for understanding.** The agent orchestration loop is hand-written (function-calling loop against the Groq API) rather than delegated to LangGraph/CrewAI, so you can explain exactly how it works. Frameworks can be mentioned as "evaluated and consciously not used" if asked.

### 1.3 Explicit non-goals

- Not a general-purpose chatbot — the agent only investigates payment incidents.
- Not a production payments processor — transaction/gateway logic is realistic but simulated (no real money movement, no PCI scope).
- Not optimized for maximum feature count — optimized for depth you can defend in a 45-minute system design interview.

---

## 2. Software Requirements Specification (SRS)

### 2.1 Introduction

**2.1.1 Purpose**
This SRS defines the functional and non-functional requirements for PInSight, a system that (a) simulates a realistic payment transaction lifecycle with injectable failure modes, and (b) provides an agentic investigation service that determines root cause for a given failed transaction/incident using retrieval and tool-calling over structured and unstructured data.

**2.1.2 Scope**
In scope: transaction/event simulation and API, idempotency and concurrency handling, webhook processing and dedup, log/incident ingestion pipeline, vector-based retrieval, agent orchestration and tool-calling, evaluation harness, dashboard UI, deployment.
Out of scope: real payment gateway integration, real money movement, PCI-DSS compliance, multi-region deployment (documented as future work only).

**2.1.3 Definitions / Acronyms**

- **RCA** — Root Cause Analysis
- **RAG** — Retrieval-Augmented Generation
- **Idempotency key** — client-supplied unique key ensuring a repeated request has no additional effect
- **Outbox pattern** — writing an event to an "outbox" table in the same DB transaction as the state change, then relaying it asynchronously, to guarantee at-least-once delivery without dual-write inconsistency
- **p99 latency** — 99th percentile response time

**2.1.4 Intended audience**
You (as builder/maintainer), and secondarily technical interviewers evaluating the system design.

### 2.2 Overall Description

**2.2.1 Product perspective**
Standalone system: FastAPI backend + Postgres/pgvector + Redis/RQ worker + Next.js frontend, containerized, deployed on AWS EC2 (backend) and Vercel (frontend).

**2.2.2 Product functions (summary)**

- Simulate transactions and payment events with realistic failure injection
- Enforce idempotency and concurrency correctness
- Ingest logs/incidents/runbooks and generate embeddings asynchronously
- Run an agentic investigation on demand, producing an evidenced RCA with confidence score
- Provide a dashboard: transaction timeline view, incident list, agent trace viewer, semantic search
- Evaluate agent RCA quality against a labeled test set

**2.2.3 User classes**

- **Operator/on-call engineer (simulated persona)** — triggers investigations, reads RCA output, browses traces
- **Admin (you, for demo)** — seeds data, runs evals, manages runbooks

**2.2.4 Operating environment**
Docker containers on Ubuntu (EC2 t3.micro, free tier), frontend on Vercel. Python 3.11+, Node 20+.

**2.2.5 Design & implementation constraints**

- EC2 free-tier instance: 1 vCPU / 1GB RAM — backend services only (Postgres, Redis, FastAPI, RQ worker); frontend deployed separately.
- Groq API rate limits (free tier) — must be handled via the reliability layer (2.4.2), not ignored.
- No real PII — all transaction/customer data synthetic.

### 2.3 Functional Requirements

| ID    | Requirement                                                                                                                                                                                                                                   |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-1  | System shall accept transaction creation requests with a required idempotency key; duplicate keys shall not create duplicate charges.                                                                                                         |
| FR-2  | System shall model transaction states:`authorized → captured → settled`, with `refunded`/`failed` branches, and reject invalid state transitions.                                                                                     |
| FR-3  | System shall accept webhook events (gateway callbacks) and deduplicate by event ID, processing each exactly once at the business-logic level.                                                                                                 |
| FR-4  | System shall support a synthetic data generator capable of injecting named failure classes (see 4.4).                                                                                                                                         |
| FR-5  | System shall allow creation of an "incident" referencing one or more transactions.                                                                                                                                                            |
| FR-6  | System shall provide an endpoint to trigger an agent investigation for a given incident.                                                                                                                                                      |
| FR-7  | The agent shall have access to distinct tools (2.5.3) and decide which to call and in what order.                                                                                                                                             |
| FR-8  | The agent shall produce a structured output: root cause hypothesis, confidence score, cited evidence (tool call + retrieved item reference), and — if confidence is below threshold — a statement of what additional information is needed. |
| FR-9  | System shall store every tool call, its arguments, result, and latency for each investigation (agent trace).                                                                                                                                  |
| FR-10 | System shall provide semantic search over incidents and runbooks (pgvector).                                                                                                                                                                  |
| FR-11 | System shall provide a dashboard showing: transaction timeline, incident list/detail, agent trace viewer, semantic search UI.                                                                                                                 |
| FR-12 | System shall support an evaluation mode: run the agent against a labeled test set and report accuracy/precision/recall/hallucination-rate metrics.                                                                                            |
| FR-13 | System shall authenticate API requests via JWT.                                                                                                                                                                                               |
| FR-14 | System shall rate-limit API requests per client (token bucket).                                                                                                                                                                               |

### 2.4 Non-Functional Requirements

**2.4.1 Performance**

- API p99 latency target: < 300ms for non-agent endpoints (excludes LLM call latency).
- System shall correctly deduplicate idempotency keys under concurrent load (verified via load test, not just unit test — see 8.8/9).
- Target: handle at least 50 req/s sustained on a single t3.micro for non-LLM endpoints (measured, reported, not assumed).

**2.4.2 Reliability**

- All Groq API calls shall have a timeout, retry with exponential backoff (max 3 attempts), and a circuit breaker (open after N consecutive failures).
- On LLM failure after retries, the investigation endpoint shall degrade gracefully: return raw retrieved evidence without a generated narrative, with a clear `degraded: true` flag — never a hard 500.

**2.4.3 Scalability (design-only, not deployed at scale)**

- Stateless API layer → horizontally scalable behind a load balancer.
- Read-heavy queries (transaction history) → documented plan for read replicas.
- Vector index → documented plan for partitioning by merchant_id once index size exceeds single-node capacity.
- This is written up in section 6.4 as a "how would you scale this" answer, not implemented.

**2.4.4 Security**

- Secrets (DB creds, Groq API key) via environment variables / `.env`, never committed.
- JWT-based auth on all mutating endpoints.
- No real PII anywhere in the system.

**2.4.5 Maintainability**

- Schema changes via Alembic migrations only, no manual DDL.
- Minimum test coverage target: all concurrency-sensitive code paths (idempotency, webhook dedup, refund/capture race) must have integration tests that actually exercise concurrent requests, not just sequential unit tests.

**2.4.6 Observability**

- Structured JSON logging.
- Every agent investigation fully traced (tool calls, latencies, token counts, cost estimate).

### 2.5 External Interface Requirements

**2.5.1 REST API (representative, not exhaustive — full contract in section 5)**
`POST /v1/transactions`, `POST /v1/webhooks`, `GET /v1/transactions/{id}/timeline`, `POST /v1/incidents`, `POST /v1/incidents/{id}/investigate`, `GET /v1/incidents/{id}/trace`, `GET /v1/search`, `POST /v1/eval/run`.

**2.5.2 Database**
PostgreSQL 15+ with `pgvector` extension.

**2.5.3 Agent tools (interface contract)**

- `query_transaction_db(transaction_id)` → structured event timeline
- `search_logs(query, filters)` → matching raw log lines
- `retrieve_similar_incidents(query, k)` → top-k past incidents via pgvector
- `retrieve_runbooks(query, k)` → top-k relevant runbook sections
- `check_failure_signatures(transaction_id)` → deterministic rule-based match against known failure patterns (non-LLM, ensures not everything depends on model judgment)

**2.5.4 LLM Provider**
Groq API (function-calling / tool-use capable model), accessed through a thin internal client wrapper (so provider is swappable later without touching the agent loop).

### 2.6 UI/UX Design Requirements

**2.6.1 Reference bar**
This is a production fintech-ops dashboard, not a marketing site or a portfolio card layout. Benchmark against Stripe Dashboard, Linear, Mercury, and Ramp for information density, component sophistication, and motion polish — then reskin from their blue/dark/monochrome palettes to the Fresh Botanical palette below. If a screen would look sparse or "empty" next to those references, it's under-built, not "clean."

**2.6.2 Visual direction: Fresh Botanical, production-grade**
Organic and warm, never black/blue/purple as a theme color — but "organic" describes the *palette*, not the density or sophistication of the layout. The bar is: would this pass as a real fintech ops tool if you swapped the color tokens? If yes, it's on target. A screen with three cards and a lot of empty cream background is not the goal.

**2.6.3 Design tokens**

*Color ramps (7 stops each, light-mode base — generate dark-mode equivalents by inverting lightness, not by introducing black/blue/purple):*

| Ramp                      | 50          | 100         | 300                 | 500 (base)              | 700                   | 900                    |
| ------------------------- | ----------- | ----------- | ------------------- | ----------------------- | --------------------- | ---------------------- |
| Sage (primary)            | `#F1F5EC` | `#DCE7CE` | `#A3C17F`         | `#6B8E5A`             | `#4A6640`           | `#2E4028`            |
| Wood/clay (secondary)     | `#F6EDE2` | `#E8D3B8` | `#C9A276`         | `#8B6F47`             | `#6B5535`           | `#463823`            |
| Cream (neutral surface)   | `#FEFCF8` | `#FAF7F0` | `#F0EBDD`         | `#DDD5C0`             | `#B8AF97`           | `#8A8168`            |
| Terracotta (danger/error) | `#FBEEE8` | `#F3D3C1` | `#DE9670`         | `#C2653A`             | `#984C2A`           | `#6B3419`            |
| Amber (warning)           | `#FBF3E2` | `#F3DFAF` | `#E0B45C`         | `#C4913A`             | `#96702A`           | `#67491A`            |
| Ink (text)                | —          | —          | `#8A8168` (muted) | `#5A5240` (secondary) | `#3D3428` (primary) | `#241F16` (headings) |

Define these as CSS custom properties (`--sage-500`, `--wood-300`, etc.) exactly like the standard `--fill-{role}`/`--bg-{role}`/`--text-{role}` pattern (base=fill, 100=bg-tint, 700=border, 900=text-on-tint) so the token *shape* stays familiar to any engineer reading the code, only the hues differ from a default design system.

*Spacing scale:* 4px base unit — 4, 8, 12, 16, 24, 32, 48, 64. No arbitrary one-off pixel values in component code.

*Type scale:* 11px (caption/meta) / 13px (body-dense, table cells) / 15px (body) / 17px (section heading) / 22px (page heading) / 28px (hero/metric display). Two weights only: 400 regular, 500 medium — never below 400 or above 600. Font pairing: a warm humanist sans for UI (body, controls, tables), a text/editorial serif reserved for page titles and the landing/marketing surface only — not on dashboard chrome, where it reads as decorative rather than functional.

*Elevation:* 3 levels via border + shadow combination, not shadow alone — `surface-0` (page bg, cream-50) → `surface-1` (card, white/cream-100, 1px `wood-100` border) → `surface-2` (popover/modal, white, 1px border + soft shadow `0 4px 16px rgba(36,31,22,0.08)`). Never more than 2 shadow-elevated layers on screen simultaneously (card + one modal/popover max).

**2.6.4 Layout & density**

- **Persistent left sidebar** (not a hamburger menu) with icon+label nav: Dashboard, Incidents, Transactions, Investigations, Runbooks, Eval Reports, Settings. Collapsible to icon-only, not hidden.
- **Top bar**: breadcrumb/page title, global search (`cmd+k` command palette — this is a real production pattern worth actually implementing, not just decorative), notifications, account menu.
- **Main content is data-dense by default**: tables with sortable/filterable columns, not card grids for list data. Cards are for summary/metric surfaces only, not used as a substitute for a proper data table.
- **Multi-panel layouts** where appropriate — e.g., incident list + incident detail as a master-detail split (like Linear's issue list), not separate full-page navigations for every drill-down.
- **Tabs** for grouping related dense content within one view (e.g., an incident detail: Overview / Timeline / Agent Trace / Related Incidents as tabs, not four separate pages).
- Whitespace is used for **visual grouping and hierarchy**, not as filler — every empty region should be doing a job (separating sections, indicating relationship) rather than existing because there wasn't enough content to place.

**2.6.5 Component inventory (build these as a reusable set, not ad hoc per screen)**

- Sidebar nav (collapsible)
- Command palette (`cmd+k`)
- Data table (sort, filter, pagination, row-select, sticky header)
- Metric/stat card with inline sparkline
- Status badge/chip set (mapped to the terracotta/amber/sage semantic colors)
- Tabs
- Modal/dialog + slide-over panel (for detail views triggered from a table row)
- Toast notification system
- Master-detail split view
- Agent trace timeline (rich version — see 2.6.6)
- Skeleton loading states (per component, not one generic spinner)
- Empty states with illustration + action, for genuinely empty data (not used to excuse sparse layout elsewhere)

**2.6.6 The agent trace viewer — flagship component, build with real production polish**
This is the component that sells the project in a demo; it deserves the most design investment. Requirements:

- Vertical timeline with connecting line, each tool call as a rich row: icon, tool name (monospace), arguments (collapsible/expandable JSON, not just a label), result summary, latency badge, timestamp.
- Steps reveal via staggered entrance (60-100ms stagger) using spring physics (Framer Motion `type: spring, stiffness: 300, damping: 30`), not linear ease — springs read as more polished/production than linear fades.
- Currently-executing step shows a subtle animated state indicator (pulsing dot or animated border), not a generic spinner.
- Final RCA output renders as a distinct, elevated card at the end of the timeline with confidence shown as a radial/circular progress indicator, not just a number.
- Clicking any step expands full tool input/output inline (accordion), so the component doubles as a debugging tool, not just a demo animation.

**2.6.7 Motion system**

| Tier         | Use case                                   | Duration                  | Easing                                                                                             |
| ------------ | ------------------------------------------ | ------------------------- | -------------------------------------------------------------------------------------------------- |
| Micro        | hover, press, toggle                       | 100-150ms                 | ease-out                                                                                           |
| Transition   | tab switch, panel open, route change       | 200-300ms                 | ease-in-out, or spring (stiffness 300/damping 30) for panels that should feel tactile              |
| Orchestrated | trace viewer reveal, multi-item list mount | 60-100ms stagger per item | spring                                                                                             |
| Data         | chart mount, number counters               | 400-600ms                 | ease-out, animate value not just opacity (numbers should count up, bars should grow from baseline) |

Implementation: Framer Motion for all React-level orchestration (`layout` animations for list reordering/filtering, `AnimatePresence` for mount/unmount), CSS transitions only for simple hover/press states on static elements. Avoid full-page fade-through on navigation — production dashboards use instant or near-instant route transitions with content-level animation instead (the sidebar/chrome never re-animates on navigation, only the content region).

**2.6.8 Non-negotiables**

- No black/blue/purple as theme colors, in any mode.
- No default/unstyled component library look — if using shadcn/ui as a base, every component must be retokenized to 2.6.3, not left with default styling.
- No sparse "portfolio site" layouts on data screens — density per 2.6.4 is a hard requirement, not a suggestion.
- No generic spinners — every loading state uses a skeleton matching the shape of the content it's replacing.
- No linear-only easing on anything that should feel tactile (panels, drawers, the trace viewer) — use spring physics.
- Interactions must stay smooth on a mid-range laptop — profile, don't just add motion everywhere.

---

## 3. System Architecture

```
                        ┌─────────────────────┐
                        │   Next.js Frontend   │  (Vercel)
                        │ Dashboard / Trace UI  │
                        └──────────┬───────────┘
                                   │ HTTPS/REST
                        ┌──────────▼───────────┐
                        │   FastAPI Backend      │  (EC2, Docker)
                        │  - Auth/rate limit     │
                        │  - Transaction API     │
                        │  - Webhook handler     │
                        │  - Investigation API   │
                        └───┬─────────────┬─────┘
                            │             │
                 ┌──────────▼───┐   ┌─────▼───────────┐
                 │  PostgreSQL   │   │  Redis + RQ     │
                 │  + pgvector   │   │  worker (async  │
                 │  (all state)  │   │  ingestion/     │
                 │               │   │  embeddings)    │
                 └───────────────┘   └─────────────────┘
                            │
                 ┌──────────▼───────────┐
                 │  Agent Orchestrator    │
                 │  (tool-calling loop)   │
                 │  → Groq API (LLM)      │
                 │  → timeout/retry/CB    │
                 └───────────────────────┘
```

All backend services run via a single `docker-compose.yml` on one EC2 instance. Frontend deployed independently on Vercel to avoid RAM contention on the free-tier box and to keep the demo alive beyond the 6-month AWS free-tier window.

---

## 4. Data Model

### 4.1 Core tables

- `merchants(id, name, created_at)`
- `transactions(id, merchant_id, idempotency_key UNIQUE, amount, currency, state, version, created_at, updated_at)`
- `transaction_events(id, transaction_id, event_type, payload JSONB, created_at)`
- `webhook_events(id, provider_event_id UNIQUE, transaction_id, payload JSONB, processed_at)` — `provider_event_id UNIQUE` is the dedup mechanism (FR-3)
- `incidents(id, transaction_id, description, status, created_at)`
- `incident_evidence(id, incident_id, tool_name, tool_args JSONB, tool_result JSONB, created_at)`
- `runbooks(id, title, content, embedding VECTOR(384))`
- `incident_embeddings(incident_id, embedding VECTOR(384))`
- `agent_traces(id, incident_id, step_number, tool_name, args, result, latency_ms, tokens_used)`
- `eval_cases(id, incident_id, ground_truth_root_cause, ground_truth_evidence)`

### 4.2 Key constraints (this is where the concurrency-correctness story lives)

- `transactions.idempotency_key` — `UNIQUE` constraint, upsert-on-conflict pattern. Duplicate request with same key returns the original result instead of creating a new transaction (FR-1).
- `transactions.version` — optimistic concurrency column; refund/capture operations use `UPDATE ... WHERE version = :expected_version`, retry on conflict (addresses the refund/capture race).
- `webhook_events.provider_event_id` — `UNIQUE` constraint for exactly-once processing (FR-3).

### 4.3 Embedding model

Sentence-Transformers (`all-MiniLM-L6-v2`, 384-dim) — local, free, no external API dependency for embeddings, keeps the Groq API reserved for agent reasoning only.

### 4.4 Synthetic failure classes to implement (this is your "realistic data" story)

1. Idempotency key collision under concurrent retry (client retries same request before first response returns)
2. Webhook retry storm (provider redelivers same event 5+ times)
3. Gateway timeout → ambiguous state (request sent, response lost, was it charged?)
4. Partial capture failure (multi-item order, one item's capture fails)
5. Settlement mismatch (captured amount ≠ settled amount, e.g. FX rounding)
6. Refund/capture race (refund initiated while capture still in flight)

---

## 5. API Contract (high-level)

| Method | Path                               | Purpose                                              |
| ------ | ---------------------------------- | ---------------------------------------------------- |
| POST   | `/v1/transactions`               | Create transaction (idempotency-key required header) |
| GET    | `/v1/transactions/{id}/timeline` | Full event timeline for a transaction                |
| POST   | `/v1/webhooks`                   | Receive gateway webhook (deduped by event ID)        |
| POST   | `/v1/incidents`                  | Create incident referencing a transaction            |
| POST   | `/v1/incidents/{id}/investigate` | Trigger agent investigation                          |
| GET    | `/v1/incidents/{id}/trace`       | Full agent trace for an investigation                |
| GET    | `/v1/search?q=`                  | Semantic search over incidents/runbooks              |
| POST   | `/v1/eval/run`                   | Run agent against labeled eval set, return metrics   |
| POST   | `/v1/auth/token`                 | Issue JWT                                            |

---

## 6. Agent Design

### 6.1 Orchestration loop (pseudocode)

```
function investigate(incident_id):
    context = load_incident(incident_id)
    trace = []
    for step in range(MAX_STEPS):
        response = call_llm_with_tools(context, available_tools, trace)
        if response.tool_call:
            result = execute_tool(response.tool_call)   # wrapped in reliability layer
            trace.append(record(response.tool_call, result))
            context.append(result)
        elif response.final_answer:
            validate_citations(response.final_answer, trace)  # every claim must map to a trace entry
            return response.final_answer, trace
    return low_confidence_fallback(trace)
```

### 6.2 Output schema

```json
{
  "root_cause": "string",
  "confidence": 0.0,
  "evidence": [{"claim": "string", "source_tool": "string", "source_ref": "string"}],
  "needs_more_info": ["string"] ,
  "degraded": false
}
```

### 6.3 Reliability wrapper around every LLM/tool call

Timeout → retry (exponential backoff, max 3) → circuit breaker (opens after 5 consecutive failures, half-open probe after cooldown) → fallback to raw-evidence response.

### 6.4 Scale-out notes (for interview discussion, not implemented)

Stateless API → LB + N instances. Vector search → partition by `merchant_id` once single-node pgvector can't hold the index in memory efficiently, or migrate to a managed vector store. Agent orchestrator → could be extracted into its own service behind a queue if investigation volume grows, decoupling it from the request/response cycle (return a job ID, poll or webhook for result).

---

## 7. Roadmap

Ordered by dependency, not calendar time (per your note — you're using an AI coding agent, so sequencing matters more than duration).

**Phase 0 — Scaffolding**
Repo structure, Docker Compose skeleton (Postgres+pgvector, Redis, FastAPI stub), Alembic setup, CI skeleton (lint + test on push).

**Phase 1 — Core payment domain**
Schema (4.1), idempotency handling (FR-1), state machine (FR-2), webhook dedup (FR-3). Write concurrency integration tests *first* against these — this is the highest-value section of the whole project, don't rush it.

**Phase 2 — Synthetic data generator**
Implement all 6 failure classes (4.4) as deliberate, reproducible scenarios (seeded, so eval set is stable).

**Phase 3 — Ingestion pipeline**
RQ worker: consumes new incidents/runbooks, generates embeddings, writes to pgvector. Prove it's actually async (don't block the API request).

**Phase 4 — Agent tools + orchestration loop**
Implement each tool (2.5.3) independently and test in isolation before wiring into the loop. Then build the loop (6.1) and reliability wrapper (6.3).

**Phase 5 — Evaluation harness**
Build the labeled eval set (50-100 cases minimum) using Phase 2's generator with known ground truth. Implement metrics: RCA accuracy, retrieval precision@k, hallucination rate (citation validity check), latency, cost/investigation.

**Phase 6 — API completion**
Auth (JWT), rate limiting, remaining endpoints, OpenAPI docs.

**Phase 7 — Frontend**
Next.js dashboard built to the visual direction in section 2.6 (Fresh Botanical: sage green / soft white / wood tones, no black/blue/purple). Screens: transaction timeline, incident list/detail, trace viewer with staggered step-reveal animation (this is your best demo screen — show the agent's actual decision path, and it's the most visually impressive place to invest animation effort), semantic search. Build the design system (colors, type scale, spacing, base components) *before* building screens, so the look stays consistent rather than assembled ad hoc.

**Phase 8 — Testing**
Unit tests for business logic, integration tests for concurrency paths (must actually fire concurrent requests), load test (Locust/k6) for the throughput/latency numbers you'll cite.

**Phase 9 — Deployment (optional for v1 — see section 11, Future Work)**
If pursued: Docker Compose on EC2 (backend), Vercel (frontend), Nginx + Let's Encrypt for HTTPS, CloudWatch basic metrics. A fully working, well-tested local/Docker-Compose system with a recorded demo is an acceptable substitute for a live deployment if deployment complexity threatens the timeline — a working system you can run and demo confidently beats a half-working live deployment.

**Phase 10 — Polish & documentation**
README with architecture diagram, this SRS linked, demo script, resume bullets (section 9), a short "design decisions" write-up (why hand-written agent loop, why RQ over Celery, etc.) — this write-up is what makes you sound rehearsed-but-honest in interviews rather than caught off guard.

---

## 8. Testing & Evaluation Plan

- **Unit tests**: state machine transitions, tool functions in isolation, circuit breaker logic.
- **Integration tests**: concurrent idempotency-key requests (fire N parallel requests, assert exactly one transaction created), concurrent refund/capture (assert no negative balance / no double-refund), webhook redelivery (assert exactly-once processing).
- **Load test**: Locust or k6 against non-agent endpoints; report req/s and p50/p95/p99 latency under concurrent idempotency-key collisions specifically (this ties directly back to FR-1 and gives you a defensible number).
- **Agent eval**: run against the labeled set from Phase 5; report accuracy, precision/recall on evidence retrieval, hallucination rate, average latency and cost per investigation.

---

## 9. Resume Bullet Templates (fill in real numbers after Phase 8/9 — never estimate)

**SDE framing:**

> Designed and built a payment-processing backend enforcing idempotent transaction handling, exactly-once webhook processing, and optimistic-concurrency-controlled settlement operations; validated correctness under concurrent load via integration and load testing ([X] req/s, [Y]ms p99).

**AI Engineer framing:**

> Built an agentic root-cause-analysis service using a hand-written tool-calling orchestration loop over structured transaction data and pgvector-based semantic retrieval, with a reliability layer (timeout/retry/circuit-breaker) around the LLM dependency and an evaluation harness measuring RCA accuracy, retrieval precision, and hallucination rate on a [N]-case labeled set.

---

## 10. Future Work (explicitly deprioritized for v1)

- **Live AWS deployment** — moved here per priority call: a fully working, tested, well-demoed local/Docker-Compose system takes precedence over a live deployment. Deploy only after Phases 1-8 are solid; if it adds too much friction, a clean local run + screen-recorded demo is an acceptable v1 deliverable.
- Multi-region / multi-node scaling (design already covered in 6.4, not implemented)
- Second non-payments dataset to show architecture generalizes
- CI/CD pipeline beyond basic lint+test

## 11. Open Questions / Assumptions to revisit

- Exact eval set size (recommend ≥50 for a credible number, more if time allows). Answer= 55
- Whether to add a second, non-payments dataset later to show the RCA architecture generalizes (future work, not required). Answer= yes, just for demoing
- Frontend auth flow for the demo (simple demo login vs. no-auth public read-only demo + authenticated admin panel) — recommend the latter so the public demo link is safe to share. Answer= public read-only demo + authenticated admin

---

*This document is the source of truth for the project. Update it as decisions change during implementation — an SRS that drifts from the actual system is worse than no SRS, since it undermines your ability to answer questions about it confidently.*