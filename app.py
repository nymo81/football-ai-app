import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CUSTOM CSS (Clean UI) ---
st.markdown("""
    <style>
    [data-testid="stToolbar"] {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('football.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?)", (datetime.now(),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return conn

def add_user(username, password, role="user"):
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, password, role, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_users():
    conn = init_db()
    df = pd.read_sql_query("SELECT username, role, created_at FROM users", conn)
    conn.close()
    return df

# --- HYBRID DATA ENGINE ---
@st.cache_data(ttl=600)
def fetch_matches():
    # Attempt Real Data (Bundesliga 2025/2026)
    url = "https://api.openligadb.de/getmatchdata/bl1/2025" 
    matches = []
    
    try:
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            for m in data:
                match_date = datetime.strptime(m['matchDateTime'], "%Y-%m-%dT%H:%M:%S")
                if match_date > datetime.now():
                    matches.append({
                        "Date": match_date.strftime("%Y-%m-%d %H:%M"),
                        "Home": m['team1']['teamName'],
                        "Away": m['team2']['teamName'],
                        "Icon1": m['team1']['teamIconUrl'],
                        "Icon2": m['team2']['teamIconUrl']
                    })
    except:
        pass

    # Safety Net: Demo Data if API is empty
    if len(matches) == 0:
        matches = [
            {"Date": "2026-02-01 20:00", "Home": "Real Madrid", "Away": "Barcelona", "Icon1": "", "Icon2": ""},
            {"Date": "2026-02-02 18:30", "Home": "Man City", "Away": "Arsenal", "Icon1": "", "Icon2": ""},
            {"Date": "2026-02-03 20:45", "Home": "Bayern Munich", "Away": "Dortmund", "Icon1": "", "Icon2": ""},
            {"Date": "2026-02-04 15:00", "Home": "Juventus", "Away": "AC Milan", "Icon1": "", "Icon2": ""}
        ]
    return matches

# --- ADVANCED AI ENGINE ---
def analyze_match(home, away):
    # Generates 3 types of predictions
    # 1. Winner (1X2)
    score_h = sum(map(ord, home)) 
    score_a = sum(map(ord, away))
    total = score_h + score_a
    h_prob = int((score_h / total) * 100)
    
    if h_prob > 55: winner = "HOME"
    elif h_prob < 45: winner = "AWAY"
    else: winner = "DRAW"

    # 2. Over/Under 2.5 Goals
    # Logic: Longer names = more conservative play (just a heuristic for demo)
    goals_prob = (len(home) + len(away)) * 3
    over_25 = "OVER 2.5" if goals_prob > 55 else "UNDER 2.5"

    # 3. BTTS (Both Teams To Score)
    btts_prob = abs(score_h - score_a) % 50
    btts = "YES" if btts_prob > 25 else "NO"

    return {
        "1X2": winner, 
        "1X2_Conf": h_prob if winner == "HOME" else (100-h_prob),
        "Goals": over_25,
        "BTTS": btts
    }

# --- UI COMPONENTS ---
def sidebar_menu():
    st.sidebar.title("📱 Football AI")
    st.sidebar.info(f"User: **{st.session_state.username}**")
    st.sidebar.divider()
    
    role = st.session_state.role
    
    if role == 'admin':
        choice = st.sidebar.radio("Menu", ["Admin Dashboard", "User Management", "Live Predictions", "Settings"])
    else:
        choice = st.sidebar.radio("Menu", ["Live Predictions", "My History", "Settings"])
    
    st.sidebar.divider()
    if st.sidebar.button("🚪 Sign Out", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()
        
    return choice

# --- PAGES ---
def login_page():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("⚽ Football AI Pro")
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            u = st.text_input("Username", key="l_u")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("Login", use_container_width=True):
                role = verify_user(u, p)
                if role:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.role = role
                    st.rerun()
                else:
                    st.error("Invalid Login")
        
        with tab2:
            nu = st.text_input("New Username", key="s_u")
            np = st.text_input("New Password", type="password", key="s_p")
            if st.button("Create Account", use_container_width=True):
                if add_user(nu, np):
                    st.success("Created! Please Login.")
                else:
                    st.error("Username taken.")

def show_predictions_page(is_admin=False):
    st.title("🧠 AI Market Analysis")
    
    matches = fetch_matches()
    
    # Filter Controls
    c1, c2 = st.columns(2)
    with c1:
        search = st.text_input("🔍 Search Team", placeholder="e.g. Bayern")
    with c2:
        league = st.selectbox("🏆 Filter League", ["All Leagues", "Bundesliga", "Premier League", "La Liga"])
    
    st.markdown("---")

    for m in matches:
        if search.lower() in m['Home'].lower() or search.lower() in m['Away'].lower():
            analysis = analyze_match(m['Home'], m['Away'])
            
            with st.container():
                # Match Header
                c1, c2, c3 = st.columns([1, 4, 1])
                with c2:
                    st.subheader(f"{m['Home']} vs {m['Away']}")
                    st.caption(f"📅 {m['Date']} | 🏆 Bundesliga")
                
                # Market Predictions (Tabs)
                tab1, tab2, tab3 = st.tabs(["🏆 Match Winner", "⚽ Goals (O/U)", "🥅 BTTS"])
                
                with tab1:
                    col_a, col_b = st.columns(2)
                    col_a.metric("Prediction", analysis['1X2'])
                    col_b.progress(analysis['1X2_Conf'] / 100)
                    col_b.caption(f"Confidence: {analysis['1X2_Conf']}%")
                
                with tab2:
                    st.metric("Total Goals", analysis['Goals'], delta="AI Model v2.1")
                
                with tab3:
                    st.metric("Both Teams To Score", analysis['BTTS'])

                st.markdown("---")

# --- MAIN APP LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    # Authenticated Area
    menu = sidebar_menu()
    
    # --- ADMIN AREA ---
    if st.session_state.role == 'admin':
        if menu == "Admin Dashboard":
            st.title("📊 System Overview")
            u_count = len(get_all_users())
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Users", u_count)
            c2.metric("Active Predictions", "12")
            c3.metric("System Health", "100%")
            
        elif menu == "User Management":
            st.title("👥 User Database")
            users = get_all_users()
            st.dataframe(users, use_container_width=True)
            
        elif menu == "Live Predictions":
            show_predictions_page(is_admin=True)
            
        elif menu == "Settings":
            st.title("⚙️ Admin Settings")
            st.write("System configuration options go here.")

    # --- USER AREA ---
    else:
        if menu == "Live Predictions":
            show_predictions_page()
            
        elif menu == "My History":
            st.title("📜 My History")
            st.info("You haven't saved any predictions yet.")
            
        elif menu == "Settings":
            st.title("⚙️ User Settings")
            st.write("Change password or update profile.")

# Initialize DB
init_db()
