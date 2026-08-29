# 🧠 AI-Powered HR Resume Screening & Interview Assistant

An end-to-end Generative AI application that helps HR teams screen, score, rank and interview candidates faster — combining LLM-based resume parsing, retrieval-augmented Q&A, analytics and automated document generation in a single Streamlit app.

---

## 📌 Problem Statement

Manual resume screening is slow and inconsistent — recruiters spend hours reading resumes, comparing candidates against a job description, and drafting follow-up questions or emails by hand. This project automates that pipeline: upload a job description and a batch of resumes, and the app extracts structured candidate data, scores each resume against the JD, ranks candidates, flags gaps and risks, and lets HR "chat" with the resumes to get grounded answers instead of re-reading every document.

---

## 🏗️ Architecture

```
                ┌─────────────────────┐
                │   Streamlit UI      │
                │  (app.py — router)  │
                └──────────┬──────────┘
                           │
        ┌──────────────────┼───────────────────────┐
        │                  │                        │
┌───────▼────────┐ ┌───────▼────────┐   ┌───────────▼───────────┐
│ utils/parser.py │ │  utils/ats.py  │   │  utils/chatbot.py     │
│ Resume & JD     │ │  Scoring +     │   │  RAG: vector store +  │
│ text extraction │ │  skill-gap +   │   │  grounded Q&A over    │
│ & LLM parsing   │ │  red-flag scan │   │  resumes / JD         │
└───────┬────────┘ └───────┬────────┘   └───────────┬───────────┘
        │                  │                         │
┌───────▼──────────────────▼─────────────────────────▼───────┐
│                     utils/llm_utils.py                      │
│              OpenAI client wrapper (chat calls)              │
└───────────────────────────┬──────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
┌───────▼────────┐  ┌────────▼─────────┐  ┌────────▼─────────┐
│ utils/          │  │ utils/           │  │ utils/           │
│ analytics.py    │  │ generators.py    │  │ report_generator │
│ Charts/metrics  │  │ Interview Qs,    │  │ .py — PDF/Excel  │
│ for dashboard   │  │ emails, JDs,     │  │ export           │
│                 │  │ career advice    │  │                  │
└─────────────────┘  └──────────────────┘  └──────────────────┘
```

**Pipeline for each resume:** extract text → regex quick-extract (email/phone/links as a fallback) → LLM structured extraction → ATS-style scoring against the JD → skill-gap analysis → red-flag detection → stored in session state for ranking, comparison, chat and reporting.

---

## ✨ Features

- **Job Description Analyzer** — paste or upload a JD; AI extracts required/preferred skills, experience, education and keywords.
- **Bulk Resume Upload** — PDF/DOCX/TXT, processed and scored in one batch with duplicate detection.
- **AI Candidate–Job Match Scoring** — structured scoring across skills, experience, education and project relevance (not a claimed "official ATS" score — an AI-generated match assessment).
- **Candidate Ranking** — leaderboard sorted by overall match score with hire-recommendation badges.
- **Resume Comparison** — side-by-side comparison of any two candidates, plus an AI-generated hiring recommendation.
- **AI Resume Chat (RAG)** — ask natural-language questions about uploaded resumes; answers are grounded in the actual documents via a vector store, with cited sources.
- **Analytics Dashboard** — score distributions, recommendation breakdown, top skills, experience/education charts (Plotly).
- **Interview Question Generator** — tailored technical, behavioral, HR, project and coding questions per candidate and difficulty level.
- **AI HR Assistant** — a second chat surface for cross-candidate questions ("who has AWS experience?", "compare the top 2").
- **Email Generator** — interview invites, rejections, shortlist and offer-summary emails.
- **JD Generator** — generate a polished job description from role, experience, skills, location and salary.
- **Career Suggestions** — personalized growth plan for a candidate based on their skill gaps vs. the JD.
- **Reports** — export candidate rankings to Excel and individual candidate profiles (with interview questions) to PDF.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| UI / App Framework | Streamlit |
| LLM | OpenAI (`gpt-4o-mini` / `gpt-4o` / `gpt-4.1` / `gpt-4.1-mini`, configurable) |
| Retrieval / RAG | Vector store over resume + JD text (`utils/chatbot.py`) |
| Data Handling | Pandas |
| Reporting | PDF & Excel export (`utils/report_generator.py`) |
| Language | Python |

---

## 📂 Project Structure

```
├── app.py                  # Main Streamlit entry point & page router
├── assets/
│   └── css/style.css       # Custom UI styling
└── utils/
    ├── parser.py            # Text extraction + LLM resume/JD parsing
    ├── llm_utils.py          # OpenAI client wrapper
    ├── ats.py                 # Match scoring, skill-gap analysis, red-flag detection
    ├── chatbot.py             # RAG vector store + grounded Q&A
    ├── analytics.py           # Dataframe helpers + Plotly charts
    ├── report_generator.py    # PDF / Excel report generation
    └── generators.py          # Interview questions, emails, JD & career-advice generation
```

---

## ⚙️ Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/gouthampotu/ai-resume-screening-bot.git
cd ai-resume-screening-bot

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your OpenAI API key (recommended: environment variable)
echo "OPENAI_API_KEY=your_key_here" > .env

# 5. Run the app
streamlit run app.py
```

> 🔑 **API key handling:** the app reads `OPENAI_API_KEY` from the environment by default and also lets you paste a key directly in the **Settings** page for the current session only (never written to disk or logged). For local development, always use a `.env` file (excluded via `.gitignore`) rather than hardcoding a key in source — **never commit real API keys to the repository.**

---

## 📸 Screenshots

> _Add screenshots of the Dashboard, Candidate Ranking, and Analytics pages here, e.g.:_
> `![Dashboard](assets/screenshots/dashboard.png)`

---

## 📊 Results / Example Output

- Upload a JD + N resumes → get a ranked leaderboard with match scores, strengths, weaknesses and hire recommendations within seconds.
- RAG chat answers are grounded strictly in uploaded documents, with source attribution, reducing hallucinated claims about candidates.

---

## ⚠️ Limitations

- Scoring quality depends on the underlying LLM's extraction accuracy — not a substitute for human judgment or a legally validated ATS system.
- Currently supports single-session state (Streamlit `session_state`); no persistent database or multi-user auth yet.
- Vector store is rebuilt in-memory per session rather than persisted.

## 🔭 Future Improvements

- Persistent storage (database) for candidates and JDs across sessions.
- Multi-user authentication and role-based access for HR teams.
- Swap in an open-source/local embedding model as an alternative to OpenAI for cost control.
- Add automated evaluation of scoring consistency across repeated runs.
- Deploy behind FastAPI + Docker for a production-style serving setup.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
