
    names = [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
    idx = st.selectbox("Select Candidate", range(len(names)), format_func=lambda i: names[i])

    if st.button("🚀 Generate Career Suggestions", type="primary"):
        client = get_client()
        cand = st.session_state.candidates[idx]
        missing = cand.get("skill_gap", {}).get("missing_skills", [])
        with st.spinner("Building personalized growth plan..."):
            suggestions = GEN.generate_career_suggestions(client, st.session_state.model, cand["resume_data"], st.session_state.jd_data, missing)
        st.markdown(suggestions)

# ============================================================
# PAGE: REPORTS
# ============================================================
def page_reports():
    hero("Reports", "Export professional PDF and Excel reports for candidates.")

    if not require_candidates():
        return

    section_title("📊 Excel Report — All Candidates")
    if st.button("Generate Excel Report"):
        excel_bytes = REPORT.generate_excel_report(st.session_state.candidates)
        st.download_button(
            "⬇️ Download Excel Report", excel_bytes,
            file_name="candidate_ranking_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.write("")
    section_title("📄 PDF Report — Individual Candidate")
    names = [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
    idx = st.selectbox("Select Candidate", range(len(names)), format_func=lambda i: names[i])
    include_questions = st.checkbox("Include interview questions (if generated)", value=True)

    if st.button("Generate PDF Report"):
        cand = st.session_state.candidates[idx]
        interview_qs = st.session_state.interview_cache.get(names[idx]) if include_questions else None
        pdf_bytes = REPORT.generate_candidate_pdf(cand, interview_qs)
        st.download_button(
            "⬇️ Download PDF Report", pdf_bytes,
            file_name=f"{names[idx].replace(' ', '_')}_report.pdf",
            mime="application/pdf",
        )


# ============================================================
# PAGE: SETTINGS
# ============================================================
def page_settings():
    hero("Settings", "Configure your API key, model, and preferences.")

    section_title("🔑 OpenAI API Configuration")
    api_key_input = st.text_input(
        "OpenAI API Key",
        value="",
        type="password",
        placeholder="sk-••••••••••••••••  (leave blank to keep current key)",
        help="Your key is stored only in this session and never logged. "
             "The field is left blank on every load so the key is never shown in plain text — "
             "leave it blank to keep the key you already saved, or type a new one to replace it.",
    )
    if st.session_state.api_key:
        st.caption("🔒 A key is currently saved for this session (hidden).")
    else:
        st.caption("⚠️ No API key saved yet.")

    model = st.selectbox("LLM Model", ["gpt-4o-mini", "gpt-4.1", "gpt-4o", "gpt-4.1-mini"],
                          index=["gpt-4o-mini", "gpt-4.1", "gpt-4o", "gpt-4.1-mini"].index(st.session_state.model)
                          if st.session_state.model in ["gpt-4o-mini", "gpt-4.1", "gpt-4o", "gpt-4.1-mini"] else 0)
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, st.session_state.temperature, 0.1)

    if st.button("💾 Save Settings", type="primary"):
        if api_key_input.strip():
            st.session_state.api_key = api_key_input.strip()
        st.session_state.model = model
        st.session_state.temperature = temperature
        st.success("✅ Settings saved for this session.")

    st.write("")
    section_title("🎨 Appearance")
    st.caption("Theme follows your Streamlit app settings (top-right menu → Settings → Theme). "
               "You can toggle Light/Dark mode there.")

    st.write("")
    section_title("🗑️ Data Management")
    if st.button("Clear All Session Data (JD + Candidates + Chats)"):
        for key in ["jd_text", "jd_data", "candidates", "vector_store", "chat_history",
                    "hr_chat_history", "interview_cache"]:
            st.session_state[key] = [] if isinstance(st.session_state.get(key), list) else (
                {} if isinstance(st.session_state.get(key), dict) else (None if key == "vector_store" else "")
            )
        st.success("All session data cleared.")


# ============================================================
# ROUTER
# ============================================================
PAGE_FUNCS = {
    "Dashboard": page_dashboard,
    "Upload Job Description": page_upload_jd,
    "Upload Resumes": page_upload_resumes,
    "Candidate Ranking": page_candidate_ranking,
    "Resume Comparison": page_resume_comparison,
    "AI Resume Chat": page_ai_resume_chat,
    "Analytics Dashboard": page_analytics_dashboard,
    "Interview Questions": page_interview_questions,
    "AI HR Assistant": page_ai_hr_assistant,
    "Email Generator": page_email_generator,
    "JD Generator": page_jd_generator,
    "Career Suggestions": page_career_suggestions,
    "Reports": page_reports,
    "Settings": page_settings,
}

PAGE_FUNCS.get(page, page_dashboard)()
