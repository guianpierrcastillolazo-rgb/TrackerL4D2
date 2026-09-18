import sqlite3
import os
from typing import List, Dict, Any, Optional

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "bot.db")
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB)

def init_db():
    try:
        db_dir = os.path.dirname(os.path.abspath(DB_PATH))
        os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        print(f"Advertencia al crear directorio de BD ({db_dir}): {e}")
        
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                steam64 TEXT PRIMARY KEY,
                persona_name TEXT,
                avatar_url TEXT,
                l4d2_hours REAL DEFAULT 0,
                vac_banned INTEGER DEFAULT 0,
                ceda_rating TEXT DEFAULT 'N/A',
                center_rating INTEGER DEFAULT 1000,
                center_matches INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_links (
                discord_user_id TEXT PRIMARY KEY,
                steam64 TEXT,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (steam64) REFERENCES players(steam64)
            )
        """)
        conn.commit()

def upsert_player(steam64: str, name: str, avatar: str, hours: float, vac_banned: bool, ceda_rating: str = "N/A", center_rating: int = 1000, center_matches: int = 0):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO players (steam64, persona_name, avatar_url, l4d2_hours, vac_banned, ceda_rating, center_rating, center_matches, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(steam64) DO UPDATE SET
                    persona_name = excluded.persona_name,
                    avatar_url = excluded.avatar_url,
                    l4d2_hours = excluded.l4d2_hours,
                    vac_banned = excluded.vac_banned,
                    ceda_rating = excluded.ceda_rating,
                    center_rating = excluded.center_rating,
                    center_matches = excluded.center_matches,
                    last_updated = CURRENT_TIMESTAMP
            """, (steam64, name, avatar, hours, 1 if vac_banned else 0, ceda_rating, center_rating, center_matches))
            conn.commit()
    except Exception as e:
        print(f"Error al guardar jugador en BD: {e}")

def link_discord_user(discord_user_id: str, steam64: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_links (discord_user_id, steam64, linked_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(discord_user_id) DO UPDATE SET
                    steam64 = excluded.steam64,
                    linked_at = CURRENT_TIMESTAMP
            """, (str(discord_user_id), steam64))
            conn.commit()
    except Exception as e:
        print(f"Error al vincular usuario: {e}")

def get_linked_steam64(discord_user_id: str) -> Optional[str]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT steam64 FROM user_links WHERE discord_user_id = ?", (str(discord_user_id),))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"Error al leer usuario vinculado: {e}")
        return None

def get_leaderboard(metric: str = "hours", limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if metric == "rating":
                order_by = "center_rating DESC"
            elif metric == "matches":
                order_by = "center_matches DESC"
            else:
                order_by = "l4d2_hours DESC"
                
            cursor.execute(f"SELECT * FROM players ORDER BY {order_by} LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error al obtener leaderboard: {e}")
        return []
