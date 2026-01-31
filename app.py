import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- THEME MANAGER (CSS) ---
# This allows changing the theme dynamically without reloading
if 'theme' not in st.session_state:
    st.session_state.theme = 'Dark'

def get_theme_css(theme):
    if theme == 'Dark':
        # Professional Dark Blue-Grey (Not Pure Black)
        bg_color = "#121212" 
        card_color = "#1E1E1E"
        text_color = "#E0E0E0"
        border_color = "#333333"
    else:
        # Clean Light Mode
        bg_color = "#F0F2F6"
        card_color = "#FFFFFF"
        text_color = "#31333F"
        border_color = "#DDDDDD"

    return f"""
    <style>
    /* Main Background */
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
    }}
    
    /* Hide Footer */
    footer {{visibility: hidden;}}
    .stAppDeployButton {{display: none;}}
    
    /* Metrics & Cards */
    div[data-testid="stMetric"], div[data-testid="stExpander"] {{
        background-color: {card_color} !important;
        border: 1px solid {border_color};
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}
    
    /* Text Input Fields */
    .stTextInput input {{
        background-color: {card_color};
        color: {text_color};
        border: 1px solid {border_color};
    }}
    
    /* Form Badges */
    .form-badge {{
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
        margin-right: 4px;
        color: white;
        display: inline-block;
    }}
    .form-w {{background-color: #28a745;}}
    .form-d {{background-color: #6c757d;}}
    .form-l {{background-color: #dc3545;}}
    </style>
    """

# --- DATABASE ENGINE ---
DB_NAME = 'football_v8_stable.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try:
        # Admin gets 1 Million Coins
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 1000000.0)", (str(datetime.now()),))
        conn.commit()
    except: pass
    return conn

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
        elif action == "add_credit":
            c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (data, target_user))
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

def place_bet_transaction(user, match, b_type, amt, odds):
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute("SELECT balance FROM users WHERE username=?", (user,))
        current_bal = c.fetchone()[0]
        if current_bal >= amt:
            new_bal = current_bal - amt
            pot_win = round(amt * odds, 2)
            c.execute("UPDATE users SET balance=? WHERE username=?", (new_bal, user))
            c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user, match, b_type, amt, pot_win, 'OPEN', str(datetime.now())))
            conn.commit()
            return True
        return False
    finally: conn.close()

# --- DATA & AI ---
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
    
    # Fallback Data (To ensure app isn't blank)
    if not matches:
        d = datetime.now().strftime("%Y-%m-%d")
        matches = [
            {"Date": d, "Time": "20:45", "Home": "Real Madrid", "Away": "Barcelona"},
            {"Date": d, "Time": "18:00", "Home": "Liverpool", "Away": "Man City"},
            {"Date": d, "Time": "21:00", "Home": "Bayern", "Away": "Dortmund"}
        ]
    return matches

def render_consistent_form(team_name):
    random.seed(team_name) 
    form = random.sample(['W', 'L', 'D', 'W', 'W', 'L'], 5)
    html = ""
    for res in form:
        c = "form-w" if res == 'W' else "form-l" if res == 'L' else "form-d"
        html += f"<span class='form-badge {c}'>{res}</span>"
    return html

def analyze_full(home, away):
    seed = len(home) + len(away)
    h = (seed * 7) % 100
    if h < 30: h += 30
    d = (100 - h) // 3
    a = 100 - h - d
    return {
        "1X2": [h, d, a],
        "Odds": [round(100/h, 2), round(100/d, 2), round(100/a, 2)],
        "Goals": (seed * 4) % 100,
        "BTTS": (seed * 9) % 100
    }

# --- TRANSLATIONS ---
LANG = {
    "en": {"nav": "Menu", "betting": "Matches", "profile": "My Wallet", "admin": "Admin", "bal": "Balance", "login": "Login", "create": "Create Account", "logout": "Logout", "add_funds": "Add Funds", "del": "Delete User"},
    "ar": {"nav": "القائمة", "betting": "المباريات", "profile": "المحفظة", "admin": "الإدارة", "bal": "الرصيد", "login": "دخول", "create": "إنشاء حساب", "logout": "خروج", "add_funds": "إضافة رصيد", "del": "حذف"}
}

def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- INIT ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

# Apply CSS based on selected theme
st.markdown(get_theme_css(st.session_state.theme), unsafe_allow_html=True)

# --- LOGIN ---
if not st.session_state.logged_in:
    st.title("⚽ Football AI Pro")
    
    # Theme Toggle on Login Screen
    col_t1, col_t2 = st.columns([8, 2])
    with col_t2:
        theme = st.selectbox("Theme", ["Dark", "Light"], key="theme_select_login")
        st.session_state.theme = theme

    c1, c2 = st.columns(2)
    with c1:
        st.subheader(t("login"))
        u = st.text_input("User", key="l_u")
        p = st.text_input("Pass", type="password", key="l_p")
        if st.button("GO"):
            d, _ = get_data(u)
            if d and d[1] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = d[2]
                st.rerun()
            else: st.error("Invalid")
    with c2:
        st.subheader(t("create"))
        nu = st.text_input("New User")
        np = st.text_input("New Pass", type="password")
        if st.button("Create"):
            if manage_user("add", nu, np): st.success("Created! Login now."); 
            else: st.error("Taken")

# --- MAIN APP ---
else:
    # SIDEBAR
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        u_data, _ = get_data(st.session_state.username)
        st.metric(t("bal"), f"${u_data[5]:,.2f}")
        
        # Settings
        st.markdown("---")
        st.caption("Settings")
        l = st.radio("Language", ["English", "العربية"])
        st.session_state.lang = "ar" if l == "العربية" else "en"
        
        th = st.radio("Theme", ["Dark", "Light"])
        st.session_state.theme = th
        
        # Navigation
        st.markdown("---")
        opts = [t("betting"), t("profile")]
        if st.session_state.role == 'admin': opts = [t("admin")] + opts
        menu = st.radio(t("nav"), opts)
        
        st.markdown("---")
        if st.button(t("logout")):
            st.session_state.logged_in = False
            st.rerun()

    # 1. BETTING PAGE
    if menu == t("betting"):
        st.subheader(f"🔥 {t('betting')}")
        matches = fetch_matches()
        
        # ACTIVE BET SLIP (Sticky)
        if 'slip' in st.session_state:
            slip = st.session_state.slip
            with st.expander(f"🎫 Bet Slip: {slip['m']} (Active)", expanded=True):
                c1, c2 = st.columns([2,1])
                wager = c1.number_input("Amount", 1.0, u_data[5], 50.0)
                c2.metric("Win", f"${wager * slip['o']:.2f}")
                
                if st.button("Confirm Bet", type="primary", use_container_width=True):
                    if place_bet_transaction(st.session_state.username, slip['m'], slip['t'], wager, slip['o']):
                        st.success("Bet Placed!")
                        del st.session_state.slip
                        st.rerun()
                    else: st.error("No Funds")

        for m in matches:
            data = analyze_full(m['Home'], m['Away'])
            odds = data['Odds']
            probs = data['1X2']
            
            with st.container():
                # Clean Match Header
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{m['Home']}** vs **{m['Away']}**")
                c1.caption(f"{m['Time']} | {m['Date']}")
                c2.markdown(f"{render_consistent_form(m['Home'])}", unsafe_allow_html=True)
                c2.markdown(f"{render_consistent_form(m['Away'])}", unsafe_allow_html=True)
                
                # Tabs (The feature you liked)
                tab1, tab2, tab3 = st.tabs(["Match Winner", "Goals", "BTTS"])
                
                with tab1:
                    b1, b2, b3 = st.columns(3)
                    if b1.button(f"🏠 Home {odds[0]}", key=f"h{m['Home']}"):
                        st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'HOME', 'o': odds[0]}
                        st.rerun()
                    if b2.button(f"⚖️ Draw {odds[1]}", key=f"d{m['Home']}"):
                        st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'DRAW', 'o': odds[1]}
                        st.rerun()
                    if b3.button(f"✈️ Away {odds[2]}", key=f"a{m['Home']}"):
                        st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'AWAY', 'o': odds[2]}
                        st.rerun()
                
                with tab2:
                    st.progress(data['Goals']/100)
                    st.caption(f"Over 2.5 Probability: {data['Goals']}%")
                
                with tab3:
                    st.progress(data['BTTS']/100)
                    st.caption(f"BTTS Probability: {data['BTTS']}%")
                
                st.markdown("---")

    # 2. ADMIN PANEL
    elif menu == t("admin"):
        st.subheader("🛡️ Admin Dashboard")
        conn = init_db()
        users = pd.read_sql("SELECT username, role, balance FROM users", conn)
        conn.close()
        
        st.dataframe(users, use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("### Manage Funds")
            target = st.selectbox("Select User", users['username'].unique())
            amt = st.number_input("Amount to Add ($)", 0.0, 100000.0, 1000.0)
            if st.button(t("add_funds")):
                manage_user("add_credit", target, amt)
                st.success(f"Added ${amt} to {target}")
                st.rerun()
        
        with c2:
            st.write("### Actions")
            if st.button(t("del"), type="primary"):
                manage_user("delete", target)
                st.rerun()
            if st.button("Make Admin"):
                manage_user("change_role", target, 'admin')
                st.rerun()

    # 3. PROFILE
    elif menu == t("profile"):
        st.subheader(t("profile"))
        st.metric(t("bal"), f"${u_data[5]:,.2f}")
        
        st.write("### History")
        if bets:
            df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
            st.dataframe(df[['Date','Match','Type','Amt','Win','Status']], use_container_width=True)
        else:
            st.info("No history")
