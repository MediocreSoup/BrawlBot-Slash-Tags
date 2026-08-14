import json
import re

import discord
from redbot.core import commands, app_commands
from redbot.core.config import Config

# all tags are wrapped inside embeds

ADMIN_ROLE_ID = 1200986093286342846


async def category_autocomplete(interaction: discord.Interaction, current: str):
    cog = interaction.client.get_cog("SlashTags")
    if cog is None:
        return []

    data = await cog._load_tags()
    categories = [name for name in data.keys() if current.lower() in name.lower()]
    return [
        app_commands.Choice(name=name, value=name)
        for name in categories[:25]
    ]


async def tag_autocomplete(interaction: discord.Interaction, current: str):
    cog = interaction.client.get_cog("SlashTags")
    if cog is None:
        return []

    data = await cog._load_tags()
    namespace = getattr(interaction, "namespace", {}) or {}
    category = namespace.get("category")

    if category:
        tags = list(data.get(category, {}).keys())
    else:
        tags = [tag for tags_by_cat in data.values() for tag in tags_by_cat.keys()]

    filtered = [tag for tag in tags if current.lower() in tag.lower()]
    return [
        app_commands.Choice(name=tag, value=tag)
        for tag in filtered[:25]
    ]


class SlashTags(commands.Cog):
    """Slash-command tag lookup with persistent storage."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=881728942000123456)
        self.config.register_global(tags={})

        self.manage = app_commands.Group(
            name="managetags",
            description="Manage saved tags"
        )

        self.manage.add_command(self._build_add_category())
        self.manage.add_command(self._build_add_tag())
        self.manage.add_command(self._build_delete_tag())
        self.manage.add_command(self._build_list_tags())
        self.manage.add_command(self._build_import_json())

    async def _load_tags(self):
        return await self.config.tags()

    async def _save_tags(self, data):
        await self.config.tags.set(data)

    async def _resolve_message_link(self, value: str) -> str:
        value = value.strip()
        if not value:
            return value

        regex = r"https?://(?:canary\.|ptb\.|)discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)"
        match = re.search(regex, value)
        if not match:
            return value

        guild_id, channel_id, message_id = (int(part) for part in match.groups())

        guild = self.bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id) if guild else self.bot.get_channel(channel_id)
        if channel is None:
            return value

        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return value

        if message.content:
            return message.content
        if message.embeds:
            embed = message.embeds[0]
            return embed.description or embed.title or str(embed)
        return value

    async def _build_tag_embed(self, value, interaction=None):
        if isinstance(value, discord.Embed):
            return value

        text = str(value).strip()
        if not text:
            return discord.Embed(description=" ", color=0x5865F2)

        channel = interaction.channel if interaction is not None and interaction.channel is not None else None
        color = await self.bot.get_embed_color(channel) if channel is not None else 0x5865F2
        embed = discord.Embed(description=text, color=color)

        image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp")
        if text.startswith("http") and text.lower().endswith(image_extensions):
            embed.set_image(url=text)
            embed.description = " "

        return embed

    def _build_add_category(self):
        @app_commands.command(name="add_category", description="Create a new tag category")
        @app_commands.describe(category="The category name to create")
        @app_commands.autocomplete(category=category_autocomplete)
        async def add_category(interaction: discord.Interaction, category: str):
            if not interaction.user.get_role(ADMIN_ROLE_ID):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data:
                data[category] = {}
                await self._save_tags(data)
                await interaction.response.send_message(f"Created category `{category}`.", ephemeral=True)
                return
            await interaction.response.send_message(f"Category `{category}` already exists.", ephemeral=True)

        return add_category

    def _build_add_tag(self):
        @app_commands.command(name="add_tag", description="Add or update a tag")
        @app_commands.describe(category="The category to save into", tag="The tag name", value="A Discord message link or raw text")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def add_tag(interaction: discord.Interaction, category: str, tag: str, value: str):
            if not interaction.user.get_role(ADMIN_ROLE_ID):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data:
                data[category] = {}

            resolved_value = await self._resolve_message_link(value)
            data[category][tag] = resolved_value
            await self._save_tags(data)
            await interaction.response.send_message(f"Saved `{tag}` under `{category}`.", ephemeral=True)

        return add_tag

    def _build_delete_tag(self):
        @app_commands.command(name="delete_tag", description="Delete a tag")
        @app_commands.describe(category="The category to remove from", tag="The tag name")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def delete_tag(interaction: discord.Interaction, category: str, tag: str):
            if not interaction.user.get_role(ADMIN_ROLE_ID):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            del data[category][tag]
            await self._save_tags(data)
            await interaction.response.send_message(f"Deleted `{tag}` from `{category}`.", ephemeral=True)

        return delete_tag

    def _build_list_tags(self):
        @app_commands.command(name="list", description="List tags in a category")
        @app_commands.describe(category="The category to list")
        @app_commands.autocomplete(category=category_autocomplete)
        async def list_tags(interaction: discord.Interaction, category: str):
            if not interaction.user.get_role(ADMIN_ROLE_ID):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            tags = data.get(category, {})
            if not tags:
                await interaction.response.send_message(f"No tags found for `{category}`.", ephemeral=True)
                return

            names = ", ".join(f"`{name}`" for name in tags.keys())
            await interaction.response.send_message(f"Tags in `{category}`: {names}", ephemeral=True)

        return list_tags

    def _build_import_json(self):
        @app_commands.command(name="import_json", description="Import tags from a JSON object")
        @app_commands.describe(json_data="A JSON object mapping category names to tag dictionaries")
        async def import_json(interaction: discord.Interaction, json_data: str):
            if not interaction.user.get_role(ADMIN_ROLE_ID):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            try:
                payload = json.loads(json_data)
            except json.JSONDecodeError:
                await interaction.response.send_message("Invalid JSON payload.", ephemeral=True)
                return

            if not isinstance(payload, dict):
                await interaction.response.send_message("The JSON payload must be an object keyed by category name.", ephemeral=True)
                return

            merged = await self._load_tags()
            for category, tags in payload.items():
                if not isinstance(tags, dict):
                    await interaction.response.send_message(f"Category `{category}` is not a valid object of tags.", ephemeral=True)
                    return
                merged.setdefault(category, {})
                merged[category].update(tags)

            await self._save_tags(merged)
            await interaction.response.send_message("Imported tags from JSON.", ephemeral=True)

        return import_json

    @app_commands.command(name="tag")
    @app_commands.describe(category="The tag category", tag="The tag name")
    @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
    async def tag(self, interaction: discord.Interaction, category: str, tag: str):
        data = await self._load_tags()
        value = data.get(category, {}).get(tag)

        if value is None:
            await interaction.response.send_message(f"I couldn't find `{tag}` in `{category}`.", ephemeral=True)
            return

        embed = await self._build_tag_embed(value, interaction)
        if embed.color is None:
            embed.color = await self.bot.get_embed_color(interaction.channel)
        await interaction.response.send_message(embed=embed)

    async def cog_load(self):
        self.bot.tree.add_command(self.manage)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.manage.name)


async def setup(bot):
    await bot.add_cog(SlashTags(bot))
