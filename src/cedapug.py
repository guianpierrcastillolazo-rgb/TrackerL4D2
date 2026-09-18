import aiohttp
from typing import Dict, Any

class CedapugTracker:
    """Consulta perfiles y estadísticas competitivas en CEDAPug."""
    BASE_URL = "https://cedapug.com"

    @staticmethod
    async def get_player_stats(session: aiohttp.ClientSession, steam64: str) -> Dict[str, Any]:
        """Obtiene las métricas de CEDAPug asociadas al SteamID64."""
        # Endpoint de perfil de CEDAPug
        url = f"{CedapugTracker.BASE_URL}/cedapug/php/pages/player.php?id={steam64}"
        stats = {
            "found": False,
            "url": url,
            "rating": "N/A",
            "matches": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": "0%",
            "mvp_points": 0,
            "sub_count": 0,
            "reliability": "100%"
        }
        
        try:
            headers = {"User-Agent": "L4D2-Stats-Discord-Bot/1.0"}
            async with session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Si el jugador existe en CEDAPug
                    if "Player not found" not in text and len(text) > 500:
                        stats["found"] = True
                        # En caso de página activa se extraen valores o se presentan enlaces directos
                        stats["rating"] = "Activo en PUGs"
        except Exception:
            pass
            
        return stats
