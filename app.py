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

# --- 2. MODERN UI: CLEAN WHITE THEME (RESTORED) ---
st.markdown("""
    <style>
    /* Global Font & Background */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #F4F6F9; /* Soft Grey Background */
        color: #1F2937; /* Dark Text */
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
    }
    
    /* Card Styling */
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
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom Badges */
    .status-live {color: #DC2626; font-weight: bold; animation: pulse 2s infinite;}
    .status-sched {color: #059669; font-weight: bold;}
    
    @keyframes pulse {0% {opacity: 1;} 50% {opacity: 0.5;} 100% {opacity: 1;}}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE (YOUR EXISTING DB) ---
DB_NAME = 'football_v33_hybrid.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try: c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000.0)", (str(datetime.now()),)); conn.commit()
    except: pass
    conn.close()

init_db()

def t(key):
    D = {
        "en": {"live": "Match Market", "search": "Search Team/League...", "no_data": "No matches found.", "bet": "Place Bet", "conf": "AI Confidence"},
        "ar": {"live": "سوق المباريات", "search": "بحث عن فريق...", "no_data": "لا توجد مباريات", "bet": "راهن الآن", "conf": "ثقة الذكاء"}
    }
    return D[st.session_state.get('lang', 'en')].get(key, key)

# --- 4. HYBRID API ENGINE (RAPIDAPI + ESPN FALLBACK) ---
@st.cache_data(ttl=300, show_spinner=False)
def fetch_matches_cached():
    matches = []
    
    # --- A. TRY RAPIDAPI (Your Key) ---
    try:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        headers = {
            "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
            "x-rapidapi-key": "f84fc89ce9msh35e8c7081df9999p1df9d8jsn071086d01b59"
        }
        # Get Today's Matches
        params = {"date": datetime.now().strftime("%Y-%m-%d")}
        r = requests.get(url, headers=headers, params=params, timeout=3)
        
        if r.status_code == 200:
            data = r.json()
            for item in data.get('response', []):
                # Filter specific leagues to keep it clean (EPL, La Liga, etc.)
                # ID 39=EPL, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1
                if item['league']['id'] in [39, 140, 135, 78, 61, 2, 9]: 
                    matches.append({
                        "League": item['league']['name'],
                        "Date": item['fixture']['date'][:10],
                        "Time": item['fixture']['date'][11:16],
                        "Status": item['fixture']['status']['short'], 
                        "Home": item['teams']['home']['name'],
                        "Away": item['teams']['away']['name']
                    })
    except: pass

    # --- B. FALLBACK TO ESPN (If RapidAPI fails/not subscribed) ---
    if not matches:
        leagues = [
            {"id": "eng.1", "name": "🇬🇧 Premier League"}, {"id": "esp.1", "name": "🇪🇸 La Liga"},
            {"id": "ita.1", "name": "🇮🇹 Serie A"}, {"id": "ger.1", "name": "🇩🇪 Bundesliga"},
            {"id": "fra.1", "name": "🇫🇷 Ligue 1"}, {"id": "uefa.champions", "name": "🇪🇺 Champions League"}
        ]
        
        dates = [datetime.now().strftime("%Y%m%d"), (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")]
        
        for d in dates:
            if len(matches) > 20: break
            for l in leagues:
                try:
                    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard?dates={d}"
                    r = requests.get(url, timeout=2)
                    if r.status_code == 200:
                        data = r.json()
                        for e in data.get('events', []):
                            status = e['status']['type']['shortDetail']
                            # Filter Finished Matches
                            if "FT" in status or "Final" in status: continue
                                
                            utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                            local = utc + timedelta(hours=3) # Baghdad Time
                            
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
    return {"OddsH": round(100/h_win,2), "OddsD": round(100/d_win,2), "OddsA": round(100/a_win,2), "Goals": int((seed*4)%100), "BTTS": int((seed*9)%100)}

# --- 5. APP LOGIC ---
def login_view():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("⚽ Football AI Pro")
        
        with st.container():
            st.markdown("<div class='match-card'>", unsafe_allow_html=True)
            u = st.text_input("Username").strip()
            p = st.text_input("Password", type="password").strip()
            
            if st.button("Login", use_container_width=True, type="primary"):
                # 1. Hardcoded Admin Bypass
                if u == "admin" and p == "admin123":
                    st.session_state.logged_in = True; st.session_state.username = "admin"; st.session_state.role = "admin"; st.rerun()
                
                # 2. DB Check
                conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=?", (u,))
                user = c.fetchone()
                conn.close()
                
                if user and user[1] == p:
                    st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = user[2]; st.rerun()
                else:
                    st.error("Invalid Credentials") # Secure Generic Message
            st.markdown("</div>", unsafe_allow_html=True)

def app_view():
    with st.sidebar:
        st.header(f"Hi, {st.session_state.username}")
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE username=?", (st.session_state.username,)); 
        bal = c.fetchone()[0]
        conn.close()
        st.metric("Wallet", f"${bal:,.2f}")
        
        if st.button("Sign Out", use_container_width=True):
            st.session_state.logged_in = False; st.rerun()

    st.subheader(t('live'))
    search_query = st.text_input("", placeholder=t('search'))
    
    with st.spinner("Scanning Global Market..."):
        matches = fetch_matches_cached()
    
    if search_query:
        matches = [m for m in matches if search_query.lower() in m['Home'].lower() or search_query.lower() in m['Away'].lower()]
    
    if not matches:
        st.info(t('no_data'))
    
    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"##### {league}")
            for _, m in df[df['League'] == league].iterrows():
                stats = analyze_match(m['Home'], m['Away'])
                
                # MATCH CARD UI
                st.markdown(f"""
                <div class="match-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-size:1.1em; font-weight:600;">{m['Home']} <span style="color:#9CA3AF;">vs</span> {m['Away']}</div>
                        <div class="{'status-live' if m['Status'] in ['Live','In Play'] else 'status-sched'}">
                            {m['Time']}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                if c1.button(f"1 ({stats['OddsH']})", key=f"h_{m['Home']}"): pass 
                if c2.button(f"X ({stats['OddsD']})", key=f"d_{m['Home']}"): pass
                if c3.button(f"2 ({stats['OddsA']})", key=f"a_{m['Home']}"): pass
                
                with st.expander(f"📊 {t('conf')}"):
                    st.progress(stats['Goals'] / 100)
                    st.caption(f"Over 2.5 Goals: {stats['Goals']}%")

# --- ENTRY POINT ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in: login_view()
else: app_view()
