import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CSS: DARK GREY THEME & BOTTOM SIDEBAR BUTTON ---
st.markdown("""
    <style>
    /* 1. DARK GREY THEME (Not Pure Black) */
    .stApp {
        background-color: #262730; /* Soft Dark Grey */
        color: #FAFAFA;
    }
    
    /* 2. SIDEBAR BACKGROUND */
    [data-testid="stSidebar"] {
        background-color: #1F2026; /* Slightly darker grey for sidebar */
    }
    
    /* 3. METRICS & CARDS */
    div[data-testid="stMetric"], div[data-testid="stExpander"] {
        background-color: #31333F !important; /* Lighter Grey for cards */
        border: 1px solid #45474B;
        border-radius: 8px;
    }
    
    /* 4. MOVE NAV BUTTON (<<) TO BOTTOM LEFT */
    [data-testid="stSidebarCollapsedControl"] {
        position: fixed !important;
        bottom: 20px !important;
        left: 20px !important;
        top: auto !important;
        z-index: 1000000;
        background-color: #FF4B4B; /* Red button to make it visible */
        color: white !important;
        border-radius: 50%;
        padding: 0.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* 5. Hide Footer/Toolbar */
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    [data-testid="stToolbar"] {visibility: hidden;}

    /* 6. Form Badges */
    .form-badge {
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
        margin-right: 4px;
        color: white;
    }
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
        "menu_logs": "System Logs", "balance": "Balance", "add_credit": "Add Credit",
        "promote": "Promote to Admin", "delete": "Delete User", "save": "Save Changes"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "create_acc": "إنشاء الحساب",
        "nav": "القائمة الرئيسية", "menu_predictions": "التوقعات المباشرة", "menu_profile": "ملفي الشخصي",
        "menu_admin_dash": "لوحة التحكم", "menu_users": "إدارة المستخدمين",
        "menu_logs": "سجلات النظام", "balance": "الرصيد", "add_credit": "إضافة رصيد",
        "promote": "ترقية لمدير", "delete": "حذف المستخدم", "save": "حفظ التغييرات"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v10_grey.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users with Balance
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    # Logs
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    # Bets
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),))
        conn.commit()
    except: pass
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
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()), 'New User', 1000.0))
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

# --- DATA ENGINE ---
@st.cache_data(ttl=600)
def fetch_matches():
    url = "https://api.openligadb.de/getmatchdata/bl1/2025"
    matches = []
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            for m in r.json():
                dt = datetime.strptime(m['matchDateTime'], "%Y-%m-%dT%H:%M:%S")
                if dt > datetime.now():
                    matches.append({"Date": dt.strftime("%Y-%m-%d"), "Time": dt.strftime("%H:%M"), "Home": m['team1']['teamName'], "Away": m['team2']['teamName']})
    except: pass
    
    # Fallback to avoid empty screen
    if not matches:
        d = datetime.now().strftime("%Y-%m-%d")
        matches = [
            {"Date": d, "Time": "20:00", "Home": "Real Madrid", "Away": "Barcelona"},
            {"Date": d, "Time": "22:00", "Home": "Liverpool", "Away": "Man City"},
            {"Date": d, "Time": "18:30", "Home": "Bayern", "Away": "Dortmund"}
        ]
    return matches

def render_consistent_form(team_name):
    random.seed(team_name) # Keep form consistent
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
    return {
        "1X2": {"Home": h_win, "Draw": d_win, "Away": a_win},
        "Odds": {"Home": round(100/h_win, 2), "Draw": round(100/d_win, 2), "Away": round(100/a_win, 2)},
        "Goals": {"Over": (seed * 4) % 100},
        "BTTS": {"Yes": (seed * 9) % 100}
    }

# --- UI HELPER ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- INIT ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

# --- LOGIN ---
if not st.session_state.logged_in:
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
            else: st.error("Error")
    
    with tab2:
        nu = st.text_input("New User")
        np = st.text_input("New Pass", type="password")
        if st.button(t('create_acc'), use_container_width=True):
            if manage_user("add", nu, np): st.success("Created! Login."); 
            else: st.error("Taken")

# --- MAIN APP ---
else:
    # SIDEBAR
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        u_data, _ = get_user_info(st.session_state.username)
        st.metric(t('balance'), f"${u_data[5]:,.2f}")
        
        lang = st.radio("Language", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
        
        options = [t('menu_predictions'), t('menu_profile')]
        if st.session_state.role == 'admin':
            options = [t('menu_admin_dash')] + options
        
        menu = st.radio(t('nav'), options)
        
        st.divider()
        if st.button(t('sign_out')):
            st.session_state.logged_in = False
            st.rerun()

    # 1. LIVE MATCHES & BETTING
    if menu == t('menu_predictions'):
        st.header(t('menu_predictions'))
        
        # ACTIVE SLIP
        if 'slip' in st.session_state:
            slip = st.session_state.slip
            with st.expander(f"🎫 Bet Slip: {slip['m']} (Active)", expanded=True):
                st.write(f"Selection: **{slip['t']}** | Odds: **{slip['o']}**")
                wager = st.number_input("Amount ($)", 1.0, u_data[5], 50.0)
                st.write(f"Potential Win: **${wager * slip['o']:.2f}**")
                
                if st.button("Confirm Bet", type="primary"):
                    if place_bet_db(st.session_state.username, slip['m'], slip['t'], wager, slip['o']):
                        st.success("Placed!")
                        del st.session_state.slip
                        st.rerun()
                    else: st.error("No Funds")

        matches = fetch_matches()
        for m in matches:
            data = analyze_advanced(m['Home'], m['Away'])
            odds = data['Odds']
            
            with st.container():
                c1, c2 = st.columns([3, 1])
                c1.subheader(f"{m['Home']} vs {m['Away']}")
                c1.caption(f"📅 {m['Date']} | ⏰ {m['Time']}")
                c2.markdown(f"**{m['Home']}**: {render_consistent_form(m['Home'])}", unsafe_allow_html=True)
                c2.markdown(f"**{m['Away']}**: {render_consistent_form(m['Away'])}", unsafe_allow_html=True)
                
                tab1, tab2, tab3 = st.tabs([t('winner'), t('goals'), t('btts')])
                
                with tab1:
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

                with tab2: st.metric("Over 2.5", f"{data['Goals']['Over']}%"); st.progress(data['Goals']['Over']/100)
                with tab3: st.metric("BTTS", f"{data['BTTS']['Yes']}%"); st.progress(data['BTTS']['Yes']/100)
                st.divider()

    # 2. PROFILE
    elif menu == t('menu_profile'):
        st.header(t('menu_profile'))
        st.metric(t('balance'), f"${u_data[5]:,.2f}")
        
        st.subheader("Betting History")
        u_info, bets = get_user_info(st.session_state.username)
        if bets:
            df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
            st.dataframe(df[['Date','Match','Type','Amt','Win','Status']], use_container_width=True)
        else:
            st.info("No bets found.")
            
        with st.expander("Edit Profile"):
            with st.form("prof"):
                np = st.text_input("New Pass")
                if st.form_submit_button(t('save')):
                    manage_user("update_profile", st.session_state.username, {'pass': np, 'bio': ''})
                    st.success("Updated")

    # 3. ADMIN DASHBOARD
    elif menu == t('menu_admin_dash'):
        st.header(t('menu_admin_dash'))
        
        conn = init_db()
        users = pd.read_sql("SELECT username, role, balance FROM users", conn)
        logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn)
        conn.close()
        
        c1, c2 = st.columns(2)
        c1.metric("Users", len(users))
        c2.metric("Logs", len(logs))
        
        st.dataframe(users, use_container_width=True)
        
        # ADMIN CONTROLS
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Manage Funds")
            target = st.selectbox("Select User", users['username'].unique())
            amt = st.number_input("Amount ($)", value=1000.0)
            if st.button(t('add_credit')):
                manage_user("add_credit", target, amt)
                log_action(st.session_state.username, f"Added ${amt} to {target}")
                st.success(f"Added ${amt}")
                st.rerun()
        
        with c2:
            st.subheader("Actions")
            if st.button(t('promote')):
                manage_user("change_role", target, "admin")
                st.rerun()
            if st.button(t('delete')):
                manage_user("delete", target)
                st.rerun()
        
        st.subheader(t('menu_logs'))
        st.dataframe(logs, use_container_width=True)
