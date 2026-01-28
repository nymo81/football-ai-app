import sys
from sqlalchemy import create_engine, text
import random

# --- PASTE YOUR RAILWAY URL BELOW ---
# Keep the quotes! ""python feeder.py
DB_URL = "mysql://root:QsvXAFTUozUMAJRfoMWnPQdodhNvlmil@shinkansen.proxy.rlwy.net:25428/railway"

# FIX: Sometimes Railway URLs need a small tweak for Python
# We replace 'mysql://' with 'mysql+pymysql://' to make it work
if DB_URL.startswith("mysql://"):
    DB_URL = DB_URL.replace("mysql://", "mysql+pymysql://")

def generate_data():
    print("🚀 Connecting to Railway Database...")
    try:
        engine = create_engine(DB_URL)
        connection = engine.connect()
        print("✅ Connected!")

        # 1. Clear old data (Optional - keeps it fresh)
        connection.execute(text("TRUNCATE TABLE predictions"))
        connection.commit()

        # 2. Generate AI Predictions
        teams = [
            ("Arsenal", "Man City"), ("Liverpool", "Chelsea"), 
            ("Real Madrid", "Barcelona"), ("Bayern", "Dortmund"),
            ("PSG", "Marseille"), ("Al-Nassr", "Al-Hilal"),
            ("Inter Miami", "LA Galaxy"), ("Juventus", "Milan")
        ]
        
        print("🔮 Generating Predictions...")
        for home, away in teams:
            confidence = random.randint(55, 98)
            
            # Simple AI Logic: Higher confidence = Home Win
            if confidence > 60:
                pred = "HOME WIN"
            else:
                pred = "DRAW"

            # SQL Insert Query
            query = text("""
                INSERT INTO predictions (home_team, away_team, prediction, confidence, created_at, updated_at)
                VALUES (:home, :away, :pred, :conf, NOW(), NOW())
            """)
            
            connection.execute(query, {"home": home, "away": away, "pred": pred, "conf": confidence})
            print(f"   -> Analyzed: {home} vs {away}")

        connection.commit()
        print("\n🎉 SUCCESS! Go check your website now.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    generate_data()