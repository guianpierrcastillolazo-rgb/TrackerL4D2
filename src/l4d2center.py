import os
import struct
import aiohttp
from typing import Dict, Any, Optional, List, Tuple

# ---------------------------------------------------------------------------
# Decodificador protobuf minimalista (sin dependencias extra).
# L4D2Center expone su API en https://api.l4d2center.com/v2/getplayers y
# responde con un mensaje protobuf "PlayerList" (ver /players/script.js del sitio).
# ---------------------------------------------------------------------------

def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    result = 0
    shift = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, i
        shift += 7
    raise ValueError("varint truncado")


def _parse_message(buf: bytes) -> Dict[int, List[Any]]:
    """Devuelve {numero_de_campo: [valores...]} con valores crudos."""
    out: Dict[int, List[Any]] = {}
    i = 0
    while i < len(buf):
        key, i = _read_varint(buf, i)
        field, wire = key >> 3, key & 0x07
        if wire == 0:
            val, i = _read_varint(buf, i)
        elif wire == 1:
            val = buf[i:i + 8]
            i += 8
        elif wire == 2:
            length, i = _read_varint(buf, i)
            val = buf[i:i + length]
            i += length
        elif wire == 5:
            val = buf[i:i + 4]
            i += 4
        else:
            raise ValueError(f"wire type no soportado: {wire}")
        out.setdefault(field, []).append(val)
    return out


def _as_int(values: Optional[List[Any]], default: int = 0) -> int:
    if not values:
        return default
    v = values[-1]
    if isinstance(v, int):
        # zig-zag no se usa aquí (int32/int64 normales)
        if v >= (1 << 63):
            v -= (1 << 64)
        return v
    return default


def _as_bool(values: Optional[List[Any]]) -> bool:
    return bool(_as_int(values, 0))


def _as_str(values: Optional[List[Any]], default: str = "") -> str:
    if not values:
        return default
    v = values[-1]
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return default
    return default


def _as_float(values: Optional[List[Any]], default: float = 0.0) -> float:
    if not values:
        return default
    v = values[-1]
    if isinstance(v, (bytes, bytearray)) and len(v) == 4:
        return struct.unpack("<f", bytes(v))[0]
    if isinstance(v, (bytes, bytearray)) and len(v) == 8:
        return struct.unpack("<d", bytes(v))[0]
    return default


class L4D2CenterTracker:
    """Consulta el SteamID64 en la API real de L4D2Center.

    Endpoint usado por la propia web (l4d2center.com/players):
        GET https://api.l4d2center.com/v2/getplayers?type=all&low=0&high=9&search=<steamid_o_nick>
    Respuesta: protobuf PlayerList (Success, List[PlayerInfo], TotalPlayers, ...).

    Campos de PlayerInfo que leemos:
        2 SteamID64 (string), 3 AvatarSmall, 4 AvatarBig, 5 Nickname,
        6 Mmr (int32), 7 MmrUncertainty (float), 12 ProfValidated, 13 RulesAccepted,
        15 IsOnline, 17 IsInGame, 18 IsInQueue, 19 MmrGrade (int32),
        43 BanID, 45 Subscription, 54 CasualMmr, 56 CasualMmrGrade.
    """

    BASE_URL = "https://l4d2center.com"
    PLAYERS_URL = f"{BASE_URL}/players/"
    API_URL = os.getenv("L4D2CENTER_API_URL", "https://api.l4d2center.com/v2/getplayers")
    HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": BASE_URL,
        "Referer": PLAYERS_URL,
    }

    SUB_NAMES = {0: "", 1: "Basic", 2: "Premium"}

    @staticmethod
    def _is_cf_challenge(status: int, body: bytes) -> bool:
        if status not in (403, 503):
            return False
        head = body[:4000].lower()
        return b"just a moment" in head or b"cf-chl" in head or b"challenge-platform" in head

    @classmethod
    def _grade_name(cls, grade: int) -> str:
        if grade <= 0:
            return "Sin rango"
        return f"Grado {grade}"

    @classmethod
    def _parse_player(cls, raw: bytes) -> Dict[str, Any]:
        f = _parse_message(raw)
        sub_type = 0
        sub_msg = f.get(45)
        if sub_msg and isinstance(sub_msg[-1], (bytes, bytearray)):
            try:
                sub_type = _as_int(_parse_message(bytes(sub_msg[-1])).get(1), 0)
            except Exception:
                sub_type = 0
        return {
            "steam64": _as_str(f.get(2)),
            "avatar_small": _as_str(f.get(3)),
            "avatar_big": _as_str(f.get(4)),
            "nickname": _as_str(f.get(5)),
            "mmr": _as_int(f.get(6)),
            "mmr_uncertainty": _as_float(f.get(7)),
            "validated": _as_bool(f.get(12)),
            "rules_accepted": _as_bool(f.get(13)),
            "online": _as_bool(f.get(15)),
            "in_game": _as_bool(f.get(17)),
            "in_queue": _as_bool(f.get(18)),
            "mmr_grade": _as_int(f.get(19)),
            "ban_id": _as_int(f.get(43)),
            "subscription": sub_type,
            "casual_mmr": _as_int(f.get(54)),
            "casual_grade": _as_int(f.get(56)),
        }

    @classmethod
    def _parse_playerlist(cls, raw: bytes, steam64: str) -> Optional[Dict[str, Any]]:
        msg = _parse_message(raw)
        if not _as_bool(msg.get(1)):
            return None
        for entry in msg.get(5, []):
            if not isinstance(entry, (bytes, bytearray)):
                continue
            try:
                player = cls._parse_player(bytes(entry))
            except Exception:
                continue
            if player.get("steam64") == steam64:
                return player
        return None

    @classmethod
    async def get_player_stats(cls, session: aiohttp.ClientSession, steam64: str) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "found": False,
            "blocked": False,
            "url": f"{cls.PLAYERS_URL}",
            "profile_url": f"{cls.BASE_URL}/profile/?steam_id={steam64}",
            "rank_tier": "Sin rango",
            "rating": "0",
            "mmr": 0,
            "mmr_grade": 0,
            "casual_mmr": 0,
            "casual_grade": 0,
            "matches": 0,
            "winrate": "N/A",
            "damage_per_round": "N/A",
            "mvp": 0,
            "name": "",
            "avatar": "",
            "online": False,
            "in_game": False,
            "in_queue": False,
            "validated": False,
            "banned": False,
            "subscription": "",
        }

        params = {"type": "all", "low": 0, "high": 9, "search": steam64}
        try:
            async with session.get(cls.API_URL, params=params, headers=cls.HEADERS, timeout=10) as resp:
                status = resp.status
                body = await resp.read()
        except Exception as e:
            print(f"Error consultando L4D2Center: {e}")
            return stats

        if cls._is_cf_challenge(status, body):
            stats["blocked"] = True
            return stats
        if status != 200 or not body:
            if status in (403, 503):
                stats["blocked"] = True
            return stats

        try:
            player = cls._parse_playerlist(body, steam64)
        except Exception as e:
            print(f"Error decodificando respuesta de L4D2Center: {e}")
            return stats

        if not player:
            return stats

        stats.update({
            "found": True,
            "url": stats["profile_url"],
            "name": player["nickname"],
            "avatar": player["avatar_big"] or player["avatar_small"],
            "mmr": player["mmr"],
            "mmr_grade": player["mmr_grade"],
            "rating": str(player["mmr"]) if player["mmr_grade"] > 0 else "En calibración",
            "rank_tier": cls._grade_name(player["mmr_grade"]),
            "casual_mmr": player["casual_mmr"],
            "casual_grade": player["casual_grade"],
            "online": player["online"],
            "in_game": player["in_game"],
            "in_queue": player["in_queue"],
            "validated": player["validated"],
            "banned": player["ban_id"] > 0,
            "subscription": cls.SUB_NAMES.get(player["subscription"], ""),
        })
        return stats
