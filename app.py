import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CLEAN CSS (No "Hiding" Hacks - Just Clean UI) ---
st.markdown("""
    <style>
    /* Remove the "Black Box" background you disliked */
    .stMetric {
        background-color: transparent !important;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 10px;
    }
    
    /* Make buttons look better */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
    }

    /* Simple hiding of the footer only */
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "create_acc": "Create Account",
        "nav": "Menu", "menu_predictions": "Matches & Betting", "menu_profile": "Wallet & Profile",
        "menu_admin_dash": "Admin Control", "menu_users": "Manage Users", "menu_logs": "Logs",
        "balance": "Balance", "place_bet": "Place Bet", "bet_history": "My Bets",
        "sign_out": "Sign Out", "promote": "Promote", "demote": "Demote", "delete": "Delete"
    },
    "ar": {
        "app_name": "المحلل الذكي", "login": "دخول", "signup": "تسجيل",
        "username": "المستخدم", "password": "كلمة المرور", "create_acc": "إنشاء حساب",
        "nav": "القائمة", "menu_predictions": "المباريات والمراهنة", "menu_profile": "المحفظة والملف",
        "menu_admin_dash": "لوحة الإدارة", "menu_users": "إدارة المستخدمين", "menu_logs": "السجلات",
        "balance": "الرصيد", "place_bet": "راهن الآن", "bet_history": "سجل رهاناتي",
        "sign_out": "خروج", "promote": "ترقية", "demote": "تخفيض", "delete": "حذف"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v5.db'

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
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()), 'New', 1000.0))
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
    except: return False
    finally: conn.close()

def get_data(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    u = c.fetchone()
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,))
    b = c.fetchall()
    conn.close()
    return u, b

def place_bet(user, match, b_type, amt, odds):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username=?", (user,))
    bal = c.fetchone()[0]
    if bal >= amt:
        c.execute("UPDATE users SET balance=? WHERE username=?", (bal - amt, user))
        c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user, match, b_type, amt, amt*odds, 'OPEN', str(datetime.now())))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# --- FETCH & AI ---
@st.cache_data(ttl=600)
def fetch_matches():
    # Only Real Data + Fallback if empty to ensure UI works
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
    
    # Minimal fallback so app isn't blank
    if not matches:
        d = datetime.now().strftime("%Y-%m-%d")
        matches = [
            {"Date": d, "Time": "20:45", "Home": "Real Madrid", "Away": "Barcelona"},
            {"Date": d, "Time": "18:00", "Home": "Liverpool", "Away": "Man City"},
            {"Date": d, "Time": "21:00", "Home": "Bayern", "Away": "Dortmund"}
        ]
    return matches

def get_odds(home, away):
    # Deterministic odds based on name length (Consistent AI)
    s = len(home) + len(away)
    h = (s * 7) % 100
    if h < 30: h += 30
    d = (100 - h) // 3
    a = 100 - h - d
    return round(100/h, 2), round(100/d, 2), round(100/a, 2), h, d, a

# --- UI ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

# --- LOGIN PAGE ---
if not st.session_state.logged_in:
    st.title("⚽ " + t('app_name'))
    l_col, r_col = st.columns([1,1])
    
    with l_col:
        st.subheader(t('login'))
        u = st.text_input(t('username'), key="l_u")
        p = st.text_input(t('password'), type="password", key="l_p")
        if st.button("Login"):
            d, _ = get_data(u)
            if d and d[1] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = d[2]
                st.rerun()
            else: st.error("Invalid")

    with r_col:
        st.subheader(t('signup'))
        nu = st.text_input("New User")
        np = st.text_input("New Pass", type="password")
        if st.button("Create Account"):
            if manage_user("add", nu, np): st.success("Created!"); st.rerun()
            else: st.error("Taken")

    st.divider()
    lang = st.radio("Language", ["English", "العربية"], horizontal=True)
    st.session_state.lang = "ar" if lang == "العربية" else "en"

# --- MAIN APP ---
else:
    # SIDEBAR
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        lang = st.radio("Language / اللغة", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
        
        opts = [t('menu_predictions'), t('menu_profile')]
        if st.session_state.role == 'admin': opts = [t('menu_admin_dash')] + opts
        menu = st.radio(t('nav'), opts)
        
        st.divider()
        if st.button(t('sign_out')):
            st.session_state.logged_in = False
            st.rerun()

    # ADMIN DASHBOARD
    if menu == t('menu_admin_dash'):
        st.header(t('menu_admin_dash'))
        conn = init_db()
        users = pd.read_sql("SELECT username, role, balance, created_at FROM users", conn)
        logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC", conn)
        conn.close()

        c1, c2 = st.columns(2)
        c1.metric("Total Users", len(users))
        c2.metric("System Logs", len(logs))

        st.subheader("Manage Users")
        # Editable Dataframe is easier
        st.dataframe(users, use_container_width=True)
        
        # Actions
        sel_user = st.selectbox("Select User to Modify", users['username'].unique())
        c1, c2, c3 = st.columns(3)
        if c1.button(t('promote')): manage_user("change_role", sel_user, "admin"); st.rerun()
        if c2.button(t('demote')): manage_user("change_role", sel_user, "user"); st.rerun()
        if c3.button(t('delete')): manage_user("delete", sel_user); st.rerun()
        
        st.subheader("System Logs")
        st.dataframe(logs, use_container_width=True)

    # PREDICTIONS & BETTING
    elif menu == t('menu_predictions'):
        u_info, _ = get_data(st.session_state.username)
        st.header(t('menu_predictions'))
        st.info(f"💰 {t('balance')}: **${u_info[5]:,.2f}**")
        
        matches = fetch_matches()
        for m in matches:
            oh, od, oa, ph, pd_val, pa = get_odds(m['Home'], m['Away'])
            
            with st.expander(f"{m['Home']} vs {m['Away']} ({m['Time']})", expanded=True):
                c1, c2, c3 = st.columns(3)
                
                # Home
                c1.write(f"**{m['Home']}**")
                c1.progress(ph/100)
                if c1.button(f"Win ({oh})", key=f"h_{m['Home']}"):
                    st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'HOME', 'o': oh}
                
                # Draw
                c2.write("**Draw**")
                c2.progress(pd_val/100)
                if c2.button(f"Draw ({od})", key=f"d_{m['Home']}"):
                    st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'DRAW', 'o': od}
                
                # Away
                c3.write(f"**{m['Away']}**")
                c3.progress(pa/100)
                if c3.button(f"Win ({oa})", key=f"a_{m['Home']}"):
                    st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'AWAY', 'o': oa}

        # Bet Slip
        if 'slip' in st.session_state:
            st.divider()
            s = st.session_state.slip
            st.warning(f"🎫 Slip: {s['m']} - {s['t']} @ {s['o']}")
            wager = st.number_input(t('amount'), min_value=1.0, max_value=u_info[5], value=50.0)
            if st.button(t('place_bet')):
                if place_bet(st.session_state.username, s['m'], s['t'], wager, s['o']):
                    st.success("Success!")
                    del st.session_state.slip
                    st.rerun()

    # PROFILE
    elif menu == t('menu_profile'):
        u_info, bets = get_data(st.session_state.username)
        st.header(t('menu_profile'))
        st.metric(t('balance'), f"${u_info[5]:,.2f}")
        
        st.subheader(t('bet_history'))
        if bets:
            df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
            st.dataframe(df[['Match','Type','Amt','Win','Status','Date']], use_container_width=True)
        else:
            st.write("No bets yet.")
        
        st.subheader("Edit Profile")
        new_pass = st.text_input("New Password")
        if st.button("Update"):
            manage_user("update_profile", st.session_state.username, {'pass': new_pass, 'bio': ''})
            st.success("Updated")
