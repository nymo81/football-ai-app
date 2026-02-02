import streamlit as st
import pandas as pd
import requests
import sqlite3
from datetime import datetime, timedelta
import random

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Football AI Dashboard", 
    layout="wide", 
    page_icon="⚽", 
    initial_sidebar_state="expanded"
)

# --- 2. MODERN PRO THEME (White/Clean) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1F2937;
    }
    
    .stApp {
        background-color: #F3F4F6; /* Lightest Grey */
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
    }
    
    /* Card Container */
    .dashboard-card {
        background-color: #FFFFFF;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #E5E7EB;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-weight: 600 !important;
        color: #111827 !important;
    }
    
    /* KPI Metrics */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Status Badges */
    .badge-live {
        background-color: #FEF2F2; color: #DC2626; 
        padding: 4px 12px; border-radius: 20px; 
        font-size: 0.85em; font-weight: 700; border: 1px solid #FECACA;
        animation: pulse 2s infinite;
    }
    .badge-sched {
        background-color: #ECFDF5; color: #059669; 
        padding: 4px 12px; border-radius: 20px; 
        font-size: 0.85em; font-weight: 700; border: 1px solid #A7F3D0;
    }
    
    @keyframes pulse {0% {opacity: 1;} 50% {opacity: 0.6;} 100% {opacity: 1;}}
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE (Clean - No Betting Tables) ---
DB_NAME = 'football_dashboard_v1.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # User Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT)''')
    # Logs Table
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    
    # Create Admin (Hardcoded Backup)
    try: c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin', ?)", (str(datetime.now()),))
    except: pass
    conn.commit(); conn.close()

init_db()

# --- 4. DATA ENGINE (ESPN - Guaranteed Data) ---
@st.cache_data(ttl=300)
def fetch_data():
    matches = []
    # Major Leagues
    leagues = [
        {"id": "eng.1", "name": "🇬🇧 Premier League"}, 
        {"id": "esp.1", "name": "🇪🇸 La Liga"},
        {"id": "ita.1", "name": "🇮🇹 Serie A"}, 
        {"id": "ger.1", "name": "🇩🇪 Bundesliga"},
        {"id": "fra.1", "name": "🇫🇷 Ligue 1"}, 
        {"id": "uefa.champions", "name": "🇪🇺 Champions League"}
    ]
    
    # Fetch Today & Tomorrow
    dates = [datetime.now().strftime("%Y%m%d"), (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")]
    
    for d in dates:
        for l in leagues:
            try:
                url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l['id']}/scoreboard?dates={d}"
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    for e in data.get('events', []):
                        status = e['status']['type']['shortDetail']
                        # Skip Final results to keep dashboard "Fresh"
                        if "FT" in status or "Final" in status: continue
                        
                        utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                        local = utc + timedelta(hours=3) # Baghdad Time
                        
                        matches.append({
                            "League": l['name'],
                            "Time": local.strftime("%H:%M"),
                            "Date": local.strftime("%Y-%m-%d"),
                            "Status": status,
                            "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                            "Away": e['competitions'][0]['competitors'][1]['team']['displayName']
                        })
            except: continue
    return matches

def analyze_match(h, a):
    # Simulation of AI Analysis
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {"Win %": h_win, "Draw %": d_win, "Away %": a_win, "Goals > 2.5": int((seed*4)%100)}

def log_system(user, action):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", (user, action, str(datetime.now())))
    conn.commit(); conn.close()

# --- 5. VIEWS ---

# FIXED FUNCTION NAME: 'login_view' matches the call at the bottom
def login_view():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center;'>⚽ Football AI Dashboard</h1>", unsafe_allow_html=True)
        
        with st.container():
            st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
            tab1, tab2 = st.tabs(["Login", "Register"])
            
            with tab1:
                u = st.text_input("Username", key="l_u").strip()
                p = st.text_input("Password", type="password", key="l_p").strip()
                if st.button("Access Dashboard", type="primary", use_container_width=True):
                    # Admin Bypass
                    if u == "admin" and p == "admin123":
                        st.session_state.user = {"name": "admin", "role": "admin"}
                        st.rerun()
                    
                    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username=?", (u,))
                    user = c.fetchone()
                    conn.close()
                    
                    if user and user[1] == p:
                        st.session_state.user = {"name": u, "role": user[2]}
                        log_system(u, "Login")
                        st.rerun()
                    else: st.error("Invalid Credentials")

            with tab2:
                nu = st.text_input("New User")
                np = st.text_input("New Pass", type="password")
                if st.button("Create Account", use_container_width=True):
                    try:
                        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                        c.execute("INSERT INTO users VALUES (?, ?, 'user', ?)", (nu, np, str(datetime.now())))
                        conn.commit(); conn.close()
                        st.success("Success! Please Login.")
                    except: st.error("Username taken.")
            st.markdown("</div>", unsafe_allow_html=True)

def user_dashboard():
    # Header
    c1, c2 = st.columns([3, 1])
    c1.title("Match Analysis Dashboard")
    c2.metric("System Status", "Live ●", delta_color="normal")
    
    # Search
    search = st.text_input("🔍 Search Teams, Leagues...", placeholder="Type 'Real Madrid' or 'Premier League'...")
    
    with st.spinner("Analyzing Market Data..."):
        matches = fetch_data()
    
    if search:
        matches = [m for m in matches if search.lower() in str(m).lower()]
    
    if not matches:
        st.info("No upcoming matches found in the database.")
        return

    # Data Grid
    df = pd.DataFrame(matches)
    for league in df['League'].unique():
        st.markdown(f"### {league}")
        
        for _, m in df[df['League'] == league].iterrows():
            ai = analyze_match(m['Home'], m['Away'])
            
            # Card UI
            st.markdown(f"""
            <div class="dashboard-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <div style="font-size:1.1em; font-weight:bold; color:#111827;">{m['Home']} <span style="color:#9CA3AF; margin:0 10px;">vs</span> {m['Away']}</div>
                    <div class="{'badge-live' if m['Status'] in ['Live','In Play'] else 'badge-sched'}">{m['Time']} ({m['Status']})</div>
                </div>
                <div style="display:flex; gap:20px; font-size:0.9em; color:#4B5563;">
                    <div>🏠 Home: <strong>{ai['Win %']}%</strong></div>
                    <div>🤝 Draw: <strong>{ai['Draw %']}%</strong></div>
                    <div>✈️ Away: <strong>{ai['Away %']}%</strong></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def admin_dashboard():
    st.title("Admin Control Panel")
    
    conn = sqlite3.connect(DB_NAME)
    users = pd.read_sql("SELECT rowid, * FROM users", conn)
    logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    
    t1, t2 = st.tabs(["User Management", "System Logs"])
    
    with t1:
        st.dataframe(users, use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            target = st.selectbox("Select User", users['username'].unique())
        with c2:
            if st.button("Delete User", type="primary"):
                if target == 'admin': st.error("Cannot delete Root Admin."); 
                else:
                    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                    c.execute("DELETE FROM users WHERE username=?", (target,))
                    conn.commit(); conn.close()
                    st.success(f"Deleted {target}"); st.rerun()

    with t2:
        st.dataframe(logs, use_container_width=True)

# --- 6. MAIN CONTROLLER ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    login_view()
else:
    # Sidebar Navigation
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user['name']}")
        st.caption(f"Role: {st.session_state.user['role'].upper()}")
        st.markdown("---")
        
        menu = st.radio("Navigation", ["Dashboard", "Admin Panel"] if st.session_state.user['role'] == 'admin' else ["Dashboard"])
        
        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    if menu == "Dashboard":
        user_dashboard()
    elif menu == "Admin Panel":
        if st.session_state.user['role'] == 'admin':
            admin_dashboard()
        else:
            st.error("Access Denied.")
