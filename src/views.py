import discord

class StatsView(discord.ui.View):
    """Vista interactiva con botones para alternar entre secciones de estadísticas."""
    
    def __init__(self, player_bundle: dict, author_id: int, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.player_bundle = player_bundle
        self.author_id = author_id
        self.current_page = "overview"
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Solo el autor puede controlar los botones (pero cualquiera puede leer el embed)
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("⏳ Solo quien invocó el comando puede usar estos botones.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Resumen", emoji="📋", style=discord.ButtonStyle.primary)
    async def overview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "overview"
        await self._update(interaction)

    @discord.ui.button(label="Infectados", emoji="🧟", style=discord.ButtonStyle.danger)
    async def infected_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "infected"
        await self._update(interaction)

    @discord.ui.button(label="Supervivientes", emoji="🏃", style=discord.ButtonStyle.success)
    async def survivors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "survivors"
        await self._update(interaction)

    @discord.ui.button(label="Actualizar", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self._update(interaction, force_refresh=True)

    async def _update(self, interaction: discord.Interaction, force_refresh: bool = False):
        embed = create_stats_embed(
            self.player_bundle["steam"],
            self.player_bundle["ceda"],
            self.player_bundle["center"],
            self.player_bundle["input_type"],
            page=self.current_page
        )
        await interaction.response.edit_message(embed=embed, view=self)
        if force_refresh:
            await interaction.followup.send("✅ Datos actualizados.", ephemeral=True)
