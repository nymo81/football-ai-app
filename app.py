import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- 1. CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(
    page_title="Football AI Pro", 
    layout="wide", 
    page_icon="⚽", 
    initial_sidebar_state="expanded"
)

# --- 2. MODERN UI: CLEAN WHITE THEME ---
st.markdown("""
    <style>
    /* Global Font & Background */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #F4F6F9; /* Very soft grey background for contrast */
        color: #1F2937; /* Dark Grey Text */
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
        box-shadow: 2px 0 5px rgba(0,0,0,0.02);
    }
    
    /* Card Styling (Replaces Black Boxes) */
    .match-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 16px;
        transition: transform 0.2s;
    }
    .match-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
    }
    
    /* Hide Default Streamlit Elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    
    /* Inputs & Buttons */
    .stTextInput>div>div>input {
        border-radius: 8px;
        border: 1px solid #E5E7EB;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        border: none;
        transition: all 0.3s;
    }
    
    /* Custom Badges */
    .status-live {color: #DC2626; font-weight: bold; animation: pulse 2s infinite;}
    .status-sched {color: #059669; font-weight: bold;}
    
    @keyframes pulse {
        0% {opacity: 1;}
        50% {opacity: 0.5;}
        100% {opacity: 1;}
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. TRANSLATIONS (CLEAN TITLES) ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "nav": "Main Menu",
        "menu_live": "Match Market", "menu_profile": "My Wallet",
        "menu_admin": "Admin Panel", "no_matches": "No upcoming matches found.",
        "search": "Search Team or League...", "conf": "AI Confidence",
        "winner": "Match Winner", "goals": "Total Goals", "btts": "Both Teams Score",
        "balance": "Balance", "bet_slip": "Betting Slip", "confirm": "Place Bet",
        "logout": "Sign Out", "admin_area": "Admin Area", "add_funds": "Add Funds",
        "welcome": "Welcome back,"
    },
    "ar": {
        "app_name": "المحلل الذكي", "login": "دخول", "signup": "تسجيل جديد",
        "username": "المستخدم", "password": "كلمة المرور", "nav": "القائمة",
        "menu_live": "سوق المباريات", "menu_profile": "محفظتي",
        "menu_admin": "لوحة الإدارة", "no_matches": "لا توجد مباريات قادمة",
        "search": "بحث عن فريق أو دوري...", "conf": "ثقة الذكاء",
        "winner": "الفائز", "goals": "الأهداف", "btts": "كلا الفريقين",
        "balance": "الرصيد", "bet_slip": "قسيمة الرهان", "confirm": "تأكيد الرهان",
        "logout": "تسجيل خروج", "admin_area": "منطقة الإدارة", "add_funds": "إضافة رصيد",
        "welcome": "أهلاً بك،"
    }
}

# --- 4. DATABASE & SESSION ---
DB_NAME = 'football_v34_pro.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    # Force Admin Creation (Silent)
    try: c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),)); conn.commit()
    except: pass
    conn.close()

init_db() # Run immediately

def t(key):
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- 5. GLOBAL API ENGINE (CACHED) ---
# This runs ONCE every 5 minutes for ALL users
@st.cache_data(ttl=300, show_spinner=False)
def fetch_global_matches():
    # Leagues: EPL, Championship, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, UCL
    leagues = [
        {"id": "eng.1", "name": "🇬🇧 Premier League"}, {"id": "eng.2", "name": "🇬🇧 Championship"},
        {"id": "esp.1", "name": "🇪🇸 La Liga"}, {"id": "ita.1", "name": "🇮🇹 Serie A"},
        {"id": "ger.1", "name": "🇩🇪 Bundesliga"}, {"id": "fra.1", "name": "🇫🇷 Ligue 1"},
        {"id": "ned.1", "name": "🇳🇱 Eredivisie"}, {"id": "uefa.champions", "name": "🇪🇺 Champions League"}
    ]
    
    matches = []
    # Check Today & Tomorrow (Baghdad Time)
    dates = [datetime.now().strftime("%Y%m%d"), (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")]
    
    for d_str in dates:
        for l in leagues:
            try:
                url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard?dates={d_str}"
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    for e in data.get('events', []):
                        # Convert UTC to Baghdad (UTC+3)
                        utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                        local = utc + timedelta(hours=3)
                        
                        # FILTER: Exclude Finished Matches (FT)
                        status_id = e['status']['type']['name'] # STATUS_FINAL, STATUS_SCHEDULED
                        status_text = e['status']['type']['shortDetail'] # FT, 15:00
                        
                        if "FINAL" not in status_id and "POST" not in status_id:
                            matches.append({
                                "League": l['name'],
                                "Date": local.strftime("%Y-%m-%d"),
                                "Time": local.strftime("%H:%M"),
                                "Status": status_text,
                                "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                                "Away": e['competitions'][0]['competitors'][1]['team']['displayName']
                            })
            except: continue
            
    return matches

def analyze_match(h, a):
    # Deterministic AI Logic (Consistent per match)
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {
        "1X2": {"Home": h_win, "Draw": d_win, "Away": a_win},
        "Odds": {"Home": round(100/h_win,2), "Draw": round(100/d_win,2), "Away": round(100/a_win,2)},
        "Goals": int((seed*4)%100), "BTTS": int((seed*9)%100)
    }

# --- 6. PAGE VIEWS ---
def login_view():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"<h1 style='text-align: center; margin-bottom: 30px;'>⚽ {t('app_name')}</h1>", unsafe_allow_html=True)
        
        # Language Selector
        lang = st.selectbox("Language / اللغة", ["English", "العربية"], label_visibility="collapsed")
        st.session_state.lang = "ar" if lang == "العربية" else "en"

        with st.container():
            st.markdown("<div class='match-card'>", unsafe_allow_html=True)
            tab1, tab2 = st.tabs([t('login'), t('signup')])
            
            with tab1:
                u = st.text_input(t('username'), key="l_u").strip()
                p = st.text_input(t('password'), type="password", key="l_p").strip()
                if st.button(t('login'), use_container_width=True, type="primary"):
                    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username=?", (u,))
                    user = c.fetchone()
                    conn.close()
                    
                    # Hardcoded Admin Bypass (Safety Net)
                    if (u == "admin" and p == "admin123") or (user and user[1] == p):
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.session_state.role = "admin" if u == "admin" else user[2]
                        st.rerun()
                    else:
                        st.error("Invalid Credentials") # Generic Error Message (Secure)

            with tab2:
                nu = st.text_input("New Username")
                np = st.text_input("New Password", type="password")
                if st.button(t('signup'), use_container_width=True):
                    try:
                        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (nu, np, 'user', str(datetime.now()), 'New User', 1000.0))
                        conn.commit(); conn.close()
                        st.success("Account Created! Please Login.")
                    except: st.error("Username taken.")
            st.markdown("</div>", unsafe_allow_html=True)

def app_view():
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### {t('welcome')} {st.session_state.username}")
        
        # Wallet Display
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE username=?", (st.session_state.username,))
        res = c.fetchone()
        bal = res[0] if res else 0.0
        conn.close()
        
        st.metric(t('balance'), f"${bal:,.2f}")
        
        # Navigation
        st.markdown("---")
        nav_options = [t('menu_live'), t('menu_profile')]
        if st.session_state.role == 'admin': nav_options.insert(0, t('menu_admin'))
        
        selection = st.radio("", nav_options, label_visibility="collapsed")
        
        st.markdown("---")
        lang_toggle = st.radio("Language", ["English", "العربية"])
        st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
        
        if st.button(f"🚪 {t('logout')}", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # --- 1. MATCH MARKET ---
    if selection == t('menu_live'):
        c1, c2 = st.columns([3, 1])
        c1.title(t('menu_live'))
        
        # Search Bar
        search_q = c2.text_input("", placeholder=t('search'), label_visibility="collapsed")
        
        with st.spinner("Loading Global Market..."):
            matches = fetch_global_matches()
        
        # Search Filtering
        if search_q:
            matches = [m for m in matches if search_q.lower() in m['Home'].lower() or search_q.lower() in m['Away'].lower() or search_q.lower() in m['League'].lower()]
        
        if not matches:
            st.info(t('no_matches'))
        
        # Render Matches grouped by League
        df = pd.DataFrame(matches)
        if not df.empty:
            for league in df['League'].unique():
                st.markdown(f"##### {league}")
                league_matches = df[df['League'] == league]
                
                for _, m in league_matches.iterrows():
                    stats = analyze_match(m['Home'], m['Away'])
                    odds = stats['Odds']
                    
                    # --- MODERN CARD LAYOUT ---
                    with st.container():
                        st.markdown(f"""
                        <div class="match-card">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                <div style="font-weight:bold; font-size:1.1em;">{m['Home']} <span style="color:#6B7280; font-size:0.8em;">vs</span> {m['Away']}</div>
                                <div class="{'status-live' if m['Status'] in ['Live','In Play'] else 'status-sched'}">{m['Time']}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Betting Interface (Integrated directly below card)
                        c1, c2, c3 = st.columns(3)
                        if c1.button(f"{m['Home']} @ {odds['Home']}", key=f"h_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'HOME', 'o': odds['Home']}
                        if c2.button(f"Draw @ {odds['Draw']}", key=f"d_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'DRAW', 'o': odds['Draw']}
                        if c3.button(f"{m['Away']} @ {odds['Away']}", key=f"a_{m['Home']}"):
                            st.session_state.slip = {'m': f"{m['Home']} v {m['Away']}", 't': 'AWAY', 'o': odds['Away']}
                        
                        # AI Stats Bars
                        with st.expander(f"📊 {t('conf')} Analysis"):
                            st.caption(f"{t('goals')} > 2.5")
                            st.progress(stats['Goals'] / 100)
                            st.caption(f"{t('btts')}")
                            st.progress(stats['BTTS'] / 100)

    # --- 2. PROFILE ---
    elif selection == t('menu_profile'):
        st.title(t('menu_profile'))
        
        # History
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("SELECT date, match, bet_type, amount, potential_win FROM bets WHERE user=? ORDER BY id DESC", (st.session_state.username,))
        history = c.fetchall()
        conn.close()
        
        if history:
            st.markdown(f"### {t('bet_history')}")
            hist_df = pd.DataFrame(history, columns=['Time', 'Match', 'Pick', 'Stake', 'Potential Win'])
            st.dataframe(hist_df, use_container_width=True)
        else:
            st.info("No betting history found.")

    # --- 3. ADMIN ---
    elif selection == t('menu_admin'):
        st.title(t('admin_area'))
        conn = sqlite3.connect(DB_NAME)
        users = pd.read_sql("SELECT username, balance, role FROM users", conn)
        conn.close()
        st.dataframe(users, use_container_width=True)
        
        st.subheader(t('add_funds'))
        c1, c2 = st.columns(2)
        target = c1.selectbox("User", users['username'].unique())
        amt = c2.number_input("Amount", 100, 10000)
        if st.button("Add"):
            conn = sqlite3.connect(DB_NAME); c = conn.cursor()
            c.execute("UPDATE users SET balance = balance + ? WHERE username=?", (amt, target))
            conn.commit(); conn.close()
            st.success("Funded!")

    # --- BET SLIP SIDEBAR ---
    if 'slip' in st.session_state:
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"### 🎫 {t('bet_slip')}")
            st.info(f"**{st.session_state.slip['m']}**\n\nPick: {st.session_state.slip['t']} @ {st.session_state.slip['o']}")
            
            wager = st.number_input("Stake ($)", min_value=1.0, max_value=bal, value=10.0)
            st.write(f"**To Win:** ${wager * st.session_state.slip['o']:.2f}")
            
            if st.button(t('confirm'), type="primary", use_container_width=True):
                conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                c.execute("UPDATE users SET balance = balance - ? WHERE username=?", (wager, st.session_state.username))
                c.execute("INSERT INTO bets (user, match, bet_type, amount, potential_win, status, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (st.session_state.username, st.session_state.slip['m'], st.session_state.slip['t'], wager, wager*st.session_state.slip['o'], 'OPEN', str(datetime.now())))
                conn.commit(); conn.close()
                st.success("Bet Placed!")
                del st.session_state.slip
                st.rerun()

# --- MAIN CONTROLLER ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_view()
else:
    app_view()
