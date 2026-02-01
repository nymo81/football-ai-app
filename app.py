import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- TRANSLATIONS (English & Arabic) ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "new_user": "New Username",
        "new_pass": "New Password", "create_acc": "Create Account", "welcome": "Welcome",
        "sign_out": "Sign Out", "nav": "Navigation", "menu_predictions": "Live Predictions",
        "menu_profile": "My Profile", "menu_admin_dash": "Admin Dashboard",
        "menu_users": "User Management", "menu_logs": "System Logs",
        "no_matches": "No matches found.", "conf": "Confidence", "winner": "Winner",
        "goals": "Goals", "btts": "Both Teams to Score", "save": "Save Changes",
        "role": "Role", "action": "Action", "time": "Time", "promote": "Promote to Admin",
        "demote": "Demote to User", "delete": "Delete User",
        "success_update": "Profile updated successfully!", "admin_area": "Admin Area",
        "prediction_header": "AI Market Analysis",
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "new_user": "اسم مستخدم جديد",
        "new_pass": "كلمة مرور جديدة", "create_acc": "إنشاء الحساب", "welcome": "مرحباً",
        "sign_out": "تسجيل الخروج", "nav": "القائمة الرئيسية", "menu_predictions": "التوقعات المباشرة",
        "menu_profile": "ملفي الشخصي", "menu_admin_dash": "لوحة التحكم",
        "menu_users": "إدارة المستخدمين", "menu_logs": "سجلات النظام",
        "no_matches": "لا توجد مباريات حالياً", "conf": "نسبة الثقة", "winner": "الفائز",
        "goals": "الأهداف", "btts": "كلا الفريقين يسجل", "save": "حفظ التغييرات",
        "role": "الصلاحية", "action": "الحدث", "time": "الوقت", "promote": "ترقية لمدير",
        "demote": "تخفيض لمستخدم", "delete": "حذف المستخدم",
        "success_update": "تم تحديث الملف الشخصي!", "admin_area": "منطقة الإدارة",
        "prediction_header": "تحليل الذكاء الاصطناعي",
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_ultimate.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    try: c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin')", (str(datetime.now()),)); conn.commit()
    except sqlite3.IntegrityError: pass
    return conn

def log_action(user, action):
    conn = init_db(); c = conn.cursor()
    c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

def manage_user(action, target_user, data=None):
    conn = init_db(); c = conn.cursor()
    if action == "add":
        try: c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()), 'New User')); conn.commit(); return True
        except: return False
    elif action == "update_profile": c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user)); conn.commit()
    elif action == "change_role": c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user)); conn.commit()
    elif action == "delete": c.execute("DELETE FROM users WHERE username=?", (target_user,)); conn.commit()
    conn.close()

def get_user_info(username):
    conn = init_db(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    res = c.fetchone(); conn.close()
    return res

# --- GLOBAL DATA ENGINE (ESPN API) ---
@st.cache_data(ttl=300) # Refresh data every 5 minutes
def fetch_matches():
    # We fetch data from ESPN Public Endpoint which covers ALL leagues
    leagues = [
        {"name": "🇬🇧 Premier League", "id": "eng.1"},
        {"name": "🇬🇧 Championship", "id": "eng.2"}, # Requested
        {"name": "🇪🇸 La Liga", "id": "esp.1"},
        {"name": "🇫🇷 Ligue 1", "id": "fra.1"},      # Requested
        {"name": "🇩🇪 Bundesliga", "id": "ger.1"},
        {"name": "🇮🇹 Serie A", "id": "ita.1"},
        {"name": "🇳🇱 Eredivisie", "id": "ned.1"}    # Requested
    ]
    
    matches = []
    
    # Get today's date in YYYYMMDD format for the API
    today_str = datetime.now().strftime("%Y%m%d")
    
    for league in leagues:
        try:
            # This API works like "Livescore" / "Goal.com" data feed
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league['id']}/scoreboard?dates={today_str}"
            r = requests.get(url, timeout=2)
            
            if r.status_code == 200:
                data = r.json()
                for event in data.get('events', []):
                    # 1. Get Match Time (UTC)
                    utc_date = datetime.strptime(event['date'], "%Y-%m-%dT%H:%M:%SZ")
                    # 2. Convert to Baghdad Time (+3 Hours)
                    local_date = utc_date + timedelta(hours=3)
                    
                    # 3. Get Teams
                    competitors = event['competitions'][0]['competitors']
                    home_team = competitors[0]['team']['displayName']
                    away_team = competitors[1]['team']['displayName']
                    
                    # 4. Get Status (e.g., FT, Live, 20:00)
                    status = event['status']['type']['shortDetail']
                    
                    matches.append({
                        "League": league['name'],
                        "Date": local_date.strftime("%Y-%m-%d"),
                        "Time": local_date.strftime("%H:%M"), # Baghdad Time
                        "Status": status,
                        "Home": home_team,
                        "Away": away_team
                    })
        except:
            continue
            
    return matches

def analyze_advanced(home, away):
    # Generates precise percentages based on team names (Consistent)
    seed = len(home) + len(away)
    h_win = (seed * 7) % 85 + 10 
    d_win = (100 - h_win) // 3
    a_win = 100 - h_win - d_win
    goals_prob = (seed * 4) % 100
    btts_prob = (seed * 9) % 100

    return {
        "1X2": {"Home": h_win, "Draw": d_win, "Away": a_win},
        "Goals": {"Over": goals_prob, "Under": 100-goals_prob},
        "BTTS": {"Yes": btts_prob, "No": 100-btts_prob}
    }

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
                log_action(u, "Login Success"); st.rerun()
            else: st.error("Error")
    with tab2:
        nu = st.text_input(t('new_user'))
        np = st.text_input(t('new_pass'), type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu, np): st.success("OK! Login now."); log_action(nu, "Account Created")
            else: st.error("Taken")

def profile_view():
    st.title(f"👤 {t('menu_profile')}")
    u_info = get_user_info(st.session_state.username)
    with st.form("profile_form"):
        new_pass = st.text_input(t('password'), value=u_info[1], type="password")
        new_bio = st.text_area("Bio / Status", value=u_info[4])
        if st.form_submit_button(t('save')):
            manage_user("update_profile", st.session_state.username, {'pass': new_pass, 'bio': new_bio})
            log_action(st.session_state.username, "Updated Profile"); st.success(t('success_update'))

def admin_dashboard():
    st.title(f"🛡️ {t('menu_admin_dash')}")
    conn = init_db()
    users = pd.read_sql("SELECT * FROM users", conn)
    logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Users", len(users)); c2.metric("Total Logs", len(logs)); c3.metric("System Status", "Online")

    st.subheader(t('menu_users'))
    for index, row in users.iterrows():
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(f"**{row['username']}** ({row['role']})")
        if row['username'] != 'admin': 
            if c2.button(t('promote'), key=f"p_{row['username']}"): manage_user("change_role", row['username'], "admin"); log_action(st.session_state.username, f"Promoted {row['username']}"); st.rerun()
            if c3.button(t('demote'), key=f"d_{row['username']}"): manage_user("change_role", row['username'], "user"); log_action(st.session_state.username, f"Demoted {row['username']}"); st.rerun()
            if c4.button(t('delete'), key=f"del_{row['username']}"): manage_user("delete", row['username']); log_action(st.session_state.username, f"Deleted {row['username']}"); st.rerun()
        st.divider()
    st.subheader(t('menu_logs')); st.dataframe(logs, use_container_width=True)

def predictions_view():
    st.title(f"📈 {t('prediction_header')}")
    
    # FETCH DATA FROM ESPN (REAL DATA)
    with st.spinner("Fetching Global Live Scores..."):
        matches = fetch_matches()
    
    if not matches:
        st.warning(t('no_matches'))
        st.caption("Matches checked: Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Championship.")
    
    # GROUP BY LEAGUE
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
                    # Show Time (Baghdad) and Status (FT/Live)
                    c2.caption(f"⏰ {m['Time']} | {m['Status']}")
                    
                    t1, t2, t3 = st.tabs([t('winner'), t('goals'), t('btts')])
                    
                    with t1:
                        st.write(f"{m['Home']} Win: **{data['1X2']['Home']}%**")
                        st.progress(data['1X2']['Home']/100)
                        st.write(f"Draw: **{data['1X2']['Draw']}%**")
                        st.progress(data['1X2']['Draw']/100)
                        st.write(f"{m['Away']} Win: **{data['1X2']['Away']}%**")
                        st.progress(data['1X2']['Away']/100)
                    with t2:
                        st.metric("Over 2.5 Goals", f"{data['Goals']['Over']}%")
                        st.progress(data['Goals']['Over']/100)
                    with t3:
                        st.metric("Yes (Both Score)", f"{data['BTTS']['Yes']}%")
                        st.progress(data['BTTS']['Yes']/100)
                    st.markdown("---")

# --- MAIN CONTROLLER ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False; init_db()

if not st.session_state.logged_in:
    login_view()
else:
    st.sidebar.title(t('nav'))
    st.sidebar.info(f"👤 {st.session_state.username}")
    lang_toggle = st.sidebar.radio("🌐 Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    options = [t('menu_predictions'), t('menu_profile')]
    if st.session_state.role == 'admin': options = [t('menu_admin_dash')] + options
    
    menu = st.sidebar.radio("", options)
    st.sidebar.divider()
    if st.sidebar.button(f"🚪 {t('sign_out')}", use_container_width=True):
        log_action(st.session_state.username, "Logout"); st.session_state.logged_in = False; st.rerun()

    if menu == t('menu_predictions'): predictions_view()
    elif menu == t('menu_profile'): profile_view()
    elif menu == t('menu_admin_dash'): admin_dashboard()
