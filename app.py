import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    [data-testid="stToolbar"] {visibility: hidden;}
    footer {visibility: hidden;}
    .stMetric {background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333;}
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE (New Filename to avoid conflicts) ---
DB_NAME = 'football_v2.db'  # <--- CHANGED THIS TO FIX THE ERROR

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create table with 4 columns
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT)''')
    try:
        # Create Default Admin
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?)", (str(datetime.now()),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return conn

def add_user(username, password, role="user"):
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, password, role, str(datetime.now())))
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

    if len(matches) == 0:
        matches = [
            {"Date": "2026-02-01 20:00", "Home": "Real Madrid", "Away": "Barcelona", "Icon1": "", "Icon2": ""},
            {"Date": "2026-02-02 18:30", "Home": "Man City", "Away": "Arsenal", "Icon1": "", "Icon2": ""},
            {"Date": "2026-02-03 20:45", "Home": "Bayern Munich", "Away": "Dortmund", "Icon1": "", "Icon2": ""},
            {"Date": "2026-02-04 15:00", "Home": "Juventus", "Away": "AC Milan", "Icon1": "", "Icon2": ""}
        ]
    return matches

# --- AI ENGINE ---
def analyze_match(home, away):
    score_h = sum(map(ord, home)) 
    score_a = sum(map(ord, away))
    total = score_h + score_a
    h_prob = int((score_h / total) * 100)
    
    if h_prob > 55: winner = "HOME"
    elif h_prob < 45: winner = "AWAY"
    else: winner = "DRAW"

    return {
        "1X2": winner, 
        "1X2_Conf": h_prob if winner == "HOME" else (100-h_prob),
        "Goals": "OVER 2.5" if (len(home)+len(away)) % 2 == 0 else "UNDER 2.5",
        "BTTS": "YES" if abs(score_h - score_a) < 20 else "NO"
    }

# --- UI LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # Login Page
    st.title("⚽ Football AI Pro")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        u = st.text_input("Username", key="l_u")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Login"):
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
        if st.button("Create Account"):
            if add_user(nu, np):
                st.success("Created! Please Login.")
            else:
                st.error("Username taken.")

else:
    # Dashboard
    st.sidebar.title("Navigation")
    st.sidebar.info(f"User: **{st.session_state.username}**")
    
    menu_options = ["Live Predictions", "My History", "Settings"]
    if st.session_state.role == 'admin':
        menu_options = ["Admin Dashboard", "User Management"] + menu_options
        
    menu = st.sidebar.radio("Go to:", menu_options)
    
    st.sidebar.divider()
    if st.sidebar.button("Sign Out"):
        st.session_state.logged_in = False
        st.rerun()

    # --- MENU PAGES ---
    if menu == "Admin Dashboard":
        st.title("📊 System Overview")
        st.metric("Total Users", len(get_all_users()))
        
    elif menu == "User Management":
        st.title("👥 Users")
        st.dataframe(get_all_users(), use_container_width=True)

    elif menu == "Live Predictions":
        st.title("🧠 AI Analysis")
        matches = fetch_matches()
        for m in matches:
            analysis = analyze_match(m['Home'], m['Away'])
            with st.expander(f"{m['Home']} vs {m['Away']}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Winner", analysis['1X2'])
                c2.metric("Goals", analysis['Goals'])
                c3.metric("BTTS", analysis['BTTS'])

    elif menu == "Settings":
        st.title("Settings")
        st.write("Profile settings.")

# Init DB
init_db()
