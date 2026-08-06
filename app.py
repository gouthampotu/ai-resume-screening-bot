"""
app.py
AI-Powered HR Resume Screening & Interview Assistant
Main Streamlit application entry point.
"""

import os
import json
import streamlit as st""
app.py
AI-Powered HR Resume Screening & Interview Assistant
Main Streamlit application entry point.
"""

import os
import json
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from utils import parser as P
from utils import llm_utils as LLM
from utils import ats as ATS
from utils import chatbot as CHAT
from utils import analytics as AN
from utils import report_generator as REPORT
from utils import generators as GEN

load_dotenv()

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI HR Resume Screening & Interview Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
CSS_PATH = os.path.join(os.path.dirname(__file__), "assets", "css", "style.css")
if os.path.exists(CSS_PATH):
    with open(CSS_PATH) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
def init_state():
    defaults = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0.4,
        "jd_text": "",
        "jd_data": {},
        "candidates": [],          # list of candidate dicts
        "vector_store": None,
        "chat_history": [],
        "hr_chat_history": [],
        "current_page": "Dashboard",
        "interview_cache": {},     # candidate_name -> questions dict
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def get_client():
    if not st.session_state.api_key:
        return None
    return LLM.get_client(st.session_state.api_key)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown(
        "<div style='text-align:center; padding: 10px 0 20px 0;'>"
        "<span style='font-size:38px;'>🧠</span><br>"
        "<span style='font-size:19px; font-weight:800;'>HR AI Screening</span><br>"
        "<span style='font-size:12px; opacity:0.7;'>Resume &amp; Interview Assistant</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    PAGES = [
        "Dashboard",
        "Upload Job Description",
        "Upload Resumes",
        "Candidate Ranking",
        "Resume Comparison",
        "AI Resume Chat",
        "Analytics Dashboard",
        "Interview Questions",
        "AI HR Assistant",
        "Email Generator",
        "JD Generator",
        "Career Suggestions",
        "Reports",
        "Settings",
    ]
    ICONS = ["🏠", "📄", "📥", "🏆", "⚖️", "💬", "📊", "🎯", "🤖", "✉️", "📝", "🚀", "📑", "⚙️"]

    page = st.radio(
        "Navigate",
        PAGES,
        format_func=lambda p: f"{ICONS[PAGES.index(p)]}  {p}",
        label_visibility="collapsed",
    )

    st.markdown("---")
    n_candidates = len(st.session_state.candidates)
    jd_status = "✅ Loaded" if st.session_state.jd_data else "❌ Not uploaded"
    st.markdown(
        f"<div style='font-size:13px; line-height:1.9;'>"
        f"<b>JD Status:</b> {jd_status}<br>"
        f"<b>Candidates:</b> {n_candidates}<br>"
        f"<b>Model:</b> {st.session_state.model}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    if not st.session_state.api_key:
        st.warning("⚠️ Add your OpenAI API key in Settings to enable AI features.")

# ============================================================
# SHARED UI HELPERS
# ============================================================
def hero(title: str, subtitle: str):
    st.markdown(
        f"<div class='hr-hero'><h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def section_title(text: str):
    st.markdown(f"<div class='section-title'>{text}</div>", unsafe_allow_html=True)


def metric_card(col, label, value):
    col.markdown(
        f"<div class='metric-card'><div class='value'>{value}</div>"
        f"<div class='label'>{label}</div></div>",
        unsafe_allow_html=True,
    )


def recommendation_badge(rec: str) -> str:
    mapping = {
        "Highly Recommended": "badge-gold",
        "Recommended": "badge-green",
        "Consider After Interview": "badge-blue",
        "Hold": "badge-yellow",
        "Reject": "badge-red",
    }
    css_class = mapping.get(rec, "badge-blue")
    return f"<span class='badge {css_class}'>{rec}</span>"


def require_api_key() -> bool:
    if not st.session_state.api_key:
        st.error("🔑 Please add your OpenAI API key in **Settings** to use this feature.")
        return False
    return True


def require_jd() -> bool:
    if not st.session_state.jd_data:
        st.warning("📄 Please upload/parse a Job Description first (see **Upload Job Description**).")
        return False
    return True


def require_candidates() -> bool:
    if not st.session_state.candidates:
        st.warning("📥 Please upload and process resumes first (see **Upload Resumes**).")
        return False
    return True


def process_single_resume(client, uploaded_file, jd_data: dict):
    """Full pipeline: extract -> parse -> score -> gap analysis -> fraud check."""
    raw_text = P.extract_text(uploaded_file)
    if raw_text.startswith("[ERROR") or raw_text.startswith("[Unsupported"):
        return {"error": raw_text, "file_name": uploaded_file.name}

    quick = P.regex_quick_extract(raw_text)
    resume_data = P.llm_extract_resume(client, st.session_state.model, raw_text)

    if "error" in resume_data:
        return {"error": resume_data["error"], "file_name": uploaded_file.name}

    # Fill gaps from regex extraction if LLM missed them
    for field in ["email", "phone", "linkedin", "github"]:
        if not resume_data.get(field) or resume_data.get(field) in ("", "Not found"):
            resume_data[field] = quick.get(field, "Not found")
    if not resume_data.get("name"):
        resume_data["name"] = uploaded_file.name.rsplit(".", 1)[0]

    ats_result = ATS.compute_ats_score(client, st.session_state.model, jd_data, resume_data)
    gap = ATS.skill_gap_analysis(jd_data.get("required_skills", []), resume_data.get("skills", []))
    flags = ATS.detect_red_flags(raw_text, resume_data)

    return {
        "file_name": uploaded_file.name,
        "raw_text": raw_text,
        "resume_data": resume_data,
        "ats": ats_result,
        "skill_gap": gap,
        "red_flags": flags,
    }

# ============================================================
# PAGE: DASHBOARD
# ============================================================
def page_dashboard():
    hero("AI-Powered HR Resume Screening & Interview Assistant",
         "Screen, score, rank, and interview candidates faster with Generative AI.")

    cols = st.columns(4)
    n_candidates = len(st.session_state.candidates)
    avg_score = 0
    top_candidate = "—"
    if st.session_state.candidates:
        scores = [c["ats"].get("overall_ats_score", 0) for c in st.session_state.candidates if "ats" in c and "error" not in c.get("ats", {})]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        if scores:
            best = max(st.session_state.candidates, key=lambda c: c["ats"].get("overall_ats_score", 0))
            top_candidate = best["resume_data"].get("name", "Unknown")

    metric_card(cols[0], "Job Description", "Loaded" if st.session_state.jd_data else "Missing")
    metric_card(cols[1], "Candidates Screened", n_candidates)
    metric_card(cols[2], "Average ATS Score", f"{avg_score}%")
    metric_card(cols[3], "Top Candidate", top_candidate)

    st.write("")
    section_title("Quick Start Guide")
    steps = [
        ("1️⃣", "Upload Job Description", "Paste or upload the JD — AI extracts required skills, experience & keywords."),
        ("2️⃣", "Upload Resumes", "Bulk upload candidate resumes in PDF, DOCX, or TXT."),
        ("3️⃣", "Review Ranking", "See ATS scores, skill gaps, and hire recommendations instantly."),
        ("4️⃣", "Chat & Interview", "Ask the AI assistant questions and auto-generate interview questions."),
    ]
    cols2 = st.columns(4)
    for col, (icon, title, desc) in zip(cols2, steps):
        col.markdown(
            f"<div class='candidate-card'><div style='font-size:26px;'>{icon}</div>"
            f"<b>{title}</b><div style='font-size:13px; color:#64748B; margin-top:4px;'>{desc}</div></div>",
            unsafe_allow_html=True,
        )

    if st.session_state.candidates:
        st.write("")
        section_title("Recent Candidates")
        df = AN.candidates_to_dataframe(st.session_state.candidates)
        st.dataframe(
            df.sort_values("Overall ATS", ascending=False),
            use_container_width=True, hide_index=True,
        )


# ============================================================
# PAGE: UPLOAD JOB DESCRIPTION
# ============================================================
def page_upload_jd():
    hero("Upload Job Description", "Provide the JD so AI can extract requirements and score candidates against it.")

    if not require_api_key():
        return

    tab1, tab2 = st.tabs(["📁 Upload File", "✍️ Paste Text"])
    jd_text_input = ""

    with tab1:
        jd_file = st.file_uploader("Upload JD (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"], key="jd_file")
        if jd_file:
            jd_text_input = P.extract_text(jd_file)
            st.text_area("Extracted Text Preview", jd_text_input, height=200, key="jd_preview_file")

    with tab2:
        pasted = st.text_area("Paste Job Description here", height=250, key="jd_paste_area")
        if pasted.strip():
            jd_text_input = pasted

    if st.button("🔍 Analyze Job Description", type="primary", use_container_width=True):
        if not jd_text_input.strip():
            st.error("Please upload a file or paste JD text first.")
        else:
            with st.spinner("Analyzing job description with AI..."):
                client = get_client()
                jd_data = P.llm_extract_jd(client, st.session_state.model, jd_text_input)
                if "error" in jd_data:
                    st.error(f"Extraction failed: {jd_data['error']}")
                else:
                    st.session_state.jd_text = jd_text_input
                    st.session_state.jd_data = jd_data
                    st.session_state.vector_store = None  # reset, will rebuild on demand
                    st.success("✅ Job Description analyzed successfully!")

    if st.session_state.jd_data:
        st.write("")
        section_title("Extracted Job Requirements")
        jd = st.session_state.jd_data
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Job Title:** {jd.get('job_title', 'N/A')}")
            st.markdown(f"**Minimum Experience:** {jd.get('min_experience_years', 'N/A')} years")
            st.markdown("**Required Skills:**")
            st.write(", ".join(jd.get("required_skills", [])) or "N/A")
            st.markdown("**Preferred Skills:**")
            st.write(", ".join(jd.get("preferred_skills", [])) or "N/A")
        with c2:
            st.markdown("**Education Requirements:**")
            st.write(", ".join(jd.get("education_requirements", [])) or "N/A")
            st.markdown("**Certifications Required:**")
            st.write(", ".join(jd.get("certifications_required", [])) or "N/A")
            st.markdown("**Keywords:**")
            st.write(", ".join(jd.get("keywords", [])) or "N/A")

        st.info(f"**AI Summary:** {jd.get('summary', 'N/A')}")

# ============================================================
# PAGE: UPLOAD RESUMES
# ============================================================
def page_upload_resumes():
    hero("Upload Resumes", "Bulk upload candidate resumes for automatic parsing and ATS scoring.")

    if not require_api_key():
        return
    if not require_jd():
        return

    files = st.file_uploader(
        "Upload one or more resumes (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"], accept_multiple_files=True, key="resume_files",
    )

    col1, col2 = st.columns([3, 1])
    with col2:
        clear = st.button("🗑️ Clear All Candidates", use_container_width=True)
        if clear:
            st.session_state.candidates = []
            st.session_state.vector_store = None
            st.session_state.interview_cache = {}
            st.success("Cleared all candidates.")

    with col1:
        process = st.button("🚀 Process & Score Resumes", type="primary", use_container_width=True)

    if process:
        if not files:
            st.error("Please upload at least one resume.")
        else:
            client = get_client()
            existing_names = {c["file_name"] for c in st.session_state.candidates}
            progress = st.progress(0.0, text="Starting...")
            new_candidates = []
            for i, f in enumerate(files):
                if f.name in existing_names:
                    progress.progress((i + 1) / len(files), text=f"Skipping duplicate: {f.name}")
                    continue
                progress.progress((i + 1) / len(files), text=f"Processing {f.name}...")
                result = process_single_resume(client, f, st.session_state.jd_data)
                new_candidates.append(result)
            progress.empty()

            success_count = 0
            for r in new_candidates:
                if "error" in r:
                    st.error(f"❌ {r['file_name']}: {r['error']}")
                else:
                    st.session_state.candidates.append(r)
                    success_count += 1

            st.session_state.vector_store = None  # invalidate cache so chatbot rebuilds
            if success_count:
                st.success(f"✅ Successfully processed {success_count} resume(s)!")

    if st.session_state.candidates:
        st.write("")
        section_title(f"Processed Candidates ({len(st.session_state.candidates)})")
        for c in st.session_state.candidates:
            resume = c["resume_data"]
            ats = c.get("ats", {})
            with st.expander(f"📄 {resume.get('name', c['file_name'])} — ATS: {ats.get('overall_ats_score', 'N/A')}%"):
                colA, colB = st.columns([2, 1])
                with colA:
                    st.markdown(f"**Email:** {resume.get('email', 'N/A')}  |  **Phone:** {resume.get('phone', 'N/A')}")
                    st.markdown(f"**Skills:** {', '.join(resume.get('skills', [])) or 'N/A'}")
                    st.markdown(f"**Experience:** {resume.get('total_experience_years', 'N/A')} years")
                    st.markdown(f"**Summary:** {resume.get('summary', 'N/A')}")
                with colB:
                    st.markdown(recommendation_badge(ats.get("hire_recommendation", "N/A")), unsafe_allow_html=True)
                    st.markdown("**Red Flags:**")
                    for flag in c.get("red_flags", []):
                        st.caption(flag)


# ============================================================
# PAGE: CANDIDATE RANKING
# ============================================================
def page_candidate_ranking():
    hero("Candidate Ranking", "Leaderboard of all screened candidates, ranked by overall ATS score.")

    if not require_candidates():
        return

    ranked = sorted(
        st.session_state.candidates,
        key=lambda c: c["ats"].get("overall_ats_score", 0),
        reverse=True,
    )

    medal = ["🥇", "🥈", "🥉"]
    for i, c in enumerate(ranked):
        resume = c["resume_data"]
        ats = c["ats"]
        badge_icon = medal[i] if i < 3 else f"#{i+1}"
        with st.container():
            st.markdown("<div class='candidate-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([0.6, 3, 1.5, 1.5])
            c1.markdown(f"<div style='font-size:26px; text-align:center;'>{badge_icon}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{resume.get('name', 'Unknown')}**")
                st.caption(f"{resume.get('email', 'N/A')} · {resume.get('total_experience_years', 'N/A')} yrs experience")
            with c3:
                st.metric("ATS Score", f"{ats.get('overall_ats_score', 0)}%")
            with c4:
                st.markdown(recommendation_badge(ats.get("hire_recommendation", "N/A")), unsafe_allow_html=True)
            st.progress(min(int(ats.get("overall_ats_score", 0)), 100) / 100)
            st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    section_title("Detailed Score Table")
    df = AN.candidates_to_dataframe(st.session_state.candidates)
    st.dataframe(df.sort_values("Overall ATS", ascending=False), use_container_width=True, hide_index=True)

# ============================================================
# PAGE: RESUME COMPARISON
# ============================================================
def page_resume_comparison():
    hero("Resume Comparison", "Compare two candidates side by side across every dimension.")

    if not require_candidates():
        return
    if len(st.session_state.candidates) < 2:
        st.info("Upload at least 2 resumes to enable comparison.")
        return

    names = [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
    c1, c2 = st.columns(2)
    with c1:
        idx_a = st.selectbox("Candidate A", range(len(names)), format_func=lambda i: names[i], key="cmp_a")
    with c2:
        default_b = 1 if len(names) > 1 else 0
        idx_b = st.selectbox("Candidate B", range(len(names)), format_func=lambda i: names[i], index=default_b, key="cmp_b")

    if idx_a == idx_b:
        st.warning("Please select two different candidates.")
        return

    A = st.session_state.candidates[idx_a]
    B = st.session_state.candidates[idx_b]

    rows = [
        ("Overall ATS Score", A["ats"].get("overall_ats_score", 0), B["ats"].get("overall_ats_score", 0)),
        ("Skills Match", A["ats"].get("skills_match", {}).get("score", 0), B["ats"].get("skills_match", {}).get("score", 0)),
        ("Experience Match", A["ats"].get("experience_match", {}).get("score", 0), B["ats"].get("experience_match", {}).get("score", 0)),
        ("Education Match", A["ats"].get("education_match", {}).get("score", 0), B["ats"].get("education_match", {}).get("score", 0)),
        ("Projects Match", A["ats"].get("projects_match", {}).get("score", 0), B["ats"].get("projects_match", {}).get("score", 0)),
        ("Experience (yrs)", A["resume_data"].get("total_experience_years", 0), B["resume_data"].get("total_experience_years", 0)),
        ("Recommendation", A["ats"].get("hire_recommendation", "N/A"), B["ats"].get("hire_recommendation", "N/A")),
    ]
    df = pd.DataFrame(rows, columns=["Metric", names[idx_a], names[idx_b]])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.write("")
    colA, colB = st.columns(2)
    for col, cand in [(colA, A), (colB, B)]:
        with col:
            r = cand["resume_data"]
            st.markdown(f"### {r.get('name', 'Unknown')}")
            st.markdown(recommendation_badge(cand["ats"].get("hire_recommendation", "N/A")), unsafe_allow_html=True)
            st.markdown(f"**Skills:** {', '.join(r.get('skills', [])) or 'N/A'}")
            st.markdown("**Matched Skills:** " + (", ".join(cand["skill_gap"].get("matched_skills", [])) or "None"))
            st.markdown("**Missing Skills:** " + (", ".join(cand["skill_gap"].get("missing_skills", [])) or "None"))
            st.markdown(f"**Strengths:**")
            for s in cand["ats"].get("strengths", []):
                st.caption(f"✓ {s}")
            st.markdown(f"**Weaknesses:**")
            for w in cand["ats"].get("weaknesses", []):
                st.caption(f"✗ {w}")

    st.write("")
    if require_api_key():
        if st.button("🤖 AI Recommendation: Who should we hire?", type="primary"):
            client = get_client()
            with st.spinner("Comparing candidates..."):
                prompt = f"""Compare these two candidates for the role and recommend who is the better fit, with reasoning.

Candidate A ({names[idx_a]}): {json.dumps(A['ats'])[:2000]}
Candidate B ({names[idx_b]}): {json.dumps(B['ats'])[:2000]}
"""
                answer = LLM.chat(client, st.session_state.model,
                                   "You are a senior HR hiring manager giving a clear, decisive recommendation.",
                                   prompt, temperature=0.4)
            st.success(answer)


# ============================================================
# PAGE: AI RESUME CHAT (RAG)
# ============================================================
def page_ai_resume_chat():
    hero("AI Resume Chat", "Ask anything about uploaded resumes — answers are grounded strictly in the documents (RAG).")

    if not require_api_key():
        return
    if not require_candidates():
        return

    client = get_client()

    if st.session_state.vector_store is None:
        with st.spinner("Indexing resumes for retrieval..."):
            docs = [{"text": c["raw_text"], "source": c["resume_data"].get("name", c["file_name"]), "type": "resume"}
                    for c in st.session_state.candidates]
            if st.session_state.jd_text:
                docs.append({"text": st.session_state.jd_text, "source": "Job Description", "type": "jd"})
            st.session_state.vector_store = CHAT.build_vector_store(st.session_state.api_key, docs)

    st.caption("💡 Try: \"Summarize this resume\", \"Does the candidate know Python?\", \"Why should we hire them?\"")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask about a candidate's resume...")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = CHAT.query_chatbot(client, st.session_state.model, st.session_state.vector_store, question)
                st.markdown(result["answer"])
                if result["sources"]:
                    st.caption("📎 Sources: " + ", ".join(result["sources"]))
        st.session_state.chat_history.append({"role": "assistant", "content": result["answer"]})


# ============================================================
# PAGE: ANALYTICS DASHBOARD
# ============================================================
def page_analytics_dashboard():
    hero("Analytics Dashboard", "Visual insights across all screened candidates.")

    if not require_candidates():
        return

    df = AN.candidates_to_dataframe(st.session_state.candidates)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(AN.avg_ats_gauge(df), use_container_width=True)
    with c2:
        fig = AN.recommendation_pie(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    st.plotly_chart(AN.ranking_bar_chart(df), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig = AN.top_skills_chart(st.session_state.candidates)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    with c4:
        st.plotly_chart(AN.experience_distribution_chart(df), use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        fig = AN.education_distribution_chart(st.session_state.candidates)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No education data available.")
    with c6:
        fig = AN.certification_distribution_chart(st.session_state.candidates)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No certification data available.")

# ============================================================
# PAGE: INTERVIEW QUESTIONS
# ============================================================
def page_interview_questions():
    hero("Interview Question Generator", "Auto-generate tailored technical, behavioral, HR, project, and coding questions.")

    if not require_api_key():
        return
    if not require_candidates():
        return

    names = [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
    idx = st.selectbox("Select Candidate", range(len(names)), format_func=lambda i: names[i])
    difficulty = st.select_slider("Difficulty", options=["Easy", "Medium", "Hard"], value="Medium")

    if st.button("🎯 Generate Interview Questions", type="primary"):
        client = get_client()
        cand = st.session_state.candidates[idx]
        with st.spinner("Generating tailored questions..."):
            qs = GEN.generate_interview_questions(client, st.session_state.model, cand["resume_data"], st.session_state.jd_data, difficulty)
        if "error" in qs:
            st.error(qs["error"])
        else:
            st.session_state.interview_cache[names[idx]] = qs

    qs = st.session_state.interview_cache.get(names[idx])
    if qs:
        tabs = st.tabs(["🧠 Technical", "🤝 Behavioral", "🏢 HR", "🛠️ Project", "💻 Coding"])
        keys = ["technical_questions", "behavioral_questions", "hr_questions", "project_questions", "coding_questions"]
        for tab, key in zip(tabs, keys):
            with tab:
                for i, q in enumerate(qs.get(key, []), 1):
                    st.markdown(f"**{i}.** {q}")


# ============================================================
# PAGE: AI HR ASSISTANT
# ============================================================
def page_ai_hr_assistant():
    hero("AI HR Assistant", "Ask high-level hiring questions across all candidates — best fit, comparisons, skill search, and more.")

    if not require_api_key():
        return
    if not require_candidates():
        return

    client = get_client()

    all_context = []
    for c in st.session_state.candidates:
        r, a = c["resume_data"], c["ats"]
        all_context.append({
            "name": r.get("name"), "skills": r.get("skills"),
            "experience_years": r.get("total_experience_years"),
            "education": r.get("education"), "overall_ats": a.get("overall_ats_score"),
            "recommendation": a.get("hire_recommendation"), "strengths": a.get("strengths"),
            "weaknesses": a.get("weaknesses"),
        })

    st.caption("💡 Try: \"Who is the best candidate?\", \"Who has AWS experience?\", \"Compare the top 2 candidates\"")

    for msg in st.session_state.hr_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask the AI HR Assistant...")
    if question:
        st.session_state.hr_chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing all candidates..."):
                system = ("You are an AI HR assistant with access to structured summary data for all screened "
                          "candidates. Answer the HR user's question using ONLY this data. Be specific, cite "
                          "candidate names, and be decisive when asked for recommendations.")
                user = f"CANDIDATE DATA:\n{json.dumps(all_context, indent=2)[:8000]}\n\nQUESTION: {question}"
                answer = LLM.chat(client, st.session_state.model, system, user, temperature=0.3)
                st.markdown(answer)
        st.session_state.hr_chat_history.append({"role": "assistant", "content": answer})


# ============================================================
# PAGE: EMAIL GENERATOR
# ============================================================
def page_email_generator():
    hero("Email Generator", "Generate interview invitations, rejections, offer summaries, and shortlist emails.")

    if not require_api_key():
        return

    c1, c2 = st.columns(2)
    with c1:
        email_type = st.selectbox("Email Type", list(GEN.EMAIL_TYPES.keys()))
        candidate_options = ["(custom name)"] + [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
        chosen = st.selectbox("Candidate", candidate_options)
        candidate_name = st.text_input("Candidate Name", value="" if chosen == "(custom name)" else chosen)
    with c2:
        role = st.text_input("Role", value=st.session_state.jd_data.get("job_title", ""))
        company = st.text_input("Company Name", value="Our Company")
    notes = st.text_area("Additional Notes (optional)", placeholder="e.g. interview panel, salary range, deadlines...")

    if st.button("✉️ Generate Email", type="primary"):
        if not candidate_name.strip():
            st.error("Please enter a candidate name.")
        else:
            client = get_client()
            with st.spinner("Drafting email..."):
                email = GEN.generate_email(client, st.session_state.model, email_type, candidate_name, role, company, notes)
            st.text_area("Generated Email", email, height=300)
            st.download_button("⬇️ Download as TXT", email, file_name=f"{email_type.replace(' ', '_')}_{candidate_name}.txt")


# ============================================================
# PAGE: JD GENERATOR
# ============================================================
def page_jd_generator():
    hero("Job Description Generator", "Create a polished, professional job description in seconds.")

    if not require_api_key():
        return

    c1, c2 = st.columns(2)
    with c1:
        role = st.text_input("Role", placeholder="e.g. Senior Data Scientist")
        experience = st.text_input("Experience Required", placeholder="e.g. 3-5 years")
        skills = st.text_area("Key Skills", placeholder="e.g. Python, SQL, Machine Learning, AWS")
    with c2:
        location = st.text_input("Location", placeholder="e.g. Hyderabad, India / Remote")
        salary = st.text_input("Salary Range", placeholder="e.g. ₹12-18 LPA")

    if st.button("📝 Generate Job Description", type="primary"):
        if not role.strip():
            st.error("Please enter at least a role title.")
        else:
            client = get_client()
            with st.spinner("Writing job description..."):
                jd_text = GEN.generate_job_description(client, st.session_state.model, role, experience, skills, location, salary)
            st.markdown(jd_text)
            st.download_button("⬇️ Download JD", jd_text, file_name=f"JD_{role.replace(' ', '_')}.md")


# ============================================================
# PAGE: CAREER SUGGESTIONS
# ============================================================
def page_career_suggestions():
    hero("Career Suggestions", "Personalized growth plans for candidates based on skill gaps.")

    if not require_api_key():
        return
    if not require_candidates():
        return

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

if st.session_state.api_key:
    st.success("✅ OpenAI API Key Configured")
else:
    st.warning("❌ OpenAI API Key Not Configured")

api_key = st.text_input(
    "New OpenAI API Key",
    type="password",
    placeholder="Enter new API key (optional)"
)
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, st.session_state.temperature, 0.1)

    if st.button("💾 Save Settings", type="primary"):
        st.session_state.api_key = api_key
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
import pandas as pd
from dotenv import load_dotenv

from utils import parser as P
from utils import llm_utils as LLM
from utils import ats as ATS
from utils import chatbot as CHAT
from utils import analytics as AN
from utils import report_generator as REPORT
from utils import generators as GEN

load_dotenv()

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI HR Resume Screening & Interview Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS
CSS_PATH = os.path.join(os.path.dirname(__file__), "assets", "css", "style.css")
if os.path.exists(CSS_PATH):
    with open(CSS_PATH) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
def init_state():
    defaults = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0.4,
        "jd_text": "",
        "jd_data": {},
        "candidates": [],          # list of candidate dicts
        "vector_store": None,
        "chat_history": [],
        "hr_chat_history": [],
        "current_page": "Dashboard",
        "interview_cache": {},     # candidate_name -> questions dict
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def get_client():
    if not st.session_state.api_key:
        return None
    return LLM.get_client(st.session_state.api_key)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown(
        "<div style='text-align:center; padding: 10px 0 20px 0;'>"
        "<span style='font-size:38px;'>🧠</span><br>"
        "<span style='font-size:19px; font-weight:800;'>HR AI Screening</span><br>"
        "<span style='font-size:12px; opacity:0.7;'>Resume &amp; Interview Assistant</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    PAGES = [
        "Dashboard",
        "Upload Job Description",
        "Upload Resumes",
        "Candidate Ranking",
        "Resume Comparison",
        "AI Resume Chat",
        "Analytics Dashboard",
        "Interview Questions",
        "AI HR Assistant",
        "Email Generator",
        "JD Generator",
        "Career Suggestions",
        "Reports",
        "Settings",
    ]
    ICONS = ["🏠", "📄", "📥", "🏆", "⚖️", "💬", "📊", "🎯", "🤖", "✉️", "📝", "🚀", "📑", "⚙️"]

    page = st.radio(
        "Navigate",
        PAGES,
        format_func=lambda p: f"{ICONS[PAGES.index(p)]}  {p}",
        label_visibility="collapsed",
    )

    st.markdown("---")
    n_candidates = len(st.session_state.candidates)
    jd_status = "✅ Loaded" if st.session_state.jd_data else "❌ Not uploaded"
    st.markdown(
        f"<div style='font-size:13px; line-height:1.9;'>"
        f"<b>JD Status:</b> {jd_status}<br>"
        f"<b>Candidates:</b> {n_candidates}<br>"
        f"<b>Model:</b> {st.session_state.model}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    if not st.session_state.api_key:
        st.warning("⚠️ Add your OpenAI API key in Settings to enable AI features.")

# ============================================================
# SHARED UI HELPERS
# ============================================================
def hero(title: str, subtitle: str):
    st.markdown(
        f"<div class='hr-hero'><h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def section_title(text: str):
    st.markdown(f"<div class='section-title'>{text}</div>", unsafe_allow_html=True)


def metric_card(col, label, value):
    col.markdown(
        f"<div class='metric-card'><div class='value'>{value}</div>"
        f"<div class='label'>{label}</div></div>",
        unsafe_allow_html=True,
    )


def recommendation_badge(rec: str) -> str:
    mapping = {
        "Highly Recommended": "badge-gold",
        "Recommended": "badge-green",
        "Consider After Interview": "badge-blue",
        "Hold": "badge-yellow",
        "Reject": "badge-red",
    }
    css_class = mapping.get(rec, "badge-blue")
    return f"<span class='badge {css_class}'>{rec}</span>"


def require_api_key() -> bool:
    if not st.session_state.api_key:
        st.error("🔑 Please add your OpenAI API key in **Settings** to use this feature.")
        return False
    return True


def require_jd() -> bool:
    if not st.session_state.jd_data:
        st.warning("📄 Please upload/parse a Job Description first (see **Upload Job Description**).")
        return False
    return True


def require_candidates() -> bool:
    if not st.session_state.candidates:
        st.warning("📥 Please upload and process resumes first (see **Upload Resumes**).")
        return False
    return True


def process_single_resume(client, uploaded_file, jd_data: dict):
    """Full pipeline: extract -> parse -> score -> gap analysis -> fraud check."""
    raw_text = P.extract_text(uploaded_file)
    if raw_text.startswith("[ERROR") or raw_text.startswith("[Unsupported"):
        return {"error": raw_text, "file_name": uploaded_file.name}

    quick = P.regex_quick_extract(raw_text)
    resume_data = P.llm_extract_resume(client, st.session_state.model, raw_text)

    if "error" in resume_data:
        return {"error": resume_data["error"], "file_name": uploaded_file.name}

    # Fill gaps from regex extraction if LLM missed them
    for field in ["email", "phone", "linkedin", "github"]:
        if not resume_data.get(field) or resume_data.get(field) in ("", "Not found"):
            resume_data[field] = quick.get(field, "Not found")
    if not resume_data.get("name"):
        resume_data["name"] = uploaded_file.name.rsplit(".", 1)[0]

    ats_result = ATS.compute_ats_score(client, st.session_state.model, jd_data, resume_data)
    gap = ATS.skill_gap_analysis(jd_data.get("required_skills", []), resume_data.get("skills", []))
    flags = ATS.detect_red_flags(raw_text, resume_data)

    return {
        "file_name": uploaded_file.name,
        "raw_text": raw_text,
        "resume_data": resume_data,
        "ats": ats_result,
        "skill_gap": gap,
        "red_flags": flags,
    }

# ============================================================
# PAGE: DASHBOARD
# ============================================================
def page_dashboard():
    hero("AI-Powered HR Resume Screening & Interview Assistant",
         "Screen, score, rank, and interview candidates faster with Generative AI.")

    cols = st.columns(4)
    n_candidates = len(st.session_state.candidates)
    avg_score = 0
    top_candidate = "—"
    if st.session_state.candidates:
        scores = [c["ats"].get("overall_ats_score", 0) for c in st.session_state.candidates if "ats" in c and "error" not in c.get("ats", {})]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        if scores:
            best = max(st.session_state.candidates, key=lambda c: c["ats"].get("overall_ats_score", 0))
            top_candidate = best["resume_data"].get("name", "Unknown")

    metric_card(cols[0], "Job Description", "Loaded" if st.session_state.jd_data else "Missing")
    metric_card(cols[1], "Candidates Screened", n_candidates)
    metric_card(cols[2], "Average ATS Score", f"{avg_score}%")
    metric_card(cols[3], "Top Candidate", top_candidate)

    st.write("")
    section_title("Quick Start Guide")
    steps = [
        ("1️⃣", "Upload Job Description", "Paste or upload the JD — AI extracts required skills, experience & keywords."),
        ("2️⃣", "Upload Resumes", "Bulk upload candidate resumes in PDF, DOCX, or TXT."),
        ("3️⃣", "Review Ranking", "See ATS scores, skill gaps, and hire recommendations instantly."),
        ("4️⃣", "Chat & Interview", "Ask the AI assistant questions and auto-generate interview questions."),
    ]
    cols2 = st.columns(4)
    for col, (icon, title, desc) in zip(cols2, steps):
        col.markdown(
            f"<div class='candidate-card'><div style='font-size:26px;'>{icon}</div>"
            f"<b>{title}</b><div style='font-size:13px; color:#64748B; margin-top:4px;'>{desc}</div></div>",
            unsafe_allow_html=True,
        )

    if st.session_state.candidates:
        st.write("")
        section_title("Recent Candidates")
        df = AN.candidates_to_dataframe(st.session_state.candidates)
        st.dataframe(
            df.sort_values("Overall ATS", ascending=False),
            use_container_width=True, hide_index=True,
        )


# ============================================================
# PAGE: UPLOAD JOB DESCRIPTION
# ============================================================
def page_upload_jd():
    hero("Upload Job Description", "Provide the JD so AI can extract requirements and score candidates against it.")

    if not require_api_key():
        return

    tab1, tab2 = st.tabs(["📁 Upload File", "✍️ Paste Text"])
    jd_text_input = ""

    with tab1:
        jd_file = st.file_uploader("Upload JD (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"], key="jd_file")
        if jd_file:
            jd_text_input = P.extract_text(jd_file)
            st.text_area("Extracted Text Preview", jd_text_input, height=200, key="jd_preview_file")

    with tab2:
        pasted = st.text_area("Paste Job Description here", height=250, key="jd_paste_area")
        if pasted.strip():
            jd_text_input = pasted

    if st.button("🔍 Analyze Job Description", type="primary", use_container_width=True):
        if not jd_text_input.strip():
            st.error("Please upload a file or paste JD text first.")
        else:
            with st.spinner("Analyzing job description with AI..."):
                client = get_client()
                jd_data = P.llm_extract_jd(client, st.session_state.model, jd_text_input)
                if "error" in jd_data:
                    st.error(f"Extraction failed: {jd_data['error']}")
                else:
                    st.session_state.jd_text = jd_text_input
                    st.session_state.jd_data = jd_data
                    st.session_state.vector_store = None  # reset, will rebuild on demand
                    st.success("✅ Job Description analyzed successfully!")

    if st.session_state.jd_data:
        st.write("")
        section_title("Extracted Job Requirements")
        jd = st.session_state.jd_data
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Job Title:** {jd.get('job_title', 'N/A')}")
            st.markdown(f"**Minimum Experience:** {jd.get('min_experience_years', 'N/A')} years")
            st.markdown("**Required Skills:**")
            st.write(", ".join(jd.get("required_skills", [])) or "N/A")
            st.markdown("**Preferred Skills:**")
            st.write(", ".join(jd.get("preferred_skills", [])) or "N/A")
        with c2:
            st.markdown("**Education Requirements:**")
            st.write(", ".join(jd.get("education_requirements", [])) or "N/A")
            st.markdown("**Certifications Required:**")
            st.write(", ".join(jd.get("certifications_required", [])) or "N/A")
            st.markdown("**Keywords:**")
            st.write(", ".join(jd.get("keywords", [])) or "N/A")

        st.info(f"**AI Summary:** {jd.get('summary', 'N/A')}")

# ============================================================
# PAGE: UPLOAD RESUMES
# ============================================================
def page_upload_resumes():
    hero("Upload Resumes", "Bulk upload candidate resumes for automatic parsing and ATS scoring.")

    if not require_api_key():
        return
    if not require_jd():
        return

    files = st.file_uploader(
        "Upload one or more resumes (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"], accept_multiple_files=True, key="resume_files",
    )

    col1, col2 = st.columns([3, 1])
    with col2:
        clear = st.button("🗑️ Clear All Candidates", use_container_width=True)
        if clear:
            st.session_state.candidates = []
            st.session_state.vector_store = None
            st.session_state.interview_cache = {}
            st.success("Cleared all candidates.")

    with col1:
        process = st.button("🚀 Process & Score Resumes", type="primary", use_container_width=True)

    if process:
        if not files:
            st.error("Please upload at least one resume.")
        else:
            client = get_client()
            existing_names = {c["file_name"] for c in st.session_state.candidates}
            progress = st.progress(0.0, text="Starting...")
            new_candidates = []
            for i, f in enumerate(files):
                if f.name in existing_names:
                    progress.progress((i + 1) / len(files), text=f"Skipping duplicate: {f.name}")
                    continue
                progress.progress((i + 1) / len(files), text=f"Processing {f.name}...")
                result = process_single_resume(client, f, st.session_state.jd_data)
                new_candidates.append(result)
            progress.empty()

            success_count = 0
            for r in new_candidates:
                if "error" in r:
                    st.error(f"❌ {r['file_name']}: {r['error']}")
                else:
                    st.session_state.candidates.append(r)
                    success_count += 1

            st.session_state.vector_store = None  # invalidate cache so chatbot rebuilds
            if success_count:
                st.success(f"✅ Successfully processed {success_count} resume(s)!")

    if st.session_state.candidates:
        st.write("")
        section_title(f"Processed Candidates ({len(st.session_state.candidates)})")
        for c in st.session_state.candidates:
            resume = c["resume_data"]
            ats = c.get("ats", {})
            with st.expander(f"📄 {resume.get('name', c['file_name'])} — ATS: {ats.get('overall_ats_score', 'N/A')}%"):
                colA, colB = st.columns([2, 1])
                with colA:
                    st.markdown(f"**Email:** {resume.get('email', 'N/A')}  |  **Phone:** {resume.get('phone', 'N/A')}")
                    st.markdown(f"**Skills:** {', '.join(resume.get('skills', [])) or 'N/A'}")
                    st.markdown(f"**Experience:** {resume.get('total_experience_years', 'N/A')} years")
                    st.markdown(f"**Summary:** {resume.get('summary', 'N/A')}")
                with colB:
                    st.markdown(recommendation_badge(ats.get("hire_recommendation", "N/A")), unsafe_allow_html=True)
                    st.markdown("**Red Flags:**")
                    for flag in c.get("red_flags", []):
                        st.caption(flag)


# ============================================================
# PAGE: CANDIDATE RANKING
# ============================================================
def page_candidate_ranking():
    hero("Candidate Ranking", "Leaderboard of all screened candidates, ranked by overall ATS score.")

    if not require_candidates():
        return

    ranked = sorted(
        st.session_state.candidates,
        key=lambda c: c["ats"].get("overall_ats_score", 0),
        reverse=True,
    )

    medal = ["🥇", "🥈", "🥉"]
    for i, c in enumerate(ranked):
        resume = c["resume_data"]
        ats = c["ats"]
        badge_icon = medal[i] if i < 3 else f"#{i+1}"
        with st.container():
            st.markdown("<div class='candidate-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([0.6, 3, 1.5, 1.5])
            c1.markdown(f"<div style='font-size:26px; text-align:center;'>{badge_icon}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{resume.get('name', 'Unknown')}**")
                st.caption(f"{resume.get('email', 'N/A')} · {resume.get('total_experience_years', 'N/A')} yrs experience")
            with c3:
                st.metric("ATS Score", f"{ats.get('overall_ats_score', 0)}%")
            with c4:
                st.markdown(recommendation_badge(ats.get("hire_recommendation", "N/A")), unsafe_allow_html=True)
            st.progress(min(int(ats.get("overall_ats_score", 0)), 100) / 100)
            st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    section_title("Detailed Score Table")
    df = AN.candidates_to_dataframe(st.session_state.candidates)
    st.dataframe(df.sort_values("Overall ATS", ascending=False), use_container_width=True, hide_index=True)

# ============================================================
# PAGE: RESUME COMPARISON
# ============================================================
def page_resume_comparison():
    hero("Resume Comparison", "Compare two candidates side by side across every dimension.")

    if not require_candidates():
        return
    if len(st.session_state.candidates) < 2:
        st.info("Upload at least 2 resumes to enable comparison.")
        return

    names = [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
    c1, c2 = st.columns(2)
    with c1:
        idx_a = st.selectbox("Candidate A", range(len(names)), format_func=lambda i: names[i], key="cmp_a")
    with c2:
        default_b = 1 if len(names) > 1 else 0
        idx_b = st.selectbox("Candidate B", range(len(names)), format_func=lambda i: names[i], index=default_b, key="cmp_b")

    if idx_a == idx_b:
        st.warning("Please select two different candidates.")
        return

    A = st.session_state.candidates[idx_a]
    B = st.session_state.candidates[idx_b]

    rows = [
        ("Overall ATS Score", A["ats"].get("overall_ats_score", 0), B["ats"].get("overall_ats_score", 0)),
        ("Skills Match", A["ats"].get("skills_match", {}).get("score", 0), B["ats"].get("skills_match", {}).get("score", 0)),
        ("Experience Match", A["ats"].get("experience_match", {}).get("score", 0), B["ats"].get("experience_match", {}).get("score", 0)),
        ("Education Match", A["ats"].get("education_match", {}).get("score", 0), B["ats"].get("education_match", {}).get("score", 0)),
        ("Projects Match", A["ats"].get("projects_match", {}).get("score", 0), B["ats"].get("projects_match", {}).get("score", 0)),
        ("Experience (yrs)", A["resume_data"].get("total_experience_years", 0), B["resume_data"].get("total_experience_years", 0)),
        ("Recommendation", A["ats"].get("hire_recommendation", "N/A"), B["ats"].get("hire_recommendation", "N/A")),
    ]
    df = pd.DataFrame(rows, columns=["Metric", names[idx_a], names[idx_b]])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.write("")
    colA, colB = st.columns(2)
    for col, cand in [(colA, A), (colB, B)]:
        with col:
            r = cand["resume_data"]
            st.markdown(f"### {r.get('name', 'Unknown')}")
            st.markdown(recommendation_badge(cand["ats"].get("hire_recommendation", "N/A")), unsafe_allow_html=True)
            st.markdown(f"**Skills:** {', '.join(r.get('skills', [])) or 'N/A'}")
            st.markdown("**Matched Skills:** " + (", ".join(cand["skill_gap"].get("matched_skills", [])) or "None"))
            st.markdown("**Missing Skills:** " + (", ".join(cand["skill_gap"].get("missing_skills", [])) or "None"))
            st.markdown(f"**Strengths:**")
            for s in cand["ats"].get("strengths", []):
                st.caption(f"✓ {s}")
            st.markdown(f"**Weaknesses:**")
            for w in cand["ats"].get("weaknesses", []):
                st.caption(f"✗ {w}")

    st.write("")
    if require_api_key():
        if st.button("🤖 AI Recommendation: Who should we hire?", type="primary"):
            client = get_client()
            with st.spinner("Comparing candidates..."):
                prompt = f"""Compare these two candidates for the role and recommend who is the better fit, with reasoning.

Candidate A ({names[idx_a]}): {json.dumps(A['ats'])[:2000]}
Candidate B ({names[idx_b]}): {json.dumps(B['ats'])[:2000]}
"""
                answer = LLM.chat(client, st.session_state.model,
                                   "You are a senior HR hiring manager giving a clear, decisive recommendation.",
                                   prompt, temperature=0.4)
            st.success(answer)


# ============================================================
# PAGE: AI RESUME CHAT (RAG)
# ============================================================
def page_ai_resume_chat():
    hero("AI Resume Chat", "Ask anything about uploaded resumes — answers are grounded strictly in the documents (RAG).")

    if not require_api_key():
        return
    if not require_candidates():
        return

    client = get_client()

    if st.session_state.vector_store is None:
        with st.spinner("Indexing resumes for retrieval..."):
            docs = [{"text": c["raw_text"], "source": c["resume_data"].get("name", c["file_name"]), "type": "resume"}
                    for c in st.session_state.candidates]
            if st.session_state.jd_text:
                docs.append({"text": st.session_state.jd_text, "source": "Job Description", "type": "jd"})
            st.session_state.vector_store = CHAT.build_vector_store(st.session_state.api_key, docs)

    st.caption("💡 Try: \"Summarize this resume\", \"Does the candidate know Python?\", \"Why should we hire them?\"")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask about a candidate's resume...")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = CHAT.query_chatbot(client, st.session_state.model, st.session_state.vector_store, question)
                st.markdown(result["answer"])
                if result["sources"]:
                    st.caption("📎 Sources: " + ", ".join(result["sources"]))
        st.session_state.chat_history.append({"role": "assistant", "content": result["answer"]})


# ============================================================
# PAGE: ANALYTICS DASHBOARD
# ============================================================
def page_analytics_dashboard():
    hero("Analytics Dashboard", "Visual insights across all screened candidates.")

    if not require_candidates():
        return

    df = AN.candidates_to_dataframe(st.session_state.candidates)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(AN.avg_ats_gauge(df), use_container_width=True)
    with c2:
        fig = AN.recommendation_pie(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    st.plotly_chart(AN.ranking_bar_chart(df), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig = AN.top_skills_chart(st.session_state.candidates)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    with c4:
        st.plotly_chart(AN.experience_distribution_chart(df), use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        fig = AN.education_distribution_chart(st.session_state.candidates)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No education data available.")
    with c6:
        fig = AN.certification_distribution_chart(st.session_state.candidates)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No certification data available.")

# ============================================================
# PAGE: INTERVIEW QUESTIONS
# ============================================================
def page_interview_questions():
    hero("Interview Question Generator", "Auto-generate tailored technical, behavioral, HR, project, and coding questions.")

    if not require_api_key():
        return
    if not require_candidates():
        return

    names = [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
    idx = st.selectbox("Select Candidate", range(len(names)), format_func=lambda i: names[i])
    difficulty = st.select_slider("Difficulty", options=["Easy", "Medium", "Hard"], value="Medium")

    if st.button("🎯 Generate Interview Questions", type="primary"):
        client = get_client()
        cand = st.session_state.candidates[idx]
        with st.spinner("Generating tailored questions..."):
            qs = GEN.generate_interview_questions(client, st.session_state.model, cand["resume_data"], st.session_state.jd_data, difficulty)
        if "error" in qs:
            st.error(qs["error"])
        else:
            st.session_state.interview_cache[names[idx]] = qs

    qs = st.session_state.interview_cache.get(names[idx])
    if qs:
        tabs = st.tabs(["🧠 Technical", "🤝 Behavioral", "🏢 HR", "🛠️ Project", "💻 Coding"])
        keys = ["technical_questions", "behavioral_questions", "hr_questions", "project_questions", "coding_questions"]
        for tab, key in zip(tabs, keys):
            with tab:
                for i, q in enumerate(qs.get(key, []), 1):
                    st.markdown(f"**{i}.** {q}")


# ============================================================
# PAGE: AI HR ASSISTANT
# ============================================================
def page_ai_hr_assistant():
    hero("AI HR Assistant", "Ask high-level hiring questions across all candidates — best fit, comparisons, skill search, and more.")

    if not require_api_key():
        return
    if not require_candidates():
        return

    client = get_client()

    all_context = []
    for c in st.session_state.candidates:
        r, a = c["resume_data"], c["ats"]
        all_context.append({
            "name": r.get("name"), "skills": r.get("skills"),
            "experience_years": r.get("total_experience_years"),
            "education": r.get("education"), "overall_ats": a.get("overall_ats_score"),
            "recommendation": a.get("hire_recommendation"), "strengths": a.get("strengths"),
            "weaknesses": a.get("weaknesses"),
        })

    st.caption("💡 Try: \"Who is the best candidate?\", \"Who has AWS experience?\", \"Compare the top 2 candidates\"")

    for msg in st.session_state.hr_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask the AI HR Assistant...")
    if question:
        st.session_state.hr_chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing all candidates..."):
                system = ("You are an AI HR assistant with access to structured summary data for all screened "
                          "candidates. Answer the HR user's question using ONLY this data. Be specific, cite "
                          "candidate names, and be decisive when asked for recommendations.")
                user = f"CANDIDATE DATA:\n{json.dumps(all_context, indent=2)[:8000]}\n\nQUESTION: {question}"
                answer = LLM.chat(client, st.session_state.model, system, user, temperature=0.3)
                st.markdown(answer)
        st.session_state.hr_chat_history.append({"role": "assistant", "content": answer})


# ============================================================
# PAGE: EMAIL GENERATOR
# ============================================================
def page_email_generator():
    hero("Email Generator", "Generate interview invitations, rejections, offer summaries, and shortlist emails.")

    if not require_api_key():
        return

    c1, c2 = st.columns(2)
    with c1:
        email_type = st.selectbox("Email Type", list(GEN.EMAIL_TYPES.keys()))
        candidate_options = ["(custom name)"] + [c["resume_data"].get("name", c["file_name"]) for c in st.session_state.candidates]
        chosen = st.selectbox("Candidate", candidate_options)
        candidate_name = st.text_input("Candidate Name", value="" if chosen == "(custom name)" else chosen)
    with c2:
        role = st.text_input("Role", value=st.session_state.jd_data.get("job_title", ""))
        company = st.text_input("Company Name", value="Our Company")
    notes = st.text_area("Additional Notes (optional)", placeholder="e.g. interview panel, salary range, deadlines...")

    if st.button("✉️ Generate Email", type="primary"):
        if not candidate_name.strip():
            st.error("Please enter a candidate name.")
        else:
            client = get_client()
            with st.spinner("Drafting email..."):
                email = GEN.generate_email(client, st.session_state.model, email_type, candidate_name, role, company, notes)
            st.text_area("Generated Email", email, height=300)
            st.download_button("⬇️ Download as TXT", email, file_name=f"{email_type.replace(' ', '_')}_{candidate_name}.txt")


# ============================================================
# PAGE: JD GENERATOR
# ============================================================
def page_jd_generator():
    hero("Job Description Generator", "Create a polished, professional job description in seconds.")

    if not require_api_key():
        return

    c1, c2 = st.columns(2)
    with c1:
        role = st.text_input("Role", placeholder="e.g. Senior Data Scientist")
        experience = st.text_input("Experience Required", placeholder="e.g. 3-5 years")
        skills = st.text_area("Key Skills", placeholder="e.g. Python, SQL, Machine Learning, AWS")
    with c2:
        location = st.text_input("Location", placeholder="e.g. Hyderabad, India / Remote")
        salary = st.text_input("Salary Range", placeholder="e.g. ₹12-18 LPA")

    if st.button("📝 Generate Job Description", type="primary"):
        if not role.strip():
            st.error("Please enter at least a role title.")
        else:
            client = get_client()
            with st.spinner("Writing job description..."):
                jd_text = GEN.generate_job_description(client, st.session_state.model, role, experience, skills, location, salary)
            st.markdown(jd_text)
            st.download_button("⬇️ Download JD", jd_text, file_name=f"JD_{role.replace(' ', '_')}.md")


# ============================================================
# PAGE: CAREER SUGGESTIONS
# ============================================================
def page_career_suggestions():
    hero("Career Suggestions", "Personalized growth plans for candidates based on skill gaps.")

    if not require_api_key():
        return
    if not require_candidates():
        return

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

api_key = st.text_input(
    "OpenAI API Key",
    value="",
    placeholder="Enter your OpenAI API Key",
    type="password",
    help="Your API key is hidden and will not be displayed."
)

model = st.selectbox(
    "LLM Model",
    ["gpt-4o-mini", "gpt-4.1", "gpt-4o", "gpt-4.1-mini"],
    index=["gpt-4o-mini", "gpt-4.1", "gpt-4o", "gpt-4.1-mini"].index(st.session_state.model)
    if st.session_state.model in ["gpt-4o-mini", "gpt-4.1", "gpt-4o", "gpt-4.1-mini"] else 0
)

temperature = st.slider(
    "Creativity (Temperature)",
    0.0,
    1.0,
    st.session_state.temperature,
    0.1
)

if st.button("💾 Save Settings", type="primary"):
    if api_key.strip():
        st.session_state.api_key = api_key.strip()

    st.session_state.model = model
    st.session_state.temperature = temperature

    st.success("✅ Settings saved.")


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
