import streamlit as st
import pandas as pd
import requests
import sqlite3
import base64
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Football AI Dashboard", 
    layout="wide", 
    page_icon="⚽", 
    initial_sidebar_state="expanded"
)

# --- 2. MODERN PRO THEME ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #1F2937;
    }
    .stApp {background-color: #F3F4F6;}
    [data-testid="stSidebar"] {background-color: #FFFFFF; border-right: 1px solid #E5E7EB;}
    
    .dashboard-card {
        background-color: #FFFFFF; padding: 24px; border-radius: 16px;
        border: 1px solid #E5E7EB; margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .badge-live {
        background-color: #FEF2F2; color: #DC2626; padding: 4px 12px; 
        border-radius: 20px; font-size: 0.85em; font-weight: 700; border: 1px solid #FECACA;
        animation: pulse 2s infinite;
    }
    .badge-sched {
        background-color: #ECFDF5; color: #059669; padding: 4px 12px; 
        border-radius: 20px; font-size: 0.85em; font-weight: 700; border: 1px solid #A7F3D0;
    }
    @keyframes pulse {0% {opacity: 1;} 50% {opacity: 0.6;} 100% {opacity: 1;}}
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE ---
DB_NAME = 'football_v41_download.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    try: c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin')", )
    except: pass
    conn.commit(); conn.close()

init_db()

# --- 4. DATA ENGINE ---
@st.cache_data(ttl=300)
def fetch_data():
    matches = []
    
    # 1. Try RapidAPI (Live Endpoint)
    try:
        url = "https://free-api-live-football-data.p.rapidapi.com/football-current-live"
        headers = {
            "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
            "x-rapidapi-key": "f84fc89ce9msh35e8c7081df9999p1df9d8jsn071086d01b59"
        }
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            items = data.get('response', [])
            for item in items:
                matches.append({
                    "League": item.get('league', {}).get('name', 'Global'),
                    "Time": "LIVE",
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Status": "In Play",
                    "Home": item.get('home_team', {}).get('name', 'Home'),
                    "Away": item.get('away_team', {}).get('name', 'Away'),
                    "Score": f"{item.get('home_goal',0)}-{item.get('away_goal',0)}"
                })
    except: pass

    # 2. ESPN Fallback
    if not matches:
        leagues = [
            {"id": "eng.1", "name": "Premier League"}, {"id": "esp.1", "name": "La Liga"},
            {"id": "ita.1", "name": "Serie A"}, {"id": "ger.1", "name": "Bundesliga"},
            {"id": "fra.1", "name": "Ligue 1"}, {"id": "uefa.champions", "name": "UCL"}
        ]
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
                            if "FT" in status or "Final" in status: continue
                            
                            utc = datetime.strptime(e['date'], "%Y-%m-%dT%H:%M:%SZ")
                            local = utc + timedelta(hours=3)
                            
                            try: score = f"{e['competitions'][0]['competitors'][0]['score']}-{e['competitions'][0]['competitors'][1]['score']}"
                            except: score = "vs"

                            matches.append({
                                "League": l['name'],
                                "Time": local.strftime("%H:%M"),
                                "Date": local.strftime("%Y-%m-%d"),
                                "Status": status,
                                "Home": e['competitions'][0]['competitors'][0]['team']['displayName'],
                                "Away": e['competitions'][0]['competitors'][1]['team']['displayName'],
                                "Score": score
                            })
                except: continue
    return matches

def analyze_match(h, a):
    seed = len(h) + len(a)
    h_win = (seed * 7) % 85 + 10; d_win = (100 - h_win) // 3; a_win = 100 - h_win - d_win
    return {"Win %": h_win, "Draw %": d_win, "Away %": a_win}

# --- 5. NEW FEATURE: CSV DOWNLOAD ---
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

# --- 6. VIEWS ---
def login_view():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center;'>⚽ Football AI Dashboard</h1>", unsafe_allow_html=True)
        with st.container():
            st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
            u = st.text_input("Username").strip()
            p = st.text_input("Password", type="password").strip()
            if st.button("Access Dashboard", type="primary", use_container_width=True):
                # Bypass
                if u == "admin" and p == "admin123":
                    st.session_state.user = {"name": "admin", "role": "admin"}
                    st.rerun()
                # DB Check
                conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=?", (u,))
                user = c.fetchone()
                conn.close()
                if user and user[1] == p:
                    st.session_state.user = {"name": u, "role": user[2]}
                    st.rerun()
                else: st.error("Invalid Credentials")
            st.markdown("</div>", unsafe_allow_html=True)

def dashboard_view():
    st.title("Match Analysis Dashboard")
    
    # FETCH DATA
    with st.spinner("Fetching Live Data..."):
        matches = fetch_data()
    
    if not matches:
        st.info("No matches found right now.")
        return

    # --- SIDEBAR FILTERS (From your snippet) ---
    with st.sidebar:
        st.header("Filters")
        df_full = pd.DataFrame(matches)
        
        # League Filter
        leagues = sorted(df_full['League'].unique())
        selected_leagues = st.multiselect('Select League', leagues, leagues)
        
        # Apply Filter
        if selected_leagues:
            df_filtered = df_full[df_full['League'].isin(selected_leagues)]
        else:
            df_filtered = df_full

        st.markdown("---")
        
        # --- DOWNLOAD BUTTON (From your snippet) ---
        csv = convert_df(df_filtered)
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name='football_matches.csv',
            mime='text/csv',
            use_container_width=True
        )

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.user = None; st.rerun()

    # --- MAIN DASHBOARD ---
    # Search
    search = st.text_input("🔍 Search Teams...", placeholder="Type 'Liverpool'...")
    if search:
        df_filtered = df_filtered[df_filtered['Home'].str.contains(search, case=False) | df_filtered['Away'].str.contains(search, case=False)]

    # Display Cards
    for league in df_filtered['League'].unique():
        st.markdown(f"### {league}")
        league_data = df_filtered[df_filtered['League'] == league]
        
        for _, m in league_data.iterrows():
            ai = analyze_match(m['Home'], m['Away'])
            
            st.markdown(f"""
            <div class="dashboard-card">
                <div style="display:flex; justify-
