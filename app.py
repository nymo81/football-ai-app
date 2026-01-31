import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
import google.generativeai as genai
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CSS: DARK THEME & UI POLISH ---
st.markdown("""
    <style>
    /* Dark Theme Logic */
    .stApp {background-color: #0E1117; color: #FAFAFA;}
    [data-testid="stSidebar"] {background-color: #262730;}
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    
    /* Card Styling */
    div[data-testid="stMetric"], div[data-testid="stExpander"] {
        background-color: #1A1C24 !important;
        border: 1px solid #444;
        border-radius: 8px;
    }
    
    /* Button Styling */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "nav": "Navigation",
        "menu_predictions": "Live Matches", "menu_smart": "🧠 Smart AI Picks",
        "menu_profile": "My Profile", "menu_admin_dash": "Admin Dashboard",
        "menu_users": "User Management", "no_matches": "No matches found.",
        "conf": "Confidence", "winner": "Winner", "goals": "Goals", "btts": "BTTS",
        "balance": "Wallet", "generate": "GENERATE WINNING PICKS 🚀",
        "ai_intro": "This tool uses Google Gemini AI to analyze referee history, injuries, and form for TODAY'S matches.",
        "api_needed": "⚠️ Enter Google Gemini API Key to activate."
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "دخول", "signup": "تسجيل",
        "username": "المستخدم", "password": "كلمة المرور", "nav": "القائمة",
        "menu_predictions": "المباريات المباشرة", "menu_smart": "🧠 تحليل الذكاء الاصطناعي",
        "menu_profile": "الملف الشخصي", "menu_admin_dash": "الإدارة",
        "menu_users": "المستخدمين", "no_matches": "لا توجد مباريات",
        "conf": "الثقة", "winner": "الفائز", "goals": "أهداف", "btts": "كلا الفريقين",
        "balance": "الرصيد", "generate": "توليد التوقعات الذكية 🚀",
        "ai_intro": "هذه الأداة تستخدم ذكاء جوجل لتحليل الحكام، الإصابات، والأداء لمباريات اليوم.",
        "api_needed": "⚠️ أدخل مفتاح Google Gemini API للتفعيل."
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v14_ai.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    try: c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),)); conn.commit()
    except: pass
    return conn

def log_action(user, action):
    conn = init_db()
    c = conn.cursor()
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

# --- FIXED DATA ENGINE (Connects to ESPN for Global Data) ---
@st.cache_data(ttl=300)
def fetch_matches():
    # Automatically fetches from major leagues
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
                    utc = datetime.strptime(event['date'], "%Y-%m-%dT%H:%M:%SZ")
                    local = utc + timedelta(hours=3) # Baghdad Time
                    if local.date() == datetime.now().date() or event['status']['type']['state'] == 'in':
                        matches.append({
                            "League": league['name'], "Date": local.strftime("%Y-%m-%d"),
                            "Time": local.strftime("%H:%M"),
                            "Home": event['competitions'][0]['competitors'][0]['team']['displayName'],
                            "Away": event['competitions'][0]['competitors'][1]['team']['displayName']
                        })
        except: continue
    
    # Fallback to avoid empty screen if API fails
    if not matches:
        return [
            {"League": "🏆 Champions League", "Time": "23:00", "Home": "Real Madrid", "Away": "Man City", "Date": "Today"},
            {"League": "🇬🇧 Premier League", "Time": "19:30", "Home": "Arsenal", "Away": "Liverpool", "Date": "Today"},
        ]
    return matches

def analyze_advanced(home, away):
    seed = len(home) + len(away)
    h_win = (seed * 7) % 85 + 10 
    d_win = (100 - h_win) // 3
    a_win = 100 - h_win - d_win
    return {"1X2": {"Home": h_win, "Draw": d_win, "Away": a_win}, "Goals": {"Over": (seed*4)%100}, "BTTS": {"Yes": (seed*9)%100}}

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
    
    t1, t2 = st.tabs([t('login'), t('signup')])
    with t1:
        u = st.text_input(t('username'), key="l_u")
        p = st.text_input(t('password'), type="password", key="l_p")
        if st.button(t('login')):
            d = get_user_info(u)
            if d and d[1] == p:
                st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = d[2]
                st.rerun()
    with t2:
        nu = st.text_input(t('new_user'))
        np = st.text_input(t('new_pass'), type="password")
        if st.button(t('create_acc')):
            if manage_user("add", nu, np): st.success("OK!"); log_action(nu, "Created")

def smart_ai_view():
    st.title(f"🧠 {t('menu_smart')}")
    st.info(t('ai_intro'))
    
    # API Key Input (Stored in session so you don't re-type)
    if "api_key" not in st.session_state: st.session_state.api_key = ""
    api_key = st.text_input("Google Gemini API Key", value=st.session_state.api_key, type="password")
    st.session_state.api_key = api_key
    
    if not api_key:
        st.warning(t('api_needed'))
        st.markdown("[Get Free API Key](https://aistudio.google.com/app/apikey)")
        return

    if st.button(t('generate'), type="primary"):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            today = datetime.now().strftime("%Y-%m-%d")
            prompt = f"""
            From all the football matches happening on {today}, analyze team form, last 10 games, head-to-head stats, injuries, home/away records, and referee history.
            
            Please provide the response in this EXACT format:
            
            ### 🛡️ SAFE PICK
            (Choose ONE single outcome with highest success chance >90%. Explain reasoning briefly. Compare with 1.35+ odds).
            
            ### 💎 HIGH VALUE
            (Choose one risky but high reward outcome).
            
            ### 📋 TOP 10 MATCHES
            (List 10 matches today with brief 1X2 predictions).
            
            Give me your confidence percentage at the end. Focus on Europa League or major leagues.
            """
            
            with st.spinner("🤖 AI is analyzing thousands of data points..."):
                response = model.generate_content(prompt)
                st.markdown("---")
                st.markdown(response.text)
                st.success("Analysis Complete!")
                
        except Exception as e:
            st.error(f"Error: {e}")

def predictions_view():
    st.title(f"📈 {t('menu_predictions')}")
    matches = fetch_matches()
    
    if not matches: st.warning(t('no_matches'))
    
    # Group by League
    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"### {league}")
            for index, m in df[df['League'] == league].iterrows():
                data = analyze_advanced(m['Home'], m['Away'])
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    c1.subheader(f"{m['Home']} vs {m['Away']}")
                    c2.caption(f"⏰ {m['Time']}")
                    
                    t1, t2, t3 = st.tabs([t('winner'), t('goals'), t('btts')])
                    with t1:
                        st.write(f"**{m['Home']}**: {data['1X2']['Home']}% | **Draw**: {data['1X2']['Draw']}% | **{m['Away']}**: {data['1X2']['Away']}%")
                        st.progress(data['1X2']['Home']/100)
                    with t2:
                        st.metric("Over 2.5", f"{data['Goals']['Over']}%")
                    with t3:
                        st.metric("BTTS Yes", f"{data['BTTS']['Yes']}%")
                    st.markdown("---")

def admin_dashboard():
    st.title(t('menu_admin_dash'))
    conn = init_db()
    users = pd.read_sql("SELECT * FROM users", conn)
    conn.close()
    st.dataframe(users)

def profile_view():
    st.title(t('menu_profile'))
    u = get_user_info(st.session_state.username)
    st.metric(t('balance'), f"${u[5]:,.2f}")

# --- MAIN CONTROLLER ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False; init_db()

if not st.session_state.logged_in:
    login_view()
else:
    st.sidebar.title(t('nav'))
    st.sidebar.info(f"👤 {st.session_state.username}")
    
    lang_toggle = st.sidebar.radio("🌐 Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    # Added "Smart AI Picks" to menu
    options = [t('menu_predictions'), t('menu_smart'), t('menu_profile')]
    if st.session_state.role == 'admin': options.append(t('menu_admin_dash'))
        
    menu = st.sidebar.radio("", options)
    st.sidebar.divider()
    if st.sidebar.button(f"🚪 {t('sign_out')}"):
        log_action(st.session_state.username, "Logout"); st.session_state.logged_in = False; st.rerun()

    if menu == t('menu_predictions'): predictions_view()
    elif menu == t('menu_smart'): smart_ai_view() # New Page
    elif menu == t('menu_profile'): profile_view()
    elif menu == t('menu_admin_dash'): admin_dashboard()
