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

# Master Keys (Ganti sesuka lo bro)
BETA_KEYS = {
    "PRO2026": "Standard",
    "CAPTAIN2026": "VIP"
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
    1. Isi **API Keys** (Groq & SerpAPI) di sidebar.
    2. Masukkan posisi kerja (misal: *Data Analyst*) dan Lokasi.
    3. Upload CV PDF kamu.
    4. Klik **Mulai Berburu Loker**.
    
    {"✨ **Fitur VIP Aktif:** Kamu punya akses ke Analisa CV Mendalam & ATS Optimizer!" if st.session_state.user_tier == "VIP" else "💡 **Tips:** Upgrade ke VIP untuk analisa CV mendalam."}
    
    ---
    🔒 *Data CV & History hanya disimpan di memori browser kamu (Session State). Aman & Privat.*
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
    
    st.header("🔑 API Keys")
    user_groq_key = st.text_input("Groq API Key", type="password")
    user_serp_key = st.text_input("SerpAPI Key", type="password")
    
    st.markdown("---")
    st.header("⚙️ Filter Pencarian")
    query_input = st.text_input("Posisi Kerja", "")
    location_input = st.text_input("Lokasi", "")
    date_choice = st.selectbox("Waktu Posting", ["Semua waktu", "24 Jam terakhir", "3 Hari terakhir", "Seminggu terakhir"])
    
    st.markdown("---")
    exclude_input = st.text_input("Hindari Kata Kunci", "Alcohol, Gambling, Betting")
    min_salary = st.number_input("Target Gaji Minimal", value=0, step=1000000)
    min_score = st.slider("Minimal Skor Cocok", 50, 100, 75)
    
    st.markdown("---")
    uploaded_cv = st.file_uploader("Upload CV (PDF)", type=["pdf"])
    mulai_btn = st.button("🚀 Mulai Berburu Loker", use_container_width=True)

# ==========================================
# 🧠 AGENT LOGIC
# ==========================================
def fetch_loker(query, location, date_choice, serp_key):
    try:
        date_map = {"Semua waktu": "", "24 Jam terakhir": "date_posted:today", "3 Hari terakhir": "date_posted:3days", "Seminggu terakhir": "date_posted:week"}
        params = {"engine": "google_jobs", "q": f"{query} {location}", "hl": "id", "gl": "id", "api_key": serp_key}
        if date_map[date_choice]: params["chips"] = date_map[date_choice]
        
        res = requests.get("https://serpapi.com/search.json", params=params).json()
        jobs = []
        BANNED = ["jooble", "trovit", "trabajo", "jobisjob"]
        PREF = ["linkedin", "jobstreet", "glints", "kalibrr"]

        if "jobs_results" in res:
            for j in res["jobs_results"]:
                opts = j.get("apply_options", [])
                link = next((o['link'] for o in opts if any(p in o['link'].lower() for p in PREF)), opts[0]['link'] if opts else "")
                if link and not any(b in link.lower() for b in BANNED):
                    jobs.append({"title": j['title'], "company": j['company_name'], "desc": j['description'], "link": link})
                if len(jobs) >= 8: break
        return jobs
    except: return []

def screening_agent(job_desc, cv_text, excluded, min_sal, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"Analyze Job vs CV. Return JSON ONLY: {{'score': 0-100, 'reasons': [], 'missing': []}}. Exclude: {excluded}. Min Sal: {min_sal}. Job: {job_desc}. CV: {cv_text}"
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.1)
        return json.loads(re.search(r'\{.*\}', chat.choices[0].message.content, re.DOTALL).group(0))
    except: return {"score": 0, "reasons": ["AI Error"], "missing": []}

def vip_consultant_agent(job_desc, cv_text, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = f"""Bertindaklah sebagai Senior HR Manager. Berikan analisa CV mendalam untuk posisi ini:
        1. 3 Keyword ATS yang WAJIB ditambah ke CV.
        2. Tulis ulang 1 poin pengalaman kerja agar lebih 'Powerfull' (Result-Oriented).
        3. 1 Pertanyaan interview tersulit yang mungkin muncul.
        Job: {job_desc} | CV: {cv_text}"""
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant", temperature=0.4)
        return chat.choices[0].message.content
    except: return "Layanan VIP sedang sibuk."

# ==========================================
# 🚀 MAIN VIEW
# ==========================================
tab1, tab2 = st.tabs(["🔍 Cari Loker", "📁 Riwayat"])

with tab1:
    if mulai_btn:
        if not user_groq_key or not user_serp_key: st.error("Isi API Keys dulu bro!")
        elif not uploaded_cv: st.error("Upload CV dulu!")
        else:
            cv_text = "".join([p.extract_text() for p in PyPDF2.PdfReader(uploaded_cv).pages])
            seen = {log['Link'] for log in st.session_state.history_log}
            
            st.info("Sedang memindai langit lowongan kerja...")
            loker_list = [j for j in fetch_loker(query_input, location_input, date_choice, user_serp_key) if j['link'] not in seen]
            
            if not loker_list: st.warning("Belum ada loker baru. Coba ganti lokasi atau posisi.")
            else:
                for loker in loker_list:
                    with st.expander(f"🏢 {loker['title']} - {loker['company']}", expanded=True):
                        hasil = screening_agent(loker['desc'], cv_text, exclude_input, min_salary, user_groq_key)
                        skor = int(hasil.get('score', 0))
                        
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.metric("Match Score", f"{skor}/100")
                            st.markdown(f"🔗 [Lamar Sekarang]({loker['link']})")
                        with c2:
                            st.markdown("**Alasan Cocok:**")
                            for r in hasil.get('reasons', []): st.markdown(f"- {r}")
                        
                        # FITUR VIP
                        if st.session_state.user_tier == "VIP" and skor >= min_score:
                            st.markdown("---")
                            st.markdown("### 💎 VIP Analysis (ATS & Career Advice)")
                            with st.spinner("Konsultan AI sedang membedah CV kamu..."):
                                saran = vip_consultant_agent(loker['desc'], cv_text, user_groq_key)
                                st.write(saran)
                        
                        if skor >= min_score:
                            st.session_state.history_log.append({"Date": datetime.now().strftime("%H:%M"), "Company": loker['company'], "Position": loker['title'], "Score": skor, "Link": loker['link']})

with tab2:
    if st.session_state.history_log:
        for item in reversed(st.session_state.history_log):
            st.write(f"✅ **{item['Position']}** di {item['Company']} (Score: {item['Score']}) - [Link]({item['Link']})")
        if st.button("Hapus Riwayat"):
            st.session_state.history_log = []
            st.rerun()
    else: st.info("Belum ada riwayat pencarian.")
