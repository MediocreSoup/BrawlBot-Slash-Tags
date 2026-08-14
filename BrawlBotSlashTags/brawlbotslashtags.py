import json
import re
from datetime import datetime, timezone
from pathlib import Path

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
        self.config.register_global(tags={}, text_commands_enabled=True)

        self.manage = app_commands.Group(
            name="managetags",
            description="Manage saved tags",
            guild_only=True
        )

        self.manage.add_command(self._build_add_category())
        self.manage.add_command(self._build_add_tag())
        self.manage.add_command(self._build_edit_tag())
        self.manage.add_command(self._build_delete_tag())
        self.manage.add_command(self._build_rename_tag())
        self.manage.add_command(self._build_rename_category())
        self.manage.add_command(self._build_move_tag())
        self.manage.add_command(self._build_list_tags())
        self.manage.add_command(self._build_set_tag_embed())
        self.manage.add_command(self._build_toggle_text_commands())
        self.manage.add_command(self._build_import_json())

    def _can_manage_tags(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        if not isinstance(interaction.user, discord.Member):
            return False
        return interaction.user.get_role(ADMIN_ROLE_ID) is not None

    async def _load_tags(self):
        return await self.config.tags()

    def _backup_tags(self, data):
        backup_dir = Path(__file__).resolve().parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        backup_path = backup_dir / f"tags_backup_{timestamp}.json"
        backup_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return backup_path

    async def _save_tags(self, data):
        await self.config.tags.set(data)
        self._backup_tags(data)

    def _normalize_tag_value(self, value):
        if isinstance(value, dict):
            if "value" in value:
                return value.get("value"), bool(value.get("embed", True))
            if "content" in value:
                return value.get("content"), bool(value.get("embed", True))
            if "text" in value:
                return value.get("text"), bool(value.get("embed", True))

        return value, True

    def _build_text_tag_command(self, tag_name: str):
        async def _callback(ctx):
            data = await self._load_tags()
            for category_data in data.values():
                if tag_name in category_data:
                    value = category_data[tag_name]
                    break
            else:
                await ctx.send(f"`{tag_name}` doesnt exist.")
                return

            value, should_embed = self._normalize_tag_value(value)
            if not should_embed:
                await ctx.send(str(value))
                return

            embed = await self._build_tag_embed(value, ctx)
            if embed.color is None:
                embed.color = await self.bot.get_embed_color(ctx.channel)
            await ctx.send(embed=embed)

        return commands.Command(
            _callback,
            name=tag_name,
            help=f"Display the `{tag_name}` tag.",
        )

    async def _sync_text_tag_commands(self):
        existing = getattr(self, "_text_tag_commands", [])
        for command in existing:
            if self.bot.get_command(command.name) is command:
                self.bot.remove_command(command.name)

        self._text_tag_commands = []

        if not await self.config.text_commands_enabled():
            return

        data = await self._load_tags()
        seen = set()
        registered = []

        for category_data in data.values():
            for tag_name in category_data.keys():
                if tag_name in seen:
                    continue
                seen.add(tag_name)

                existing_command = self.bot.get_command(tag_name)
                if existing_command is not None and getattr(existing_command, "cog", None) is not self:
                    continue
                if existing_command is not None and getattr(existing_command, "cog", None) is self:
                    self.bot.remove_command(tag_name)

                command = self._build_text_tag_command(tag_name)
                self.bot.add_command(command)
                registered.append(command)

        self._text_tag_commands = registered

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
        return embed

    def _build_add_category(self):
        @app_commands.command(name="add_category", description="Create a new tag category")
        @app_commands.describe(category="The category name to create")
        @app_commands.autocomplete(category=category_autocomplete)
        async def add_category(interaction: discord.Interaction, category: str):
            if not self._can_manage_tags(interaction):
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
        @app_commands.describe(category="The category to save into", tag="The tag name", value="A Discord message link or raw text", embed="Whether this tag should display in an embed")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def add_tag(interaction: discord.Interaction, category: str, tag: str, value: str, embed: bool = True):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data:
                data[category] = {}

            resolved_value = await self._resolve_message_link(value)
            stored_value = resolved_value if embed else {"value": resolved_value, "embed": False}
            data[category][tag] = stored_value
            await self._save_tags(data)
            await interaction.response.send_message(f"Saved `{tag}` under `{category}` with embed={'on' if embed else 'off'}.", ephemeral=True)

        return add_tag

    def _build_edit_tag(self):
        @app_commands.command(name="edit_tag", description="Edit an existing tag")
        @app_commands.describe(category="The tag category", tag="The tag name", value="The new value", embed="Whether this tag should display in an embed")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def edit_tag(interaction: discord.Interaction, category: str, tag: str, value: str, embed: bool = True):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            resolved_value = await self._resolve_message_link(value)
            data[category][tag] = resolved_value if embed else {"value": resolved_value, "embed": False}
            await self._save_tags(data)
            await interaction.response.send_message(f"Updated `{tag}` in `{category}` with embed={'on' if embed else 'off'}.", ephemeral=True)

        return edit_tag

    def _build_delete_tag(self):
        @app_commands.command(name="delete_tag", description="Delete a tag")
        @app_commands.describe(category="The category to remove from", tag="The tag name")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def delete_tag(interaction: discord.Interaction, category: str, tag: str):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            del data[category][tag]
            if not data[category]:
                del data[category]
            await self._save_tags(data)
            await interaction.response.send_message(f"Deleted `{tag}` from `{category}`.", ephemeral=True)

        return delete_tag

    def _build_rename_tag(self):
        @app_commands.command(name="rename_tag", description="Rename an existing tag")
        @app_commands.describe(category="The category the tag is in", tag="The current tag name", new_tag="The new tag name")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def rename_tag(interaction: discord.Interaction, category: str, tag: str, new_tag: str):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            if new_tag in data[category]:
                await interaction.response.send_message(f"A tag named `{new_tag}` already exists in `{category}`.", ephemeral=True)
                return

            value = data[category].pop(tag)
            data[category][new_tag] = value
            await self._save_tags(data)
            await interaction.response.send_message(f"Renamed `{tag}` to `{new_tag}` in `{category}`.", ephemeral=True)

        return rename_tag

    def _build_rename_category(self):
        @app_commands.command(name="rename_category", description="Rename a tag category")
        @app_commands.describe(category="The current category name", new_category="The new category name")
        @app_commands.autocomplete(category=category_autocomplete)
        async def rename_category(interaction: discord.Interaction, category: str, new_category: str):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data:
                await interaction.response.send_message(f"Category `{category}` does not exist.", ephemeral=True)
                return

            if new_category in data:
                await interaction.response.send_message(f"Category `{new_category}` already exists.", ephemeral=True)
                return

            data[new_category] = data.pop(category)
            await self._save_tags(data)
            await interaction.response.send_message(f"Renamed category `{category}` to `{new_category}`.", ephemeral=True)

        return rename_category

    def _build_move_tag(self):
        @app_commands.command(name="move_tag", description="Move a tag into a different category")
        @app_commands.describe(category="The current category", tag="The tag name", new_category="The destination category")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def move_tag(interaction: discord.Interaction, category: str, tag: str, new_category: str):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            if new_category == category:
                await interaction.response.send_message("The destination category is the same as the current category.", ephemeral=True)
                return

            data.setdefault(new_category, {})
            if tag in data[new_category]:
                await interaction.response.send_message(f"A tag named `{tag}` already exists in `{new_category}`.", ephemeral=True)
                return

            value = data[category].pop(tag)
            data[new_category][tag] = value
            if not data[category]:
                del data[category]
            await self._save_tags(data)
            await interaction.response.send_message(f"Moved `{tag}` from `{category}` to `{new_category}`.", ephemeral=True)

        return move_tag

    def _build_list_tags(self):
        @app_commands.command(name="list", description="List tags in a category")
        @app_commands.describe(category="The category to list")
        @app_commands.autocomplete(category=category_autocomplete)
        async def list_tags(interaction: discord.Interaction, category: str):
            if not self._can_manage_tags(interaction):
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

    def _build_set_tag_embed(self):
        @app_commands.command(name="set_tag_embed", description="Set whether an existing tag should display in an embed")
        @app_commands.describe(category="The tag category", tag="The tag name", embed="Whether this tag should display in an embed")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def set_tag_embed(interaction: discord.Interaction, category: str, tag: str, embed: bool):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags()
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            value, _ = self._normalize_tag_value(data[category][tag])
            data[category][tag] = value if embed else {"value": value, "embed": False}
            await self._save_tags(data)
            await interaction.response.send_message(
                f"`{tag}` in `{category}` now {'uses an embed' if embed else 'sends as plain text'}.",
                ephemeral=True,
            )

        return set_tag_embed

    def _build_toggle_text_commands(self):
        @app_commands.command(name="toggle_text_commands", description="Enable or disable dynamic text tag commands")
        @app_commands.describe(enabled="Whether text tag commands should be enabled")
        async def toggle_text_commands(interaction: discord.Interaction, enabled: bool):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            await self.config.text_commands_enabled.set(enabled)
            await self._sync_text_tag_commands()
            await interaction.response.send_message(
                f"Text tag commands are now {'enabled' if enabled else 'disabled'}.",
                ephemeral=True,
            )

        return toggle_text_commands

    def _build_import_json(self):
        @app_commands.command(name="import_json", description="Import tags from a JSON object or attached JSON file")
        @app_commands.describe(json_data="A JSON object mapping category names to tag dictionaries", attachment="Optional JSON file to import")
        async def import_json(
            interaction: discord.Interaction,
            json_data: str = None,
            attachment: discord.Attachment = None,
        ):
            if not self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            if attachment is not None:
                try:
                    payload_text = (await attachment.read()).decode("utf-8")
                except UnicodeDecodeError:
                    await interaction.response.send_message("The attached JSON file is not valid UTF-8 text.", ephemeral=True)
                    return
            elif json_data is not None and json_data.strip():
                payload_text = json_data
            else:
                await interaction.response.send_message("Provide either a JSON string or upload a JSON file.", ephemeral=True)
                return

            try:
                payload = json.loads(payload_text)
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
                for tag_name, tag_value in tags.items():
                    if isinstance(tag_value, dict):
                        if "value" in tag_value or "content" in tag_value or "text" in tag_value:
                            merged[category][tag_name] = tag_value
                            continue
                    merged[category][tag_name] = tag_value

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

        value, should_embed = self._normalize_tag_value(value)
        if not should_embed:
            await interaction.response.send_message(str(value))
            return

        embed = await self._build_tag_embed(value, interaction)
        if embed.color is None:
            embed.color = await self.bot.get_embed_color(interaction.channel)
        await interaction.response.send_message(embed=embed)

    async def cog_load(self):
        await self._sync_text_tag_commands()
        self.bot.tree.add_command(self.manage)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.manage.name)
        for command in getattr(self, "_text_tag_commands", []):
            self.bot.remove_command(command.name)
        self._text_tag_commands = []
