"""Streamlit front end for BriefForge. Run alongside the FastAPI server."""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_URL = os.getenv("BRIEFFORGE_API_URL", "http://127.0.0.1:8002")

st.set_page_config(page_title="BriefForge", layout="wide")
st.title("BriefForge")
st.caption("A planner, researcher, writer, and editor turn a topic into a brief.")

with st.sidebar:
    try:
        health = httpx.get(f"{API_URL}/health", timeout=5).json()
        st.metric("API", "online")
        st.caption(health.get("pipeline", ""))
    except Exception:
        st.metric("API", "offline")
        st.caption("Start the API: uvicorn app.main:app --port 8002")
    st.divider()
    st.caption(f"Backend: {API_URL}")

with st.form("brief_form"):
    topic = st.text_input(
        "Topic", placeholder="e.g. Adopting on-device AI for a mobile banking app"
    )
    audience = st.text_input("Audience", value="VP of Engineering")
    notes = st.text_area(
        "Source notes (optional)",
        placeholder="Paste constraints, metrics, or context the agents must respect.",
        height=140,
    )
    submitted = st.form_submit_button("Generate brief", type="primary")

if submitted:
    if len(topic.strip()) < 3:
        st.warning("Enter a topic of at least 3 characters.")
    else:
        with st.spinner("Planning, researching, drafting, editing..."):
            try:
                response = httpx.post(
                    f"{API_URL}/brief",
                    json={
                        "topic": topic.strip(),
                        "audience": audience.strip() or "general professional audience",
                        "notes": notes,
                    },
                    timeout=300,
                )
                response.raise_for_status()
                st.session_state.brief = response.json()
            except httpx.HTTPStatusError as error:
                detail = error.response.json().get("detail", str(error))
                st.error(detail)
            except Exception as error:
                st.error(f"Request failed: {error}")

result = st.session_state.get("brief")
if result:
    st.divider()
    metrics = st.columns(3)
    metrics[0].metric("Questions", len(result.get("questions", [])))
    metrics[1].metric("Revisions", result.get("revisions", 0))
    metrics[2].metric("Status", "approved" if result.get("critique", "").upper().startswith("APPROVED") else "edited")

    brief_tab, plan_tab, review_tab = st.tabs(["Brief", "Research plan", "Editor notes"])
    with brief_tab:
        st.markdown(result.get("brief", ""))
        st.download_button(
            "Download markdown",
            data=result.get("brief", ""),
            file_name="brief.md",
            mime="text/markdown",
        )
    with plan_tab:
        for number, question_text in enumerate(result.get("questions", []), start=1):
            st.markdown(f"{number}. {question_text}")
    with review_tab:
        critique = result.get("critique", "")
        if critique.upper().startswith("APPROVED"):
            st.success("The editor approved this draft.")
        else:
            st.markdown(critique or "No notes.")
