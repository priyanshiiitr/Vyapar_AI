from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.agent.tools import TOOL_SPECS, execute_tool
from app.config import get_settings
from app.models import ChatMessage, Conversation
from app.services.observability import structured_log, trace_span

SYSTEM_PROMPT = """You are Paytm Vyapar AI, an autonomous teammate for Indian SME receivables and collections.

Core principle:
- YOU write language and select tools.
- THE LEDGER establishes payment facts. Never invent amounts, fees, deadlines, or payment links.
- Never mark invoices paid and never change transaction amounts. Only tools that draft/remind/promise/schedule/escalate are allowed for actions.
- For reminders, prefer create_reminder_draft so the merchant can approve before any sandbox send.
- Use Indian context (INR, Hinglish when asked). Be concise and action-oriented.
- When analyzing receivables, call tools first; then explain results clearly.
- Do not reveal chain-of-thought. Summarize outcomes and next actions.
"""


def _ensure_conversation(db: Session, merchant_id: str, conversation_id: int | None) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv and conv.merchant_id == merchant_id:
            return conv
    conv = Conversation(merchant_id=merchant_id, title="Vyapar AI Chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _history_for_model(db: Session, conversation_id: int) -> list[dict[str, Any]]:
    from sqlalchemy import select

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    rows = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.asc())
        )
    )
    for row in rows:
        if row.role == "user":
            messages.append({"role": "user", "content": row.content or ""})
        elif row.role == "assistant" and row.tool_name is None:
            messages.append({"role": "assistant", "content": row.content or ""})
        elif row.role == "assistant" and row.tool_call_id:
            messages.append(
                {
                    "role": "assistant",
                    "content": row.content,
                    "tool_calls": [
                        {
                            "id": row.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": row.tool_name,
                                "arguments": row.tool_args_json or "{}",
                            },
                        }
                    ],
                }
            )
        elif row.role == "tool":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": row.tool_call_id,
                    "content": row.tool_result_json or row.content or "{}",
                }
            )
    return messages


def run_agent(
    db: Session,
    *,
    merchant_id: str,
    user_message: str,
    conversation_id: int | None = None,
    max_iterations: int = 6,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.sarvam_configured:
        return {
            "ok": False,
            "error": "SARVAM_API_KEY is not configured. Add it to backend/.env. Ledger features still work.",
            "tool_calls": [],
        }

    conv = _ensure_conversation(db, merchant_id, conversation_id)
    user_row = ChatMessage(conversation_id=conv.id, role="user", content=user_message)
    db.add(user_row)
    db.commit()

    tool_trace: list[dict[str, Any]] = []

    with trace_span(
        "sarvam_agent_turn",
        {"merchant_id": merchant_id, "conversation_id": conv.id},
    ) as span:
        try:
            from sarvamai import SarvamAI
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sarvamai SDK import failed: {exc}", "tool_calls": []}

        client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
        messages = _history_for_model(db, conv.id)

        final_text = ""
        for iteration in range(max_iterations):
            try:
                response = client.chat.completions(
                    model=settings.SARVAM_CHAT_MODEL,
                    messages=messages,
                    tools=TOOL_SPECS,
                    tool_choice="auto",
                    max_tokens=settings.SARVAM_MAX_TOKENS,
                )
            except Exception as exc:  # noqa: BLE001
                structured_log("sarvam_error", error=str(exc), iteration=iteration)
                err = str(exc)
                if "429" in err or "rate" in err.lower():
                    msg = "Sarvam rate limit reached. Try again shortly. Ledger features remain available."
                elif "timeout" in err.lower():
                    msg = "Sarvam request timed out. Try again. Ledger features remain available."
                else:
                    msg = f"Sarvam AI unavailable: {err}"
                assistant = ChatMessage(conversation_id=conv.id, role="assistant", content=msg)
                db.add(assistant)
                db.commit()
                return {
                    "ok": False,
                    "error": msg,
                    "conversation_id": conv.id,
                    "tool_calls": tool_trace,
                    "assistant_message": msg,
                }

            choice = response.choices[0]
            message = choice.message
            finish = getattr(choice, "finish_reason", None) or getattr(message, "finish_reason", None)
            tool_calls = getattr(message, "tool_calls", None) or []

            if tool_calls:
                # Persist assistant tool-call message(s)
                serialized_calls = []
                for tc in tool_calls:
                    fn = tc.function
                    serialized_calls.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": fn.name, "arguments": fn.arguments},
                        }
                    )
                    db.add(
                        ChatMessage(
                            conversation_id=conv.id,
                            role="assistant",
                            content=None,
                            tool_name=fn.name,
                            tool_call_id=tc.id,
                            tool_args_json=fn.arguments,
                            tool_status="running",
                        )
                    )
                db.commit()

                messages.append({"role": "assistant", "tool_calls": serialized_calls, "content": None})

                for tc in tool_calls:
                    fn = tc.function
                    span["events"].append({"tool": fn.name, "args": fn.arguments})
                    result = execute_tool(db, merchant_id, fn.name, fn.arguments)
                    tool_trace.append(
                        {
                            "id": tc.id,
                            "name": fn.name,
                            "arguments": fn.arguments,
                            "status": "completed" if result.get("ok") else "failed",
                            "result": result,
                        }
                    )
                    result_json = json.dumps(result, default=str)
                    db.add(
                        ChatMessage(
                            conversation_id=conv.id,
                            role="tool",
                            content=result_json,
                            tool_name=fn.name,
                            tool_call_id=tc.id,
                            tool_result_json=result_json,
                            tool_status="completed" if result.get("ok") else "failed",
                        )
                    )
                    db.commit()
                    messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": result_json}
                    )
                continue

            final_text = message.content or ""
            # Strip accidental chain-of-thought markers if present
            for marker in ("</think>", "<think>"):
                if marker in final_text:
                    final_text = final_text.split(marker)[-1].strip()
            break
        else:
            final_text = "I reached the tool-call limit. Please ask me to continue with a more specific request."

        assistant = ChatMessage(conversation_id=conv.id, role="assistant", content=final_text)
        db.add(assistant)
        db.commit()
        span["events"].append({"final": True, "tools": len(tool_trace)})

    return {
        "ok": True,
        "conversation_id": conv.id,
        "assistant_message": final_text,
        "tool_calls": tool_trace,
        "finish_reason": finish if "finish" in dir() else None,
    }
