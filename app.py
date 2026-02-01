import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CSS: LIGHT THEME ---
st.markdown("""
    <style>
    .stApp {background-color: #FFFFFF; color: #31333F;}
    [data-testid="stSidebar"] {background-color: #F8F9FA; border-right: 1px solid #E6E6E6;}
    div[data-testid="stMetric"], div[data-testid="stExpander"] {
        background-color: #F0F2F6 !important; border: 1px solid #D6D6D6; border-radius: 8px; color: #31333F !important;
    }
    h1, h2, h3, p, label, .stMarkdown {color: #31333F !important;}
    [data-testid="stSidebarCollapsedControl"] {
        position: fixed !important; bottom: 20px !important; left: 20px !important; z-index: 1000000;
        background-color: #FF4B4B; color: white !important; border-radius: 50%; padding: 0.5rem;
    }
    .form-badge {padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 4px; color: white;}
    .form-w {background-color: #28a745;} .form-d {background-color: #6c757d;} .form-l {background-color: #dc3545;}
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "nav": "Navigation",
        "menu_predictions": "Live Matches", "menu_profile": "My Profile",
        "menu_admin_dash": "Admin Dashboard", "menu_users": "User Management",
        "no_matches": "No matches found today.", "conf": "Confidence", "winner": "Winner",
        "goals": "Goals", "btts": "Both Teams to Score", "save": "Save Changes",
        "role": "Role", "action": "Action", "time": "Time", "promote": "Promote to Admin",
        "demote": "Demote to User", "delete": "Delete User", "balance": "Balance",
        "add_credit": "Add Credit", "bet_history": "Betting History"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "nav": "القائمة الرئيسية",
        "menu_predictions": "التوقعات المباشرة", "menu_profile": "ملفي الشخصي",
        "menu_admin_dash": "لوحة التحكم", "menu_users": "إدارة المستخدمين",
        "no_matches": "لا توجد مباريات اليوم", "conf": "نسبة الثقة", "winner": "الفائز",
        "goals": "الأهداف", "btts": "كلا الفريقين يسجل", "save": "حفظ التغييرات",
        "role": "الصلاحية", "action": "الحدث", "time": "الوقت", "promote": "ترقية لمدير",
        "demote": "تخفيض لمستخدم", "delete": "حذف المستخدم", "balance": "الرصيد",
        "add_credit": "إضافة رصيد", "bet_history": "سجل المراهنات"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v33_hybrid.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    try:
        c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),))
        conn.commit()
    except: pass
    conn.close()

init_db()

def manage_user(action, target_user, data=None):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        if action == "add": c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()), 'New User', 1000.0)); conn.commit(); return True
        elif action == "update_profile": c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user)); conn.commit()
        elif action == "change_role": c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user)); conn.commit()
        elif action == "delete": c.execute("DELETE FROM users WHERE username=?", (target_user,)); conn.commit()
        elif action == "add_credit": c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (data, target_user)); conn.commit()
    except: return False
    finally: conn.close()

def get_user_info(username):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,)); res = c.fetchone()
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,)); bets = c.fetchall()
    conn.close(); return res, bets

def place_bet_db(user, match, bet_type, amount, odds):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        c.execute("SELECT balance FROM users WHERE username=?", (user,))
        row = c.fetchone()
        if not row: return False
        bal = row[0]
        if bal >= amount:
            c.execute("UPDATE users SET balance=? WHERE username=?", (bal - amount, user))
            c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)", (user, match, bet_type, amount, amount * odds, 'OPEN', str(datetime.now())))
            conn.commit(); return True
    except: pass
    finally: conn.close()
    return False

def log_action(user, action):
    try:
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
    except: pass

# --- HYBRID DATA ENGINE (Smart Fetch) ---
@st.cache_data(ttl=300)
def fetch_matches():
    matches = []
    
    # 1. PRIMARY: Try Your SportAPI7 Key (Correct Matches Endpoint)
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Correct endpoint for matches (NOT player ratings)
        url = f"https://sportapi7.p.rapidapi.com/api/v1/sport/football/scheduled-events/{today_str}"
        headers = {
            "x-rapidapi-host": "sportapi7.p.rapidapi.com",
            "x-rapidapi-key": "f84fc89ce9msh35e8c7081df9999p1df9d8jsn071086d01b59"
        }
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            data = r.json()
            for event in data.get('events', []):
                matches.append({
                    "League": event['tournament']['name'],
                    "Date": today_str,
                    "Time": datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M'),
                    "Status": event['status']['type'],
                    "Home": event['homeTeam']['name'],
                    "Away": event['awayTeam']['name'],
                    "Score": f"{event.get('homeScore',{}).get('current',0)}-{event.get('awayScore',{}).get('current',0)}"
                })
    except:
        pass # Silently fail to fallback

    # 2. FALLBACK: ESPN Public API (Guaranteed Data)
    if not matches:
        leagues = [
            {"id": "eng.1", "name": "🇬🇧 Premier League"}, {"id": "eng.2", "name": "🇬🇧 Championship"},
            {"id": "esp.1", "name": "🇪🇸 La Liga"}, {"id": "ita.1", "name": "🇮🇹 Serie A"},
            {"id": "ger.1", "name": "🇩🇪 Bundesliga"}, {"id": "fra.1", "name": "🇫🇷 Ligue 1"},
            {"id": "ned.1", "name": "🇳🇱 Eredivisie"}
        ]
        
        # Check Today AND Tomorrow
        dates = [datetime.now().strftime("%Y%m%d"), (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")]
        
        for d_str in dates:
            if len(matches) > 15: break
            for l in leagues:
                try:
                    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard?dates={d_str}"
                    r = requests.get(url, timeout=2)
                    if r.status_code == 200:
                        data = r.json()
                        for e in data.get('events', []):
                            utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                            local = utc + timedelta(hours=3)
                            
                            status = e['status']['type']['shortDetail']
                            try: score = f"{e['competitions'][0]['competitors'][0]['score']}-{e['competitions'][0]['competitors'][1]['score']}"
                            except: score = "vs"
                            
                            matches.append({
                                "League": l['name'],
                                "Date": local.strftime("%Y-%m-%d"),
                                "Time": local.strftime("%H:%M"),
                                "Status": status,
                                "Score": score,
                                "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                                "Away": e['competitions'][0]['competitors'][1]['team']['displayName']
                            })
                except: continue

    return matches

def render_form(name):
    random.seed(name)
    form = random.sample(['W','L','D','W','W'], 5)
    return "".join([f"<span class='form-badge {'form-w' if x=='W' else 'form-l' if x=='L' else 'form-d'}'>{x}</span>" for x in form])

def analyze_advanced(h, a):
    h = str(h); a = str(a)
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {
        "1X2": {"Home": h_win, "Draw": d_win, "Away": a_win},
        "Odds": {"Home": round(100/h_win,2), "Draw": round(100/d_win,2), "Away": round(100/a_win,2)},
        "Goals": {"Over": int((seed*4)%100)}, "BTTS": {"Yes": int((seed*9)%100)}
    }

# --- UI HELPER ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- PAGE FUNCTIONS ---
def login_view():
    st.markdown(f"<h1 style='text-align: center;'>⚽ {t('app_name')}</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns([8, 2])
    with c2:
        lang = st.selectbox("Language / اللغة", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
    t1, t2 = st.tabs([t('login'), t('signup')])
    with t1:
        u = st.text_input(t('username'), key="l_u").strip()
        p = st.text_input(t('password'), type="password", key="l_p").strip()
        if st.button(t('login'), use_container_width=True):
            # HARDCODED ADMIN BYPASS
            if u == "admin" and p == "admin123":
                st.session_state.logged_in = True; st.session_state.username = "admin"; st.session_state.role = "admin"
                manage_user("add", "admin", "admin123") 
                st.rerun()
            
            user_data, _ = get_user_info(u)
            if user_data and user_data[1] == p:
                st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = user_data[2]
                log_action(u, "Login Success"); st.rerun()
            else: st.error("Invalid Credentials. Default: 'admin' / 'admin123'")
    with t2:
        nu = st.text_input(t('new_user'))
        np = st.text_input(t('new_pass'), type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu.strip(), np.strip()): st.success("Created! Login now."); log_action(nu, "Account Created")
            else: st.error("Username Taken")

def profile_view():
    st.title(f"👤 {t('menu_profile')}")
    u_info, bets = get_user_info(st.session_state.username)
    if not u_info and st.session_state.username == 'admin':
         u_info = ('admin', 'admin123', 'admin', str(datetime.now()), 'System Admin', 100000.0)
    
    st.metric(t('balance'), f"${u_info[5]:,.2f}")
    st.subheader(t('bet_history'))
    if bets:
        df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
        st.dataframe(df[['Date','Match','Type','Amt','Win','Status']], use_container_width=True)
    else: st.info("No bets yet.")
    with st.expander("Edit Profile"):
        with st.form("profile_form"):
            new_pass = st.text_input(t('password'), value=u_info[1], type="password")
            new_bio = st.text_area("Bio / Status", value=u_info[4])
            if st.form_submit_button(t('save')):
                manage_user("update_profile", st.session_state.username, {'pass': new_pass, 'bio': new_bio})
                st.success(t('success_update'))

def admin_dashboard():
    st.title(f"🛡️ {t('menu_admin_dash')}")
    conn = sqlite3.connect(DB_NAME); users = pd.read_sql("SELECT * FROM users", conn); logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn); conn.close()
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
    st.subheader("Manage Funds")
    c1, c2 = st.columns(2)
    target = c1.selectbox("Select User", users['username'].unique())
    amt = c2.number_input(f"{t('add_credit')} ($)", value=1000.0)
    if st.button(t('add_credit')):
        manage_user("add_credit", target, amt); log_action(st.session_state.username, f"Added ${amt} to {target}"); st.success("Added!"); st.rerun()
    st.subheader(t('menu_logs')); st.dataframe(logs, use_container_width=True)

def predictions_view():
    st.title(f"📈 {t('prediction_header')}")
    
    with st.spinner("Scanning Real-Time Data Sources..."):
        matches = fetch_matches()
    
    if not matches:
        st.warning(t('no_matches'))
    
    # BET SLIP
    if 'slip' in st.session_state:
        u_info, _ = get_user_info(st.session_state.username)
        if not u_info and st.session_state.username == 'admin': u_info = ('','','','','',100000.0)
        
        slip = st.session_state.slip
        with st.sidebar.expander(f"🎫 Bet Slip", expanded=True):
            st.write(f"**{slip['m']}**")
            st.write(f"Selection: {slip['t']} | Odds: {slip['o']}")
            wager = st.number_input("Wager", 1.0, u_info[5], 50.0)
            st.write(f"Win: ${wager * slip['o']:.2f}")
            if st.button("Confirm Bet", type="primary"):
                if place_bet_db(st.session_state.username, slip['m'], slip['t'], wager, slip['o']):
                    st.success("Placed!"); del st.session_state.slip; st.rerun()
                else: st.error("No Funds")

    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"### {league}")
            league_matches = df[df['League'] == league]
            for index, m in league_matches.iterrows():
                data = analyze_advanced(m['Home'], m['Away'])
                odds = data['Odds']
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    c1.subheader(f"{m['Home']} {m['Score']} {m['Away']}")
                    c2.caption(f"📅 {m['Date']} | ⏰ {m['Time']} | {m['Status']}")
                    c2.markdown(f"**{m['Home']}**: {render_form(m['Home'])}", unsafe_allow_html=True)
                    
                    t1, t2, t3 = st.tabs([t('winner'), t('goals'), t('btts')])
                    with t1:
                        b1, b2, b3 = st.columns(3)
                        if b1.button(f"🏠 {odds['Home']}", key=f"h{index}{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'HOME', 'o': odds['Home']}; st.rerun()
                        if b2.button(f"⚖️ {odds['Draw']}", key=f"d{index}{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'DRAW', 'o': odds['Draw']}; st.rerun()
                        if b3.button(f"✈️ {odds['Away']}", key=f"a{index}{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'AWAY', 'o': odds['Away']}; st.rerun()
                    
                    with t2:
                        g_prob = float(data['Goals']['Over']) / 100.0
                        st.metric("Over 2.5", f"{data['Goals']['Over']}%")
                        st.progress(min(max(g_prob, 0.0), 1.0))
                    with t3:
                        b_prob = float(data['BTTS']['Yes']) / 100.0
                        st.metric("BTTS", f"{data['BTTS']['Yes']}%")
                        st.progress(min(max(b_prob, 0.0), 1.0))
                    st.markdown("---")

# --- MAIN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

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
