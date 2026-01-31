import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Football AI Pro",
    layout="wide",
    page_icon="⚽",
    initial_sidebar_state="expanded"
)

# --- THEME MANAGEMENT ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

# --- DYNAMIC CSS (Based on Theme) ---
theme_css = """
<style>
    /* VARIABLES */
    :root {
        --bg-color: #0E1117;
        --card-bg: #1A1C24;
        --text-color: #ffffff;
        --accent: #FF4B4B;
        --border: #333;
        --shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* LIGHT MODE OVERRIDES */
    [data-theme="light"] {
        --bg-color: #ffffff;
        --card-bg: #f8f9fa;
        --text-color: #31333F;
        --accent: #FF4B4B;
        --border: #ddd;
        --shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* GLOBAL STYLES */
    .stApp {
        background-color: var(--bg-color);
        color: var(--text-color);
    }
    
    /* HIDE STREAMLIT BRANDING */
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    [data-testid="stToolbar"] {visibility: hidden;}
    
    /* MATCH CARD UI */
    .match-card {
        background-color: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: var(--shadow);
        transition: transform 0.2s;
    }
    .match-card:hover {
        transform: translateY(-2px);
    }
    
    /* FORM BADGES */
    .form-badge {
        display: inline-block;
        width: 20px;
        height: 20px;
        line-height: 20px;
        text-align: center;
        border-radius: 4px;
        font-size: 10px;
        font-weight: bold;
        color: white;
        margin-right: 2px;
    }
    .w {background: #28a745;}
    .l {background: #dc3545;}
    .d {background: #6c757d;}
    
    /* CUSTOM METRICS */
    div[data-testid="stMetric"] {
        background-color: var(--card-bg);
        border: 1px solid var(--border);
        padding: 15px;
        border-radius: 8px;
        box-shadow: var(--shadow);
    }
    
    /* BET TICKET */
    .ticket {
        border-top: 4px solid var(--accent);
        background: var(--card-bg);
        padding: 15px;
        border-radius: 0 0 8px 8px;
        box-shadow: var(--shadow);
    }
</style>
"""

# Inject CSS based on session state
bg_class = 'data-theme="light"' if st.session_state.theme == 'light' else 'data-theme="dark"'
st.markdown(f'<div {bg_class}></div>', unsafe_allow_html=True)
st.markdown(theme_css, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "nav": "Menu", "home": "Live Matches", "wallet": "My Wallet", "admin": "Admin",
        "balance": "Balance", "ticket": "Bet Slip", "place": "Place Bet", "odds": "Odds",
        "win": "To Win", "draw": "Draw", "form": "Form", "login": "Login", "create": "Create Account",
        "promo": "Admin Actions", "add_funds": "Add Funds", "del": "Delete User"
    },
    "ar": {
        "nav": "القائمة", "home": "المباريات", "wallet": "المحفظة", "admin": "الإدارة",
        "balance": "الرصيد", "ticket": "قسيمة الرهان", "place": "تأكيد", "odds": "الاحتمال",
        "win": "فوز", "draw": "تعادل", "form": "الأداء", "login": "دخول", "create": "حساب جديد",
        "promo": "إجراءات", "add_funds": "إضافة رصيد", "del": "حذف"
    }
}

def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- DATABASE ---
DB_NAME = 'football_ui_v1.db'
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY, user TEXT, match TEXT, selection TEXT, amount REAL, potential REAL, status TEXT, date TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('admin', '123', 'admin', 50000.0)")
        conn.commit()
    except: pass
    return conn

def db_action(query, params=()):
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute(query, params)
        conn.commit()
        return c.fetchall()
    except Exception as e:
        return None
    finally:
        conn.close()

# --- LOGIC ---
@st.cache_data(ttl=300)
def get_matches():
    # Only Real Data
    url = "https://api.openligadb.de/getmatchdata/bl1/2025"
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = []
            for m in r.json():
                dt = datetime.strptime(m['matchDateTime'], "%Y-%m-%dT%H:%M:%S")
                if dt > datetime.now():
                    data.append({
                        "id": m['matchID'], "date": dt.strftime("%d/%m"), "time": dt.strftime("%H:%M"),
                        "h": m['team1']['teamName'], "a": m['team2']['teamName']
                    })
            return data
    except: pass
    # Fallback to keep UI visible if API empty
    return [
        {"id": 1, "date": "Today", "time": "20:00", "h": "Real Madrid", "a": "Barcelona"},
        {"id": 2, "date": "Today", "time": "22:00", "h": "Man City", "a": "Liverpool"},
        {"id": 3, "date": "Tmrw", "time": "18:00", "h": "Bayern", "a": "Dortmund"}
    ]

def get_odds(h, a):
    # Stable odds generator
    seed = len(h) + len(a)
    p_h = (seed * 7) % 100
    if p_h < 30: p_h += 30
    p_d = (100 - p_h) // 3
    p_a = 100 - p_h - p_d
    return round(100/p_h, 2), round(100/p_d, 2), round(100/p_a, 2)

def render_form(name):
    random.seed(name)
    badges = ""
    for r in random.sample(['w','l','d','w','w','l'], 5):
        badges += f"<span class='form-badge {r}'>{r.upper()}</span>"
    return badges

# --- MAIN APP ---
if 'user' not in st.session_state:
    st.session_state.user = None

# 1. LOGIN SCREEN
if not st.session_state.user:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown(f"<h1 style='text-align:center'>⚽ Football AI Pro</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs([t("login"), t("create")])
        
        with tab1:
            u = st.text_input("Username", key="l_u")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("🚀 Enter", use_container_width=True):
                res = db_action("SELECT * FROM users WHERE username=?", (u,))
                if res and res[0][1] == p:
                    st.session_state.user = {'name': u, 'role': res[0][2]}
                    st.rerun()
                else: st.error("Invalid credentials")
                
        with tab2:
            nu = st.text_input("New Username")
            np = st.text_input("New Password", type="password")
            if st.button("✨ Join Now", use_container_width=True):
                if db_action("INSERT INTO users VALUES (?, ?, 'user', 1000.0)", (nu, np)):
                    st.success("Account created! Login now.")
                else: st.error("Username taken")
        
        st.divider()
        col_l, col_t = st.columns(2)
        with col_l:
            l = st.radio("Language", ["English", "العربية"], label_visibility="collapsed")
            st.session_state.lang = 'ar' if l == 'العربية' else 'en'
        with col_t:
            if st.button("🌗 Theme Toggle", use_container_width=True):
                toggle_theme()
                st.rerun()

# 2. DASHBOARD
else:
    # SIDEBAR
    with st.sidebar:
        st.title(f"👤 {st.session_state.user['name']}")
        bal = db_action("SELECT balance FROM users WHERE username=?", (st.session_state.user['name'],))[0][0]
        st.metric(t("balance"), f"${bal:,.2f}")
        
        menu = st.radio(t("nav"), [t("home"), t("wallet"), t("admin")] if st.session_state.user['role'] == 'admin' else [t("home"), t("wallet")])
        
        st.markdown("---")
        if st.button("🌗 Theme"): toggle_theme(); st.rerun()
        if st.button("🚪 Logout"): st.session_state.user = None; st.rerun()

    # PAGE: LIVE MATCHES
    if menu == t("home"):
        st.subheader(f"🔥 {t('home')}")
        matches = get_matches()
        
        # ACTIVE TICKET
        if 'slip' in st.session_state:
            s = st.session_state.slip
            with st.expander(f"🎫 {t('ticket')} (Active)", expanded=True):
                st.markdown(f"**{s['m']}**")
                st.info(f"{s['s']} @ {s['o']}")
                wager = st.number_input("Amount", 10.0, bal, 50.0)
                st.caption(f"Potential Win: ${wager * s['o']:.2f}")
                
                if st.button(t("place"), type="primary", use_container_width=True):
                    db_action("UPDATE users SET balance = balance - ? WHERE username=?", (wager, st.session_state.user['name']))
                    db_action("INSERT INTO bets (user, match, selection, amount, potential, status, date) VALUES (?,?,?,?,?,?,?)",
                              (st.session_state.user['name'], s['m'], s['s'], wager, wager*s['o'], 'OPEN', str(datetime.now())))
                    del st.session_state.slip
                    st.success("Success!")
                    st.rerun()
        
        # MATCH CARDS
        for m in matches:
            oh, od, oa = get_odds(m['h'], m['a'])
            
            # HTML Card Structure
            st.markdown(f"""
            <div class="match-card">
                <div style="display:flex; justify-content:space-between; color:#888; font-size:0.8em; margin-bottom:10px;">
                    <span>📅 {m['date']} {m['time']}</span>
                    <span>Bundesliga</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <div style="text-align:left; width:40%;">
                        <div style="font-weight:bold; font-size:1.1em;">{m['h']}</div>
                        <div>{render_form(m['h'])}</div>
                    </div>
                    <div style="font-weight:bold; color:var(--accent);">VS</div>
                    <div style="text-align:right; width:40%;">
                        <div style="font-weight:bold; font-size:1.1em;">{m['a']}</div>
                        <div>{render_form(m['a'])}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Button Logic (Streamlit buttons can't be inside HTML div comfortably, so we place them below)
            c1, c2, c3 = st.columns(3)
            if c1.button(f"Home {oh}", key=f"h{m['id']}"):
                st.session_state.slip = {'m': f"{m['h']} vs {m['a']}", 's': 'HOME', 'o': oh}
                st.rerun()
            if c2.button(f"Draw {od}", key=f"d{m['id']}"):
                st.session_state.slip = {'m': f"{m['h']} vs {m['a']}", 's': 'DRAW', 'o': od}
                st.rerun()
            if c3.button(f"Away {oa}", key=f"a{m['id']}"):
                st.session_state.slip = {'m': f"{m['h']} vs {m['a']}", 's': 'AWAY', 'o': oa}
                st.rerun()
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    # PAGE: WALLET
    elif menu == t("wallet"):
        st.subheader(f"💳 {t('wallet')}")
        
        c1, c2 = st.columns(2)
        c1.metric(t("balance"), f"${bal:,.2f}")
        c2.metric("Status", "VIP Member")
        
        st.markdown("### Transaction History")
        bets = db_action("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (st.session_state.user['name'],))
        if bets:
            df = pd.DataFrame(bets, columns=['ID','User','Match','Pick','Amt','Win','Status','Date'])
            st.dataframe(df[['Date','Match','Pick','Amt','Win','Status']], use_container_width=True)
        else:
            st.info("No betting history found.")

    # PAGE: ADMIN
    elif menu == t("admin"):
        st.subheader("🛡️ Admin Dashboard")
        
        tab_u, tab_f = st.tabs(["Users", "Finance"])
        
        users = pd.DataFrame(db_action("SELECT * FROM users"), columns=['User','Pass','Role','Bal'])
        
        with tab_u:
            st.dataframe(users, use_container_width=True)
            target = st.selectbox("Select User", users['User'].unique())
            c1, c2 = st.columns(2)
            if c1.button(t("del"), type="primary"):
                db_action("DELETE FROM users WHERE username=?", (target,))
                st.rerun()
            if c2.button("Reset Password"):
                db_action("UPDATE users SET password='123' WHERE username=?", (target,))
                st.success("Pass reset to '123'")

        with tab_f:
            st.write(f"Adjust Balance for: **{target}**")
            amt = st.number_input("Amount ($)", value=1000.0)
            if st.button(t("add_funds")):
                db_action("UPDATE users SET balance = balance + ? WHERE username=?", (amt, target))
                st.success("Done")
                st.rerun()
