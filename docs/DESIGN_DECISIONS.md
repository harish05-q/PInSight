# Design Decisions

This document captures the "why" behind key architectural choices in PInSight — the reasoning that makes you sound rehearsed-but-honest in interviews rather than caught off guard.

---

## 1. Hand-Written Agent Loop vs. LangGraph / CrewAI

**Decision**: The agent orchestration loop is implemented by hand (~150 lines) rather than delegated to a framework like LangGraph or CrewAI.

**Why**: Frameworks like LangGraph impose opinionated control flow (directed graphs, channel-based state) that obscure the actual decision logic. For a portfolio project where the point is to demonstrate *understanding* of agent architecture, hiding the loop behind a framework defeats the purpose. The hand-written loop makes the control flow — tool selection, step budget, citation validation gate — explicit, debuggable, and fully visible to an interviewer reading the code. It also eliminates a heavyweight dependency for what is fundamentally a simple while-loop with a match statement.

**Trade-off acknowledged**: For a production multi-agent system with complex routing, a framework would reduce boilerplate. At this scale (single agent, ≤10 tools, ≤10 steps), the framework overhead exceeds the benefit.

---

## 2. RQ over Celery

**Decision**: Background task processing uses RQ (Redis Queue) rather than Celery.

**Why**: Celery is a production workhorse but brings significant operational complexity — a broker (RabbitMQ or Redis), result backend configuration, worker prefork/eventlet mode decisions, and ~15 configuration knobs before you process your first task. RQ is a single-file dependency that reuses the Redis instance we already need for rate limiting. For a system that processes one async job type (agent investigation), RQ's simplicity is a feature: the worker configuration is a single command (`rq worker default`), the job definition is a plain Python function, and there's no serialization format debate.

**Trade-off acknowledged**: RQ lacks Celery's multi-broker support, task chaining primitives, and battle-tested scaling to thousands of workers. None of those apply at this project's scale.

---

## 3. pgvector over Pinecone / Weaviate / Qdrant

**Decision**: Vector similarity search uses pgvector (a Postgres extension) rather than a dedicated vector database.

**Why**: Adding a dedicated vector DB introduces a new service to deploy, monitor, and pay for. pgvector lets us store embeddings in the same Postgres instance that holds our relational data, which means: (a) a single backup strategy, (b) no cross-service consistency issues, (c) JOINs between vector results and relational metadata in a single query. For a dataset of ~1,000 incidents and ~50 runbooks, pgvector's performance is more than sufficient.

**Trade-off acknowledged**: pgvector's approximate nearest neighbor (HNSW) index is slower than purpose-built vector DBs at million-scale. The SRS documents a partitioning plan (§6.4) for when this becomes relevant.

---

## 4. Citation Validation as a Hard Gate

**Decision**: The agent's `validate_citations` step is a hard gate — if the LLM's response cites evidence that wasn't returned by a tool call, the response is rejected and the agent re-generates.

**Why**: The SRS (§6.1) specifies that every claim in the RCA must be traceable to a specific tool call and result. A soft warning ("citation not found") would let hallucinated evidence reach the user, which in a payment investigation context could lead to incorrect root-cause attribution. By making it a gate, we guarantee that the final output is clean *by construction*. We track the hallucination rate by counting how often the gate fires (not whether the final output is clean, since it always is after the gate).

**Trade-off acknowledged**: The gate can cause the agent to burn extra steps (and tokens) re-generating. The step budget (max 10) prevents infinite loops.

---

## 5. Optimistic Concurrency Control (Version Column)

**Decision**: Transaction state transitions use a `version` column with optimistic locking rather than `SELECT ... FOR UPDATE` pessimistic locking.

**Why**: Pessimistic locking (`FOR UPDATE`) holds a row-level lock for the duration of the transaction, which under concurrent load creates lock contention and potential deadlocks. Optimistic concurrency — incrementing a version column and using `WHERE version = expected_version` in the UPDATE — fails fast with a 409 Conflict on contention rather than blocking. This is a better fit for payment state machines where concurrent mutations to the same transaction are genuinely conflicting (not queueable), and the correct response is to reject the loser immediately.

**Trade-off acknowledged**: Under extremely high write contention to the same row, optimistic locking produces more application-level retries. For payment transactions (low contention per row, high total throughput), this is the right trade-off.

---

## 6. Swappable LLM Client Wrapper

**Decision**: All Groq API calls go through a thin `LLMClient` wrapper class rather than calling `httpx` directly in the orchestrator.

**Why**: This decision paid for itself mid-project. The original plan specified `llama-3.3-70b-versatile` via Groq, but Groq deprecated that model in June 2026. Swapping to `openai/gpt-oss-120b` required changing exactly one constant in `llm_client.py` — zero changes to the orchestrator, tools, or tests. The wrapper also centralizes timeout configuration, retry logic, token counting, and the circuit breaker integration in a single file, rather than scattering HTTP call details across the orchestrator. If the project later needs to support multiple LLM providers (e.g., fallback from Groq to a local model), the swap surface is one class, not a codebase-wide refactor.

**Trade-off acknowledged**: The wrapper adds one level of indirection. For a single-provider system this is minimal overhead; the decoupling benefit far outweighs it.
