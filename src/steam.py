import re
import aiohttp
from typing import Optional, Dict, Any, Tuple

STEAM64_BASE = 76561197960265728

class SteamResolver:
    """Detecta y normaliza identificadores de Steam y consulta la API oficial."""
    
    @staticmethod
    def detect_and_normalize(input_str: str) -> Tuple[str, str]:
        """
        Detecta el formato de entrada y retorna (tipo_detectado, valor_normalizado).
        Tipos: 'steam64', 'steam_id', 'steam_id3', 'vanity', 'url_profile', 'url_vanity'
        """
        s = input_str.strip()
        
        # URL completa con /profiles/7656119...
        m = re.search(r'steamcommunity\.com/profiles/(\d{17})', s)
        if m:
            return 'steam64', m.group(1)
            
        # URL completa con /id/custom_name
        m = re.search(r'steamcommunity\.com/id/([a-zA-Z0-9_\-]+)', s)
        if m:
            return 'vanity', m.group(1)
            
        # SteamID64 numérico (17 dígitos comenzando por 7656)
        if re.match(r'^7656\d{13}$', s):
            return 'steam64', s
            
        # SteamID clásico (STEAM_0:0:12345 o STEAM_1:1:12345)
        m = re.match(r'^STEAM_[0-1]:([0-1]):(\d+)$', s, re.IGNORECASE)
        if m:
            auth_server = int(m.group(1))
            auth_id = int(m.group(2))
            steam64 = str(STEAM64_BASE + (auth_id * 2) + auth_server)
            return 'steam_id', steam64
            
        # SteamID3 [U:1:12345] o U:1:12345
        m = re.match(r'^\[?U:1:(\d+)\]?$', s, re.IGNORECASE)
        if m:
            account_id = int(m.group(1))
            steam64 = str(STEAM64_BASE + account_id)
            return 'steam_id3', steam64
            
        # Si no coincide con ninguno, asumimos que es un Vanity URL (custom name)
        clean_vanity = re.sub(r'[^a-zA-Z0-9_\-]', '', s)
        return 'vanity', clean_vanity

    @staticmethod
    async def resolve_to_steam64(session: aiohttp.ClientSession, api_key: str, input_str: str) -> Tuple[Optional[str], str]:
        """Resuelve cualquier entrada a SteamID64 usando la Steam API si es necesario."""
        detected_type, value = SteamResolver.detect_and_normalize(input_str)
        
        if detected_type != 'vanity':
            return value, detected_type
            
        # Resolver vanity URL mediante API de Steam
        url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
        params = {"key": api_key, "vanityurl": value}
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", {})
                    if response.get("success") == 1:
                        return response.get("steamid"), "vanity"
        except Exception:
            pass
            
        return None, "vanity"

    @staticmethod
    async def get_player_summary(session: aiohttp.ClientSession, api_key: str, steam64: str) -> Dict[str, Any]:
        """Obtiene avatar, nombre, horas en L4D2 y estado de baneos de Steam."""
        res = {
            "steam64": steam64,
            "persona_name": "Desconocido",
            "profile_url": f"https://steamcommunity.com/profiles/{steam64}",
            "avatar_url": "",
            "l4d2_hours": 0.0,
            "vac_banned": False,
            "community_banned": False,
            "days_since_last_ban": 0
        }
        
        # 1. Player summary
        try:
            url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
            params = {"key": api_key, "steamids": steam64}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    players = data.get("response", {}).get("players", [])
                    if players:
                        p = players[0]
                        res["persona_name"] = p.get("personaname", "Desconocido")
                        res["avatar_url"] = p.get("avatarfull", "")
                        res["profile_url"] = p.get("profileurl", res["profile_url"])
        except Exception:
            pass

        # 2. Bans
        try:
            url = "https://api.steampowered.com/ISteamUser/GetPlayerBans/v1/"
            params = {"key": api_key, "steamids": steam64}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    players = data.get("players", [])
                    if players:
                        b = players[0]
                        res["vac_banned"] = b.get("VACBanned", False)
                        res["community_banned"] = b.get("CommunityBanned", False)
                        res["days_since_last_ban"] = b.get("DaysSinceLastBan", 0)
        except Exception:
            pass

        # 3. Left 4 Dead 2 playtime (AppID: 550)
        try:
            url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
            params = {"key": api_key, "steamid": steam64, "appids_filter[0]": 550, "include_appinfo": 1}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    games = data.get("response", {}).get("games", [])
                    for g in games:
                        if g.get("appid") == 550:
                            res["l4d2_hours"] = round(g.get("playtime_forever", 0) / 60, 1)
        except Exception:
            pass

        return res
