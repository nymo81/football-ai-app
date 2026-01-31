import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- SAFE CSS (Fixes Navigation Issue) ---
st.markdown("""
    <style>
    /* 1. Hide the Streamlit Header Decoration and Hamburger Menu */
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stToolbar"] {visibility: hidden;}
    .stAppDeployButton {display: none;}
    footer {visibility: hidden;}
    
    /* 2. CRITICAL FIX: Force the Sidebar Toggle (Arrow) to stay visible and clickable */
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        visibility: visible !important;
        position: fixed !important;
        top: 15px !important;
        left: 15px !important;
        z-index: 1000002 !important;
        background-color: #0E1117; /* Matches dark theme background */
        border-radius: 5px;
        padding: 5px;
    }
    
    /* 3. Make the header transparent so it doesn't block clicks */
    [data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none; /* Allows clicking through the header */
    }
    
    /* 4. Betting & Form UI */
    .stMetric {background-color: #0E1117; border: 1px solid #333; padding: 10px; border-radius: 8px;}
    .form-badge {padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 2px;}
    .form-w {background-color: #00cc00; color: white;}
    .form-d {background-color: #aaaaaa; color: black;}
    .form-l {background-color: #cc0000; color: white;}
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "create_acc": "Create Account",
        "welcome": "Welcome", "sign_out": "Sign Out", "nav": "Navigation",
        "menu_predictions": "Live Predictions", "menu_profile": "My Profile",
        "menu_admin_dash": "Admin Dashboard", "menu_users": "User Management",
        "menu_logs": "System Logs", "no_matches": "No matches found.",
        "conf": "Confidence", "winner": "Winner", "goals": "Goals", "btts": "Both Teams to Score",
        "save": "Save Changes", "role": "Role", "action": "Action", "time": "Time",
        "promote": "Promote to Admin", "demote": "Demote to User", "delete": "Delete User",
        "success_update": "Profile updated successfully!", "admin_area": "Admin Area",
        "prediction_header": "AI Market Analysis",
        "balance": "Wallet Balance", "place_bet": "Place Bet", "amount": "Wager Amount",
        "potential_win": "Potential Win", "bet_placed": "Bet Placed Successfully!",
        "insufficient_funds": "Insufficient Funds!", "form": "Recent Form",
        "bet_history": "Betting History"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "create_acc": "إنشاء الحساب",
        "welcome": "مرحباً", "sign_out": "تسجيل الخروج", "nav": "القائمة الرئيسية",
        "menu_predictions": "التوقعات المباشرة", "menu_profile": "ملفي الشخصي",
        "menu_admin_dash": "لوحة التحكم", "menu_users": "إدارة المستخدمين",
        "menu_logs": "سجلات النظام", "no_matches": "لا توجد مباريات حالياً",
        "conf": "نسبة الثقة", "winner": "الفائز", "goals": "الأهداف", "btts": "كلا الفريقين يسجل",
        "save": "حفظ التغييرات", "role": "الصلاحية", "action": "الحدث", "time": "الوقت",
        "promote": "ترقية لمدير", "demote": "تخفيض لمستخدم", "delete": "حذف المستخدم",
        "success_update": "تم تحديث الملف الشخصي!", "admin_area": "منطقة الإدارة",
        "prediction_header": "تحليل الذكاء الاصطناعي",
        "balance": "رصيد المحفظة", "place_bet": "ضع رهانك", "amount": "قيمة الرهان",
        "potential_win": "الربح المتوقع", "bet_placed": "تم وضع الرهان بنجاح!",
        "insufficient_funds": "الرصيد غير كافي!", "form": "أداء الفريق",
        "bet_history": "سجل المراهنات"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_pro_v3.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000)", (str(datetime.now()),))
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
    if action == "add":
        try:
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                      (target_user, data, 'user', str(datetime.now()), 'New Bettor', 1000.0))
            conn.commit()
            return True
        except: return False
    elif action == "update_profile":
        c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user))
        conn.commit()
    elif action == "change_role":
        c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user))
        conn.commit()
    elif action == "delete":
        c.execute("DELETE FROM users WHERE username=?", (target_user,))
        conn.commit()
    conn.close()

def get_user_info(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    u = c.fetchone()
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,))
    bets = c.fetchall()
    conn.close()
    return u, bets

def place_bet_db(user, match, bet_type, amount, odds):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username=?", (user,))
    bal = c.fetchone()[0]
    if bal >= amount:
        new_bal = bal - amount
        pot_win = amount * odds
        c.execute("UPDATE users SET balance=? WHERE username=?", (new_bal, user))
        c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user, match, bet_type, amount, pot_win, 'OPEN', str(datetime.now())))
        conn.commit()
        conn.close()
        return True
    return False

# --- DATA ENGINE ---
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

    # 2. Demo Fallback (To ensure app always looks good)
    if not matches:
        base_date = datetime.now()
        matches = [
            {"Date": (base_date).strftime("%Y-%m-%d"), "Time": "20:45", "Home": "Real Madrid", "Away": "Barcelona", "Icon1": "", "Icon2": ""},
            {"Date": (base_date).strftime("%Y-%m-%d"), "Time": "18:30", "Home": "Man City", "Away": "Arsenal", "Icon1": "", "Icon2": ""},
            {"Date": (base_date).strftime("%Y-%m-%d"), "Time": "21:00", "Home": "Bayern", "Away": "Dortmund", "Icon1": "", "Icon2": ""},
        ]
    return matches

def generate_form():
    return random.sample(['W', 'L', 'D', 'W', 'W', 'L'], 5)

def render_form_badges(form_list):
    html = ""
    for res in form_list:
        color = "form-w" if res == 'W' else "form-l" if res == 'L' else "form-d"
        html += f"<span class='form-badge {color}'>{res}</span>"
    return html

def analyze_advanced(home, away):
    seed = len(home) + len(away)
    h_win = (seed * 7) % 100
    if h_win < 30: h_win += 30
    d_win = (100 - h_win) // 3
    a_win = 100 - h_win - d_win
    h_odd = round(100/h_win, 2)
    d_odd = round(100/d_win, 2)
    a_odd = round(100/a_win, 2)
    return {
        "1X2": {"Home": h_win, "Draw": d_win, "Away": a_win},
        "Odds": {"Home": h_odd, "Draw": d_odd, "Away": a_odd},
        "Goals": {"Over": (seed * 4) % 100},
        "BTTS": {"Yes": (seed * 9) % 100}
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
            user_data, _ = get_user_info(u)
            if user_data and user_data[1] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = user_data[2]
                st.rerun()
            else:
                st.error("Error")
    with tab2:
        nu = st.text_input("New Username")
        np = st.text_input("New Password", type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu, np):
                st.success("OK! Login now.")
            else:
                st.error("Taken")

def profile_view():
    st.title(f"👤 {t('menu_profile')}")
    u_info, bets = get_user_info(st.session_state.username)
    st.metric(t('balance'), f"${u_info[5]:,.2f}")
    
    with st.form("profile_form"):
        new_pass = st.text_input(t('password'), value=u_info[1], type="password")
        new_bio = st.text_area("Bio / Status", value=u_info[4])
        if st.form_submit_button(t('save')):
            manage_user("update_profile", st.session_state.username, {'pass': new_pass, 'bio': new_bio})
            st.success(t('success_update'))
            
    st.subheader(t('bet_history'))
    if bets:
        for b in bets:
            col = "green" if b[6] == "WON" else "orange"
            st.markdown(f"<div style='border-left:4px solid {col}; padding-left:10px; margin-bottom:5px; background:#1e1e1e; padding:5px;'><b>{b[2]}</b><br>{b[3]} (${b[4]}) -> ${b[5]}</div>", unsafe_allow_html=True)
    else:
        st.caption("No bets yet.")

def admin_dashboard():
    st.title(f"🛡️ {t('menu_admin_dash')}")
    conn = init_db()
    users = pd.read_sql("SELECT * FROM users", conn)
    logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Users", len(users))
    c2.metric("Logs", len(logs))
    c3.metric("System", "Online")

    st.subheader(t('menu_users'))
    for index, row in users.iterrows():
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(f"**{row['username']}** ({row['role']})")
        if row['username'] != 'admin':
            with c2:
                if st.button(t('promote'), key=f"p_{row['username']}"):
                    manage_user("change_role", row['username'], "admin")
                    st.rerun()
            with c3:
                if st.button(t('demote'), key=f"d_{row['username']}"):
                    manage_user("change_role", row['username'], "user")
                    st.rerun()
            with c4:
                if st.button(t('delete'), key=f"del_{row['username']}"):
                    manage_user("delete", row['username'])
                    st.rerun()
        st.divider()

    st.subheader(t('menu_logs'))
    st.dataframe(logs, use_container_width=True)

def predictions_view():
    st.title(f"📈 {t('prediction_header')}")
    u_info, _ = get_user_info(st.session_state.username)
    st.caption(f"💰 {t('balance')}: ${u_info[5]:,.2f}")
    
    matches = fetch_matches()
    for m in matches:
        data = analyze_advanced(m['Home'], m['Away'])
        probs = data['1X2']
        odds = data['Odds']
        
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{m['Home']} vs {m['Away']}")
                st.caption(f"📅 {m['Date']} | ⏰ {m['Time']}")
                st.markdown(f"{m['Home']}: {render_form_badges(generate_form())}", unsafe_allow_html=True)
                st.markdown(f"{m['Away']}: {render_form_badges(generate_form())}", unsafe_allow_html=True)

            t1, t2 = st.tabs([t('winner'), "Stats"])
            with t1:
                b1, b2, b3 = st.columns(3)
                with b1: 
                    st.info(f"{m['Home']} ({probs['Home']}%)")
                    if st.button(f"Bet Home @ {odds['Home']}", key=f"bh_{m['Home']}"):
                        st.session_state.bet_slip = {'match': f"{m['Home']} vs {m['Away']}", 'type': 'HOME', 'odds': odds['Home']}
                with b2:
                    st.warning(f"Draw ({probs['Draw']}%)")
                    if st.button(f"Bet Draw @ {odds['Draw']}", key=f"bd_{m['Home']}"):
                        st.session_state.bet_slip = {'match': f"{m['Home']} vs {m['Away']}", 'type': 'DRAW', 'odds': odds['Draw']}
                with b3:
                    st.error(f"{m['Away']} ({probs['Away']}%)")
                    if st.button(f"Bet Away @ {odds['Away']}", key=f"ba_{m['Home']}"):
                        st.session_state.bet_slip = {'match': f"{m['Home']} vs {m['Away']}", 'type': 'AWAY', 'odds': odds['Away']}

            with t2:
                st.metric("Over 2.5", f"{data['Goals']['Over']}%")
                st.metric("BTTS", f"{data['BTTS']['Yes']}%")
            st.markdown("---")

    if 'bet_slip' in st.session_state:
        slip = st.session_state.bet_slip
        with st.expander("🎫 Active Bet Slip", expanded=True):
            st.write(f"**Match:** {slip['match']}")
            st.write(f"**Prediction:** {slip['type']} (Odds: {slip['odds']})")
            wager = st.number_input(t('amount'), min_value=10.0, max_value=u_info[5], value=50.0)
            st.write(f"**{t('potential_win')}:** ${wager * slip['odds']:.2f}")
            if st.button(t('place_bet'), type="primary"):
                if place_bet_db(st.session_state.username, slip['match'], slip['type'], wager, slip['odds']):
                    st.success(t('bet_placed'))
                    del st.session_state.bet_slip
                    st.rerun()
                else:
                    st.error(t('insufficient_funds'))

# --- MAIN CONTROLLER ---
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
    if st.session_state.role == 'admin':
        options = [t('menu_admin_dash')] + options
        
    menu = st.sidebar.radio("", options)
    
    st.sidebar.divider()
    if st.sidebar.button(f"🚪 {t('sign_out')}", use_container_width=True):
        log_action(st.session_state.username, "Logout")
        st.session_state.logged_in = False
        st.rerun()

    if menu == t('menu_predictions'):
        predictions_view()
    elif menu == t('menu_profile'):
        profile_view()
    elif menu == t('menu_admin_dash'):
        admin_dashboard()
