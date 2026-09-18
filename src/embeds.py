import discord

def create_stats_embed(steam_data: dict, cedapug_data: dict, l4d2center_data: dict, input_type: str, page: str = "overview") -> discord.Embed:
    name = steam_data.get("persona_name", "Jugador")
    steam64 = steam_data.get("steam64", "")
    avatar = steam_data.get("avatar_url", "")
    profile_url = steam_data.get("profile_url", "")
    l4d2_hours = steam_data.get("l4d2_hours", 0)
    vac_banned = steam_data.get("vac_banned", False)
    ban_badge = "🔴 VAC BAN" if vac_banned else "🟢 Limpio"
    
    color = discord.Color.red() if vac_banned else discord.Color.dark_theme()
    
    has_ceda = cedapug_data.get("found", False)
    has_center = l4d2center_data.get("found", False)
    
    if page == "infected":
        embed = discord.Embed(
            title=f"🧟 Infectados — {name}",
            url=profile_url,
            color=discord.Color.purple()
        )
        embed.description = "Estadísticas y parámetros de juego competitivo (Config CedaMod/ZoneMod)."
        embed.add_field(
            name="☠️ Special Infected",
            value=(
                "**Smoker:** Tongue Range `750-825`\n"
                "**Hunter:** Godframes `1.2s`\n"
                "**Jockey:** Speed `275` / HP `350`\n"
                "**Boomer:** Horde `15-47`\n"
                "**Charger:** Godframes `1.8s`"
            ),
            inline=False
        )
        links = []
        if has_ceda:
            links.append(f"[CEDAPug]({cedapug_data.get('url')})")
        if has_center:
            links.append(f"[L4D2Center]({l4d2center_data.get('url')})")
        if links:
            embed.add_field(name="🔗 Perfiles competitivos", value=" • ".join(links), inline=False)
            
    elif page == "survivors":
        embed = discord.Embed(
            title=f"🏃 Supervivientes — {name}",
            url=profile_url,
            color=discord.Color.green()
        )
        embed.add_field(
            name="🛡️ Rendimiento Superviviente",
            value=(
                f"**Horas totales:** `{l4d2_hours:,} hrs`\n"
                f"**Estado:** {ban_badge}\n"
                "**Armas:** Tier 1 & Tier 2 competitivas\n"
                "**Config:** ZoneMod / CedaMod"
            ),
            inline=False
        )
        links = []
        if has_ceda:
            links.append(f"[CEDAPug]({cedapug_data.get('url')})")
        if has_center:
            links.append(f"[L4D2Center]({l4d2center_data.get('url')})")
        if links:
            embed.add_field(name="🔗 Perfiles competitivos", value=" • ".join(links), inline=False)
            
    else:  # overview
        embed = discord.Embed(
            title=f"📊 Estadísticas L4D2 — {name}",
            url=profile_url,
            color=color
        )
        if avatar:
            embed.set_thumbnail(url=avatar)
            
        embed.add_field(
            name="🎮 Steam Overview",
            value=(
                f"**SteamID64:** `{steam64}`\n"
                f"**Horas L4D2:** `{l4d2_hours:,} hrs`\n"
                f"**Estado:** {ban_badge}\n"
                f"**Formato detectado:** `{input_type}`"
            ),
            inline=False
        )
        
        # Solo mostrar CEDAPug si el perfil realmente existe
        if has_ceda:
            ceda_url = cedapug_data.get("url", "https://cedapug.com")
            rating = cedapug_data.get("rating", "Activo")
            tier = cedapug_data.get("tier", "Sin rango")
            trust = cedapug_data.get("trust_factor", "N/A")
            rounds = cedapug_data.get("rounds", 0)
            ceda_lines = [f"**Rating:** `{rating}`", f"**Tier:** `{tier}`", f"**Trust Factor:** `{trust}`"]
            if rounds:
                ceda_lines.append(f"**Rondas:** `{rounds}`")
            ceda_lines.append(f"[Stats]({ceda_url}) • [Ratings]({cedapug_data.get('ratings_url', 'https://cedapug.com/ratings')})")
            embed.add_field(name="⚔️ CEDAPug", value="\n".join(ceda_lines), inline=True)
            
        # Solo mostrar L4D2Center si el perfil realmente existe
        if has_center:
            center_url = l4d2center_data.get("url", "https://l4d2center.com/players/")
            tier = l4d2center_data.get("rank_tier", "Sin rango")
            rating = l4d2center_data.get("rating", "En calibración")
            center_lines = [f"**Rango:** `{tier}`", f"**MMR:** `{rating}`"]
            casual = l4d2center_data.get("casual_mmr", 0)
            if casual:
                center_lines.append(f"**MMR casual:** `{casual}`")
            sub = l4d2center_data.get("subscription")
            if sub:
                center_lines.append(f"**Suscripción:** `{sub}`")
            estado = []
            if l4d2center_data.get("in_game"):
                estado.append("En partida")
            elif l4d2center_data.get("in_queue"):
                estado.append("En cola")
            elif l4d2center_data.get("online"):
                estado.append("En línea")
            if l4d2center_data.get("banned"):
                estado.append("⛔ Baneado")
            if estado:
                center_lines.append(f"**Estado:** `{' • '.join(estado)}`")
            center_lines.append(f"[Ver en L4D2Center]({center_url})")
            embed.add_field(name="🏆 L4D2Center", value="\n".join(center_lines), inline=True)
        elif l4d2center_data.get("blocked"):
            embed.add_field(
                name="🏆 L4D2Center",
                value=f"*L4D2Center bloqueó la consulta automática (Cloudflare).*\n[Buscar `{steam64}` manualmente](https://l4d2center.com/players/)",
                inline=True
            )

            
        # Si no está en ninguno, mostrar aviso limpio
        if not has_ceda and not has_center:
            embed.add_field(
                name="🎮 Perfil Competitivo",
                value="*Sin perfil registrado en CEDAPug ni L4D2Center*",
                inline=False
            )
    
    embed.set_footer(text="L4D2 Stats Hub Bot • Búsqueda por SteamID, Vanity o URL")
    return embed

def create_compare_embed(p1: dict, p2: dict) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Comparación de Jugadores L4D2",
        color=discord.Color.gold()
    )
    for i, player in enumerate([p1, p2], 1):
        steam = player["steam"]
        name = steam.get("persona_name", f"Jugador {i}")
        hours = steam.get("l4d2_hours", 0)
        ban = "🔴 VAC" if steam.get("vac_banned") else "🟢 Limpio"
        links = [f"[Steam]({steam['profile_url']})"]
        if player["ceda"].get("found"):
            links.append(f"[CEDAPug]({player['ceda']['url']})")
        if player["center"].get("found"):
            links.append(f"[Center]({player['center']['url']})")
            
        embed.add_field(
            name=f"👤 {name}",
            value=(
                f"**Horas:** `{hours:,} hrs`\n"
                f"**Estado:** {ban}\n" +
                " • ".join(links)
            ),
            inline=True
        )
    return embed

def create_leaderboard_embed(entries: list, metric: str) -> discord.Embed:
    titles = {
        "hours": ("⏰ Más Horas en L4D2", "Horas"),
        "rating": ("🏆 Mejor Rating en L4D2Center", "Rating"),
        "matches": ("🎮 Más Partidas Jugadas", "Partidas")
    }
    title, metric_label = titles.get(metric, titles["hours"])
    
    embed = discord.Embed(title=title, color=discord.Color.gold())
    
    if not entries:
        embed.description = "No hay jugadores registrados todavía. Usa `/stats` o `!stats` para empezar."
    else:
        lines = []
        for idx, entry in enumerate(entries, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"**{idx}.**")
            value = entry.get("hours", 0) if metric == "hours" else entry.get("center_rating", 1000) if metric == "rating" else entry.get("center_matches", 0)
            lines.append(f"{medal} **{entry.get('name', 'Desconocido')}** — `{value:,}` {metric_label}")
        embed.description = "\n".join(lines)
    
    embed.set_footer(text="L4D2 Stats Hub Bot • Leaderboard del servidor")
    return embed
