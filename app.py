import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- THEME & CSS MANAGER ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'Dark'

def get_theme_css():
    if st.session_state.theme == 'Dark':
        # Dark Mode (Professional Grey - NOT Pure Black)
        bg = "#121212"
        card = "#1E1E1E" 
        text = "#E0E0E0"
    else:
        # Light Mode
        bg = "#F5F7F9"
        card = "#FFFFFF"
        text = "#31333F"
    
    return f"""
    <style>
    /* 1. Main Theme Colors */
    .stApp {{
        background-color: {bg};
        color: {text};
    }}
    
    /* 2. Metrics & Cards Styling */
    div[data-testid="stMetric"], div[data-testid="stExpander"] {{
        background-color: {card} !important;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px;
    }}
    
    /* 3. Hide Streamlit Branding (Safe Mode) */
    footer {{visibility: hidden;}}
    .stAppDeployButton {{display: none;}}
    [data-testid="stToolbar"] {{visibility: hidden;}}
    
    /* 4. FORCE Navigation Toggle to be Visible */
    [data-testid="stSidebarCollapsedControl"] {{
        visibility: visible !important;
        display: block !important;
        color: {text} !important;
    }}

    /* 5. Form Badges */
    .form-badge {{
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
        margin-right: 4px;
        color: white;
    }}
    .form-w {{background-color: #28a745;}}
    .form-d {{background-color: #6c757d;}}
    .form-l {{background-color: #dc3545;}}
    </style>
    """

st.markdown(get_theme_css(), unsafe_allow_html=True)

# --- TRANSLATIONS (English & Arabic) ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "new_user": "New Username",
        "new_pass": "New Password", "create_acc": "Create Account", "welcome": "Welcome",
        "sign_out": "Sign Out", "nav": "Navigation", "menu_predictions": "Live Matches & Betting",
        "menu_profile": "My Profile & Wallet", "menu_admin_dash": "Admin Dashboard",
        "menu_users": "User Management", "menu_logs": "System Logs",
        "no_matches": "No matches found.", "conf": "Confidence", "winner": "Winner",
        "goals": "Goals", "btts": "Both Teams to Score", "save": "Save Changes",
        "role": "Role", "action": "Action", "time": "Time",
        "promote": "Promote to Admin", "demote": "Demote to User", "delete": "Delete User",
        "success_update": "Profile updated successfully!", "admin_area": "Admin Area",
        "prediction_header": "AI Market Analysis", "balance": "Wallet Balance",
        "add_funds": "Add Funds", "bet_history": "Betting History", "place_bet": "Place Bet"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "new_user": "اسم مستخدم جديد",
        "new_pass": "كلمة مرور جديدة", "create_acc": "إنشاء الحساب", "welcome": "مرحباً",
        "sign_out": "تسجيل الخروج", "nav": "القائمة الرئيسية", "menu_predictions": "المباريات والمراهنة",
        "menu_profile": "محفظتي وملفي", "menu_admin_dash": "لوحة التحكم",
        "menu_users": "إدارة المستخدمين", "menu_logs": "سجلات النظام",
        "no_matches": "لا توجد مباريات حالياً", "conf": "نسبة الثقة", "winner": "الفائز",
        "goals": "الأهداف", "btts": "كلا الفريقين يسجل", "save": "حفظ التغييرات",
        "role": "الصلاحية", "action": "الحدث", "time": "الوقت",
        "promote": "ترقية لمدير", "demote": "تخفيض لمستخدم", "delete": "حذف المستخدم",
        "success_update": "تم تحديث الملف الشخصي!", "admin_area": "منطقة الإدارة",
        "prediction_header": "تحليل الذكاء الاصطناعي", "balance": "رصيد المحفظة",
        "add_funds": "إضافة رصيد", "bet_history": "سجل المراهنات", "place_bet": "تأكيد الرهان"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v9_final.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users (Added Balance)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    # Logs
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    # Bets (New Table)
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try:
        # Admin gets 1 Million
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 1000000.0)", (str(datetime.now()),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return conn

def log_action(user, action):
    conn = init_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", 
              (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def manage_user(action, target_user, data=None):
    conn = init_db()
    c = conn.cursor()
    try:
        if action == "add":
            # New User Bonus: $1000
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                      (target_user, data, 'user', str(datetime.now()), 'New User', 1000.0))
            conn.commit()
            return True
        elif action == "update_profile":
            c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user))
            conn.commit()
        elif action == "change_role":
            c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user))
            conn.commit()
        elif action == "delete":
            c.execute("DELETE FROM users WHERE username=?", (target_user,))
            conn.commit()
        elif action == "add_credit":
            c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (data, target_user))
            conn.commit()
    except: return False
    finally: conn.close()

def get_user_info(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    res = c.fetchone()
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,))
    bets = c.fetchall()
    conn.close()
    return res, bets

def place_bet_db(user, match, bet_type, amount, odds):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username=?", (user,))
    bal = c.fetchone()[0]
    if bal >= amount:
        new_bal = bal - amount
        pot_win = round(amount * odds, 2)
        c.execute("UPDATE users SET balance=? WHERE username=?", (new_bal, user))
        c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user, match, bet_type, amount, pot_win, 'OPEN', str(datetime.now())))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# --- DATA & AI ENGINE ---
@st.cache_data(ttl=600)
def fetch_matches():
    # 1. Real Data Attempt
    url = "https://api.openligadb.de/getmatchdata/bl1/2025"
    matches = []
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            for m in r.json():
                dt = datetime.strptime(m['matchDateTime'], "%Y-%m-%dT%H:%M:%S")
                if dt > datetime.now():
                    matches.append({
                        "Date": dt.strftime("%Y-%m-%d"),
                        "Time": dt.strftime("%H:%M"),
                        "Home": m['team1']['teamName'],
                        "Away": m['team2']['teamName'],
                        "Icon1": m['team1']['teamIconUrl'],
                        "Icon2": m['team2']['teamIconUrl']
                    })
    except: pass

    # 2. Fallback Demo Data (As per your request)
    if not matches:
        base_date = datetime.now()
        matches = [
            {"Date": (base_date).strftime("%Y-%m-%d"), "Time": "20:45", "Home": "Real Madrid", "Away": "Barcelona", "Icon1": "", "Icon2": ""},
            {"Date": (base_date).strftime("%Y-%m-%d"), "Time": "18:30", "Home": "Man City", "Away": "Arsenal", "Icon1": "", "Icon2": ""},
            {"Date": (base_date).strftime("%Y-%m-%d"), "Time": "21:00", "Home": "Bayern", "Away": "Dortmund", "Icon1": "", "Icon2": ""},
        ]
    return matches

def render_consistent_form(team_name):
    random.seed(team_name) # Lock random so it doesn't change on refresh
    form = random.sample(['W', 'L', 'D', 'W', 'W', 'L'], 5)
    html = ""
    for res in form:
        c = "form-w" if res == 'W' else "form-l" if res == 'L' else "form-d"
        html += f"<span class='form-badge {c}'>{res}</span>"
    return html

def analyze_advanced(home, away):
    seed = len(home) + len(away)
    h_win = (seed * 7) % 100
    if h_win < 30: h_win += 30 
    d_win = (100 - h_win) // 3
    a_win = 100 - h_win - d_win
    
    # Calculate Odds
    odds_h = round(100/h_win, 2)
    odds_d = round(100/d_win, 2)
    odds_a = round(100/a_win, 2)

    return {
        "1X2": {"Home": h_win, "Draw": d_win, "Away": a_win},
        "Odds": {"Home": odds_h, "Draw": odds_d, "Away": odds_a},
        "Goals": {"Over": (seed * 4) % 100, "Under": 100-((seed*4)%100)},
        "BTTS": {"Yes": (seed * 9) % 100, "No": 100-((seed*9)%100)}
    }

# --- UI HELPER ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- PAGES ---
def login_view():
    st.markdown(f"<h1 style='text-align: center;'>⚽ {t('app_name')}</h1>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([8, 2])
    with col2:
        lang = st.selectbox("Language / اللغة", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"

    tab1, tab2 = st.tabs([t('login'), t('signup')])
    
    with tab1:
        u = st.text_input(t('username'), key="l_u")
        p = st.text_input(t('password'), type="password", key="l_p")
        if st.button(t('login'), use_container_width=True):
            user_data, _ = get_user_info(u)
            if user_data and user_data[1] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = user_data[2]
                log_action(u, "Login Success")
                st.rerun()
            else:
                st.error("Error")
    
    with tab2:
        nu = st.text_input(t('new_user'))
        np = st.text_input(t('new_pass'), type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu, np):
                st.success("OK! Login now.")
            else:
                st.error("Taken")

def profile_view():
    st.title(f"👤 {t('menu_profile')}")
    u_info, bets = get_user_info(st.session_state.username)
    
    # Wallet
    st.metric(t('balance'), f"${u_info[5]:,.2f}")
    
    # Bet History
    st.subheader(t('bet_history'))
    if bets:
        df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
        st.dataframe(df[['Date','Match','Type','Amt','Win','Status']], use_container_width=True)
    else:
        st.info("No bets yet.")
    
    # Profile Settings
    with st.expander("Edit Profile"):
        with st.form("profile_form"):
            new_pass = st.text_input(t('password'), value=u_info[1], type="password")
            new_bio = st.text_area("Bio / Status", value=u_info[4])
            if st.form_submit_button(t('save')):
                manage_user("update_profile", st.session_state.username, {'pass': new_pass, 'bio': new_bio})
                st.success(t('success_update'))

def admin_dashboard():
    st.title(f"🛡️ {t('menu_admin_dash')}")
    
    conn = init_db()
    users = pd.read_sql("SELECT username, role, balance, created_at FROM users", conn)
    logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Users", len(users))
    c2.metric("Total Logs", len(logs))
    c3.metric("Status", "Online")

    st.subheader(t('menu_users'))
    st.dataframe(users, use_container_width=True)
    
    # Admin Actions
    c1, c2 = st.columns(2)
    with c1:
        st.write("### Manage Funds")
        target_user = st.selectbox("Select User", users['username'].unique())
        amt = st.number_input(f"{t('add_funds')} ($)", value=1000.0)
        if st.button(t('add_funds')):
            manage_user("add_credit", target_user, amt)
            log_action(st.session_state.username, f"Added ${amt} to {target_user}")
            st.success(f"Added ${amt} to {target_user}")
            st.rerun()

    with c2:
        st.write("### Account Actions")
        if target_user != 'admin':
            col_a, col_b = st.columns(2)
            if col_a.button(t('promote')):
                manage_user("change_role", target_user, "admin")
                st.rerun()
            if col_b.button(t('delete')):
                manage_user("delete", target_user)
                st.rerun()

    st.subheader(t('menu_logs'))
    st.dataframe(logs, use_container_width=True)

def predictions_view():
    st.title(f"📈 {t('prediction_header')}")
    
    # Active Bet Slip (Sticky)
    if 'slip' in st.session_state:
        slip = st.session_state.slip
        with st.expander(f"🎫 Bet Slip: {slip['m']} (Active)", expanded=True):
            st.write(f"Selection: **{slip['t']}** | Odds: **{slip['o']}**")
            u_info, _ = get_user_info(st.session_state.username)
            wager = st.number_input("Amount", 1.0, u_info[5], 50.0)
            st.write(f"Potential Win: **${wager * slip['o']:.2f}**")
            
            if st.button(t('place_bet'), type="primary", use_container_width=True):
                if place_bet_db(st.session_state.username, slip['m'], slip['t'], wager, slip['o']):
                    st.success("Bet Placed!")
                    del st.session_state.slip
                    st.rerun()
                else:
                    st.error("Insufficient Funds")
    
    matches = fetch_matches()
    for m in matches:
        data = analyze_advanced(m['Home'], m['Away'])
        probs = data['1X2']
        odds = data['Odds']
        
        with st.container():
            # Match Header
            c1, c2 = st.columns([3, 1])
            c1.subheader(f"{m['Home']} vs {m['Away']}")
            c1.caption(f"📅 {m['Date']} | ⏰ {m['Time']}")
            # Form Guide
            c2.markdown(f"**{m['Home']}**: {render_consistent_form(m['Home'])}", unsafe_allow_html=True)
            c2.markdown(f"**{m['Away']}**: {render_consistent_form(m['Away'])}", unsafe_allow_html=True)
            
            # Betting Tabs
            t1, t2, t3 = st.tabs([t('winner'), t('goals'), t('btts')])
            
            with t1:
                b1, b2, b3 = st.columns(3)
                if b1.button(f"🏠 Home {odds['Home']}", key=f"h{m['Home']}"):
                    st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'HOME', 'o': odds['Home']}
                    st.rerun()
                if b2.button(f"⚖️ Draw {odds['Draw']}", key=f"d{m['Home']}"):
                    st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'DRAW', 'o': odds['Draw']}
                    st.rerun()
                if b3.button(f"✈️ Away {odds['Away']}", key=f"a{m['Home']}"):
                    st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'AWAY', 'o': odds['Away']}
                    st.rerun()
                
            with t2:
                st.metric("Over 2.5", f"{data['Goals']['Over']}%")
                st.progress(data['Goals']['Over']/100)
                
            with t3:
                st.metric("BTTS", f"{data['BTTS']['Yes']}%")
                st.progress(data['BTTS']['Yes']/100)
            
            st.markdown("---")

# --- MAIN CONTROLLER ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

if not st.session_state.logged_in:
    login_view()
else:
    # --- SIDEBAR NAV ---
    st.sidebar.title(t('nav'))
    st.sidebar.info(f"👤 {st.session_state.username}")
    u_data, _ = get_user_info(st.session_state.username)
    st.sidebar.caption(f"💰 ${u_data[5]:,.2f}")
    
    # Settings
    lang_toggle = st.sidebar.radio("🌐 Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    theme_toggle = st.sidebar.radio("🌗 Theme", ["Dark", "Light"])
    st.session_state.theme = theme_toggle
    
    # Dynamic Menu
    options = [t('menu_predictions'), t('menu_profile')]
    if st.session_state.role == 'admin':
        options = [t('menu_admin_dash')] + options
        
    menu = st.sidebar.radio("", options)
    
    st.sidebar.divider()
    if st.sidebar.button(f"🚪 {t('sign_out')}", use_container_width=True):
        log_action(st.session_state.username, "Logout")
        st.session_state.logged_in = False
        st.rerun()

    # --- ROUTING ---
    if menu == t('menu_predictions'):
        predictions_view()
    elif menu == t('menu_profile'):
        profile_view()
    elif menu == t('menu_admin_dash'):
        admin_dashboard()
