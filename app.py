import streamlit as st
import pandas as pd
import requests
import sqlite3
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Football AI Pro", layout="wide", page_icon="⚽", initial_sidebar_state="expanded")

# --- UPGRADE 1: SMART CSS (Hide Branding + Keep Sidebar) ---
st.markdown("""
    <style>
    /* Hide Streamlit Branding */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none;}
    [data-testid="stToolbar"] {visibility: hidden;}
    
    /* Force Sidebar Toggle to be Visible */
    [data-testid="stSidebarCollapsedControl"] {
        visibility: visible !important;
        display: block !important;
        color: white !important;
        z-index: 100000;
    }
    
    /* Betting & Form UI */
    .stMetric {background-color: #0E1117; border: 1px solid #333; padding: 10px; border-radius: 8px;}
    .form-badge {padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold; margin-right: 2px;}
    .form-w {background-color: #00cc00; color: white;}
    .form-d {background-color: #aaaaaa; color: black;}
    .form-l {background-color: #cc0000; color: white;}
    </style>
    """, unsafe_allow_html=True)

# --- TRANSLATIONS (English & Arabic) ---
LANG = {
    "en": {
        "app_name": "Football AI Pro", "login": "Login", "signup": "Sign Up",
        "username": "Username", "password": "Password", "create_acc": "Create Account",
        "welcome": "Welcome", "sign_out": "Sign Out", "nav": "Navigation",
        "menu_predictions": "Live Predictions", "menu_profile": "My Profile",
        "menu_admin_dash": "Admin Dashboard", "menu_users": "User Management",
        "menu_logs": "System Logs", "no_matches": "No matches found.",
        "conf": "Confidence", "winner": "Winner", "goals": "Goals", "btts": "Both Teams to Score",
        "save": "Save Changes", "role": "Role", "action": "Action", "time": "Time",
        "promote": "Promote to Admin", "demote": "Demote to User", "delete": "Delete User",
        "success_update": "Profile updated successfully!", "admin_area": "Admin Area",
        "prediction_header": "AI Market Analysis",
        # BETTING TERMS
        "balance": "Wallet Balance", "place_bet": "Place Bet", "amount": "Wager Amount",
        "potential_win": "Potential Win", "bet_placed": "Bet Placed Successfully!",
        "insufficient_funds": "Insufficient Funds!", "form": "Recent Form",
        "bet_history": "Betting History"
    },
    "ar": {
        "app_name": "المحلل الذكي لكرة القدم", "login": "تسجيل الدخول", "signup": "إنشاء حساب",
        "username": "اسم المستخدم", "password": "كلمة المرور", "create_acc": "إنشاء الحساب",
        "welcome": "مرحباً", "sign_out": "تسجيل الخروج", "nav": "القائمة الرئيسية",
        "menu_predictions": "التوقعات المباشرة", "menu_profile": "ملفي الشخصي",
        "menu_admin_dash": "لوحة التحكم", "menu_users": "إدارة المستخدمين",
        "menu_logs": "سجلات النظام", "no_matches": "لا توجد مباريات حالياً",
        "conf": "نسبة الثقة", "winner": "الفائز", "goals": "الأهداف", "btts": "كلا الفريقين يسجل",
        "save": "حفظ التغييرات", "role": "الصلاحية", "action": "الحدث", "time": "الوقت",
        "promote": "ترقية لمدير", "demote": "تخفيض لمستخدم", "delete": "حذف المستخدم",
        "success_update": "تم تحديث الملف الشخصي!", "admin_area": "منطقة الإدارة",
        "prediction_header": "تحليل الذكاء الاصطناعي",
        # BETTING TERMS
        "balance": "رصيد المحفظة", "place_bet": "ضع رهانك", "amount": "قيمة الرهان",
        "potential_win": "الربح المتوقع", "bet_placed": "تم وضع الرهان بنجاح!",
        "insufficient_funds": "الرصيد غير كافي!", "form": "أداء الفريق",
        "bet_history": "سجل المراهنات"
    }
}

# --- DATABASE ENGINE (Upgraded for Betting) ---
DB_NAME = 'football_pro_v3.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Users Table (Now with Balance)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, created_at TEXT, bio TEXT, balance REAL)''')
    # Logs Table
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, action TEXT, timestamp TEXT)''')
    # Bets Table (New)
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, match TEXT, bet_type TEXT, amount REAL, potential_win REAL, status TEXT, date TEXT)''')
    try:
        c.execute("INSERT INTO users VALUES ('admin', 'admin123', 'admin', ?, 'System Admin', 100000)", (str(datetime.now()),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return conn

def log_action(user, action):
    conn = init_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user, action, timestamp) VALUES (?, ?, ?)", 
              (user, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def manage_user(action, target_user, data=None):
    conn = init_db()
    c = conn.cursor()
    if action == "add":
        try:
            # New users get 1000 Coins Bonus
            c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                      (target_user, data, 'user', str(datetime.now()), 'New Bettor', 1000.0))
            conn.commit()
            return True
        except: return False
    elif action == "update_profile":
        c.execute("UPDATE users SET password=?, bio=? WHERE username=?", (data['pass'], data['bio'], target_user))
        conn.commit()
    elif action == "change_role":
        c.execute("UPDATE users SET role=? WHERE username=?", (data, target_user))
        conn.commit()
    elif action == "delete":
        c.execute("DELETE FROM users WHERE username=?", (target_user,))
        conn.commit()
    conn.close()

def get_user_info(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    u = c.fetchone()
    # Fetch bets
    c.execute("SELECT * FROM bets WHERE user=? ORDER BY id DESC", (username,))
    bets = c.fetchall()
    conn.close()
    return u, bets

def place_bet_db(user, match, bet_type, amount, odds):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE username=?", (user,))
    bal = c.fetchone()[0]
    
    if bal >= amount:
        new_bal = bal
