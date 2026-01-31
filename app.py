import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CSS: DARK GREY & FIXED NAV ---
st.markdown("""
    <style>
    /* 1. THEME */
    .stApp {background-color: #262730; color: #FAFAFA;}
    [data-testid="stSidebar"] {background-color: #1F2026; border-right: 1px solid #333;}
    
    /* 2. CARDS */
    div[data-testid="stMetric"], div[data-testid="stExpander"] {
        background-color: #31333F !important;
        border: 1px solid #45474B;
        border-radius: 8px;
    }
    
    /* 3. NAV BUTTON FIX (Bottom Left) */
    [data-testid="stSidebarCollapsedControl"] {
        position: fixed !important; bottom: 20px !important; left: 20px !important; top: auto !important;
        z-index: 1000000; background-color: #FF4B4B; color: white !important;
        border-radius: 50%; padding: 0.5rem;
    }
    
    /* 4. HIDE JUNK */
    footer {visibility: hidden;} .stAppDeployButton {display: none;} [data-testid="stToolbar"] {visibility: hidden;}

    /* 5. LEAGUE BADGES */
    .league-tag {
        font-size: 0.75em; padding: 2px 6px; border-radius: 4px; background-color: #444; color: #aaa; margin-bottom: 5px; display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "nav": "Navigation",
        "menu_live": "Global Matches", "menu_profile": "My Wallet", "menu_admin": "Admin",
        "balance": "Balance", "add_funds": "Add Funds", "place_bet": "Place Bet",
        "no_matches": "No matches found today.", "logout": "Logout"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "دخول", "signup": "تسجيل",
        "username": "المستخدم", "password": "كلمة المرور", "nav": "القائمة",
        "menu_live": "المباريات العالمية", "menu_profile": "المحفظة", "menu_admin": "الإدارة",
        "balance": "الرصيد", "add_funds": "إضافة رصيد", "place_bet": "تأكيد الرهان",
        "no_matches": "لا توجد مباريات اليوم", "logout": "خروج"
    }
}

# --- DATABASE ---
DB_NAME = 'football_global_v1.db'
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY, user TEXT, match TEXT, pick TEXT, amt REAL, win REAL, status TEXT, date TEXT)''')
    try: c.execute("INSERT INTO users VALUES ('admin', '123', 'admin', 100000.0)"); conn.commit()
    except: pass
    return conn

def manage_db(query, params=()):
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute(query, params)
        conn.commit()
        return c.fetchall()
    except: return False
    finally: conn.close()

# --- NEW: ESPN GLOBAL API ENGINE ---
@st.cache_data(ttl=600)
def fetch_global_matches():
    # We fetch from ESPN's hidden public API for multiple leagues
    endpoints = [
        {"league": "🇬🇧 Premier League", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"},
        {"league": "🇬🇧 Championship", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.2/scoreboard"},
        {"league": "🇪🇸 La Liga", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"},
        {"league": "🇩🇪 Bundesliga", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard"},
        {"league": "🇮🇹 Serie A", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"},
        {"league": "🇫🇷 Ligue 1", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/fra.1/scoreboard"},
        {"league": "🇳🇱 Eredivisie", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/ned.1/scoreboard"},
    ]
    
    all_matches = []
    
    for ep in endpoints:
        try:
            r = requests.get(ep['url'], timeout=2)
            if r.status_code == 200:
                data = r.json()
                for event in data.get('events', []):
                    # Extract Data
                    match_id = event['id']
                    status = event['status']['type']['state'] # pre, in, post
                    date_str = event['date'] # UTC string
                    
                    # Convert Time: UTC -> Baghdad (+3)
                    dt_utc = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
                    dt_baghdad = dt_utc + timedelta(hours=3)
                    
                    # Only show matches for TODAY (or currently playing)
                    if dt_baghdad.date() == datetime.now().date() or status == 'in':
                        teams = event['competitions'][0]['competitors']
                        home_team = teams[0]['team']['displayName']
                        away_team = teams[1]['team']['displayName']
                        
                        all_matches.append({
                            "League": ep['league'],
                            "Date": dt_baghdad.strftime("%Y-%m-%d"),
                            "Time": dt_baghdad.strftime("%H:%M"),
                            "Home": home_team,
                            "Away": away_team,
                            "Status": status
                        })
        except: continue
        
    return all_matches

# --- AI ENGINE ---
def analyze_match(h, a):
    # Stable AI prediction based on hashing names
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10 # 10-95%
    d_win = (100 - h_win) // 3
    a_win = 100 - h_win - d_win
    
    return {
        "1X2": [h_win, d_win, a_win],
        "Odds": [round(100/h_win, 2), round(100/d_win, 2), round(100/a_win, 2)],
        "Goals": (seed * 4) % 100,
        "BTTS": (seed * 9) % 100
    }

def get_form(name):
    random.seed(name)
    return "".join([f"<span style='color:{'#4CAF50' if x=='W' else '#F44336' if x=='L' else '#9E9E9E'};font-weight:bold;margin-right:3px'>{x}</span>" for x in random.sample(['W','L','D','W','L'], 5)])

# --- UI HELPER ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- INIT ---
if 'user' not in st.session_state:
    st.session_state.user = None
    init_db()

# --- LOGIN ---
if not st.session_state.user:
    st.title(f"⚽ {t('app_name')}")
    l = st.selectbox("Language", ["English", "العربية"])
    st.session_state.lang = 'ar' if l == "العربية" else 'en'
    
    t1, t2 = st.tabs([t('login'), t('signup')])
    with t1:
        u = st.text_input(t('username'), key="l1")
        p = st.text_input(t('password'), type="password", key="l2")
        if st.button("GO"):
            res = manage_db("SELECT * FROM users WHERE username=?", (u,))
            if res and res[0][1] == p:
                st.session_state.user = {'name': u, 'role': res[0][2]}
                st.rerun()
    with t2:
        nu = st.text_input("New User")
        np = st.text_input("New Pass", type="password")
        if st.button("Create"):
            if manage_db("INSERT INTO users VALUES (?, ?, 'user', 1000.0)", (nu, np)):
                st.success("Created! Login.")

# --- MAIN APP ---
else:
    # Sidebar
    with st.sidebar:
        st.header(f"👤 {st.session_state.user['name']}")
        bal = manage_db("SELECT balance FROM users WHERE username=?", (st.session_state.user['name'],))[0][0]
        st.metric(t('balance'), f"${bal:,.2f}")
        
        st.divider()
        nav = st.radio(t('nav'), [t('menu_live'), t('menu_profile'), t('menu_admin')] if st.session_state.user['role'] == 'admin' else [t('menu_live'), t('menu_profile')])
        st.divider()
        if st.button(t('logout')):
            st.session_state.user = None
            st.rerun()

    # 1. LIVE MATCHES
    if nav == t('menu_live'):
        st.header(f"🌍 {t('menu_live')}")
        
        # ACTIVE SLIP
        if 'slip' in st.session_state:
            s = st.session_state.slip
            with st.expander(f"🎫 Ticket: {s['m']} (Active)", expanded=True):
                c1, c2 = st.columns([2,1])
                wager = c1.number_input("Wager", 1.0, bal, 50.0)
                c2.metric("Win", f"${wager * s['o']:.2f}")
                if st.button(t('place_bet'), type="primary", use_container_width=True):
                    manage_db("UPDATE users SET balance = balance - ? WHERE username=?", (wager, st.session_state.user['name']))
                    manage_db("INSERT INTO bets (user, match, pick, amt, win, status, date) VALUES (?,?,?,?,?,?,?)", 
                              (st.session_state.user['name'], s['m'], s['s'], wager, wager*s['o'], 'OPEN', str(datetime.now())))
                    del st.session_state.slip
                    st.rerun()

        matches = fetch_global_matches()
        
        if not matches:
            st.warning(t('no_matches'))
            st.write("Checking: Premier League, La Liga, Bundesliga, Serie A, Ligue 1...")
        
        # Group by League
        df = pd.DataFrame(matches)
        if not df.empty:
            leagues = df['League'].unique()
            for league in leagues:
                st.subheader(league)
                league_matches = df[df['League'] == league]
                
                for _, m in league_matches.iterrows():
                    ai = analyze_match(m['Home'], m['Away'])
                    odds = ai['Odds']
                    
                    with st.container():
                        c1, c2 = st.columns([3, 1])
                        c1.write(f"**{m['Home']}** vs **{m['Away']}**")
                        c1.caption(f"⏰ {m['Time']} (Baghdad) | Status: {m['Status']}")
                        c2.markdown(f"{get_form(m['Home'])} vs {get_form(m['Away'])}", unsafe_allow_html=True)
                        
                        b1, b2, b3 = st.columns(3)
                        if b1.button(f"Home {odds[0]}", key=f"h_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 's': 'HOME', 'o': odds[0]}
                            st.rerun()
                        if b2.button(f"Draw {odds[1]}", key=f"d_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 's': 'DRAW', 'o': odds[1]}
                            st.rerun()
                        if b3.button(f"Away {odds[2]}", key=f"a_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 's': 'AWAY', 'o': odds[2]}
                            st.rerun()
                        st.markdown("---")

    # 2. PROFILE
    elif nav == t('menu_profile'):
        st.header(t('menu_profile'))
        st.metric(t('balance'), f"${bal:,.2f}")
        
        bets = manage_db("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (st.session_state.user['name'],))
        if bets:
            df = pd.DataFrame(bets, columns=['ID','User','Match','Pick','Amt','Win','Status','Date'])
            st.dataframe(df[['Date','Match','Pick','Amt','Win','Status']], use_container_width=True)
        else:
            st.info("No bets found.")

    # 3. ADMIN
    elif nav == t('menu_admin'):
        st.header("Admin Panel")
        users = pd.DataFrame(manage_db("SELECT * FROM users"), columns=['User','Pass','Role','Bal'])
        st.dataframe(users)
        
        target = st.selectbox("User", users['User'].unique())
        amt = st.number_input("Amount", 0.0, 100000.0, 1000.0)
        
        c1, c2 = st.columns(2)
        if c1.button(t('add_funds')):
            manage_db("UPDATE users SET balance = balance + ? WHERE username=?", (amt, target))
            st.success("Done")
            st.rerun()
        if c2.button("Delete User"):
            manage_db("DELETE FROM users WHERE username=?", (target,))
            st.rerun()
