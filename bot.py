import os
import re
import asyncio
import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from dotenv import load_dotenv

from src.steam import SteamResolver
from src.cedapug import CedapugTracker
from src.l4d2center import L4D2CenterTracker
from src.database import init_db, upsert_player, link_discord_user, get_linked_steam64, get_leaderboard
from src.embeds import create_stats_embed, create_compare_embed, create_leaderboard_embed
from src.views import StatsView

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
GUILD_ID = os.getenv("GUILD_ID")
PORT = os.getenv("PORT", "8080")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Servidor HTTP ligero para Health Check de Railway, Render, Koyeb, Fly.io, etc.
async def run_health_server():
    try:
        app = web.Application()
        async def health(request):
            status = "online" if client.is_ready() else "connecting"
            return web.json_response({
                "status": status,
                "bot": str(client.user) if client.user else None,
                "service": "l4d2-stats-discord-bot"
            })
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        
        port = int(PORT) if str(PORT).isdigit() else 8080
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"Healthcheck HTTP server escuchando en 0.0.0.0:{port}")
    except Exception as e:
        print(f"Aviso servidor de salud HTTP: {e}")

@client.event
async def setup_hook():
    init_db()
    # Iniciar servidor web de salud para plataformas de hosting
    asyncio.create_task(run_health_server())

@client.event
async def on_ready():
    print(f"✅ Bot conectado exitosamente como {client.user} (ID: {client.user.id})")
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            print(f"Slash commands sincronizados con el servidor {GUILD_ID}")
        else:
            await tree.sync()
            print("Slash commands sincronizados globalmente")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

# Manejador global de errores en Slash Commands para evitar caídas
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Error en comando '{interaction.command.name}': {error}")
    msg = "❌ Ocurrió un error inesperado al procesar el comando. Inténtalo de nuevo."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

async def resolve_all_player_stats(session: aiohttp.ClientSession, query: str):
    """Resuelve cualquier formato (ID, vanity, URL) y obtiene todos los datos."""
    steam64, input_type = await SteamResolver.resolve_to_steam64(session, STEAM_API_KEY, query)
    if not steam64:
        return None, input_type, None, None, None
        
    steam_data = await SteamResolver.get_player_summary(session, STEAM_API_KEY, steam64)
    cedapug_data = await CedapugTracker.get_player_stats(session, steam64)
    l4d2center_data = await L4D2CenterTracker.get_player_stats(session, steam64)
    
    upsert_player(
        steam64=steam_data.get("steam64", steam64),
        name=steam_data.get("persona_name", "Desconocido"),
        avatar=steam_data.get("avatar_url", ""),
        hours=steam_data.get("l4d2_hours", 0.0),
        vac_banned=steam_data.get("vac_banned", False),
        ceda_rating=str(cedapug_data.get("rating", "N/A")),
        center_rating=int(l4d2center_data.get("rating", 1000) if str(l4d2center_data.get("rating", "1000")).isdigit() else 1000),
        center_matches=int(l4d2center_data.get("matches", 0) or 0)
    )
    
    return steam_data, input_type, cedapug_data, l4d2center_data, steam64

@tree.command(
    name="stats",
    description="Consulta las estadísticas de un jugador por SteamID/URL o mencionando a un usuario"
)
@app_commands.describe(
    busqueda="SteamID, vanity, URL de perfil o mención de usuario",
    usuario="O selecciona directamente a un miembro de este servidor"
)
async def stats(
    interaction: discord.Interaction,
    busqueda: str = None,
    usuario: discord.Member = None
):
    await interaction.response.defer()
    
    if not STEAM_API_KEY:
        await interaction.followup.send("⚠️ La variable `STEAM_API_KEY` no está configurada en las variables de entorno del bot.", ephemeral=True)
        return

    target_query = busqueda
    
    if usuario:
        linked_steam64 = get_linked_steam64(usuario.id)
        if not linked_steam64:
            await interaction.followup.send(
                f"❌ El usuario {usuario.mention} no tiene ninguna cuenta de Steam vinculada todavía (usa `/link`).",
                ephemeral=True
            )
            return
        target_query = linked_steam64

    elif target_query:
        mention_match = re.match(r'^<@!?(\d+)>$', target_query.strip())
        if mention_match:
            user_id = mention_match.group(1)
            linked_steam64 = get_linked_steam64(user_id)
            if not linked_steam64:
                await interaction.followup.send(
                    f"❌ El usuario mencionado no tiene ninguna cuenta vinculada todavía.",
                    ephemeral=True
                )
                return
            target_query = linked_steam64

    elif not target_query and not usuario:
        linked_steam64 = get_linked_steam64(interaction.user.id)
        if not linked_steam64:
            await interaction.followup.send(
                "❌ No especificaste búsqueda ni tienes cuenta vinculada. Usa `/stats <steam_id>` o `/link` primero.",
                ephemeral=True
            )
            return
        target_query = linked_steam64

    async with aiohttp.ClientSession() as session:
        steam_data, input_type, ceda_data, center_data, _ = await resolve_all_player_stats(session, target_query)
        
        if not steam_data:
            await interaction.followup.send(
                f"❌ No se pudo encontrar ningún perfil con: `{target_query}`.\n"
                f"Verifica que el SteamID o perfil sea público y esté bien escrito.",
                ephemeral=True
            )
            return

        embed = create_stats_embed(steam_data, ceda_data, center_data, input_type)
        view = StatsView(
            player_bundle={"steam": steam_data, "ceda": ceda_data, "center": center_data, "input_type": input_type},
            author_id=interaction.user.id
        )
        await interaction.followup.send(embed=embed, view=view)

@tree.command(
    name="me",
    description="Muestra tus estadísticas de L4D2 si tienes tu cuenta vinculada con /link"
)
async def me(interaction: discord.Interaction):
    await interaction.response.defer()
    steam64 = get_linked_steam64(interaction.user.id)
    if not steam64:
        await interaction.followup.send(
            "❌ No tienes ninguna cuenta de Steam vinculada. Usa `/link <steam_id>` primero.",
            ephemeral=True
        )
        return
    
    async with aiohttp.ClientSession() as session:
        steam_data, input_type, ceda_data, center_data, _ = await resolve_all_player_stats(session, steam64)
        if not steam_data:
            await interaction.followup.send("❌ No se pudo recuperar el perfil vinculado.", ephemeral=True)
            return
        
        embed = create_stats_embed(steam_data, ceda_data, center_data, "vinculado")
        view = StatsView(
            player_bundle={"steam": steam_data, "ceda": ceda_data, "center": center_data, "input_type": "vinculado"},
            author_id=interaction.user.id
        )
        await interaction.followup.send(embed=embed, view=view)

@tree.command(
    name="link",
    description="Vincula tu cuenta de Steam a tu usuario de Discord para consultas rápidas"
)
@app_commands.describe(busqueda="SteamID, vanity o URL completa de tu perfil de Steam")
async def link(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer(ephemeral=True)
    
    if not STEAM_API_KEY:
        await interaction.followup.send("⚠️ La variable `STEAM_API_KEY` no está configurada en el bot.", ephemeral=True)
        return

    async with aiohttp.ClientSession() as session:
        steam64, input_type = await SteamResolver.resolve_to_steam64(session, STEAM_API_KEY, busqueda)
        if not steam64:
            await interaction.followup.send(f"❌ No se pudo resolver `{busqueda}` a un perfil de Steam válido.", ephemeral=True)
            return
        
        link_discord_user(interaction.user.id, steam64)
        await interaction.followup.send(f"✅ Tu cuenta de Discord ha sido vinculada a SteamID `{steam64}` ({input_type}).", ephemeral=True)

@tree.command(
    name="compare",
    description="Compara las estadísticas de dos jugadores de L4D2 frente a frente"
)
@app_commands.describe(
    jugador1="SteamID, vanity, URL o mención del primer jugador",
    jugador2="SteamID, vanity, URL o mención del segundo jugador"
)
async def compare(interaction: discord.Interaction, jugador1: str, jugador2: str):
    await interaction.response.defer()
    
    if not STEAM_API_KEY:
        await interaction.followup.send("⚠️ La variable `STEAM_API_KEY` no está configurada.", ephemeral=True)
        return

    def resolve_mention(q: str):
        m = re.match(r'^<@!?(\d+)>$', q.strip())
        if m:
            linked = get_linked_steam64(m.group(1))
            return linked or q
        return q

    q1 = resolve_mention(jugador1)
    q2 = resolve_mention(jugador2)

    async with aiohttp.ClientSession() as session:
        s1, t1, c1, cnt1, _ = await resolve_all_player_stats(session, q1)
        s2, t2, c2, cnt2, _ = await resolve_all_player_stats(session, q2)
        
        if not s1 or not s2:
            await interaction.followup.send("❌ No se pudo resolver uno o ambos jugadores especificados.", ephemeral=True)
            return
            
        p1 = {"steam": s1, "ceda": c1, "center": cnt1}
        p2 = {"steam": s2, "ceda": c2, "center": cnt2}
        
        embed = create_compare_embed(p1, p2)
        await interaction.followup.send(embed=embed)

@tree.command(
    name="leaderboard",
    description="Muestra la tabla de clasificación del servidor por horas, rating o partidas"
)
@app_commands.describe(metrica="Criterio de clasificación")
@app_commands.choices(metrica=[
    app_commands.Choice(name="⏰ Más horas en L4D2", value="hours"),
    app_commands.Choice(name="🏆 Mejor rating L4D2Center", value="rating"),
    app_commands.Choice(name="🎮 Más partidas", value="matches")
])
async def leaderboard(interaction: discord.Interaction, metrica: app_commands.Choice[str] = None):
    await interaction.response.defer()
    
    metric = metrica.value if metrica else "hours"
    entries = get_leaderboard(metric=metric, limit=10)
    embed = create_leaderboard_embed(entries, metric)
    await interaction.followup.send(embed=embed)

@tree.command(
    name="help",
    description="Muestra los comandos disponibles y formatos de búsqueda aceptados"
)
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 Bot Tracker de L4D2 — Comandos y Uso",
        description="Rastrea perfiles y estadísticas en **Steam**, **CEDAPug** y **L4D2Center**.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📌 Comandos",
        value=(
            "`/stats [búsqueda] [usuario]` — Consulta por SteamID, URL, mención `@usuario` o autocompletado.\n"
            "`/me` — Muestra tus propias estadísticas vinculadas.\n"
            "`/link <búsqueda>` — Vincula tu cuenta de Steam a Discord.\n"
            "`/compare <jugador1> <jugador2>` — Compara dos jugadores (acepta SteamID o mención).\n"
            "`/leaderboard [métrica]` — Tabla de clasificación del servidor.\n"
            "`/help` — Muestra este menú."
        ),
        inline=False
    )
    embed.add_field(
        name="🔍 Formatos de búsqueda aceptados",
        value=(
            "• **Mención de Discord:** `@usuario` (debe haber usado `/link`)\n"
            "• **SteamID clásico:** `STEAM_0:0:12345678`\n"
            "• **SteamID3:** `[U:1:24691356]` o `U:1:24691356`\n"
            "• **SteamID64:** `76561198000000000`\n"
            "• **Vanity Username:** `mi_usuario`\n"
            "• **URL de perfil:** `https://steamcommunity.com/profiles/7656119...`\n"
            "• **URL personalizada:** `https://steamcommunity.com/id/mi_usuario/`"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@tree.command(
    name="ayuda",
    description="Muestra los comandos disponibles y formatos de búsqueda aceptados"
)
async def ayuda_cmd(interaction: discord.Interaction):
    await help_cmd(interaction)


def get_help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎮 Bot Tracker de L4D2 — Comandos y Uso",
        description="Rastrea perfiles y estadísticas en **Steam**, **CEDAPug** y **L4D2Center**.\nFunciona con prefijo `!` y con comandos de barra `/`.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📋 Comandos disponibles",
        value=(
            "`!stats <id/url>` o `/stats` — Consulta Steam, CEDAPug y L4D2Center\n"
            "`!me` o `/me` — Muestra tus estadísticas vinculadas\n"
            "`!link <id/url>` o `/link` — Vincula tu Steam a tu Discord\n"
            "`!compare <p1> <p2>` o `/compare` — Comparativa directa\n"
            "`!leaderboard` o `/leaderboard` — Ranking del servidor\n"
            "`!ayuda` o `!help` o `/ayuda` — Muestra este menú"
        ),
        inline=False
    )
    embed.add_field(
        name="🔍 Formatos aceptados",
        value=(
            "• **Mención:** `@usuario` (debe haber usado `!link`)\n"
            "• **SteamID clásico:** `STEAM_0:0:12345678`\n"
            "• **SteamID3:** `[U:1:24691356]` o `U:1:24691356`\n"
            "• **SteamID64:** `76561198000000000`\n"
            "• **Vanity:** `mi_usuario`\n"
            "• **URL:** `https://steamcommunity.com/id/mi_usuario/`"
        ),
        inline=False
    )
    return embed

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_lower = message.content.strip().lower()

    if content_lower in ["!help", "!ayuda", "!comandos"]:
        await message.channel.send(embed=get_help_embed())
        return

    if content_lower == "!me":
        steam64 = get_linked_steam64(message.author.id)
        if not steam64:
            await message.reply("❌ No tienes cuenta de Steam vinculada. Usa `!link <steam_id>` primero.")
            return
        async with aiohttp.ClientSession() as session:
            s_data, i_type, c_data, cnt_data, _ = await resolve_all_player_stats(session, steam64)
            if not s_data:
                await message.reply("❌ No se pudo recuperar tu perfil vinculado.")
                return
            emb = create_stats_embed(s_data, c_data, cnt_data, "vinculado")
            v = StatsView(
                player_bundle={"steam": s_data, "ceda": c_data, "center": cnt_data, "input_type": "vinculado"},
                author_id=message.author.id
            )
            await message.channel.send(embed=emb, view=v)
        return

    if content_lower.startswith("!link "):
        query = message.content[6:].strip()
        if not STEAM_API_KEY:
            await message.reply("⚠️ STEAM_API_KEY no configurada.")
            return
        async with aiohttp.ClientSession() as session:
            steam64, input_type = await SteamResolver.resolve_to_steam64(session, STEAM_API_KEY, query)
            if not steam64:
                await message.reply(f"❌ No se pudo resolver `{query}` a un perfil válido.")
                return
            link_discord_user(message.author.id, steam64)
            await message.reply(f"✅ Vinculado a SteamID `{steam64}` ({input_type}).")
        return

    if content_lower.startswith("!stats"):
        query = message.content[6:].strip()
        if not query:
            linked = get_linked_steam64(message.author.id)
            if not linked:
                await message.reply("❌ Especifica una búsqueda: `!stats <steamid/url/@usuario>` o usa `!link`.")
                return
            query = linked

        m_match = re.match(r"^<@!?(\d+)>$", query)
        if m_match:
            linked_m = get_linked_steam64(m_match.group(1))
            if not linked_m:
                await message.reply("❌ El usuario mencionado no tiene cuenta vinculada.")
                return
            query = linked_m

        async with aiohttp.ClientSession() as session:
            s_data, i_type, c_data, cnt_data, _ = await resolve_all_player_stats(session, query)
            if not s_data:
                await message.reply(f"❌ No se encontró ningún perfil con `{query}`.")
                return
            emb = create_stats_embed(s_data, c_data, cnt_data, i_type)
            v = StatsView(
                player_bundle={"steam": s_data, "ceda": c_data, "center": cnt_data, "input_type": i_type},
                author_id=message.author.id
            )
            await message.channel.send(embed=emb, view=v)
        return

    if content_lower.startswith("!leaderboard") or content_lower.startswith("!top"):
        entries = get_leaderboard(metric="hours", limit=10)
        await message.channel.send(embed=create_leaderboard_embed(entries, "hours"))
        return

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("Error: Falta DISCORD_BOT_TOKEN en las variables de entorno (.env)")
    client.run(DISCORD_TOKEN)
