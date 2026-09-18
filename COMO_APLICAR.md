# Actualización TrackerL4D2 — búsqueda por SteamID64 en CEDAPug y L4D2Center

## Archivos a reemplazar en tu repo
- `src/cedapug.py`     → busca el SteamID64 en https://cedapug.com/ratings (mismo endpoint que la tabla) y saca rating, tier, trust factor y rondas (export JSON de /stats).
- `src/l4d2center.py`  → busca el SteamID64 en https://l4d2center.com/players (varias rutas + variable opcional L4D2CENTER_API_URL). Detecta el bloqueo de Cloudflare.
- `src/embeds.py`      → muestra los nuevos datos en el embed de `/stats`.
- `.env.example`       → nueva variable opcional `L4D2CENTER_API_URL`.

No hace falta tocar `bot.py`, `database.py` ni `views.py`.

## Cómo subirlo
1. Descarga esta carpeta y copia los archivos encima de los de tu repo (misma ruta).
2. `git add . && git commit -m "Buscar SteamID64 en CEDAPug y L4D2Center" && git push`
3. Redespliega el bot (Railway/Render/Docker).

## Importante sobre L4D2Center
La sección /players de l4d2center.com está detrás de un desafío de Cloudflare ("Just a moment...") que
bloquea cualquier petición que no venga de un navegador real. Por eso el bot, si lo bloquean, muestra
un botón/enlace para buscar el SteamID manualmente en lugar de fallar.

Si encuentras la URL real de datos (abre l4d2center.com/players en tu navegador → F12 → pestaña Network →
busca la petición que devuelve la lista de jugadores), ponla en `.env` como:
    L4D2CENTER_API_URL=https://l4d2center.com/....?steamid={steam64}
y el bot la usará automáticamente.
