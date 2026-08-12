import json
import time
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import tools as agent_tools
from app.agent.llm_client import LLMClient
from app.models.agent import AgentTrace, IncidentEvidence
from app.models.incident import Incident

log = structlog.get_logger()

# Define the tools available to the LLM (OpenAI JSON Schema format)
AVAILABLE_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_transaction_db",
            "description": "Retrieve the full event timeline and state for a transaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string", "description": "UUID of the transaction"}
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Search raw gateway and app logs for a transaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"},
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g. 'error', 'timeout')",
                    },
                },
                "required": ["transaction_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_similar_incidents",
            "description": "Retrieve top similar past incidents using semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Description of the current incident",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_runbooks",
            "description": "Retrieve relevant runbook/SOP sections for an error.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Error or failure description"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_failure_signatures",
            "description": "Deterministic rule-based check against known failure patterns (retry storms, mismatches).",
            "parameters": {
                "type": "object",
                "properties": {"transaction_id": {"type": "string"}},
                "required": ["transaction_id"],
            },
        },
    },
]

# Output schema instructions
SYSTEM_PROMPT = """You are PInSight, an expert payment incident investigation agent.
You must investigate the given incident by using your tools.
When you are ready to provide a final analysis, you MUST output a raw JSON object (without markdown blocks) exactly matching this schema:
{
  "root_cause": "string explaining the cause",
  "confidence": 0.0 to 1.0,
  "evidence": [
      {"claim": "string", "source_tool": "string", "source_ref": "string"}
  ],
  "needs_more_info": ["list of questions if confidence < 0.8"],
  "degraded": false
}
Do not return a final answer until you have enough evidence. Ensure every piece of evidence cited comes directly from a tool call you made.
"""


def validate_citations(final_answer: dict[str, Any], trace: list[dict[str, Any]]) -> bool:
    """Validate that every claim in the final answer cites a tool that was actually executed."""
    if "evidence" not in final_answer:
        return True

    executed_tools = {step["tool_name"] for step in trace if step["tool_name"]}

    for item in final_answer["evidence"]:
        source = item.get("source_tool")
        if source not in executed_tools:
            log.warning("Invalid citation detected", source=source, executed=list(executed_tools))
            return False
    return True


def low_confidence_fallback(trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Fallback when max steps are exhausted or LLM fails entirely."""
    return {
        "root_cause": "Investigation aborted: maximum steps exceeded or LLM failure.",
        "confidence": 0.0,
        "evidence": [
            {
                "claim": f"Executed tool {t['tool_name']}",
                "source_tool": t["tool_name"],
                "source_ref": "trace",
            }
            for t in trace
            if t["tool_name"]
        ],
        "needs_more_info": ["Human review required. Agent failed to conclude within limits."],
        "degraded": True,
    }


async def investigate_incident(
    session: AsyncSession, incident_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """The main orchestration loop for an investigation."""
    incident = await session.get(Incident, uuid.UUID(incident_id))
    if not incident:
        raise ValueError("Incident not found")

    client = LLMClient()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Please investigate incident {incident_id}. Description: {incident.description}. Transaction ID: {incident.transaction_id}",
        },
    ]

    trace = []
    MAX_STEPS = 10
    hallucination_count = 0
    total_tokens_used = 0

    for step in range(MAX_STEPS):
        try:
            start_time = time.time()
            response = await client.chat_completion(messages, tools=AVAILABLE_TOOLS_SCHEMA)
            _ = int((time.time() - start_time) * 1000)

            # Track tokens
            step_tokens = response.get("usage", {}).get("total_tokens", 0)
            total_tokens_used += step_tokens

            message = response["choices"][0]["message"]
            messages.append(message)  # Add assistant message to history

            # Check for tool calls
            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    args = json.loads(tool_call["function"]["arguments"])

                    log.info("Executing tool", step=step, func=func_name, args=args)

                    # Execute tool
                    tool_start = time.time()
                    try:
                        func = getattr(agent_tools, func_name)
                        result = await func(session=session, **args)
                    except Exception as e:
                        result = {"error": str(e)}

                    tool_latency = int((time.time() - tool_start) * 1000)

                    # Add tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": func_name,
                            "content": json.dumps(result),
                        }
                    )

                    # Record in trace
                    trace.append(
                        {
                            "step_number": step,
                            "tool_name": func_name,
                            "args": args,
                            "result": result,
                            "latency_ms": tool_latency,
                            "tokens_used": step_tokens,  # Save the tokens used at this step
                        }
                    )
                continue

            # If no tool calls, this should be the final JSON answer
            content = message.get("content", "")
            try:
                final_answer = json.loads(content)

                # Gate: Validate citations
                if not validate_citations(final_answer, trace):
                    hallucination_count += 1
                    # Force correction
                    messages.append(
                        {
                            "role": "user",
                            "content": "You cited a source_tool that you never actually executed. Please correct your analysis and only cite tools you have run.",
                        }
                    )
                    continue

                return final_answer, trace, hallucination_count

            except json.JSONDecodeError:
                # LLM didn't return valid JSON
                messages.append(
                    {
                        "role": "user",
                        "content": "Your response was not valid JSON. Please return exactly the JSON structure requested.",
                    }
                )

        except Exception as e:
            log.error("LLM or orchestration error", error=str(e))
            break

    # If we exit the loop via max steps or exception, return fallback
    log.warning("Investigation hit max steps or exception, using fallback.")
    fallback = low_confidence_fallback(trace)
    return fallback, trace, hallucination_count


async def run_investigation_and_save(session: AsyncSession, incident_id: str) -> dict[str, Any]:
    """Run investigation and persist the trace and evidence."""
    final_answer, trace, hall_count = await investigate_incident(session, incident_id)

    # Save traces
    total_latency = 0
    total_tokens = 0
    for t in trace:
        at = AgentTrace(
            incident_id=uuid.UUID(incident_id),
            step_number=t["step_number"],
            tool_name=t["tool_name"],
            args=t["args"],
            result=t["result"],
            latency_ms=t["latency_ms"],
            tokens_used=t["tokens_used"],
        )
        total_latency += t["latency_ms"]
        total_tokens += t["tokens_used"]
        session.add(at)

    # Save evidence
    for ev in final_answer.get("evidence", []):
        ie = IncidentEvidence(
            incident_id=uuid.UUID(incident_id),
            tool_name=ev.get("source_tool", "unknown"),
            tool_result={"claim": ev.get("claim"), "source_ref": ev.get("source_ref", "")},
        )
        session.add(ie)

    await session.commit()

    # Inject metadata for the eval harness to pick up
    final_answer["_meta"] = {
        "hallucination_count": hall_count,
        "steps": len(trace),
        "latency_ms": total_latency,
        "tokens_used": total_tokens,
    }
    return final_answer
