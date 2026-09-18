# 🧟 L4D2 Stats Tracker — Discord Bot

Bot de Discord para rastrear estadísticas y perfiles competitivos de **Left 4 Dead 2** en **Steam**, **CEDAPug** ([cedapug.com](https://cedapug.com)) y **L4D2Center** ([l4d2center.com](https://l4d2center.com)).

---

## 🚀 Características
* **Detección inteligente de formatos:**
  * SteamID clásico: `STEAM_0:0:12345678`
  * SteamID3: `[U:1:24691356]` o `U:1:24691356`
  * SteamID64: `76561198000000000`
  * Vanity Username: `tu_alias`
  * URLs de Steam: `https://steamcommunity.com/id/...` o `https://steamcommunity.com/profiles/...`
* **Estadísticas de Steam:** Horas en L4D2, estado VAC / community bans, avatar y perfil.
* **Integración CEDAPug:** Enlace directo e información del perfil competitivo en la comunidad CedaMod.
* **Integración L4D2Center:** Enlace directo y datos clasificados del sistema Ranked Lobby.
* **Comparador de jugadores:** Comando `/compare` para enfrentar dos perfiles frente a frente.
* **Botones interactivos:** Cambia entre vista de Resumen, Infectados y Supervivientes sin recargar.
* **Vinculación de cuenta:** `/link <steam_id>` para consultas instantáneas con `/me`.
* **Tabla de clasificación:** `/leaderboard` para rankear a los jugadores de tu servidor.

---

## 🛠️ Requisitos
* Python 3.10+ (o Docker)
* Token de Bot de Discord ([Discord Developer Portal](https://discord.com/developers/applications))
* Steam Web API Key ([Steam Community Dev Key](https://steamcommunity.com/dev/apikey))

---

## 📦 Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/guian17/l4d2-stats-discord-bot.git
cd l4d2-stats-discord-bot
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
```
Edita `.env` con tus claves:
```env
DISCORD_BOT_TOKEN=tu_token_aqui
STEAM_API_KEY=tu_steam_api_key_aqui
# Opcional (para registrar slash commands al instante en un servidor):
# GUILD_ID=tu_server_id
```

### 3. Ejecutar con Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### 4. O ejecutar con Docker Compose
```bash
docker compose up -d --build
```

---

## 🤖 Comandos de Discord (Slash Commands)
* `/stats <búsqueda>` — Ficha de estadísticas con botones interactivos (Resumen / Infectados / Supervivientes).
* `/me` — Muestra tus estadísticas vinculadas.
* `/link <búsqueda>` — Vincula tu cuenta de Steam a tu perfil de Discord.
* `/compare <jugador1> <jugador2>` — Compara dos jugadores.
* `/leaderboard [métrica]` — Muestra el ranking interno del servidor (por horas, rating o partidas).
* `/help` — Muestra la guía de formatos y comandos.
