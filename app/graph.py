"""A small multi-agent pipeline that plans, researches, drafts, and critiques."""

from __future__ import annotations

import json
import os
import re
from typing import TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph


class BriefState(TypedDict, total=False):
    topic: str
    audience: str
    notes: str
    questions: list[str]
    findings: list[str]
    draft: str
    critique: str
    revision: int
    final: str


PLAN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a research planner. Break the topic into exactly 4 sharp, "
            "non-overlapping questions that a decision-maker would need answered. "
            "Return a JSON array of strings and nothing else.",
        ),
        (
            "human",
            "Topic: {topic}\nAudience: {audience}\nSource notes:\n{notes}",
        ),
    ]
)

RESEARCH_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a research analyst. Answer the question in under 120 words. "
            "Use the supplied notes when relevant. Clearly label assumptions. "
            "Never invent statistics or citations.",
        ),
        (
            "human",
            "Topic: {topic}\nQuestion: {question}\nSource notes:\n{notes}",
        ),
    ]
)

WRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a briefing writer. Produce a markdown brief with these sections: "
            "## Executive summary, ## Key findings, ## Risks and open questions, "
            "## Recommended next steps. Be specific and under 500 words. "
            "If reviewer feedback is provided, address every point.",
        ),
        (
            "human",
            "Topic: {topic}\nAudience: {audience}\n\nResearch:\n{findings}\n\n"
            "Reviewer feedback:\n{critique}",
        ),
    ]
)

CRITIQUE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a demanding editor. Check the draft against the research for "
            "accuracy, specificity, and missing risks. Reply with APPROVED if it is "
            "ready. Otherwise list at most 3 concrete gaps, one per line. No preamble.",
        ),
        (
            "human",
            "Topic: {topic}\n\nResearch:\n{findings}\n\nDraft:\n{draft}",
        ),
    ]
)


def get_llm() -> ChatOpenAI:
    kwargs: dict = {"api_key": os.getenv("OPENAI_API_KEY")}
    if os.getenv("OPENAI_BASE_URL"):
        kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        **kwargs,
    )


def _run(prompt: ChatPromptTemplate, llm, payload: dict) -> str:
    return (prompt | llm | StrOutputParser()).invoke(payload).strip()


def parse_questions(raw: str, fallback_topic: str = "the topic") -> list[str]:
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None

    if isinstance(data, dict):
        data = data.get("questions")
    if not isinstance(data, list):
        return [f"What are the key considerations for {fallback_topic}?"]

    questions = [str(item).strip() for item in data if str(item).strip()]
    return questions[:4] or [f"What are the key considerations for {fallback_topic}?"]


def plan(state: BriefState, llm) -> dict:
    raw = _run(
        PLAN_PROMPT,
        llm,
        {
            "topic": state["topic"],
            "audience": state.get("audience", "general professional audience"),
            "notes": state.get("notes", "")[:3000],
        },
    )
    return {"questions": parse_questions(raw, state["topic"]), "revision": 0}


def research(state: BriefState, llm) -> dict:
    findings = []
    for question in state["questions"]:
        answer = _run(
            RESEARCH_PROMPT,
            llm,
            {
                "topic": state["topic"],
                "question": question,
                "notes": state.get("notes", "")[:5000],
            },
        )
        findings.append(f"### {question}\n{answer}")
    return {"findings": findings}


def write(state: BriefState, llm) -> dict:
    draft = _run(
        WRITE_PROMPT,
        llm,
        {
            "topic": state["topic"],
            "audience": state.get("audience", "general professional audience"),
            "findings": "\n\n".join(state.get("findings", [])),
            "critique": state.get("critique", ""),
        },
    )
    return {"draft": draft}


def critique(state: BriefState, llm) -> dict:
    feedback = _run(
        CRITIQUE_PROMPT,
        llm,
        {
            "topic": state["topic"],
            "findings": "\n\n".join(state.get("findings", [])),
            "draft": state.get("draft", ""),
        },
    )
    return {"critique": feedback, "revision": state.get("revision", 0) + 1}


def route(state: BriefState) -> str:
    approved = state.get("critique", "").strip().upper().startswith("APPROVED")
    if approved or state.get("revision", 0) >= 2:
        return "finalize"
    return "revise"


def finalize(state: BriefState) -> dict:
    return {"final": state.get("draft", "")}


def build_graph(llm=None):
    model = llm or get_llm()
    builder = StateGraph(BriefState)

    builder.add_node("plan", lambda state: plan(state, model))
    builder.add_node("research", lambda state: research(state, model))
    builder.add_node("write", lambda state: write(state, model))
    builder.add_node("critique", lambda state: critique(state, model))
    builder.add_node("finalize", finalize)

    builder.set_entry_point("plan")
    builder.add_edge("plan", "research")
    builder.add_edge("research", "write")
    builder.add_edge("write", "critique")
    builder.add_conditional_edges(
        "critique", route, {"revise": "write", "finalize": "finalize"}
    )
    builder.add_edge("finalize", END)
    return builder.compile()
