import aiohttp
import re
from typing import Dict, Any

class CedapugTracker:
    """Consulta perfiles y estadísticas competitivas en CEDAPug."""
    BASE_URL = "https://cedapug.com"

    @staticmethod
    async def get_player_stats(session: aiohttp.ClientSession, steam64: str) -> Dict[str, Any]:
        """Obtiene las métricas de CEDAPug asociadas al SteamID64 usando la URL oficial de stats."""
        url = f"{CedapugTracker.BASE_URL}/stats?steamid={steam64}"
        stats = {
            "found": False,
            "url": url,
            "rating": "N/A",
            "rounds": 0
        }
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            async with session.get(url, headers=headers, timeout=6) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Si tiene partidas registradas y no es solo plantilla vacía
                    if "No data available" not in text and ("Rounds Played" in text or "Wall of Fame" in text):
                        stats["found"] = True
                        stats["rating"] = "Activo en PUGs"
                        
                        r_match = re.search(r"Rounds Played\s*(\d+)", text)
                        if r_match:
                            stats["rounds"] = int(r_match.group(1))
                            stats["rating"] = f"{stats['rounds']} rondas jugadas"
        except Exception as e:
            print(f"Error consultando CEDAPug: {e}")
            
        return stats
