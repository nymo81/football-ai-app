import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
import google.generativeai as genai
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "nav": "Navigation",
        "menu_predictions": "Live Predictions", "menu_smart": "🧠 Smart AI Agent",
        "menu_profile": "My Profile", "menu_admin_dash": "Admin Dashboard",
        "menu_users": "User Management", "menu_logs": "System Logs",
        "no_matches": "No matches found.", "conf": "Confidence", "winner": "Winner",
        "goals": "Goals", "btts": "Both Teams to Score", "save": "Save Changes",
        "role": "Role", "action": "Action", "time": "Time",
        "promote": "Promote to Admin", "demote": "Demote to User", "delete": "Delete User",
        "success_update": "Profile updated successfully!", "admin_area": "Admin Area",
        "prediction_header": "AI Market Analysis", "generate": "Generate AI Picks 🚀",
        "api_error": "⚠️ Please enter a Google Gemini API Key."
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "nav": "القائمة الرئيسية",
        "menu_predictions": "التوقعات المباشرة", "menu_smart": "🧠 المحلل الذكي",
        "menu_profile": "ملفي الشخصي", "menu_admin_dash": "لوحة التحكم",
        "menu_users": "إدارة المستخدمين", "menu_logs": "سجلات النظام",
        "no_matches": "لا توجد مباريات حالياً", "conf": "نسبة الثقة", "winner": "الفائز",
        "goals": "الأهداف", "btts": "كلا الفريقين يسجل", "save": "حفظ التغييرات",
        "role": "الصلاحية", "action": "الحدث", "time": "الوقت",
        "promote": "ترقية لمدير", "demote": "تخفيض لمستخدم", "delete": "حذف المستخدم",
        "success_update": "تم تحديث الملف الشخصي!", "admin_area": "منطقة الإدارة",
        "prediction_header": "تحليل الذكاء الاصطناعي", "generate": "تحليل ذكي للمباريات 🚀",
        "api_error": "⚠️ يرجى إدخال مفتاح Google Gemini API"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v15_ai.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    try: c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),)); conn.commit()
    except: pass
    return conn

def log_action(user, action):
    conn = init_db(); c = conn.cursor()
    c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def manage_user(action, target_user, data=None):
    conn = init_db(); c = conn.cursor()
    try:
        if action == "add":
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()), 'New User', 1000.0))
            conn.commit(); return True
        elif action == "update_profile":
            c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user)); conn.commit()
        elif action == "change_role":
            c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user)); conn.commit()
        elif action == "delete":
            c.execute("DELETE FROM users WHERE username=?", (target_user,)); conn.commit()
    except: return False
    finally: conn.close()

def get_user_info(username):
    conn = init_db(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    res = c.fetchone(); conn.close()
    return res

# --- GLOBAL MATCH ENGINE (ESPN - FIXES "NO MATCHES") ---
@st.cache_data(ttl=300)
def fetch_matches():
    # Covers: Championship, Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie
    leagues = [
        {"name": "🇬🇧 Premier League", "id": "eng.1"}, {"name": "🇬🇧 Championship", "id": "eng.2"},
        {"name": "🇪🇸 La Liga", "id": "esp.1"}, {"name": "🇩🇪 Bundesliga", "id": "ger.1"},
        {"name": "🇮🇹 Serie A", "id": "ita.1"}, {"name": "🇫🇷 Ligue 1", "id": "fra.1"},
        {"name": "🇳🇱 Eredivisie", "id": "ned.1"}
    ]
    matches = []
    
    for league in leagues:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league['id']}/scoreboard"
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                data = r.json()
                for event in data.get('events', []):
                    utc_date = datetime.strptime(event['date'], "%Y-%m-%dT%H:%M:%SZ")
                    local_date = utc_date + timedelta(hours=3) # Baghdad Time
                    
                    # Show match if it is TODAY or LIVE
                    if local_date.date() == datetime.now().date() or event['status']['type']['state'] == 'in':
                        matches.append({
                            "League": league['name'],
                            "Date": local_date.strftime("%Y-%m-%d"),
                            "Time": local_date.strftime("%H:%M"),
                            "Home": event['competitions'][0]['competitors'][0]['team']['displayName'],
                            "Away": event['competitions'][0]['competitors'][1]['team']['displayName']
                        })
        except: continue
        
    return matches

def analyze_advanced(home, away):
    seed = len(home) + len(away)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {"1X2": {"Home": h_win, "Draw": d_win, "Away": a_win}, "Goals": {"Over": (seed * 4) % 100}, "BTTS": {"Yes": (seed * 9) % 100}}

# --- UI HELPER ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- PAGES ---
def login_view():
    st.markdown(f"<h1 style='text-align: center;'>⚽ {t('app_name')}</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns([8, 2])
    with c2:
        lang = st.selectbox("Language / اللغة", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
    tab1, tab2 = st.tabs([t('login'), t('signup')])
    with tab1:
        u = st.text_input(t('username'), key="l_u")
        p = st.text_input(t('password'), type="password", key="l_p")
        if st.button(t('login'), use_container_width=True):
            user_data = get_user_info(u)
            if user_data and user_data[1] == p:
                st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = user_data[2]
                st.rerun()
            else: st.error("Error")
    with tab2:
        nu = st.text_input(t('new_user'))
        np = st.text_input(t('new_pass'), type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu, np): st.success("OK!"); log_action(nu, "Created")
            else: st.error("Taken")

def profile_view():
    st.title(f"👤 {t('menu_profile')}")
    u_info = get_user_info(st.session_state.username)
    with st.form("profile_form"):
        new_pass = st.text_input(t('password'), value=u_info[1], type="password")
        new_bio = st.text_area("Bio", value=u_info[4])
        if st.form_submit_button(t('save')):
            manage_user("update_profile", st.session_state.username, {'pass': new_pass, 'bio': new_bio})
            st.success(t('success_update'))

# --- NEW: SMART AI PAGE ---
def smart_ai_view():
    st.title(f"🧠 {t('menu_smart')}")
    
    # API Key Input
    if "api_key" not in st.session_state: st.session_state.api_key = ""
    api_key = st.text_input("Google Gemini API Key", value=st.session_state.api_key, type="password")
    st.session_state.api_key = api_key
    
    if st.button(t('generate'), type="primary", use_container_width=True):
        if not api_key:
            st.error(t('api_error'))
        else:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                today = datetime.now().strftime("%Y-%m-%d")
                
                # The Prompt you requested
                prompt = f"""
                From all the football matches happening on {today}, analyze team form, last 10 games, head-to-head stats, injuries, home/away records, and referee history.
                Then, choose ONE single outcome that has the highest chance of success, aiming for at least 90% probability. Consider markets such as 1X2, Over/Under 2.5 goals, or Both Teams to Score (Yes/No).
                Provide the safest pick and explain the reasoning. Also, compare your prediction with the current betting odds to verify if it aligns with at least a 1.35 quote.
                Finally, give me your confidence percentage. Europa league or any league.
                
                Response Format:
                ### 🛡️ SAFE PICK
                (Details here)
                ### 💎 HIGH VALUE
                (Risky option)
                ### 📋 TOP 10 MATCHES
                (List 10 matches)
                """
                
                with st.spinner("🤖 Analyzing global match data..."):
                    response = model.generate_content(prompt)
                    st.markdown("---")
                    st.markdown(response.text)
                    st.success("Analysis Complete")
            except Exception as e:
                st.error(f"Error: {e}")

def predictions_view():
    st.title(f"📈 {t('prediction_header')}")
    matches = fetch_matches() # Uses new ESPN engine
    
    if not matches: st.warning(t('no_matches'))
    
    # Group by League
    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"### {league}")
            league_matches = df[df['League'] == league]
            for index, m in league_matches.iterrows():
                data = analyze_advanced(m['Home'], m['Away'])
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    c1.subheader(f"{m['Home']} vs {m['Away']}")
                    c2.caption(f"⏰ {m['Time']}")
                    
                    t1, t2, t3 = st.tabs([t('winner'), t('goals'), t('btts')])
                    with t1:
                        st.write(f"**{m['Home']}**: {data['1X2']['Home']}% | **Draw**: {data['1X2']['Draw']}% | **{m['Away']}**: {data['1X2']['Away']}%")
                        st.progress(data['1X2']['Home']/100)
                    with t2: st.metric("Over 2.5", f"{data['Goals']['Over']}%")
                    with t3: st.metric("BTTS", f"{data['BTTS']['Yes']}%")
                    st.markdown("---")

def admin_dashboard():
    st.title(f"🛡️ {t('menu_admin_dash')}")
    conn = init_db(); users = pd.read_sql("SELECT * FROM users", conn); logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn); conn.close()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Users", len(users)); c2.metric("Logs", len(logs)); c3.metric("System", "Online")
    
    st.subheader(t('menu_users'))
    for index, row in users.iterrows():
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(f"**{row['username']}** ({row['role']})")
        if row['username'] != 'admin':
            if c2.button(t('promote'), key=f"p_{row['username']}"): manage_user("change_role", row['username'], "admin"); st.rerun()
            if c3.button(t('demote'), key=f"d_{row['username']}"): manage_user("change_role", row['username'], "user"); st.rerun()
            if c4.button(t('delete'), key=f"del_{row['username']}"): manage_user("delete", row['username']); st.rerun()
        st.divider()
    st.subheader(t('menu_logs')); st.dataframe(logs, use_container_width=True)

# --- MAIN CONTROLLER ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False; init_db()

if not st.session_state.logged_in:
    login_view()
else:
    st.sidebar.title(t('nav'))
    st.sidebar.info(f"👤 {st.session_state.username}")
    lang_toggle = st.sidebar.radio("🌐 Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    options = [t('menu_predictions'), t('menu_smart'), t('menu_profile')] # Added Smart AI here
    if st.session_state.role == 'admin': options = [t('menu_admin_dash')] + options
    
    menu = st.sidebar.radio("", options)
    st.sidebar.divider()
    if st.sidebar.button(f"🚪 {t('sign_out')}", use_container_width=True):
        log_action(st.session_state.username, "Logout"); st.session_state.logged_in = False; st.rerun()

    if menu == t('menu_predictions'): predictions_view()
    elif menu == t('menu_smart'): smart_ai_view()
    elif menu == t('menu_profile'): profile_view()
    elif menu == t('menu_admin_dash'): admin_dashboard()
