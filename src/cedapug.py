import re
import aiohttp
from typing import Dict, Any, Optional


class CedapugTracker:
    """Consulta el rating y las estadísticas de un jugador en CEDAPug a partir de su SteamID64.

    Busca por SteamID64 en:
      1. La tabla de ratings de https://cedapug.com/ratings (DataTables server-side).
      2. El export JSON oficial: https://cedapug.com/stats?export=1&steamid=...

    Si la tabla de ratings está caída o responde vacía (pasa a menudo), el módulo
    NO falla: sigue con el export de /stats, que es la fuente de rondas y stats.
    """

    BASE_URL = "https://cedapug.com"
    RATINGS_ENDPOINT = f"{BASE_URL}/cedapug/php/get/ratings.php"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{BASE_URL}/ratings",
        "X-Requested-With": "XMLHttpRequest",
    }

    # Umbrales publicados en la página /ratings (mu - 3*sigma). Se refrescan al consultar.
    _threshold_intermediate = 12.80
    _threshold_expert = 18.47

    @staticmethod
    def _rating_from(mu: float, sigma: float, last_played: int) -> Optional[int]:
        """Misma fórmula que usa la web: round((mu - 3*sigma) * 100), solo si el rating está 'estable'."""
        if sigma < 3 and last_played < 7:
            return int(round((mu - 3 * sigma) * 100))
        return None

    @classmethod
    def _tier_from(cls, mu: float, sigma: float) -> str:
        raw = mu - 3 * sigma
        if raw >= cls._threshold_expert:
            return "Expert"
        if raw >= cls._threshold_intermediate:
            return "Intermediate"
        return "Beginner"

    @classmethod
    async def _refresh_thresholds(cls, session: aiohttp.ClientSession) -> None:
        try:
            async with session.get(f"{cls.BASE_URL}/ratings", headers=cls.HEADERS, timeout=6) as resp:
                if resp.status != 200:
                    return
                html = await resp.text()
                # En la web las variables están intercambiadas: ratingIntermediate (18.47) es el umbral Expert
                m_exp = re.search(r'ratingIntermediate\s*=\s*"([\d.]+)"', html)
                m_int = re.search(r'ratingExpert\s*=\s*"([\d.]+)"', html)
                if m_exp:
                    cls._threshold_expert = float(m_exp.group(1))
                if m_int:
                    cls._threshold_intermediate = float(m_int.group(1))
        except Exception:
            pass

    @staticmethod
    async def _safe_json(resp: "aiohttp.ClientResponse") -> Optional[Any]:
        """Parsea JSON tolerando cuerpo vacío o HTML inesperado. Devuelve None si no hay JSON válido."""
        try:
            body = await resp.text()
        except Exception:
            return None
        if not body or not body.strip():
            return None
        try:
            return await resp.json(content_type=None)
        except Exception:
            try:
                import json
                return json.loads(body)
            except Exception:
                return None

    @staticmethod
    def _extract_player_entry(data: Dict[str, Any], steam64: str) -> Optional[Dict[str, Any]]:
        """Extrae la entrada del jugador del export de /stats.

        PlayerStats puede llegar como dict {steamid: {...}} o como lista [{...}].
        """
        ps = data.get("PlayerStats")
        if isinstance(ps, dict):
            entry = ps.get(str(steam64))
            if isinstance(entry, dict):
                return entry
            for v in ps.values():
                if isinstance(v, dict) and str(v.get("SteamId", "")) == str(steam64):
                    return v
            return None
        if isinstance(ps, list):
            for entry in ps:
                if isinstance(entry, dict) and str(entry.get("SteamId", "")) == str(steam64):
                    return entry
        return None

    @classmethod
    async def search_ratings(cls, session: aiohttp.ClientSession, steam64: str) -> Optional[dict]:
        """Busca el SteamID64 en la tabla de ratings y devuelve la fila exacta (o None).

        Nunca lanza excepciones: si la tabla está caída devuelve None.
        """
        params = {
            "draw": "1",
            "start": "0",
            "length": "10",
            "search[value]": steam64,
            "search[regex]": "false",
            "order[0][column]": "3",
            "order[0][dir]": "desc",
        }
        try:
            async with session.get(cls.RATINGS_ENDPOINT, params=params, headers=cls.HEADERS, timeout=8) as resp:
                if resp.status != 200:
                    return None
                payload = await cls._safe_json(resp)
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        for row in payload.get("data", []) or []:
            try:
                if str(row[2]) != str(steam64):
                    continue
                profile = row[0] or {}
                persona = row[1] or {}
                rating_obj = row[3] or {}
                return {
                    "steam64": str(row[2]),
                    "avatar": profile.get("avatar"),
                    "name": persona.get("personaName"),
                    "mu": float(rating_obj.get("mu", 0) or 0),
                    "sigma": float(rating_obj.get("sigma", 0) or 0),
                    "last_played": int(rating_obj.get("lastPlayed", 0) or 0),
                    "trust_factor": str(row[4]) if len(row) > 4 else "N/A",
                }
            except (IndexError, TypeError, ValueError):
                continue
        return None

    @classmethod
    async def get_rounds_played(cls, session: aiohttp.ClientSession, steam64: str) -> int:
        """Usa el export JSON oficial: /stats?export=1&steamid=... (S_RoundCount + I_RoundCount)."""
        try:
            async with session.get(
                f"{cls.BASE_URL}/stats",
                params={"export": "1", "steamid": steam64},
                headers=cls.HEADERS,
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    return 0
                data = await cls._safe_json(resp)
            if not isinstance(data, dict):
                return 0
            player = cls._extract_player_entry(data, steam64)
            if not player:
                return 0
            return int(player.get("S_RoundCount", 0) or 0) + int(player.get("I_RoundCount", 0) or 0)
        except Exception:
            return 0

    @classmethod
    async def get_player_stats(cls, session: aiohttp.ClientSession, steam64: str) -> Dict[str, Any]:
        """Obtiene rating, tier, trust factor y rondas de CEDAPug para el SteamID64.

        Estrategia:
          1. Tabla de ratings (si está disponible): rating, tier, trust factor, mu/sigma.
          2. Export de /stats (siempre): rondas jugadas. Si la tabla de ratings falla,
             el jugador se marca como encontrado igualmente si tiene stats en /stats.
        """
        stats: Dict[str, Any] = {
            "found": False,
            "url": f"{cls.BASE_URL}/stats?steamid={steam64}",
            "ratings_url": f"{cls.BASE_URL}/ratings",
            "rating": "N/A",
            "rating_value": None,
            "tier": "Sin rango",
            "trust_factor": "N/A",
            "name": None,
            "mu": None,
            "sigma": None,
            "last_played": None,
            "rounds": 0,
        }

        await cls._refresh_thresholds(session)

        # 1) Tabla de ratings (tolera caída: devuelve None si falla)
        row = await cls.search_ratings(session, steam64)
        if row:
            stats["found"] = True
            stats["name"] = row["name"]
            stats["mu"] = row["mu"]
            stats["sigma"] = row["sigma"]
            stats["last_played"] = row["last_played"]
            stats["trust_factor"] = row["trust_factor"]

            rating = cls._rating_from(row["mu"], row["sigma"], row["last_played"])
            if rating is not None:
                stats["rating_value"] = rating
                stats["rating"] = str(rating)
                stats["tier"] = cls._tier_from(row["mu"], row["sigma"])
            elif row["sigma"] >= 3:
                stats["rating"] = "En calibración"
                stats["tier"] = "Sin rango"
            else:
                stats["rating"] = "Inactivo"
                stats["tier"] = cls._tier_from(row["mu"], row["sigma"])

        # 2) Export de /stats: rondas jugadas (y señal de que el jugador existe)
        try:
            async with session.get(
                f"{cls.BASE_URL}/stats",
                params={"export": "1", "steamid": steam64},
                headers=cls.HEADERS,
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = await cls._safe_json(resp)
                else:
                    data = None
        except Exception as e:
            print(f"Error consultando CEDAPug /stats: {e}")
            data = None

        player = None
        if isinstance(data, dict):
            player = cls._extract_player_entry(data, steam64)

        if player:
            stats["found"] = True
            try:
                stats["rounds"] = int(player.get("S_RoundCount", 0) or 0) + int(player.get("I_RoundCount", 0) or 0)
            except (TypeError, ValueError):
                stats["rounds"] = 0
            # Sin fila en la tabla de ratings: mostrar solo rondas
            if not row:
                if stats["rating"] == "N/A":
                    stats["rating"] = "Sin rating" if stats["rounds"] > 0 else "N/A"

        return stats
