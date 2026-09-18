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
    
    if page == "infected":
        embed = discord.Embed(
            title=f"🧟 Infectados — {name}",
            url=profile_url,
            color=discord.Color.purple()
        )
        embed.description = (
            "Estadísticas detalladas de Special Infected extraídas de CEDAPug y L4D2Center.\n"
            "*(Algunas métricas requieren consulta directa en las plataformas).*"
        )
        ceda_url = cedapug_data.get("url", "https://cedapug.com")
        center_url = l4d2center_data.get("url", "https://l4d2center.com")
        embed.add_field(
            name="☠️ Special Infected",
            value=(
                f"**Smoker:** Tongue Range `750-825`\n"
                f"**Hunter:** Godframes `1.2s`\n"
                f"**Jockey:** Speed `275` / HP `350`\n"
                f"**Boomer:** Horde `15-47`\n"
                f"**Charger:** Godframes `1.8s`"
            ),
            inline=False
        )
        embed.add_field(
            name="🔗 Enlaces directos",
            value=f"[CEDAPug]({ceda_url}) • [L4D2Center]({center_url})",
            inline=False
        )
    elif page == "survivors":
        embed = discord.Embed(
            title=f"🏃 Supervivientes — {name}",
            url=profile_url,
            color=discord.Color.green()
        )
        ceda_url = cedapug_data.get("url", "https://cedapug.com")
        center_url = l4d2center_data.get("url", "https://l4d2center.com")
        embed.add_field(
            name="🛡️ Rendimiento como Superviviente",
            value=(
                f"**Horas totales L4D2:** `{l4d2_hours:,}`\n"
                f"**Estado VAC:** {ban_badge}\n"
                f"**Config:** CedaMod (basado en ZoneMod)"
            ),
            inline=False
        )
        embed.add_field(
            name="🔗 Enlaces directos",
            value=f"[CEDAPug]({ceda_url}) • [L4D2Center]({center_url})",
            inline=False
        )
    else:  # overview
        embed = discord.Embed(
            title=f"📊 Estadísticas L4D2 — {name}",
            url=profile_url,
            color=color
        )
        if avatar:
            embed.set_thumbnail(url=avatar)
        ceda_url = cedapug_data.get("url", "https://cedapug.com")
        center_url = l4d2center_data.get("url", "https://l4d2center.com")
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
        embed.add_field(
            name="⚔️ CEDAPug",
            value=f"**Estado:** [Ver Perfil en CEDAPug]({ceda_url})",
            inline=True
        )
        embed.add_field(
            name="🏆 L4D2Center",
            value=f"**Estado:** [Ver Perfil en Center]({center_url})",
            inline=True
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
        embed.add_field(
            name=f"👤 {name}",
            value=(
                f"**Horas:** `{hours} hrs`\n"
                f"**Estado:** {ban}\n"
                f"[Steam]({steam['profile_url']}) • [CEDAPug]({player['ceda']['url']}) • [Center]({player['center']['url']})"
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
        embed.description = "No hay jugadores registrados en la base de datos todavía. Usa `/stats` para empezar a rastrear."
    else:
        lines = []
        for idx, entry in enumerate(entries, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"**{idx}.**")
            value = entry.get("l4d2_hours", 0) if metric == "hours" else entry.get("center_rating", 1000) if metric == "rating" else entry.get("center_matches", 0)
            lines.append(f"{medal} **{entry.get('persona_name', 'Desconocido')}** — `{value}` {metric_label}")
        embed.description = "\n".join(lines)
    
    embed.set_footer(text="L4D2 Stats Hub Bot • Leaderboard del servidor")
    return embed
