import os
import re
import json
import aiohttp
from typing import Dict, Any, Optional

class L4D2CenterTracker:
    """Busca el SteamID64 de un jugador en L4D2Center (https://l4d2center.com/players).

    Nota: la sección /players de L4D2Center está protegida por un desafío de Cloudflare
    ("Just a moment..."), que bloquea peticiones automáticas. El tracker:
      1. Intenta la URL configurada en L4D2CENTER_API_URL (opcional, ver README) con {steam64}.
      2. Intenta la página pública /players/?steamid=... y varias rutas JSON conocidas.
      3. Si Cloudflare responde con desafío, marca `blocked=True` y devuelve el enlace de búsqueda
         para que el usuario lo abra manualmente desde Discord.
    """
    BASE_URL = "https://l4d2center.com"
    PLAYERS_URL = f"{BASE_URL}/players/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": PLAYERS_URL,
    }

    @staticmethod
    def _is_cf_challenge(status: int, text: str) -> bool:
        return status in (403, 503) and ("Just a moment" in text or "cf-chl" in text or "challenge-platform" in text)

    @classmethod
    def _candidate_urls(cls, steam64: str):
        custom = os.getenv("L4D2CENTER_API_URL")
        if custom:
            yield custom.replace("{steam64}", steam64)
        yield f"{cls.PLAYERS_URL}?steamid={steam64}"
        yield f"{cls.PLAYERS_URL}?search={steam64}"
        yield f"{cls.PLAYERS_URL}{steam64}"
        yield f"{cls.BASE_URL}/api/players/{steam64}"
        yield f"{cls.BASE_URL}/api/player/{steam64}"

    @staticmethod
    def _parse_json(data: Any, steam64: str) -> Optional[dict]:
        """Extrae un jugador de una respuesta JSON con forma desconocida."""
        candidates = []
        if isinstance(data, dict):
            for key in ("data", "players", "results", "items", "player", "profile"):
                if key in data:
                    candidates.append(data[key])
            candidates.append(data)
        elif isinstance(data, list):
            candidates.append(data)

        for c in candidates:
            rows = c if isinstance(c, list) else [c]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                sid = str(row.get("steamid") or row.get("steamId") or row.get("steam64") or row.get("steamid64") or "")
                if sid == steam64:
                    return row
        return None

    @staticmethod
    def _parse_html(html: str, steam64: str) -> Optional[dict]:
        """Busca la fila del jugador en el HTML de /players."""
        if steam64 not in html:
            return None
        # Intentar localizar la fila <tr> que contiene el SteamID
        row_match = re.search(r"<tr[^>]*>(?:(?!</tr>).)*" + re.escape(steam64) + r"(?:(?!</tr>).)*</tr>", html, re.S | re.I)
        chunk = row_match.group(0) if row_match else html[max(0, html.find(steam64) - 1500): html.find(steam64) + 1500]
        text = re.sub(r"<[^>]+>", " ", chunk)
        text = re.sub(r"\s+", " ", text).strip()

        result: Dict[str, Any] = {"raw": text}
        m = re.search(r"(?:mmr|rating)\D{0,20}(\d{3,5})", text, re.I)
        if m:
            result["mmr"] = int(m.group(1))
        m = re.search(r"(?:games|matches|partidas)\D{0,20}(\d+)", text, re.I)
        if m:
            result["matches"] = int(m.group(1))
        m = re.search(r"(?:win\s*rate|winrate)\D{0,10}(\d{1,3})\s*%", text, re.I)
        if m:
            result["winrate"] = f"{m.group(1)}%"
        m = re.search(r"(?:rank|tier|rango)\D{0,10}([A-Za-z]+(?:\s?[IVX0-9]+)?)", text, re.I)
        if m:
            result["rank"] = m.group(1)
        return result

    @classmethod
    async def get_player_stats(cls, session: aiohttp.ClientSession, steam64: str) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "found": False,
            "blocked": False,
            "url": f"{cls.PLAYERS_URL}?steamid={steam64}",
            "rank_tier": "Unranked",
            "rating": "1000",
            "matches": 0,
            "winrate": "0%",
            "damage_per_round": "N/A",
            "mvp": 0,
        }

        for url in cls._candidate_urls(steam64):
            try:
                async with session.get(url, headers=cls.HEADERS, timeout=8, allow_redirects=True) as resp:
                    status = resp.status
                    ctype = resp.headers.get("Content-Type", "")
                    text = await resp.text(errors="ignore")
            except Exception as e:
                print(f"Error consultando L4D2Center ({url}): {e}")
                continue

            if cls._is_cf_challenge(status, text):
                stats["blocked"] = True
                continue
            if status != 200:
                continue

            row = None
            if "json" in ctype or text.lstrip().startswith(("{", "[")):
                try:
                    row = cls._parse_json(json.loads(text), steam64)
                except Exception:
                    row = None
            else:
                row = cls._parse_html(text, steam64)

            if row:
                stats["found"] = True
                stats["url"] = url if "api/" not in url else stats["url"]
                mmr = row.get("mmr") or row.get("rating") or row.get("elo")
                if mmr is not None:
                    stats["rating"] = str(mmr)
                matches = row.get("matches") or row.get("games") or row.get("games_played")
                if matches is not None:
                    stats["matches"] = int(matches)
                if row.get("winrate"):
                    stats["winrate"] = str(row["winrate"])
                rank = row.get("rank") or row.get("tier") or row.get("rank_tier")
                if rank:
                    stats["rank_tier"] = str(rank)
                elif stats["matches"] >= 11:
                    stats["rank_tier"] = "Ranked"
                else:
                    stats["rank_tier"] = "Placement"
                if row.get("mvp") is not None:
                    stats["mvp"] = int(row["mvp"])
                break

        return stats
