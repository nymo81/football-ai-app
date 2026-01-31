import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- SMART CSS (FIXED SIDEBAR TOGGLE) ---
st.markdown("""
    <style>
    /* Hide Branding */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    [data-testid="stToolbar"] {visibility: hidden;}
    
    /* Force Sidebar Toggle to be Visible */
    [data-testid="stSidebarCollapsedControl"] {
        visibility: visible !important;
        display: block !important;
        color: white !important;
        z-index: 100000;
    }
    
    /* UI Polish */
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
        "nav": "Navigation", "menu_betting": "Betting Center", "menu_profile": "My Wallet & Profile",
        "balance": "Wallet Balance", "place_bet": "Place Bet", "amount": "Wager Amount",
        "potential_win": "Potential Win", "bet_placed": "Bet Placed Successfully!",
        "insufficient_funds": "Insufficient Funds!", "form": "Recent Form",
        "sign_out": "Sign Out", "login": "Login", "signup": "Sign Up",
        "admin_area": "Admin Dashboard", "no_matches": "No matches found.",
    },
    "ar": {
        "nav": "القائمة", "menu_betting": "مركز المراهنات", "menu_profile": "محفظتي والملف",
        "balance": "رصيد المحفظة", "place_bet": "ضع رهانك", "amount": "قيمة الرهان",
        "potential_win": "الربح المتوقع", "bet_placed": "تم وضع الرهان بنجاح!",
        "insufficient_funds": "الرصيد غير كافي!", "form": "أداء الفريق",
        "sign_out": "خروج", "login": "دخول", "signup": "تسجيل",
        "admin_area": "لوحة الإدارة", "no_matches": "لا توجد مباريات",
    }
}

# --- DATABASE ENGINE (Updated for Betting) ---
DB_NAME = 'football_super.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users: Added 'balance' column (Default 1000)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    # Bets Table
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000)", (str(datetime.now()),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return conn

def manage_user(action, target_user, data=None):
    conn = init_db()
    c = conn.cursor()
    if action == "add":
        try:
            # New users get 1000 coins bonus
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                      (target_user, data, 'user', str(datetime.now()), 'New Bettor', 1000.0))
            conn.commit()
            return True
        except: return False
    elif action == "update_balance":
        c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (data, target_user))
        conn.commit()
    conn.close()

def place_bet_db(user, match, bet_type, amount, odds):
    conn = init_db()
    c = conn.cursor()
    # Check balance
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
    else:
        conn.close()
        return False

def get_user_data(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    u = c.fetchone()
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,))
    b = c.fetchall()
    conn.close()
    return u, b

# --- DATA ENGINE ---
@st.cache_data(ttl=600)
def fetch_matches():
    # Fetch Real Bundesliga Data
    url = "https://api.openligadb.de/getmatchdata/bl1/2025" 
    matches = []
    try:
        r = requests.get(url, timeout=4)
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
    return matches

def generate_form():
    # Generates a random realistic form (e.g. W-W-L-D-W)
    outcomes = ['W', 'L', 'D', 'W', 'W', 'L']
    return random.sample(outcomes, 5)

def analyze_match(home, away):
    # AI Logic
    seed = len(home) + len(away)
    h_win = (seed * 7) % 100
    if h_win < 30: h_win += 30
    d_win = (100 - h_win) // 3
    a_win = 100 - h_win - d_win
    
    # Calculate Odds (Decimal)
    try: h_odd = round(100/h_win, 2)
    except: h_odd = 2.50
    try: a_odd = round(100/a_win, 2)
    except: a_odd = 3.10
    try: d_odd = round(100/d_win, 2)
    except: d_odd = 3.50

    return {"probs": [h_win, d_win, a_win], "odds": [h_odd, d_odd, a_odd]}

# --- UI COMPONENTS ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

def render_form_badges(form_list):
    html = ""
    for res in form_list:
        color = "form-w" if res == 'W' else "form-l" if res == 'L' else "form-d"
        html += f"<span class='form-badge {color}'>{res}</span>"
    return html

# --- PAGES ---
def login_view():
    st.markdown(f"<h1 style='text-align: center;'>⚽ Football AI Super</h1>", unsafe_allow_html=True)
    lang = st.selectbox("Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang == "العربية" else "en"
    
    tab1, tab2 = st.tabs([t('login'), t('signup')])
    with tab1:
        u = st.text_input(t('login'), key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("GO", use_container_width=True):
            user, _ = get_user_data(u)
            if user and user[1] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = user[2]
                st.rerun()
    with tab2:
        nu = st.text_input("New User")
        np = st.text_input("New Pass", type="password")
        if st.button("Create + Get $1000", use_container_width=True):
            if manage_user("add", nu, np):
                st.success("Created! Login now.")

def betting_dashboard():
    st.title(f"💰 {t('menu_betting')}")
    
    # Show User Balance
    user_info, _ = get_user_data(st.session_state.username)
    st.metric(t('balance'), f"${user_info[5]:,.2f}")
    
    matches = fetch_matches()
    if not matches: st.warning(t('no_matches'))

    for m in matches:
        data = analyze_match(m['Home'], m['Away'])
        probs = data['probs']
        odds = data['odds']
        
        with st.container():
            # Match Header with Form Guide
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{m['Home']} vs {m['Away']}")
                st.caption(f"📅 {m['Date']} | ⏰ {m['Time']}")
                # Form Guide
                st.markdown(f"{m['Home']}: {render_form_badges(generate_form())}", unsafe_allow_html=True)
                st.markdown(f"{m['Away']}: {render_form_badges(generate_form())}", unsafe_allow_html=True)
            
            # Betting Odds Buttons
            b1, b2, b3 = st.columns(3)
            
            # Home Bet
            with b1:
                st.info(f"🏠 {m['Home']} ({probs[0]}%)")
                if st.button(f"Bet Home @ {odds[0]}", key=f"bh_{m['Home']}"):
                    st.session_state.bet_slip = {'match': f"{m['Home']} vs {m['Away']}", 'type': 'HOME', 'odds': odds[0]}
            
            # Draw Bet
            with b2:
                st.warning(f"⚖️ Draw ({probs[1]}%)")
                if st.button(f"Bet Draw @ {odds[1]}", key=f"bd_{m['Home']}"):
                    st.session_state.bet_slip = {'match': f"{m['Home']} vs {m['Away']}", 'type': 'DRAW', 'odds': odds[1]}
            
            # Away Bet
            with b3:
                st.error(f"✈️ {m['Away']} ({probs[2]}%)")
                if st.button(f"Bet Away @ {odds[2]}", key=f"ba_{m['Home']}"):
                    st.session_state.bet_slip = {'match': f"{m['Home']} vs {m['Away']}", 'type': 'AWAY', 'odds': odds[2]}
            
            st.markdown("---")

    # Bet Slip Pop-up (Bottom)
    if 'bet_slip' in st.session_state:
        slip = st.session_state.bet_slip
        with st.expander("🎫 Active Bet Slip", expanded=True):
            st.write(f"**Match:** {slip['match']}")
            st.write(f"**Prediction:** {slip['type']} (Odds: {slip['odds']})")
            wager = st.number_input(t('amount'), min_value=10, max_value=int(user_info[5]), value=50)
            st.write(f"**{t('potential_win')}:** ${wager * slip['odds']:.2f}")
            
            if st.button(t('place_bet'), type="primary"):
                if place_bet_db(st.session_state.username, slip['match'], slip['type'], wager, slip['odds']):
                    st.success(t('bet_placed'))
                    del st.session_state.bet_slip
                    st.rerun()
                else:
                    st.error(t('insufficient_funds'))

def profile_page():
    st.title(f"👤 {t('menu_profile')}")
    u, bets = get_user_data(st.session_state.username)
    
    st.metric("Total Balance", f"${u[5]:,.2f}")
    
    st.subheader("📜 Bet History")
    if bets:
        for b in bets:
            # b = (id, user, match, type, amount, win, status, date)
            col_color = "green" if b[6] == "WON" else "orange"
            st.markdown(f"""
            <div style='border-left: 5px solid {col_color}; padding-left: 10px; margin-bottom: 10px; background: #1e1e1e; padding: 10px;'>
                <b>{b[2]}</b><br>
                Type: {b[3]} | Wager: ${b[4]} | Potential: ${b[5]}<br>
                <small>{b[7]} | Status: {b[6]}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No bets placed yet.")

# --- MAIN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

if not st.session_state.logged_in:
    login_view()
else:
    # Sidebar
    st.sidebar.title(t('nav'))
    lang_toggle = st.sidebar.radio("Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    menu = st.sidebar.radio("Go To:", [t('menu_betting'), t('menu_profile'), t('sign_out')])
    
    if menu == t('sign_out'):
        st.session_state.logged_in = False
        st.rerun()
    elif menu == t('menu_betting'):
        betting_dashboard()
    elif menu == t('menu_profile'):
        profile_page()
