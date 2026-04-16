import streamlit as st
import os
import json
import requests
import PyPDF2
import re
import time
from datetime import datetime
from groq import Groq

# ==========================================
# 🎨 CONFIG & THEME
# ==========================================
st.set_page_config(page_title="LokerPilot AI", page_icon="🚀", layout="wide")

# Master Keys
BETA_KEYS = {
    "PILOT2026": "Standard",
    "CAPTAIN2026": "VIP"
}

# ==========================================
# 🌐 DICTIONARY BAHASA
# ==========================================
TEXT = {
    "English": {
        "title": "🚀 LokerPilot AI",
        "tab_search": "🔍 Search Jobs",
        "tab_history": "📁 History",
        "role": "Job Role",
        "loc": "Location",
        "date_posted": "Date Posted",
        "date_opts": ["Any time", "Past 24 hours", "Past 3 days", "Past week"],
        "exclude": "Excluded Keywords",
        "min_sal": "Min Monthly Salary",
        "min_score": "Min Match Score",
        "cv": "Upload CV (PDF)",
        "btn": "🚀 Start Hunting",
        "score_lbl": "Match Score",
        "apply_btn": "Apply Here",
        "reasons": "**✨ Match Reasons:**",
        "missing": "**⚠️ Missing Skills:**",
        "draft_lbl": "✉️ Cover Letter / Email Draft:",
        "low_score": "Score too low for auto-drafting.",
        "spin_search": "Scanning the horizon for jobs...",
        "spin_analyze": "Analyzing fit...",
        "spin_draft": "Writing cover letter...",
        "spin_vip": "VIP Consultant analyzing CV..."
    },
    "Bahasa Indonesia": {
        "title": "🚀 LokerPilot AI",
        "tab_search": "🔍 Cari Loker",
        "tab_history": "📁 Riwayat",
        "role": "Posisi Pekerjaan",
        "loc": "Lokasi",
        "date_posted": "Waktu Posting",
        "date_opts": ["Semua waktu", "24 Jam terakhir", "3 Hari terakhir", "Seminggu terakhir"],
        "exclude": "Hindari Kata Kunci",
        "min_sal": "Target Gaji Minimal",
        "min_score": "Minimal Skor Cocok",
        "cv": "Upload CV Kamu (PDF)",
        "btn": "🚀 Mulai Berburu Loker",
        "score_lbl": "Skor Kecocokan",
        "apply_btn": "Lamar Sekarang",
        "reasons": "**✨ Alasan Cocok:**",
        "missing": "**⚠️ Kekurangan di CV:**",
        "draft_lbl": "✉️ Draf Email / Cover Letter:",
        "low_score": "Skor terlalu rendah untuk dibuatkan draf.",
        "spin_search": "Memindai langit lowongan kerja...",
        "spin_analyze": "Menganalisa kecocokan...",
        "spin_draft": "Menulis draf lamaran...",
        "spin_vip": "Konsultan VIP sedang membedah CV..."
    }
}

# ==========================================
# 🧠 SESSION STATE
# ==========================================
if "history_log" not in st.session_state:
    st.session_state.history_log = []
if "access_granted" not in st.session_state:
    st.session_state.access_granted = False
if "user_tier" not in st.session_state:
    st.session_state.user_tier = "Standard"
if "welcome_shown" not in st.session_state:
    st.session_state.welcome_shown = False

# ==========================================
# 🔒 LOGIN SYSTEM
# ==========================================
if not st.session_state.access_granted:
    st.title("🚀 LokerPilot: Fly to Your Next Career")
    st.markdown("### Masukkan Kode Akses Founder's Club")
    
    pwd_input = st.text_input("Beta Key / License Key:", type="password")
    if st.button("Buka Kokpit ✈️", use_container_width=True):
        if pwd_input in BETA_KEYS:
            st.session_state.access_granted = True
            st.session_state.user_tier = BETA_KEYS[pwd_input]
            st.success(f"Akses {st.session_state.user_tier} Diberikan! Memuat sistem...")
            time.sleep(1)
            st.rerun()
        else:
            st.error("⚠️ Kode akses salah. Pastikan kamu sudah mendapatkan lisensi dari Mayar.")
    st.stop()

# ==========================================
# 📖 WELCOME DIALOG
# ==========================================
@st.dialog("📖 Panduan LokerPilot")
def welcome_dialog():
    st.markdown(f"""
    ### Welcome, {st.session_state.user_tier}! 
    Kamu masuk menggunakan akses **{st.session_state.user_tier}**.
    
    **Cara Mulai:**
    1. Isi **API Keys** di sidebar.
    2. Masukkan kriteria loker dan Upload CV PDF kamu.
    3. Klik **Mulai Berburu Loker**.
    
    {"✨ **Fitur VIP Aktif:** Kamu punya akses ke Analisa CV Mendalam & ATS Optimizer!" if st.session_state.user_tier == "VIP" else "💡 **Tips:** Upgrade ke paket Captain (VIP) untuk analisa CV mendalam."}
    """)
    if st.button("Siap, Gas!", use_container_width=True):
        st.session_state.welcome_shown = True
        st.rerun()

if not st.session_state.welcome_shown:
    welcome_dialog()

# ==========================================
# 🛠️ SIDEBAR SETTINGS
# ==========================================
with st.sidebar:
    st.title("🎮 Dashboard Kontrol")
    st.info(f"Status: **{st.session_state.user_tier} Member**")
    
    lang_choice = st.selectbox("🌐 Language", ["Bahasa Indonesia", "English"])
    t = TEXT[lang_choice]
    
    st.header("🔑 API Keys")
    user_groq_key = st.text_input("Groq API Key", type="password")
    user_serp_key = st.text_input("SerpAPI Key", type="password")
    
    st.markdown("---")
    st.header("⚙️ Filter Pencarian")
    query_input = st.text_input(t["role"], "")
    location_input = st.text_input(t["loc"], "")
    date_choice = st.selectbox(t["date_posted"], t["date_opts"])
    
    st.markdown("---")
    exclude_input = st.text_input(t["exclude"], "Alcohol, Gambling, Betting")
    min_salary = st.number_input(t["min_sal"], value=0, step=1000000)
    min_score = st.slider(t["min_score"], 50, 100, 75)
    
    st.markdown("---")
    uploaded_cv = st.file_uploader(t["cv"], type=["pdf"])
    mulai_btn = st.button(t["btn"], use_container_width=True)

# ==========================================
# 🧠 AGENT LOGIC
# ==========================================
def fetch_loker(query, location, date_choice, serp_key):
    try:
        date_map = {"Semua waktu": "", "24 Jam terakhir": "date_posted:today", "3 Hari terakhir": "date_posted:3days", "Seminggu terakhir": "date_posted:week", "Any time": "", "Past 24 hours": "date_posted:today", "Past 3 days": "date_posted:3days", "Past week": "date_posted:week"}
        params = {"engine": "google_jobs", "q": f"{query} {location}", "hl": "id", "gl": "id", "api_key": serp_key}
        if date_map.get(date_choice): params["chips"] = date_map[date_choice]
        
        res = requests.get("https://serpapi.com/search.json", params=params).json()
        jobs = []
        BANNED = ["jooble", "trovit", "trabajo", "jobisjob"]
        PREF = ["linkedin", "jobstreet", "glints", "kalibrr", "kitalulus", "techinasia"]

        if "jobs_results" in res:
            for j in res["jobs_results"]:
                opts = j.get("apply_options", [])
                link = next((o['link'] for o in opts if any(p in o['link'].lower() for p in PREF)), opts[0]['link'] if opts else "")
                if link and not any(b in link.lower() for b in BANNED):
                    jobs.append({"title": j['title'], "company": j['company_name'], "desc": j['description'], "link": link})
                if len(jobs) >= 6: break
        return jobs
    except: return []

def screening_agent(job_desc, cv_text, excluded, min_sal, lang, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"Analyze Job vs CV. Return JSON ONLY: {{'score': 0-100, 'reasons': [], 'missing': []}}. Respond in {lang}. Exclude: {excluded}. Min Sal: {min_sal}. Job: {job_desc}. CV: {cv_text}"
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.1)
        return json.loads(re.search(r'\{.*\}', chat.choices[0].message.content, re.DOTALL).group(0))
    except: return {"score": 0, "reasons": ["AI Error"], "missing": []}

def drafting_agent(job_desc, reasons, lang, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"Write a professional cover letter/email in {lang} for this job based on these matching points: {reasons}. Keep it under 150 words. Job: {job_desc}"
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.5)
        return chat.choices[0].message.content.strip()
    except: return "⚠️ Error generating draft."

def vip_consultant_agent(job_desc, cv_text, lang, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"""Act as a Senior HR Manager. Respond in {lang}. Analyze this CV against the Job Desc.
        Format your response cleanly with markdown:
        1. **3 ATS Keywords** missing from the CV.
        2. **Rewrite 1 Work Experience Bullet** to be more Result-Oriented.
        3. **1 Tough Interview Question** to prepare for.
        Job: {job_desc} | CV: {cv_text}"""
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.4)
        return chat.choices[0].message.content
    except: return "⚠️ Layanan VIP sedang sibuk / VIP Service busy."

# ==========================================
# 🚀 MAIN VIEW
# ==========================================
st.title(t["title"])
tab1, tab2 = st.tabs([t["tab_search"], t["tab_history"]])

with tab1:
    if mulai_btn:
        if not user_groq_key or not user_serp_key: st.error("⚠️ Masukkan API Keys!")
        elif not uploaded_cv: st.error("⚠️ Upload CV!")
        else:
            cv_text = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_cv).pages])
            seen = {log['Link'] for log in st.session_state.history_log}
            
            st.info(t["spin_search"])
            loker_list = [j for j in fetch_loker(query_input, location_input, date_choice, user_serp_key) if j['link'] not in seen]
            
            if not loker_list: st.warning("Belum ada loker baru / No new jobs. Coba ganti lokasi atau posisi.")
            else:
                for loker in loker_list:
                    with st.expander(f"🏢 {loker['title']} - {loker['company']}", expanded=True):
                        
                        with st.spinner(t["spin_analyze"]):
                            hasil = screening_agent(loker['desc'], cv_text, exclude_input, min_salary, lang_choice, user_groq_key)
                            skor = int(hasil.get('score', 0))
                        
                        # --- 3 KOLOM LAYOUT ---
                        c1, c2, c3 = st.columns([1, 1.5, 1.5]) # Pembagian proporsi lebar kolom
                        
                        # KOLOM 1: SKOR & ALASAN
                        with c1:
                            st.metric(t["score_lbl"], f"{skor}/100")
                            st.markdown(f"🔗 **[{t['apply_btn']}]({loker['link']})**")
                            st.markdown(t["reasons"])
                            for r in hasil.get('reasons', []): st.markdown(f"- {r}")
                            if hasil.get('missing'):
                                st.markdown(t["missing"])
                                for m in hasil.get('missing', []): st.markdown(f"- {m}")
                        
                        # KOLOM 2: DRAF EMAIL
                        with c2:
                            if skor >= min_score:
                                with st.spinner(t["spin_draft"]):
                                    draf = drafting_agent(loker['desc'], hasil.get('reasons'), lang_choice, user_groq_key)
                                    # Height 350 biar kotaknya besar dan enak dibaca
                                    st.text_area(t["draft_lbl"], value=draf, height=350, key=f"draft_{loker['link']}") 
                            else:
                                st.warning(t["low_score"])
                        
                        # KOLOM 3: VIP ANALYSIS
                        with c3:
                            if skor >= min_score:
                                if st.session_state.user_tier == "VIP":
                                    st.markdown("### 💎 VIP CV Review")
                                    with st.spinner(t["spin_vip"]):
                                        saran = vip_consultant_agent(loker['desc'], cv_text, lang_choice, user_groq_key)
                                        st.write(saran)
                                else:
                                    st.markdown("### 💎 VIP CV Review")
                                    st.info("🔒 **Fitur Terkunci.**\n\nUpgrade Lisensi kamu ke paket **Captain (VIP)** untuk mendapatkan Bedah CV Mendalam, Optimasi Keyword ATS, dan Prediksi Interview di sini.")
                        
                        # Simpan ke riwayat
                        if skor >= min_score:
                            st.session_state.history_log.append({"Date": datetime.now().strftime("%H:%M"), "Company": loker['company'], "Position": loker['title'], "Score": skor, "Link": loker['link']})

with tab2:
    if st.session_state.history_log:
        for item in reversed(st.session_state.history_log):
            st.write(f"✅ **{item['Position']}** di {item['Company']} (Score: {item['Score']}) - [Link]({item['Link']})")
        if st.button("Hapus Riwayat / Clear History"):
            st.session_state.history_log = []
            st.rerun()
    else: st.info("Belum ada riwayat pencarian / No history.")
