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
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1F2937;
    }
    
    .stApp {
        background-color: #F4F6F9;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
    }
    
    /* Match Card */
    .match-card {
        background-color: #FFFFFF;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .match-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
    }
    
    /* Badges */
    .status-live {
        color: #DC2626; 
        background-color: #FEF2F2;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85em;
        animation: pulse 2s infinite;
    }
    .status-sched {
        color: #059669; 
        background-color: #ECFDF5;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85em;
    }
    
    @keyframes pulse {0% {opacity: 1;} 50% {opacity: 0.6;} 100% {opacity: 1;}}
    
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE (Clean - No Betting) ---
DB_NAME = 'football_v44_nobet.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Removed 'balance' and 'bets' table
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    
    # Ensure Admin Exists
    try: c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin', ?)", (str(datetime.now()),)); conn.commit()
    except: pass
    conn.close()

init_db()

def t(key):
    LANG = {
        "en": {"app": "Football AI", "login": "Login", "user": "Username", "pass": "Password", "live": "Match Analysis", "no_data": "No upcoming matches found.", "logout": "Sign Out", "search": "Search Team/League..."},
        "ar": {"app": "المحلل الذكي", "login": "دخول", "user": "اسم المستخدم", "pass": "كلمة المرور", "live": "تحليل المباريات", "no_data": "لا توجد مباريات", "logout": "خروج", "search": "بحث..."}
    }
    lang = st.session_state.get('lang', 'en')
    return LANG[lang].get(key, key)

def manage_user(action, target_user, data=None):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        if action == "add": c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (target_user, data, 'user', str(datetime.now()))); conn.commit(); return True
        elif action == "change_role": c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user)); conn.commit()
        elif action == "delete": c.execute("DELETE FROM users WHERE username=?", (target_user,)); conn.commit()
    except: return False
    finally: conn.close()

def get_user_info(username):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,)); res = c.fetchone()
    conn.close(); return res

def log_action(user, action):
    try:
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
    except: pass

# --- 4. API ENGINE ---
@st.cache_data(ttl=300)
def fetch_matches():
    matches = []
    
    # 1. RAPID API (SportAPI7)
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        url = f"https://sportapi7.p.rapidapi.com/api/v1/sport/football/scheduled-events/{today_str}"
        headers = {
            "x-rapidapi-host": "sportapi7.p.rapidapi.com",
            "x-rapidapi-key": "f84fc89ce9msh35e8c7081df9999p1df9d8jsn071086d01b59"
        }
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            data = r.json()
            for event in data.get('events', []):
                # Filter Finished
                status = event['status']['type']
                if status == 'finished': continue 

                matches.append({
                    "League": event['tournament']['name'],
                    "Date": today_str,
                    "Time": datetime.fromtimestamp(event['startTimestamp']).strftime('%H:%M'),
                    "Status": status,
                    "Home": event['homeTeam']['name'],
                    "Away": event['awayTeam']['name'],
                    "Score": f"{event.get('homeScore',{}).get('current',0)}-{event.get('awayScore',{}).get('current',0)}"
                })
    except: pass

    # 2. ESPN BACKUP
    if not matches:
        leagues = [
            {"id": "eng.1", "name": "🇬🇧 Premier League"}, {"id": "esp.1", "name": "🇪🇸 La Liga"},
            {"id": "ita.1", "name": "🇮🇹 Serie A"}, {"id": "ger.1", "name": "🇩🇪 Bundesliga"},
            {"id": "fra.1", "name": "🇫🇷 Ligue 1"}, {"id": "uefa.champions", "name": "🇪🇺 Champions League"}
        ]
        
        dates = [datetime.now().strftime("%Y%m%d"), (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")]
        
        for d_str in dates:
            if len(matches) > 15: break
            for l in leagues:
                try:
                    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard?dates={d_str}"
                    r = requests.get(url, timeout=2)
                    if r.status_code == 200:
                        data = r.json()
                        for e in data.get('events', []):
                            status = e['status']['type']['shortDetail']
                            # FILTER: Hide Finished (FT/Final)
                            if "FT" in status or "Final" in status: continue
                            
                            utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                            local = utc + timedelta(hours=3) # Baghdad
                            
                            try: score = f"{e['competitions'][0]['competitors'][0]['score']}-{e['competitions'][0]['competitors'][1]['score']}"
                            except: score = "vs"
                            
                            matches.append({
                                "League": l['name'], "Date": local.strftime("%Y-%m-%d"),
                                "Time": local.strftime("%H:%M"), "Status": status,
                                "Score": score,
                                "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                                "Away": e['competitions'][0]['competitors'][1]['team']['displayName']
                            })
                except: continue

    return matches

def analyze_advanced(h, a):
    # Simulated Analysis Logic
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {"OddsH": round(100/h_win,2), "OddsD": round(100/d_win,2), "OddsA": round(100/a_win,2), "Goals": int((seed*4)%100), "BTTS": int((seed*9)%100)}

# --- 5. PAGE FUNCTIONS ---
def login_view():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"<br><h1 style='text-align: center;'>⚽ {t('app')}</h1>", unsafe_allow_html=True)
        
        # Language
        lang = st.selectbox("Language / اللغة", ["English", "العربية"])
        st.session_state.lang = "ar" if lang == "العربية" else "en"
        
        with st.container():
            st.markdown("<div class='match-card'>", unsafe_allow_html=True)
            t1, t2 = st.tabs([t('login'), "Register"])
            
            with t1:
                u = st.text_input(t('user'), key="l_u").strip()
                p = st.text_input(t('pass'), type="password", key="l_p").strip()
                if st.button(t('login'), use_container_width=True, type="primary"):
                    # Admin Bypass
                    if u == "admin" and p == "admin123":
                        st.session_state.logged_in = True; st.session_state.username = "admin"; st.session_state.role = "admin"
                        manage_user("add", "admin", "admin123") 
                        st.rerun()
                    
                    user_data = get_user_info(u)
                    if user_data and user_data[1] == p:
                        st.session_state.logged_in = True; st.session_state.username = u; st.session_state.role = user_data[2]
                        log_action(u, "Login Success"); st.rerun()
                    else: 
                        st.error("Invalid Credentials") # SECURE: Removed admin hints
            
            with t2:
                nu = st.text_input("New User")
                np = st.text_input("New Pass", type="password")
                if st.button("Create Account", use_container_width=True):
                    if manage_user("add", nu.strip(), np.strip()): st.success("Success! Login now."); log_action(nu, "Account Created")
                    else: st.error("Username Taken")
            st.markdown("</div>", unsafe_allow_html=True)

def admin_dashboard():
    st.title("🛡️ Admin Panel")
    conn = sqlite3.connect(DB_NAME); users = pd.read_sql("SELECT * FROM users", conn); logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn); conn.close()
    
    st.subheader("Users")
    for index, row in users.iterrows():
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(f"**{row['username']}** ({row['role']})")
        if row['username'] != 'admin':
            if c2.button("Promote", key=f"p_{row['username']}"): manage_user("change_role", row['username'], "admin"); st.rerun()
            if c3.button("Demote", key=f"d_{row['username']}"): manage_user("change_role", row['username'], "user"); st.rerun()
            if c4.button("Delete", key=f"del_{row['username']}"): manage_user("delete", row['username']); st.rerun()
        st.divider()
    
    st.subheader("Logs"); st.dataframe(logs, use_container_width=True)

def predictions_view():
    st.title(f"📈 {t('live')}")
    
    # SEARCH BAR
    search_q = st.text_input("", placeholder=t('search'))
    
    with st.spinner("Analyzing Market..."):
        matches = fetch_matches()
    
    # Filter by Search
    if search_q:
        matches = [m for m in matches if search_q.lower() in m['Home'].lower() or search_q.lower() in m['Away'].lower() or search_q.lower() in m['League'].lower()]
    
    if not matches:
        st.info(t('no_data'))
    
    df = pd.DataFrame(matches)
    if not df.empty:
        for league in df['League'].unique():
            st.markdown(f"### {league}")
            league_matches = df[df['League'] == league]
            for index, m in league_matches.iterrows():
                stats = analyze_advanced(m['Home'], m['Away'])
                
                # Dynamic Badge
                status_class = "status-live" if m['Status'] in ['Live','In Play'] else "status-sched"
                
                # CLEAN CARD UI (No Betting)
                st.markdown(f"""
                <div class="match-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                        <div style="font-size:1.2em; font-weight:700; color:#1F2937;">
                            {m['Home']} <span style="color:#9CA3AF; margin:0 8px;">{m['Score']}</span> {m['Away']}
                        </div>
                        <div class="{status_class}">
                            {m['Time']}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; color:#4B5563; font-size:0.9em; border-top:1px solid #F3F4F6; padding-top:10px;">
                        <div>🔥 Win: <strong>{stats['OddsH']}</strong></div>
                        <div>⚖️ Draw: <strong>{stats['OddsD']}</strong></div>
                        <div>🛡️ Win: <strong>{stats['OddsA']}</strong></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Detailed Analysis Expander
                with st.expander("📊 AI Analysis & Predictions"):
                    c1, c2 = st.columns(2)
                    c1.caption("Goals > 2.5 Probability")
                    c1.progress(stats['Goals'] / 100)
                    c2.caption("Both Teams To Score")
                    c2.progress(stats['BTTS'] / 100)

# --- MAIN CONTROLLER ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    init_db()

if not st.session_state.logged_in:
    login_view()
else:
    # Sidebar
    st.sidebar.title(f"👤 {st.session_state.username}")
    lang_toggle = st.sidebar.radio("Language", ["English", "العربية"])
    st.session_state.lang = "ar" if lang_toggle == "العربية" else "en"
    
    options = ["Matches"]
    if st.session_state.role == 'admin': options.append("Admin Panel")
    
    menu = st.sidebar.radio("Menu", options)
    
    st.sidebar.markdown("---")
    if st.sidebar.button(t('logout'), use_container_width=True): 
        st.session_state.logged_in = False; st.rerun()

    if menu == "Matches": predictions_view()
    elif menu == "Admin Panel": admin_dashboard()
