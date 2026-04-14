import streamlit as st
import os
import json
import csv
import pandas as pd
import requests
import PyPDF2
import re
import time
from datetime import datetime
from groq import Groq

# ==========================================
# 🎨 STREAMLIT DASHBOARD UI & TEXT
# ==========================================
st.set_page_config(page_title="AI Job Hunter Pro", page_icon="💼", layout="wide")

TEXT = {
    "English": {
        "title": "🤖 Personal AI Job Hunter Pro",
        "sub": "Automatically find, screen, and filter jobs based on your specific preferences.",
        "tab_search": "🔍 Search Jobs",
        "tab_history": "📁 History Log",
        "role": "Job Role",
        "loc": "Location",
        "work_type": "Work Type",
        "date_posted": "Date Posted",
        "date_opts": ["Any time", "Past month", "Past week", "Past 3 days", "Past 24 hours"],
        "exclude": "Excluded Keywords",
        "min_sal": "Min Monthly Salary",
        "min": "Minimum Match Score",
        "cv": "Upload your CV (PDF)",
        "btn": "🚀 Start Hunting",
        "err_cv": "⚠️ Please upload your CV PDF first!",
        "err_api": "⚠️ Please enter your API Keys!",
        "score_lbl": "Match Score",
        "reasons": "**✨ Why it's a match:**",
        "missing": "**⚠️ Missing Skills / Filter Warnings:**",
        "draft_lbl": "✉️ Email Draft / Cover Letter:",
        "no_new": "✨ No new jobs found. Check your history."
    },
    "Bahasa Indonesia": {
        "title": "🤖 Personal AI Job Hunter Pro",
        "sub": "Cari, seleksi, dan filter loker otomatis sesuai kriteria spesifikmu.",
        "tab_search": "🔍 Cari Loker",
        "tab_history": "📁 Riwayat Lamaran",
        "role": "Posisi Pekerjaan",
        "loc": "Lokasi",
        "work_type": "Tipe Kerja",
        "date_posted": "Waktu Posting",
        "date_opts": ["Semua waktu", "Sebulan terakhir", "Seminggu terakhir", "3 Hari terakhir", "24 Jam terakhir"],
        "exclude": "Kata Kunci Dihindari",
        "min_sal": "Target Gaji Minimal",
        "min": "Minimal Skor Kecocokan",
        "cv": "Upload CV Kamu (PDF)",
        "btn": "🚀 Mulai Berburu Loker",
        "err_cv": "⚠️ Upload CV PDF kamu dulu bro!",
        "err_api": "⚠️ Masukkan API Key kamu dulu!",
        "score_lbl": "Skor Kecocokan",
        "reasons": "**✨ Alasan Cocok:**",
        "missing": "**⚠️ Kekurangan / Peringatan Filter:**",
        "draft_lbl": "✉️ Draf Email / Cover Letter:",
        "no_new": "✨ Tidak ada loker baru. Semua sudah ada di riwayat."
    }
}

DATE_MAPPING = {
    "Any time": "", "Past month": "date_posted:month", "Past week": "date_posted:week", "Past 3 days": "date_posted:3days", "Past 24 hours": "date_posted:today",
    "Semua waktu": "", "Sebulan terakhir": "date_posted:month", "Seminggu terakhir": "date_posted:week", "3 Hari terakhir": "date_posted:3days", "24 Jam terakhir": "date_posted:today"
}

# --- SIDEBAR ---
with st.sidebar:
    lang_choice = st.selectbox("🌐 Language", ["English", "Bahasa Indonesia"])
    t = TEXT[lang_choice]
    
    st.header("🔑 API Keys")
    user_groq_key = st.text_input("Groq API Key", type="password")
    user_serp_key = st.text_input("SerpAPI Key", type="password")
    
    st.markdown("---")
    st.header("⚙️ Settings")
    query_input = st.text_input(t["role"], "Data Analyst")
    location_input = st.text_input(t["loc"], "Tangerang")
    work_type = st.selectbox(t["work_type"], ["All", "Remote", "Hybrid", "On-site"])
    date_choice = st.selectbox(t["date_posted"], t["date_opts"])
    
    st.markdown("---")
    exclude_input = st.text_input(t["exclude"], "Alcohol, Gambling")
    min_salary = st.number_input(t["min_sal"], value=11000000, step=1000000)
    min_score = st.slider(t["min"], 50, 100, 75)
    
    st.markdown("---")
    uploaded_cv = st.file_uploader(t["cv"], type=["pdf"])
    mulai_btn = st.button(t["btn"], use_container_width=True)

# ==========================================
# 🧠 FUNGSI AGENT & LOGGING
# ==========================================
def save_to_csv(company, position, score, reasons, missing, link):
    filename = "job_hunting_log.csv"
    file_exists = os.path.isfile(filename)
    reasons_str = " | ".join(reasons)
    missing_str = " | ".join(missing)
    
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Date", "Company", "Position", "Score", "Reasons", "Missing", "Link"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), company, position, score, reasons_str, missing_str, link])

def fetch_loker(query, location, w_type, date_chip, serp_key):
    try:
        search_query = f"{query} {location}"
        if w_type != "All": search_query += f" {w_type}"
        params = {"engine": "google_jobs", "q": search_query, "hl": "id", "gl": "id", "api_key": serp_key}
        if date_chip: params["chips"] = date_chip
        response = requests.get("https://serpapi.com/search.json", params=params).json()
        jobs = []
        if "jobs_results" in response:
            for job in response["jobs_results"][:5]:
                link = job.get("apply_options", [{}])[0].get("link", "")
                jobs.append({"title": job.get("title", ""), "company": job.get("company_name", ""), "description": job.get("description", ""), "link": link})
        return jobs
    except: return []

def screening_agent(job_desc, cv_text, language, excluded, min_sal, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"Analyze Job vs CV. JSON ONLY: {{'score': 0-100, 'reasons': [], 'missing': []}}. Exclude: {excluded}. Min Sal: {min_sal}. Language: {language}. Job: {job_desc}. CV: {cv_text}"
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.2)
        match = re.search(r'\{.*\}', chat.choices[0].message.content, re.DOTALL)
        return json.loads(match.group(0)) if match else {"score": 0, "reasons": [], "missing": []}
    except: return {"score": 0, "reasons": ["Error AI Connection"], "missing": []}

def drafting_agent(job_desc, reasons, language, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"Write professional email in {language} for this job: {job_desc}. Matching points: {reasons}. Under 150 words."
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.5)
        return chat.choices[0].message.content.strip()
    except: return "⚠️ Error generating draft."

# ==========================================
# 🚀 MAIN AREA (TABBED VIEW)
# ==========================================
st.title(t["title"])
tab1, tab2 = st.tabs([t["tab_search"], t["tab_history"]])

with tab1:
    if mulai_btn:
        if not user_groq_key or not user_serp_key: 
            st.error(t["err_api"])
        elif not uploaded_cv: 
            st.error(t["err_cv"])
        else:
            reader = PyPDF2.PdfReader(uploaded_cv)
            cv_text = "".join([p.extract_text() for p in reader.pages])
            
            seen_links = set()
            if os.path.isfile("job_hunting_log.csv"):
                try: 
                    seen_links = set(pd.read_csv("job_hunting_log.csv")['Link'].dropna().tolist())
                except: 
                    pass
            
            # --- BAGIAN INI YANG TADI KEGESER ---
            st.info(f"🔍 Searching for {query_input}...")
            selected_date_chip = DATE_MAPPING[date_choice]
            loker_raw = fetch_loker(query_input, location_input, work_type, selected_date_chip, user_serp_key)
            loker_list = [j for j in loker_raw if j['link'] not in seen_links]
            
            if not loker_list: 
                st.warning(t["no_new"])
            else:
                for loker in loker_list:
                    with st.expander(f"🏢 {loker['title']} - {loker['company']}", expanded=True):
                        with st.spinner("Analyzing..."):
                            time.sleep(2)
                            hasil = screening_agent(loker['description'], cv_text, lang_choice, exclude_input, min_salary, user_groq_key)
                            skor = int(hasil.get('score', 0))
                        
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.metric(t["score_lbl"], f"{skor}/100")
                            st.markdown(f"🔗 [Apply Here]({loker['link']})")
                        with col2:
                            st.markdown(t["reasons"])
                            for r in hasil.get('reasons', []): st.markdown(f"- {r}")
                            if hasil.get('missing'):
                                st.markdown(t["missing"])
                                for m in hasil.get('missing', []): st.markdown(f"- {m}")
                        
                        if skor >= min_score and skor > 0:
                            save_to_csv(loker['company'], loker['title'], skor, hasil.get('reasons', []), hasil.get('missing', []), loker['link'])
                            with st.spinner("Drafting..."):
                                draf = drafting_agent(loker['description'], hasil.get('reasons'), lang_choice, user_groq_key)
                                st.text_area(t["draft_lbl"], value=draf, height=150)

with tab2:
    st.subheader(t["tab_history"])
    if os.path.isfile("job_hunting_log.csv"):
        df_log = pd.read_csv("job_hunting_log.csv").sort_values(by="Date", ascending=False)
        
        for _, row in df_log.iterrows():
            with st.expander(f"📌 {row['Position']} at {row['Company']} ({row['Date']})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.metric(t["score_lbl"], f"{row['Score']}/100")
                    st.markdown(f"🔗 [View Job & Apply]({row['Link']})")
                with c2:
                    st.markdown(t["reasons"])
                    for r in str(row['Reasons']).split(" | "): st.markdown(f"- {r}")
                    if pd.notna(row['Missing']):
                        st.markdown(t["missing"])
                        for m in str(row['Missing']).split(" | "): st.markdown(f"- {m}")
        
        st.markdown("---")
        if st.button("🗑️ Clear History Log"):
            os.remove("job_hunting_log.csv")
            st.rerun()
    else:
        st.info("No history found.")