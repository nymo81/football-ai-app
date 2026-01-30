import streamlit as st
import pandas as pd
import requests
import sqlite3
import hashlib
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽")
# --- HIDE STREAMLIT BRANDING ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stToolbar"] {visibility: hidden;}
            .stDeployButton {display:none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
# --- DATABASE ENGINE (SQLite) ---
# This creates a local file 'football.db' to store users.
def init_db():
    conn = sqlite3.connect('football.db')
    c = conn.cursor()
    # Create table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    # Create a default admin if not exists
    try:
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Admin already exists
    return conn

def add_user(username, password, role="user"):
    conn = init_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username taken
    finally:
        conn.close()

def verify_user(username, password):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None # Returns 'admin', 'user', or None

# --- REAL DATA ENGINE (Fixed for 2026) ---
@st.cache_data(ttl=600)
def fetch_2026_data():
    # Fetching Bundesliga 2025/2026 Season (Current Season)
    url = "https://api.openligadb.de/getmatchdata/bl1/2025" 
    try:
        response = requests.get(url)
        data = response.json()
        
        matches = []
        for m in data:
            match_date = datetime.strptime(m['matchDateTime'], "%Y-%m-%dT%H:%M:%S")
            # Only show matches in the future
            if match_date > datetime.now():
                matches.append({
                    "Date": match_date.strftime("%Y-%m-%d %H:%M"),
                    "Home": m['team1']['teamName'],
                    "Away": m['team2']['teamName'],
                    "Icon1": m['team1']['teamIconUrl'],
                    "Icon2": m['team2']['teamIconUrl']
                })
        return matches
    except:
        return []

# --- AI LOGIC ---
def predict_match(home, away):
    # Simple placeholder algorithm
    score = (len(home) + len(away)) * 7 % 100
    if score > 55: return "HOME WIN", score
    elif score < 45: return "AWAY WIN", 100-score
    else: return "DRAW", 50

# --- AUTH SYSTEM ---
def login_page():
    st.sidebar.title("🔐 Access Control")
    tab1, tab2 = st.sidebar.tabs(["Login", "Sign Up"])

    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            role = verify_user(username, password)
            if role:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        new_user = st.text_input("New Username", key="signup_user")
        new_pass = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Create Account"):
            if add_user(new_user, new_pass):
                st.success("Account created! Please login.")
            else:
                st.error("Username already taken.")

# --- MAIN APP ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    # --- LOGGED IN VIEW ---
    role = st.session_state.role
    user = st.session_state.username
    
    # SIDEBAR
    st.sidebar.success(f"User: {user} ({role.upper()})")
    
    # Show different menus based on Role
    if role == "admin":
        menu = st.sidebar.radio("Admin Menu", ["Dashboard", "User Management", "System Logs", "Logout"])
    else:
        menu = st.sidebar.radio("User Menu", ["Live Matches", "My Profile", "Logout"])

    # --- PAGE LOGIC ---
    if menu == "Logout":
        st.session_state.logged_in = False
        st.rerun()

    # ADMIN: DASHBOARD
    elif menu == "Dashboard":
        st.title("Admin Dashboard")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Users", "52", "+3")
        c2.metric("API Requests", "1,204", "Success")
        c3.metric("System Health", "100%", "Good")

    # ADMIN: USER MANAGEMENT
    elif menu == "User Management":
        st.title("User Management")
        st.warning("Only Admins can see this area.")
        
        # Show all users (Fetch from DB)
        conn = init_db()
        df = pd.read_sql_query("SELECT username, role FROM users", conn)
        conn.close()
        st.dataframe(df)

    # USER: LIVE MATCHES
    elif menu == "Live Matches":
        st.title("⚽ Bundesliga 2026 Predictions")
        
        with st.spinner("Connecting to Live Feed..."):
            matches = fetch_2026_data()
        
        if matches:
            for m in matches[:10]:
                res, conf = predict_match(m['Home'], m['Away'])
                
                with st.expander(f"{m['Home']} vs {m['Away']} ({m['Date']})"):
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        st.image(m['Icon1'], width=50)
                        st.caption("VS")
                        st.image(m['Icon2'], width=50)
                    with c2:
                        st.subheader(f"Prediction: {res}")
                        st.progress(conf)
                        st.write(f"Confidence: **{conf}%**")
        else:
            st.info("No upcoming matches found in the 2026 calendar.")

    # FALLBACK
    else:
        st.title(f"Welcome, {user}")
        st.write("Select an option from the sidebar.")

# Initialize DB on first run
init_db()
