import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CLEAN CSS ---
st.markdown("""
    <style>
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    
    /* Transparent Metrics */
    .stMetric {
        background-color: transparent !important;
        border: 1px solid #444;
        border-radius: 5px;
    }
    
    /* Form Badges */
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
    
    /* Bet Ticket Style */
    .bet-ticket {
        background-color: #1e1e1e;
        border: 2px dashed #444;
        padding: 15px;
        border-radius: 10px;
        margin-top: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS ---
LANG = {
    "en": {
        "nav": "Navigation", "menu_betting": "Live Matches", "menu_profile": "My Wallet",
        "menu_admin": "Admin Panel", "balance": "Wallet", "place_bet": "Confirm Bet",
        "potential_win": "Potential Win", "bet_placed": "Ticket Confirmed!",
        "insufficient_funds": "Insufficient Funds!", "form": "Form",
        "login": "Login", "signup": "Sign Up", "sign_out": "Sign Out",
        "odds": "Odds", "winner": "Match Winner", "goals": "Goals", "btts": "BTTS"
    },
    "ar": {
        "nav": "القائمة", "menu_betting": "المباريات", "menu_profile": "محفظتي",
        "menu_admin": "لوحة الإدارة", "balance": "الرصيد", "place_bet": "تأكيد الرهان",
        "potential_win": "الربح المتوقع", "bet_placed": "تم تأكيد التذكرة!",
        "insufficient_funds": "الرصيد لا يكفي!", "form": "الأداء",
        "login": "دخول", "signup": "تسجيل", "sign_out": "خروج",
        "odds": "الاحتمالات", "winner": "الفائز", "goals": "الأهداف", "btts": "يسجل الفريقان"
    }
}

# --- DATABASE ENGINE ---
DB_NAME = 'football_v7_admin.db'

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
            # Admin adding money
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
    
    # Fallback to keep app alive if API is empty
    if not matches:
        d = datetime.now().strftime("%Y-%m-%d")
        matches = [
            {"Date": d, "Time": "20:45", "Home": "Real Madrid", "Away": "Barcelona"},
            {"Date": d, "Time": "18:00", "Home": "Liverpool", "Away": "Man City"},
            {"Date": d, "Time": "21:00", "Home": "Bayern", "Away": "Dortmund"}
        ]
    return matches

def render_consistent_form(team_name):
    # Fix: Seed random with team name so it doesn't change on refresh
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

# --- UI HELPER ---
def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

# --- LOGIN ---
if not st.session_state.logged_in:
    st.title("⚽ " + t('app_name'))
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(t('login'))
        u = st.text_input("User", key="l_u")
        p = st.text_input("Pass", type="password", key="l_p")
        if st.button("Login"):
            d, _ = get_data(u)
            if d and d[1] == p:
                st.session_state.logged_in = True
                st.session_state.username = u
                st.session_state.role = d[2]
                st.rerun()
            else: st.error("Invalid")
    with c2:
        st.subheader(t('signup'))
        nu = st.text_input("New User")
        np = st.text_input("New Pass", type="password")
        if st.button("Create"):
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
        u_data, _ = get_data(st.session_state.username)
        st.metric(t('balance'), f"${u_data[5]:,.2f}")
        
        lang = st.radio("Language", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
        
        opts = [t('menu_betting'), t('menu_profile')]
        if st.session_state.role == 'admin': opts = [t('menu_admin')] + opts
        menu = st.radio(t('nav'), opts)
        
        st.divider()
        if st.button(t('sign_out')):
            st.session_state.logged_in = False
            st.rerun()

    # 1. BETTING PAGE
    if menu == t('menu_betting'):
        st.header(t('menu_betting'))
        matches = fetch_matches()
        
        # ACTIVE TICKET (Sticky Top)
        if 'slip' in st.session_state:
            slip = st.session_state.slip
            st.markdown(f"""
            <div class="bet-ticket">
                <h3>🎫 Active Ticket: {slip['m']}</h3>
                <p>Selection: <b>{slip['t']}</b> @ Odds <b>{slip['o']}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([2, 1])
            wager = c1.number_input(t('amount'), min_value=1.0, max_value=u_data[5], value=50.0)
            c2.metric(t('potential_win'), f"${wager * slip['o']:.2f}")
            
            if st.button(t('place_bet'), type="primary", use_container_width=True):
                if place_bet_transaction(st.session_state.username, slip['m'], slip['t'], wager, slip['o']):
                    st.success(t('bet_placed'))
                    del st.session_state.slip
                    st.rerun()
                else:
                    st.error(t('insufficient_funds'))
            st.divider()

        # MATCH LIST
        for m in matches:
            data = analyze_full(m['Home'], m['Away'])
            probs = data['1X2']
            odds = data['Odds']
            
            with st.container():
                c1, c2 = st.columns([3, 1])
                c1.subheader(f"{m['Home']} vs {m['Away']}")
                c1.caption(f"{m['Time']} | {m['Date']}")
                # FIXED FORM GUIDE (No changing on refresh)
                c2.markdown(f"**{m['Home']}**: {render_consistent_form(m['Home'])}", unsafe_allow_html=True)
                c2.markdown(f"**{m['Away']}**: {render_consistent_form(m['Away'])}", unsafe_allow_html=True)

                tab1, tab2, tab3 = st.tabs([t('winner'), t('goals'), t('btts')])
                
                with tab1:
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        st.info(f"Home ({probs[0]}%)")
                        if st.button(f"Bet Home @ {odds[0]}", key=f"h_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'HOME', 'o': odds[0]}
                            st.rerun()
                    with b2:
                        st.warning(f"Draw ({probs[1]}%)")
                        if st.button(f"Bet Draw @ {odds[1]}", key=f"d_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'DRAW', 'o': odds[1]}
                            st.rerun()
                    with b3:
                        st.error(f"Away ({probs[2]}%)")
                        if st.button(f"Bet Away @ {odds[2]}", key=f"a_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'AWAY', 'o': odds[2]}
                            st.rerun()
                
                with tab2: st.metric("Over 2.5", f"{data['Goals']}%"); st.progress(data['Goals']/100)
                with tab3: st.metric("BTTS", f"{data['BTTS']}%"); st.progress(data['BTTS']/100)
                st.divider()

    # 2. ADMIN PANEL
    elif menu == t('menu_admin'):
        st.header("Admin Control Panel")
        conn = init_db()
        users = pd.read_sql("SELECT username, role, balance FROM users", conn)
        conn.close()
        
        st.dataframe(users, use_container_width=True)
        
        # USER MODIFICATION SECTION
        st.subheader("Modify User")
        c1, c2 = st.columns(2)
        target = c1.selectbox("Select User", users['username'].unique())
        
        # CREDIT MANAGEMENT
        with st.form("credit_form"):
            st.write(f"Manage Balance for **{target}**")
            amount = st.number_input("Add Credit Amount ($)", min_value=-5000.0, max_value=50000.0, value=0.0)
            if st.form_submit_button("Update Balance"):
                manage_user("add_credit", target, amount)
                st.success(f"Added ${amount} to {target}")
                st.rerun()
        
        # ROLE MANAGEMENT
        c1, c2, c3 = st.columns(3)
        if c1.button("Make Admin"): manage_user("change_role", target, "admin"); st.rerun()
        if c2.button("Make User"): manage_user("change_role", target, "user"); st.rerun()
        if c3.button("Delete User"): manage_user("delete", target); st.rerun()

    # 3. PROFILE
    elif menu == t('menu_profile'):
        st.header(t('menu_profile'))
        u_info, bets = get_data(st.session_state.username)
        st.metric(t('balance'), f"${u_info[5]:,.2f}")
        
        st.subheader("Bet History")
        if bets:
            df = pd.DataFrame(bets, columns=['ID','User','Match','Type','Amt','Win','Status','Date'])
            st.dataframe(df[['Match','Type','Amt','Win','Status','Date']], use_container_width=True)
        else:
            st.info("No bets placed yet.")
