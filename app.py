import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Football AI Pro", 
    layout="wide", 
    page_icon="⚽", 
    initial_sidebar_state="expanded"
)

# --- 2. MODERN UI (White Theme) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
    .stApp {background-color: #F4F6F9; color: #1F2937;}
    [data-testid="stSidebar"] {background-color: #FFFFFF; border-right: 1px solid #E5E7EB;}
    .match-card {
        background-color: #FFFFFF; padding: 20px; border-radius: 12px;
        border: 1px solid #E5E7EB; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        margin-bottom: 16px;
    }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .status-live {color: #DC2626; font-weight: bold; animation: pulse 2s infinite;}
    .status-sched {color: #059669; font-weight: bold;}
    @keyframes pulse {0% {opacity: 1;} 50% {opacity: 0.5;} 100% {opacity: 1;}}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE (Restored Previous Version) ---
# We use the v33 database to ensure your previous users/data are loaded.
DB_NAME = 'football_v33_hybrid.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    # Ensure Admin Exists
    try: c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),)); conn.commit()
    except: pass
    conn.close()

init_db()

def t(key):
    # Dictionary for translations
    LANG = {
        "en": {"app": "Football AI", "login": "Login", "user": "Username", "pass": "Password", "live": "Live Market", "no_data": "No matches found.", "bal": "Balance"},
        "ar": {"app": "المحلل الذكي", "login": "دخول", "user": "اسم المستخدم", "pass": "كلمة المرور", "live": "المباريات", "no_data": "لا توجد مباريات", "bal": "الرصيد"}
    }
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

# --- 4. API ENGINE (YOUR SPECIFIC API) ---
@st.cache_data(ttl=300)
def fetch_matches():
    matches = []
    
    # --- PRIORITY 1: YOUR RAPIDAPI KEY (SportAPI7) ---
    try:
        # We must use the 'scheduled-events' endpoint for matches
        date_str = datetime.now().strftime("%Y-%m-%d")
        url = f"https://sportapi7.p.rapidapi.com/api/v1/sport/football/scheduled-events/{date_str}"
        
        headers = {
            "x-rapidapi-host": "sportapi7.p.rapidapi.com",
            "x-rapidapi-key": "f84fc89ce9msh35e8c7081df9999p1df9d8jsn071086d01b59"
        }
        
        r = requests.get(url, headers=headers, timeout=3)
        
        if r.status_code == 200:
            data = r.json()
            # Parsing logic for SportAPI7 structure
            for event in data.get('events', []):
                matches.append({
                    "League": event['tournament']['name'],
                    "Date": date_str,
                    "Time": datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M'),
                    "Status": event['status']['type'], # 'finished', 'inprogress', 'notstarted'
                    "Home": event['homeTeam']['name'],
                    "Away": event['awayTeam']['name']
                })
        elif r.status_code == 403:
            st.toast("⚠️ API Key Valid but Subscription Required on RapidAPI.", icon="⚠️")
    except Exception:
        pass

    # --- PRIORITY 2: ESPN BACKUP (If API Fails/Empty) ---
    # This ensures your users NEVER see an empty screen
    if not matches:
        leagues = [
            {"id": "eng.1", "name": "🇬🇧 Premier League"}, {"id": "esp.1", "name": "🇪🇸 La Liga"},
            {"id": "ita.1", "name": "🇮🇹 Serie A"}, {"id": "ger.1", "name": "🇩🇪 Bundesliga"},
            {"id": "fra.1", "name": "🇫🇷 Ligue 1"}, {"id": "uefa.champions", "name": "🇪🇺 Champions League"}
        ]
        
        date_check = datetime.now().strftime("%Y%m%d")
        for l in leagues:
            try:
                url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard?dates={date_check}"
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    for e in data.get('events', []):
                        # Filter: Hide Finished Matches
                        status = e['status']['type']['shortDetail']
                        if status not in ["FT", "Post", "AET"]:
                            utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                            local = utc + timedelta(hours=3) # Baghdad
                            matches.append({
                                "League": l['name'], "Date": local.strftime("%Y-%m-%d"),
                                "Time": local.strftime("%H:%M"), "Status": status,
                                "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                                "Away": e['competitions'][0]['competitors'][1]['team']['displayName']
                            })
            except: continue

    return matches

def analyze_match(h, a):
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {"Home": h_win, "Draw": d_win, "Away": a_win, "OddsH": round(100/h_win,2), "OddsD": round(100/d_win,2), "OddsA": round(100/a_win,2)}

# --- 5. APP LOGIC ---
def login_view():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title(f"⚽ {t('app')}")
        lang = st.selectbox("Language", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
        
        with st.container():
            st.markdown("<div class='match-card'>", unsafe_allow_html=True)
            u = st.text_input(t('user'))
            p = st.text_input(t('pass'), type="password")
            
            if st.button(t('login'), use_container_width=True, type="primary"):
                # 1. Check Hardcoded Admin (Emergency Access)
                if u == "admin" and p == "admin123":
                    st.session_state.logged_in = True; st.session_state.username = "admin"; st.session_state.role = "admin"; st.rerun()
                
                # 2. Check Database
                conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=?", (u,))
                user = c.fetchone()
                conn.close()
                
                if user and user[1] == p:
                    st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = user[2]; st.rerun()
                else:
                    st.error("Invalid Credentials")
            
            st.markdown("</div>", unsafe_allow_html=True)

def app_view():
    # Sidebar
    with st.sidebar:
        st.header(f"Hi, {st.session_state.username}")
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE username=?", (st.session_state.username,)); 
        bal = c.fetchone()[0]
        conn.close()
        st.metric(t('bal'), f"${bal:,.2f}")
        
        if st.button("Sign Out", use_container_width=True):
            st.session_state.logged_in = False; st.rerun()

    # Main Area
    st.subheader("Match Market")
    
    # Search
    search = st.text_input("Search...", label_visibility="collapsed", placeholder="Search Team...")
    
    with st.spinner("Loading Matches..."):
        matches = fetch_matches()
        
    if search:
        matches = [m for m in matches if search.lower() in m['Home'].lower() or search.lower() in m['Away'].lower()]
        
    if not matches:
        st.info("No live or upcoming matches found right now.")
    
    # Render
    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"**{league}**")
            for _, m in df[df['League'] == league].iterrows():
                stats = analyze_match(m['Home'], m['Away'])
                
                st.markdown(f"""
                <div class="match-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:bold;">{m['Home']} vs {m['Away']}</span>
                        <span class="status-sched">{m['Time']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                if c1.button(f"1 ({stats['OddsH']})", key=f"h_{m['Home']}"): pass # Add betting logic here if needed
                if c2.button(f"X ({stats['OddsD']})", key=f"d_{m['Home']}"): pass
                if c3.button(f"2 ({stats['OddsA']})", key=f"a_{m['Home']}"): pass

# --- ENTRY POINT ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in: login_view()
else: app_view()
