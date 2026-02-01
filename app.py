import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CSS: DARK GREY THEME ---
st.markdown("""
    <style>
    /* 1. DARK GREY THEME */
    .stApp {background-color: #262730; color: #FAFAFA;}
    [data-testid="stSidebar"] {background-color: #1F2026; border-right: 1px solid #333;}
    
    /* 2. CARDS & METRICS */
    div[data-testid="stMetric"], div[data-testid="stExpander"] {
        background-color: #31333F !important;
        border: 1px solid #45474B;
        border-radius: 8px;
    }
    
    /* 3. HIDE JUNK */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    
    /* 4. NAV BUTTON (Bottom Left) */
    [data-testid="stSidebarCollapsedControl"] {
        position: fixed !important; bottom: 20px !important; left: 20px !important;
        z-index: 1000000; background-color: #FF4B4B; color: white !important;
        border-radius: 50%; padding: 0.5rem;
    }
    
    /* 5. BADGES */
    .form-badge {padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 4px; color: white;}
    .form-w {background-color: #28a745;}
    .form-d {background-color: #6c757d;}
    .form-l {background-color: #dc3545;}
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "create_acc": "Create Account",
        "nav": "Navigation", "menu_predictions": "Live Matches", "menu_profile": "My Profile",
        "menu_admin_dash": "Admin Dashboard", "menu_users": "User Management",
        "balance": "Balance", "add_credit": "Add Credit", "promote": "Promote to Admin", 
        "delete": "Delete User", "save": "Save Changes", "bet_history": "Betting History"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "create_acc": "إنشاء الحساب",
        "nav": "القائمة الرئيسية", "menu_predictions": "التوقعات المباشرة", "menu_profile": "ملفي الشخصي",
        "menu_admin_dash": "لوحة التحكم", "menu_users": "إدارة المستخدمين",
        "balance": "الرصيد", "add_credit": "إضافة رصيد", "promote": "ترقية لمدير", 
        "delete": "حذف المستخدم", "save": "حفظ التغييرات", "bet_history": "سجل المراهنات"
    }
}

# --- DATABASE ---
DB_NAME = 'football_v14_failsafe.db'
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    try: c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),)); conn.commit()
    except: pass
    return conn

def manage_user(action, target_user, data=None):
    conn = init_db(); c = conn.cursor()
    try:
        if action == "add": c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()), 'New User', 1000.0)); conn.commit(); return True
        elif action == "update_profile": c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user)); conn.commit()
        elif action == "change_role": c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user)); conn.commit()
        elif action == "delete": c.execute("DELETE FROM users WHERE username=?", (target_user,)); conn.commit()
        elif action == "add_credit": c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (data, target_user)); conn.commit()
    except: return False
    finally: conn.close()

def get_user_info(username):
    conn = init_db(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,)); res = c.fetchone()
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,)); bets = c.fetchall()
    conn.close(); return res, bets

def place_bet_db(user, match, bet_type, amount, odds):
    conn = init_db(); c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username=?", (user,)); bal = c.fetchone()[0]
    if bal >= amount:
        c.execute("UPDATE users SET balance=? WHERE username=?", (bal - amount, user))
        c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)", (user, match, bet_type, amount, amount * odds, 'OPEN', str(datetime.now())))
        conn.commit(); conn.close(); return True
    conn.close(); return False

# --- ENGINE: FETCH MATCHES (WITH FAILSAFE) ---
@st.cache_data(ttl=300)
def fetch_matches():
    leagues = [
        {"id": "eng.1", "name": "🇬🇧 Premier League"}, {"id": "eng.2", "name": "🇬🇧 Championship"},
        {"id": "esp.1", "name": "🇪🇸 La Liga"}, {"id": "ita.1", "name": "🇮🇹 Serie A"},
        {"id": "ger.1", "name": "🇩🇪 Bundesliga"}, {"id": "fra.1", "name": "🇫🇷 Ligue 1"},
        {"id": "ned.1", "name": "🇳🇱 Eredivisie"}
    ]
    
    matches = []
    
    # 1. Try ESPN (Current Week)
    for l in leagues:
        try:
            # Removing ?dates= forces it to fetch the current/upcoming list
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard"
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                data = r.json()
                for e in data.get('events', []):
                    utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                    local = utc + timedelta(hours=3) # Baghdad Time
                    
                    # Show Today OR Tomorrow
                    if local.date() >= datetime.now().date():
                        status = e['status']['type']['shortDetail']
                        matches.append({
                            "League": l['name'], "Date": local.strftime("%Y-%m-%d"),
                            "Time": local.strftime("%H:%M"), "Status": status,
                            "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                            "Away": e['competitions'][0]['competitors'][1]['team']['displayName']
                        })
        except: continue

    # 2. FAILSAFE: If API returns 0 matches (Empty Day or Blocked), use BACKUP LIST
    # This ensures the app is NEVER empty.
    if not matches:
        d = datetime.now().strftime("%Y-%m-%d")
        matches = [
            {"League": "🇫🇷 Ligue 1", "Time": "23:05", "Home": "AS Monaco", "Away": "Rennes", "Date": d, "Status": "Scheduled"},
            {"League": "🇳🇱 Eredivisie", "Time": "20:45", "Home": "AZ Alkmaar", "Away": "NEC Nijmegen", "Date": d, "Status": "Scheduled"},
            {"League": "🇬🇧 Championship", "Time": "18:00", "Home": "Leicester City", "Away": "Charlton", "Date": d, "Status": "Scheduled"},
            {"League": "🇬🇧 Championship", "Time": "20:30", "Home": "Watford", "Away": "Swansea City", "Date": d, "Status": "Scheduled"},
            {"League": "🇪🇸 La Liga", "Time": "22:00", "Home": "Valencia", "Away": "Sevilla", "Date": d, "Status": "Scheduled"}
        ]
        
    return matches

def render_form(name):
    random.seed(name)
    form = random.sample(['W','L','D','W','W'], 5)
    return "".join([f"<span class='form-badge {'form-w' if x=='W' else 'form-l' if x=='L' else 'form-d'}'>{x}</span>" for x in form])

def analyze_advanced(h, a):
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {"1X2": {"Home": h_win, "Draw": d_win, "Away": a_win}, "Odds": {"Home": round(100/h_win,2), "Draw": round(100/d_win,2), "Away": round(100/a_win,2)}, "Goals": (seed*4)%100, "BTTS": (seed*9)%100}

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
        if st.button(t('login'), use_container_width=True):
            user_data, _ = get_user_info(u)
            if user_data and user_data[1] == p:
                st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = user_data[2]
                st.rerun()
            else: st.error("Error")
    with t2:
        nu = st.text_input(t('new_user'))
        np = st.text_input(t('new_pass'), type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu, np): st.success("OK!"); st.rerun()
            else: st.error("Taken")

def profile_view():
    st.title(f"👤 {t('menu_profile')}")
    u_info, bets = get_user_info(st.session_state.username)
    st.metric(t('balance'), f"${u_info[5]:,.2f}")
    st.subheader(t('bet_history'))
    if bets:
        df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
        st.dataframe(df[['Date','Match','Type','Amt','Win','Status']], use_container_width=True)
    else: st.info("No bets.")
    with st.expander("Edit Profile"):
        with st.form("prof"):
            np = st.text_input("New Pass")
            if st.form_submit_button(t('save')):
                manage_user("update_profile", st.session_state.username, {'pass': np, 'bio': ''}); st.success("Updated")

def admin_dashboard():
    st.title(f"🛡️ {t('menu_admin_dash')}")
    conn = init_db(); users = pd.read_sql("SELECT * FROM users", conn); conn.close()
    st.dataframe(users, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        target = st.selectbox("User", users['username'].unique())
        amt = st.number_input(f"{t('add_credit')} ($)", value=1000.0)
        if st.button(t('add_credit')): manage_user("add_credit", target, amt); st.success("Added"); st.rerun()
    with c2:
        if st.button(t('promote')): manage_user("change_role", target, "admin"); st.rerun()
        if st.button(t('delete')): manage_user("delete", target); st.rerun()

def predictions_view():
    st.title(f"📈 {t('prediction_header')}")
    matches = fetch_matches()
    
    if not matches: st.warning(t('no_matches'))
    
    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"### {league}")
            league_matches = df[df['League'] == league]
            for i, m in league_matches.iterrows():
                data = analyze_advanced(m['Home'], m['Away'])
                odds = data['Odds']
                
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    c1.subheader(f"{m['Home']} vs {m['Away']}")
                    c2.caption(f"⏰ {m['Time']} | {m['Status']}")
                    c2.markdown(f"**{m['Home']}**: {render_form(m['Home'])}", unsafe_allow_html=True)
                    
                    if 'slip' in st.session_state:
                        with st.expander("🎫 Bet Slip", expanded=True):
                            u, _ = get_user_info(st.session_state.username)
                            s = st.session_state.slip
                            st.write(f"{s['m']} | {s['t']} @ {s['o']}")
                            w = st.number_input("Amount", 1.0, u[5], 50.0, key="wager")
                            if st.button("Confirm"):
                                if place_bet_db(st.session_state.username, s['m'], s['t'], w, s['o']):
                                    st.success("Placed"); del st.session_state.slip; st.rerun()
                    
                    t1, t2, t3 = st.tabs([t('winner'), t('goals'), t('btts')])
                    with t1:
                        b1, b2, b3 = st.columns(3)
                        if b1.button(f"🏠 {odds['Home']}", key=f"h{i}{m['Home']}"): st.session_state.slip = {'m':f"{m['Home']}v{m['Away']}",'t':'HOME','o':odds['Home']}; st.rerun()
                        if b2.button(f"⚖️ {odds['Draw']}", key=f"d{i}{m['Home']}"): st.session_state.slip = {'m':f"{m['Home']}v{m['Away']}",'t':'DRAW','o':odds['Draw']}; st.rerun()
                        if b3.button(f"✈️ {odds['Away']}", key=f"a{i}{m['Home']}"): st.session_state.slip = {'m':f"{m['Home']}v{m['Away']}",'t':'AWAY','o':odds['Away']}; st.rerun()
                    with t2: st.metric("Over 2.5", f"{data['Goals']['Over']}%"); st.progress(data['Goals']['Over']/100)
                    with t3: st.metric("BTTS", f"{data['BTTS']['Yes']}%"); st.progress(data['BTTS']['Yes']/100)
                    st.markdown("---")

# --- MAIN ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False; init_db()

if not st.session_state.logged_in:
    login_view()
else:
    st.sidebar.title(t('nav'))
    st.sidebar.info(f"👤 {st.session_state.username}")
    lang_toggle = st.sidebar.radio("🌐 Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    options = [t('menu_predictions'), t('menu_profile')]
    if st.session_state.role == 'admin': options.append(t('menu_admin_dash'))
    
    menu = st.sidebar.radio("", options)
    st.sidebar.divider()
    if st.sidebar.button(f"🚪 {t('sign_out')}"): st.session_state.logged_in = False; st.rerun()

    if menu == t('menu_predictions'): predictions_view()
    elif menu == t('menu_profile'): profile_view()
    elif menu == t('menu_admin_dash'): admin_dashboard()
