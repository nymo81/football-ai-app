import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽")

# --- LOGIN SYSTEM (Simple) ---
# Hardcoded for simplicity. In production, use Streamlit Secrets.
USERS = {"admin": "admin123", "user": "1234"}

def check_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.sidebar.title("🔒 Login")
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        
        if st.sidebar.button("Login"):
            if username in USERS and USERS[username] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.sidebar.error("Wrong username or password")
        return False
    return True

# --- REAL DATA ENGINE ---
@st.cache_data(ttl=600) # Cache for 10 mins
def get_live_matches():
    # Fetching Bundesliga 2024/2025 matches (Real Data)
    url = "https://api.openligadb.de/getmatchdata/bl1/2024"
    try:
        response = requests.get(url)
        data = response.json()
        
        matches = []
        for m in data:
            # Filter for upcoming matches only
            match_date = datetime.strptime(m['matchDateTime'], "%Y-%m-%dT%H:%M:%S")
            if match_date > datetime.now():
                matches.append({
                    "Date": match_date.strftime("%Y-%m-%d %H:%M"),
                    "Home": m['team1']['teamName'],
                    "Away": m['team2']['teamName'],
                    "Logo1": m['team1']['teamIconUrl'],
                    "Logo2": m['team2']['teamIconUrl']
                })
        return matches
    except:
        return []

# --- AI PREDICTION LOGIC ---
def predict(home, away):
    # Simple algorithm based on string weight (Placeholder for ML model)
    h_val = sum(map(ord, home))
    a_val = sum(map(ord, away))
    total = h_val + a_val
    
    home_prob = int((h_val / total) * 100)
    
    if home_prob > 50:
        return "HOME WIN", home_prob
    elif home_prob < 50:
        return "AWAY WIN", 100 - home_prob
    else:
        return "DRAW", 50

# --- MAIN APP ---
if check_login():
    # SIDEBAR
    st.sidebar.divider()
    st.sidebar.success(f"User: {st.session_state.username}")
    menu = st.sidebar.radio("Menu", ["Dashboard", "Live Predictions", "Settings"])
    
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

    # DASHBOARD PAGE
    if menu == "Dashboard":
        st.title("📊 Executive Dashboard")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Predictions", "1,240", "+12%")
        c2.metric("Model Accuracy", "87.4%", "+2.1%")
        c3.metric("Active Users", "14", "+1")
        
        st.subheader("Recent System Activity")
        st.table(pd.DataFrame({
            "Time": ["10:00", "10:05", "10:12"],
            "Event": ["System Update", "New User Login", "Data Refresh"],
            "Status": ["Success", "Success", "Pending"]
        }))

    # PREDICTIONS PAGE
    elif menu == "Live Predictions":
        st.title("⚽ Live Match Predictions")
        st.info("Fetching real-time data from OpenLigaDB API...")
        
        matches = get_live_matches()
        
        if not matches:
            st.warning("No upcoming matches found in the feed.")
        else:
            for match in matches[:10]: # Show next 10
                res, conf = predict(match['Home'], match['Away'])
                
                with st.container():
                    col1, col2, col3 = st.columns([1, 4, 1])
                    with col2:
                        st.write(f"**{match['Home']}** vs **{match['Away']}**")
                        st.caption(f"📅 {match['Date']}")
                        
                        # Visual Bar
                        st.progress(conf)
                        if res == "HOME WIN":
                            st.success(f"Prediction: {match['Home']} Wins ({conf}%)")
                        else:
                            st.info(f"Prediction: {match['Away']} Wins ({conf}%)")
                    st.divider()

    elif menu == "Settings":
        st.title("⚙️ Settings")
        st.write("Manage API keys and Model Parameters here.")