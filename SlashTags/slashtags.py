from __future__ import annotations

import asyncio
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
import typing

import discord
from redbot.core import commands, app_commands
from redbot.core.data_manager import cog_data_path
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import pagify

# Safe top-level interaction attributes that can be traversed with [interaction.*] syntax.
_INTERACTION_ALLOWLIST = {
    "user",
    "guild",
    "channel",
}
# Safe leaf attributes reachable from each of the above.
_INTERACTION_SAFE_ATTRS = {
    "name", "id", "display_name", "mention",
    "nick", "global_name",
}

async def category_autocomplete(interaction: discord.Interaction, current: str):
    cog = interaction.client.get_cog("SlashTags")
    if cog is None:
        return []

    data = await cog._load_tags(interaction.guild)
    current = current.lower()

    categories = [
        name for name in data
        if current in name
    ]

    return [
        app_commands.Choice(name=name[:100], value=name)
        for name in categories[:25]
    ]

async def tag_autocomplete(interaction: discord.Interaction, current: str):
    cog = interaction.client.get_cog("SlashTags")
    if cog is None:
        return []

    data = await cog._load_tags(interaction.guild)
    namespace = getattr(interaction, "namespace", None)
    category = getattr(namespace, "category", None)

    if category:
        tags = list(data.get(category, {}).keys())
    else:
        tags = [
            tag
            for tags_by_cat in data.values()
            for tag in tags_by_cat.keys()
        ]

    current = current.lower()
    filtered = [tag for tag in tags if current in tag]

    return [
        app_commands.Choice(name=tag, value=tag)
        for tag in filtered[:25]
    ]



class SlashTags(commands.Cog):
    """Slash-command tag lookup with persistent storage, scoped per guild."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=881728942000123456)
        self.config.register_guild(tags={}, text_commands_enabled=True)
        #self._text_tag_commands: typing.Dict[int, list] = {}

        self.manage = app_commands.Group(
            name="managetags",
            description="Manage saved tags",
            guild_only=True
        )

        self.manage.add_command(self._build_add_category())
        self.manage.add_command(self._build_add_tag())
        self.manage.add_command(self._build_edit_tag())
        self.manage.add_command(self._build_delete_tag())
        self.manage.add_command(self._build_delete_category())
        self.manage.add_command(self._build_rename_tag())
        self.manage.add_command(self._build_rename_category())
        self.manage.add_command(self._build_move_tag())
        self.manage.add_command(self._build_list_tags())
        self.manage.add_command(self._build_preview_embed())
        self.manage.add_command(self._build_set_tag_embed())
        self.manage.add_command(self._build_toggle_text_commands())
        self.manage.add_command(self._build_import_json())
    
    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if message.guild is None:
            return

        if isinstance(message.channel, discord.PartialMessageable):
            return

        if message.author.bot:
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        if not await self.config.guild(message.guild).text_commands_enabled():
            return

        ctx = await self.bot.get_context(message)

        if ctx.prefix is None:
            return

        # A real bot command always wins over a tag.
        if ctx.command is not None:
            return

        tag_name = (ctx.invoked_with or "").lower()
        if not tag_name:
            return

        data = await self._load_tags(message.guild)

        value = None

        for category_data in data.values():
            if tag_name in category_data:
                value = category_data[tag_name]
                break

        if value is None:
            return

        value, should_embed = self._normalize_tag_value(value)

        # Everything after the invoked tag name.
        arguments_text = ctx.view.read_rest().strip()
        parsed_arguments = self._split_tag_arguments(arguments_text)

        valid, warning = self._validate_tag_arguments(
            value,
            parsed_arguments,
            allow_interaction=False,
        )

        if not valid:
            await ctx.send(warning)
            return

        resolved_arguments = dict(
            zip(
                self._extract_tag_argument_names(value),
                parsed_arguments,
            )
        )

        rendered = self._resolve_tag_string(
            value,
            resolved_arguments,
            None,
        )

        if not should_embed:
            await self._send_text_pages(ctx, rendered)
            return

        embeds = await self._build_tag_embeds(rendered, ctx)

        for embed in embeds:
            if embed.color is None:
                embed.color = await self.bot.get_embed_color(ctx.channel)

            await ctx.send(embed=embed)
            
            
    async def _send_text_pages(self, destination, value, *, ephemeral=False):
        pages = pagify(str(value))

        if isinstance(destination, commands.Context):
            for page in pages:
                await destination.send(page)
            return

        for index, page in enumerate(pages):
            if index == 0 and not destination.response.is_done():
                await destination.response.send_message(
                    page,
                    ephemeral=ephemeral,
                )
            else:
                await destination.followup.send(
                    page,
                    ephemeral=ephemeral,
                )

    # ---------------------------------------------------------------------------
    # Permission guard
    # ---------------------------------------------------------------------------

    async def _can_manage_tags(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        if not isinstance(interaction.user, discord.Member):
            return False
        if await self.bot.is_owner(interaction.user):
            return True
        if await self.bot.is_admin(interaction.user):
            return True
        return interaction.user.guild_permissions.administrator

    # ---------------------------------------------------------------------------
    # Config helpers — all tag access is scoped to the guild
    # ---------------------------------------------------------------------------

    async def _load_tags(self, guild: typing.Optional[discord.Guild]):
        if guild is None:
            return {}
        return await self.config.guild(guild).tags()
    
    async def _save_tags(self, guild: discord.Guild, data: dict):
        await self.config.guild(guild).tags.set(data)
        await self._backup_tags(guild, data)

    # ---------------------------------------------------------------------------
    # Backups — stored in Redbot's data directory, not the cog installation dir
    # ---------------------------------------------------------------------------

    async def _backup_tags(self, guild: discord.Guild, data: dict):
        await asyncio.to_thread(
            self._backup_tags_sync,
            guild.id,
            data,
        )


    def _backup_tags_sync(self, guild_id: int, data: dict):
        backup_dir = cog_data_path(self) / "backups" / str(guild_id)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H-%M-%S-%fZ"
        )

        backup_path = backup_dir / f"tags_backup_{timestamp}.json"

        backup_path.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        backups = sorted(
            backup_dir.glob("tags_backup_*.json")
        )

        for old in backups[:-20]:
            try:
                old.unlink()
            except OSError:
                pass

    # ---------------------------------------------------------------------------
    # Text tag command sync — called automatically after every save
    # ---------------------------------------------------------------------------

    def _normalize_tag_value(self, value):
        if isinstance(value, dict):
            if "value" in value:
                return value.get("value"), bool(value.get("embed", True))
            if "content" in value:
                return value.get("content"), bool(value.get("embed", True))
            if "text" in value:
                return value.get("text"), bool(value.get("embed", True))

        return value, True

    async def _send_tag_embeds(self, interaction, value, channel=None):
        embeds = await self._build_tag_embeds(value, interaction)
        for index, embed in enumerate(embeds):
            if embed.color is None:
                embed.color = await self.bot.get_embed_color(channel or interaction.channel)
            if index == 0:
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.followup.send(embed=embed)

    def _normalize_name(self, value, field_name):
        cleaned = str(value or "").strip().lower()

        if not cleaned:
            raise ValueError(f"{field_name} cannot be empty.")

        if len(cleaned) > 100:
            raise ValueError(f"{field_name} cannot be longer than 100 characters.")

        return cleaned

    async def _resolve_message_link(self, value: str):
        value = value.strip()

        if not value:
            return value, False

        regex = (
            r"https?://(?:canary\.|ptb\.)?"
            r"discord(?:app)?\.com/channels/"
            r"(\d+)/(\d+)/(\d+)"
        )

        match = re.fullmatch(regex, value)

        if not match:
            return value, False

        guild_id, channel_id, message_id = (
            int(part)
            for part in match.groups()
        )

        guild = self.bot.get_guild(guild_id)

        channel = (
            guild.get_channel(channel_id)
            if guild is not None
            else self.bot.get_channel(channel_id)
        )

        # Try the API if the channel is not cached.
        if channel is None:
            try:
                fetched_channel = await self.bot.fetch_channel(channel_id)
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                return value, False

            channel = fetched_channel

        # Don't allow a link from another guild to accidentally resolve
        # through a cached channel.
        if guild is not None:
            channel_guild = getattr(channel, "guild", None)

            if (
                channel_guild is None
                or channel_guild.id != guild_id
            ):
                return value, False

        try:
            message = await channel.fetch_message(message_id)
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            return value, False

        # Normal text takes priority.
        if message.content:
            return message.content, False

        # Attachment-only image:
        # store the raw image URL. If embed=False, Discord will render it
        # as an image when the tag is sent as ordinary text.
        for attachment in message.attachments:
            content_type = attachment.content_type or ""

            if content_type.startswith("image/"):
                return attachment.url, False

        # An embed-only Discord message still isn't representable as a
        # plain tag string.
        if message.embeds:
            return None, True

        return value, False

    def _chunk_embed_text(self, text: str, max_chars: int = 4000):
        text = text.strip()
        if not text:
            return [""]
        if len(text) <= max_chars:
            return [text]

        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= max_chars:
                chunks.append(remaining)
                break

            split_at = max_chars
            newline_idx = remaining.rfind("\n", 0, max_chars)
            if newline_idx > 0:
                split_at = newline_idx
            else:
                space_idx = remaining.rfind(" ", 0, max_chars)
                if space_idx > 0:
                    split_at = space_idx

            chunk = remaining[:split_at].rstrip()
            if not chunk:
                chunk = remaining[:max_chars].rstrip()
            if not chunk:
                break

            chunks.append(chunk)
            remaining = remaining[split_at:].lstrip()

        return chunks
    
    def _get_tag_category(self, data: dict, tag_name: str):
        for category, category_tags in data.items():
            if tag_name in category_tags:
                return category

        return None
        
    def _has_duplicate_tag_name(
        self,
        data: dict,
        tag_name: str,
        *,
        exclude_category: str | None = None,
    ) -> bool:
        for category, category_tags in data.items():
            if category == exclude_category:
                continue

            if tag_name in category_tags:
                return True

        return False

    def _extract_tag_argument_names(self, value):
        if value is None:
            return []

        text = str(value)
        names = []
        seen_names = set()
        index = 0
        while index < len(text):
            if text[index] == "\\":
                if index + 1 < len(text) and text[index + 1] in {"{", "[", "\\"}:
                    index += 2
                    continue
                index += 1
                continue

            if text[index] == "{":
                end = text.find("}", index + 1)
                if end == -1:
                    break

                name = text[index + 1:end].strip()
                if name and re.fullmatch(r"[A-Za-z0-9_-]+", name) and name not in seen_names:
                    names.append(name)
                    seen_names.add(name)
                index = end + 1
                continue

            index += 1

        return names

    def _split_tag_arguments(self, arguments_text):
        if arguments_text is None:
            return []

        arguments_text = str(arguments_text).strip()
        if not arguments_text:
            return []

        try:
            return shlex.split(arguments_text)
        except ValueError:
            return arguments_text.split()

    def _resolve_interaction_reference(self, interaction, expression):
        """Safely resolve whitelisted [interaction.x.y] references.

        Only top-level attributes in _INTERACTION_ALLOWLIST are traversed from
        the interaction object, and only leaf attributes in _INTERACTION_SAFE_ATTRS
        are returned. This prevents leaking bot internals such as
        interaction.client.http.token.
        """
        if interaction is None or not isinstance(expression, str):
            return None

        expression = expression.strip()
        if not expression:
            return None

        if not expression.startswith("interaction."):
            return None

        parts = expression.split(".")
        # parts[0] == "interaction", parts[1] == top-level attr, parts[2] == leaf
        if len(parts) < 2 or len(parts) > 3:
            return None

        top_attr = parts[1]
        if top_attr not in _INTERACTION_ALLOWLIST:
            return None

        target = getattr(interaction, top_attr, None)
        if target is None:
            return None

        if len(parts) == 2:
            # Direct attribute on interaction itself (e.g. [interaction.guild])
            if top_attr in _INTERACTION_SAFE_ATTRS | _INTERACTION_ALLOWLIST and not callable(target):
                return target
            return None

        # len(parts) == 3
        leaf_attr = parts[2]
        if leaf_attr not in _INTERACTION_SAFE_ATTRS:
            return None
        result = getattr(target, leaf_attr, None)
        if callable(result):
            return None
        return result

    def _resolve_tag_string(self, value, arguments=None, interaction=None):
        text = str(value)
        if arguments is None:
            arguments = {}

        result = []
        index = 0
        while index < len(text):
            ch = text[index]

            if ch == "\\":
                if index + 1 < len(text):
                    next_ch = text[index + 1]
                    if next_ch in {"\\", "{", "["}:
                        result.append(next_ch)
                        index += 2
                        continue
                result.append("\\")
                index += 1
                continue

            if ch == "{":
                end = text.find("}", index + 1)
                if end == -1:
                    result.append(ch)
                    index += 1
                    continue

                name = text[index + 1:end].strip()
                if name and re.fullmatch(r"[A-Za-z0-9_-]+", name):
                    result.append(str(arguments.get(name, "")))
                else:
                    result.append(text[index:end + 1])
                index = end + 1
                continue

            if ch == "[":
                end = text.find("]", index + 1)
                if end == -1:
                    result.append(ch)
                    index += 1
                    continue

                expression = text[index + 1:end].strip()
                resolved = self._resolve_interaction_reference(interaction, expression)
                if resolved is not None:
                    result.append(str(resolved))
                else:
                    result.append(text[index:end + 1])
                index = end + 1
                continue

            result.append(ch)
            index += 1

        return "".join(result)
    
    def _contains_interaction_reference(self, value) -> bool:
        if value is None:
            return False

        text = str(value)

        for match in re.finditer(r"(?<!\\)\[([^\]]+)\]", text):
            expression = match.group(1).strip()

            if expression.startswith("interaction."):
                return True

        return False


    def _validate_tag_arguments(
        self,
        value,
        provided_arguments,
        *,
        allow_interaction=True,
    ):
        if not allow_interaction and self._contains_interaction_reference(value):
            return (
                False,
                "This tag uses `[interaction.*]` references, which are only supported when using `/tag`.",
            )

        expected = self._extract_tag_argument_names(value)
        provided = list(provided_arguments or [])

        if not expected:
            if provided:
                return False, "This tag does not support tag arguments."

            return True, ""

        if len(provided) != len(expected):
            expected_text = ", ".join(
                f'"{name}"'
                for name in expected
            )

            return (
                False,
                f'This tag requires tag arguments in order: {expected_text}.',
            )

        return True, ""

    async def _build_tag_embed(self, value, interaction=None):
        embeds = await self._build_tag_embeds(value, interaction)
        return embeds[0] if embeds else discord.Embed(description=" ", color=0x5865F2)

    async def _build_tag_embeds(self, value, interaction=None):
        if isinstance(value, discord.Embed):
            return [value]

        text = str(value).strip()
        if not text:
            channel = interaction.channel if interaction is not None and interaction.channel is not None else None
            color = await self.bot.get_embed_color(channel) if channel is not None else 0x5865F2
            return [discord.Embed(description=" ", color=color)]

        channel = interaction.channel if interaction is not None and interaction.channel is not None else None
        color = await self.bot.get_embed_color(channel) if channel is not None else 0x5865F2
        chunks = self._chunk_embed_text(text)
        return [discord.Embed(description=chunk, color=color) for chunk in chunks]

    def _build_add_category(self):
        @app_commands.command(name="add_category", description="Create a new tag category")
        @app_commands.describe(category="The category name to create")
        @app_commands.autocomplete(category=category_autocomplete)
        async def add_category(interaction: discord.Interaction, category: str):
            try:
                category = self._normalize_name(category, "Category")
            except ValueError as exc:
                await interaction.response.send_message(
                    str(exc),
                    ephemeral=True,
                )
                return
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data:
                data[category] = {}
                await self._save_tags(interaction.guild, data)
                await interaction.response.send_message(f"Created category `{category}`.", ephemeral=True)
                return
            await interaction.response.send_message(f"Category `{category}` already exists.", ephemeral=True)

        return add_category

    def _build_add_tag(self):
        @app_commands.command(name="add_tag", description="Add a new tag")
        @app_commands.describe(
            category="The category to save into",
            tag="The tag name",
            value="A Discord message link or raw text",
            embed="Whether this tag should display in an embed",
        )
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def add_tag(interaction: discord.Interaction, category: str, tag: str, value: str, embed: bool = True):
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            try:
                category = self._normalize_name(category, "Category")
                tag = self._normalize_name(tag, "Tag")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            # Defer early — message link resolution involves a network request
            await interaction.response.defer(ephemeral=True)

            data = await self._load_tags(interaction.guild)
            if category not in data:
                data[category] = {}

            if self._has_duplicate_tag_name(data, tag):
                await interaction.followup.send(
                    f"A tag named `{tag}` already exists somewhere in the tag database.",
                )
                return

            resolved_value, is_embed_message = await self._resolve_message_link(value)
            if is_embed_message:
                await interaction.followup.send(
                    "That message link points to an embed-only message, which cannot be used as a tag value.",
                )
                return
            stored_value = resolved_value if embed else {"value": resolved_value, "embed": False}
            data[category][tag] = stored_value
            await self._save_tags(interaction.guild, data)

            argument_names = self._extract_tag_argument_names(resolved_value)
            if argument_names:
                formatted = ", ".join(f'"{name}"' for name in argument_names)
                await interaction.followup.send(
                    f"Saved `{tag}` under `{category}` with embed={'on' if embed else 'off'}. "
                    f'Warning: this tag uses tag arguments in order: {formatted}. '
                    r"To show literal braces or bracket syntax, escape them as \{name} or \[interaction.user.name].",
                )
                return

            await interaction.followup.send(
                f"Saved `{tag}` under `{category}` with embed={'on' if embed else 'off'}."
            )

        return add_tag

    def _build_edit_tag(self):
        @app_commands.command(name="edit_tag", description="Edit an existing tag")
        @app_commands.describe(
            category="The tag category",
            tag="The tag name",
            value="The new value",
            embed="Whether this tag should display in an embed",
        )
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def edit_tag(interaction: discord.Interaction, category: str, tag: str, value: str, embed: bool = True):
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            try:
                category = self._normalize_name(category, "Category")
                tag = self._normalize_name(tag, "Tag")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            data = await self._load_tags(interaction.guild)
            if category not in data or tag not in data[category]:
                await interaction.followup.send(f"`{tag}` does not exist in `{category}`.")
                return

            resolved_value, is_embed_message = await self._resolve_message_link(value)
            if is_embed_message:
                await interaction.followup.send(
                    "That message link points to an embed-only message, which cannot be used as a tag value.",
                )
                return
            data[category][tag] = resolved_value if embed else {"value": resolved_value, "embed": False}
            await self._save_tags(interaction.guild, data)

            argument_names = self._extract_tag_argument_names(resolved_value)
            if argument_names:
                formatted = ", ".join(f'"{name}"' for name in argument_names)
                await interaction.followup.send(
                    f"Updated `{tag}` in `{category}` with embed={'on' if embed else 'off'}. "
                    f'Warning: this tag uses tag arguments in order: {formatted}. '
                    r"To show literal braces or bracket syntax, escape them as \{name} or \[interaction.user.name].",
                )
                return

            await interaction.followup.send(
                f"Updated `{tag}` in `{category}` with embed={'on' if embed else 'off'}."
            )

        return edit_tag

    def _build_delete_tag(self):
        @app_commands.command(name="delete_tag", description="Delete a tag")
        @app_commands.describe(category="The category to remove from", tag="The tag name")
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def delete_tag(interaction: discord.Interaction, category: str, tag: str):
            try:
                category = self._normalize_name(category, "category")
                tag = self._normalize_name(tag, "tag")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            del data[category][tag]
            if not data[category]:
                del data[category]
            await self._save_tags(interaction.guild, data)
            await interaction.response.send_message(f"Deleted `{tag}` from `{category}`.", ephemeral=True)

        return delete_tag

    def _build_delete_category(self):
        @app_commands.command(name="delete_category", description="Delete an entire tag category and all its tags")
        @app_commands.describe(category="The category to delete")
        @app_commands.autocomplete(category=category_autocomplete)
        async def delete_category(interaction: discord.Interaction, category: str):
            try:
                category = self._normalize_name(category, "category")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data:
                await interaction.response.send_message(f"Category `{category}` does not exist.", ephemeral=True)
                return

            tag_count = len(data[category])
            del data[category]
            await self._save_tags(interaction.guild, data)
            await interaction.response.send_message(
                f"Deleted category `{category}` and {tag_count} tag(s).", ephemeral=True
            )

        return delete_category

    def _build_rename_tag(self):
        @app_commands.command(name="rename_tag", description="Rename an existing tag")
        @app_commands.describe(
            category="The category the tag is in",
            tag="The current tag name",
            new_tag="The new tag name",
        )
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def rename_tag(interaction: discord.Interaction, category: str, tag: str, new_tag: str):
            try:
                category = self._normalize_name(category, "category")
                tag = self._normalize_name(tag, "tag")
                new_tag = self._normalize_name(new_tag, "new_tag")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            try:
                category = self._normalize_name(category, "Category")
                tag = self._normalize_name(tag, "Tag")
                new_tag = self._normalize_name(new_tag, "New tag")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            if self._has_duplicate_tag_name(data, new_tag):
                await interaction.response.send_message(
                    f"A tag named `{new_tag}` already exists in the tag database.",
                    ephemeral=True,
                )
                return

            value = data[category].pop(tag)
            data[category][new_tag] = value
            await self._save_tags(interaction.guild, data)
            await interaction.response.send_message(
                f"Renamed `{tag}` to `{new_tag}` in `{category}`.", ephemeral=True
            )

        return rename_tag

    def _build_rename_category(self):
        @app_commands.command(name="rename_category", description="Rename a tag category")
        @app_commands.describe(category="The current category name", new_category="The new category name")
        @app_commands.autocomplete(category=category_autocomplete)
        async def rename_category(interaction: discord.Interaction, category: str, new_category: str):
            try:
                category = self._normalize_name(category, "category")
                new_category = self._normalize_name(new_category, "new_category")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data:
                await interaction.response.send_message(f"Category `{category}` does not exist.", ephemeral=True)
                return

            if new_category in data:
                await interaction.response.send_message(f"Category `{new_category}` already exists.", ephemeral=True)
                return

            data[new_category] = data.pop(category)
            await self._save_tags(interaction.guild, data)
            await interaction.response.send_message(
                f"Renamed category `{category}` to `{new_category}`.", ephemeral=True
            )

        return rename_category

    def _build_move_tag(self):
        @app_commands.command(name="move_tag", description="Move a tag into a different category")
        @app_commands.describe(
            category="The current category",
            tag="The tag name",
            new_category="The destination category",
        )
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def move_tag(interaction: discord.Interaction, category: str, tag: str, new_category: str):
            try:
                category = self._normalize_name(category, "category")
                tag = self._normalize_name(tag, "tag")
                new_category = self._normalize_name(new_category, "new_category")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            if new_category == category:
                await interaction.response.send_message(
                    "The destination category is the same as the current category.", ephemeral=True
                )
                return

            destination = data.get(new_category)

            if destination is not None and tag in destination:
                await interaction.response.send_message(
                    f"A tag named `{tag}` already exists in `{new_category}`.",
                    ephemeral=True,
                )
                return

            if destination is None:
                destination = {}
                data[new_category] = destination

            value = data[category].pop(tag)
            data[new_category][tag] = value
            if not data[category]:
                del data[category]
            await self._save_tags(interaction.guild, data)
            await interaction.response.send_message(
                f"Moved `{tag}` from `{category}` to `{new_category}`.", ephemeral=True
            )

        return move_tag

    def _build_list_tags(self):
        @app_commands.command(name="list", description="List tags in a category")
        @app_commands.describe(category="The category to list")
        @app_commands.autocomplete(category=category_autocomplete)
        async def list_tags(interaction: discord.Interaction, category: str):
            try:
                category = self._normalize_name(category, "category")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            tags = data.get(category, {})
            if not tags:
                await interaction.response.send_message(f"No tags found for `{category}`.", ephemeral=True)
                return

            names = ", ".join(f"`{name}`" for name in tags.keys())
            await interaction.response.send_message(f"Tags in `{category}`: {names}", ephemeral=True)

        return list_tags

    def _build_preview_embed(self):
        @app_commands.command(
            name="preview_embed",
            description="Preview the embed content that a message link would resolve to",
        )
        @app_commands.describe(messageLink="A Discord message link to preview")
        async def preview_embed(interaction: discord.Interaction, messageLink: str):
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            resolved, is_embed_message = await self._resolve_message_link(messageLink)
            if is_embed_message:
                await interaction.followup.send(
                    "That message link points to an embed-only message, which cannot be previewed as a tag.",
                )
                return
            if resolved == messageLink:
                await interaction.followup.send("That link could not be resolved to message content.")
                return

            embeds = await self._build_tag_embeds(resolved, interaction)
            for embed in embeds:
                if embed.color is None:
                    embed.color = await self.bot.get_embed_color(
                        interaction.channel
                    )

                await interaction.followup.send(embed=embed)

        return preview_embed

    def _build_set_tag_embed(self):
        @app_commands.command(name="set_tag_embed", description="Set whether an existing tag should display in an embed")
        @app_commands.describe(
            category="The tag category",
            tag="The tag name",
            embed="Whether this tag should display in an embed",
        )
        @app_commands.autocomplete(category=category_autocomplete, tag=tag_autocomplete)
        async def set_tag_embed(interaction: discord.Interaction, category: str, tag: str, embed: bool):
            try:
                category = self._normalize_name(category, "category")
                tag = self._normalize_name(tag, "tag")
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            data = await self._load_tags(interaction.guild)
            if category not in data or tag not in data[category]:
                await interaction.response.send_message(f"`{tag}` does not exist in `{category}`.", ephemeral=True)
                return

            value, _ = self._normalize_tag_value(data[category][tag])
            data[category][tag] = value if embed else {"value": value, "embed": False}
            await self._save_tags(interaction.guild, data)
            await interaction.response.send_message(
                f"`{tag}` in `{category}` now {'uses an embed' if embed else 'sends as plain text'}.",
                ephemeral=True,
            )

        return set_tag_embed

    def _build_toggle_text_commands(self):
        @app_commands.command(
            name="toggle_text_commands",
            description="Enable or disable text tag commands",
        )
        @app_commands.describe(
            enabled="Whether text tag commands should be enabled"
        )
        async def toggle_text_commands(
            interaction: discord.Interaction,
            enabled: bool,
        ):
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message(
                    "You do not have permission to manage tags.",
                    ephemeral=True,
                )
                return

            await self.config.guild(
                interaction.guild
            ).text_commands_enabled.set(enabled)

            await interaction.response.send_message(
                f"Text tag commands are now "
                f"{'enabled' if enabled else 'disabled'}.",
                ephemeral=True,
            )

        return toggle_text_commands

    def _build_import_json(self):
        @app_commands.command(name="import_json", description="Import tags from a JSON object or attached JSON file")
        @app_commands.describe(
            json_data="A JSON object mapping category names to tag dictionaries",
            attachment="Optional JSON file to import (drag the file into Discord)",
        )
        async def import_json(
            interaction: discord.Interaction,
            json_data: str = None,
            attachment: discord.Attachment = None,
        ):
            if not await self._can_manage_tags(interaction):
                await interaction.response.send_message("You do not have permission to manage tags.", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            if attachment is not None:
                try:
                    payload_text = (await attachment.read()).decode("utf-8")
                except UnicodeDecodeError:
                    await interaction.followup.send("The attached JSON file is not valid UTF-8 text.")
                    return
            elif json_data is not None and json_data.strip():
                payload_text = json_data
            else:
                await interaction.followup.send("Provide either a JSON string or upload a JSON file.")
                return

            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                await interaction.followup.send("Invalid JSON payload.")
                return

            if not isinstance(payload, dict):
                await interaction.followup.send("The JSON payload must be an object keyed by category name.")
                return

            try:
                imported = self._normalize_tag_database(payload)
            except ValueError as exc:
                await interaction.followup.send(str(exc))
                return

            merged = await self._load_tags(interaction.guild)

            try:
                merged = self._normalize_tag_database(merged)
            except ValueError as exc:
                await interaction.followup.send(
                    f"Existing tag data is invalid: {exc}"
                )
                return

            for category, tags in imported.items():
                destination = merged.setdefault(category, {})

                for tag_name, tag_value in tags.items():
                    if (
                        self._has_duplicate_tag_name(
                            merged,
                            tag_name,
                        )
                        and tag_name not in destination
                    ):
                        await interaction.followup.send(
                            f"A tag named `{tag_name}` already exists in another category."
                        )
                        return

                    destination[tag_name] = tag_value

            await self._save_tags(interaction.guild, merged)
            await interaction.followup.send("Imported tags from JSON.")

        return import_json
    
    def _normalize_tag_database(self, data: dict) -> dict:
        normalized = {}

        tag_locations: dict[str, str] = {}

        for raw_category, tags in data.items():
            category = self._normalize_name(
                raw_category,
                "Category",
            )

            if not isinstance(tags, dict):
                raise ValueError(
                    f"Category `{category}` is not a valid object of tags."
                )

            normalized_category = normalized.setdefault(
                category,
                {},
            )

            for raw_tag, value in tags.items():
                tag = self._normalize_name(
                    raw_tag,
                    "Tag",
                )

                existing_category = tag_locations.get(tag)

                if existing_category is not None:
                    if existing_category == category:
                        raise ValueError(
                            f"Duplicate tag `{tag}` in category `{category}`."
                        )

                    raise ValueError(
                        f"Tag `{tag}` already exists in category "
                        f"`{existing_category}`."
                    )

                tag_locations[tag] = category
                normalized_category[tag] = value

        return normalized

    # ---------------------------------------------------------------------------
    # /tag slash command
    # ---------------------------------------------------------------------------
    
    @app_commands.command(name="tag")
    @app_commands.describe(
        category="The tag category",
        tag="The tag name",
        arguments="Ordered values for any tag arguments, quoted as needed",
    )
    @app_commands.autocomplete(
        category=category_autocomplete,
        tag=tag_autocomplete,
    )
    @app_commands.guild_only()
    async def tag(
        self,
        interaction: discord.Interaction,
        category: str,
        tag: str,
        arguments: str = "",
    ):
        try:
            category = self._normalize_name(category, "Category")
            tag = self._normalize_name(tag, "Tag")
        except ValueError as exc:
            await interaction.response.send_message(
                str(exc),
                ephemeral=True,
            )
            return

        data = await self._load_tags(interaction.guild)
        value = data.get(category, {}).get(tag)

        if value is None:
            await interaction.response.send_message(
                f"I couldn't find `{tag}` in `{category}`.",
                ephemeral=True,
            )
            return

        value, should_embed = self._normalize_tag_value(value)

        parsed_arguments = self._split_tag_arguments(arguments)

        valid, warning = self._validate_tag_arguments(
            value,
            parsed_arguments,
        )

        if not valid:
            await interaction.response.send_message(
                warning,
                ephemeral=True,
            )
            return

        resolved_arguments = dict(
            zip(
                self._extract_tag_argument_names(value),
                parsed_arguments,
            )
        )

        rendered = self._resolve_tag_string(
            value,
            resolved_arguments,
            interaction,
        )

        if not should_embed:
            await self._send_text_pages(
                interaction,
                rendered,
            )
            return

        await self._send_tag_embeds(
            interaction,
            rendered,
        )

    # ---------------------------------------------------------------------------
    # Cog lifecycle
    # ---------------------------------------------------------------------------

    async def cog_load(self):
        print("=== SlashTags cog_load ===")

        print("app commands:", self.get_app_commands())

        for command in self.get_app_commands():
            print(
                "APP COMMAND:",
                command,
                "name=", command.name,
                "parent=", command.parent,
                "guild_ids=", getattr(command, "_guild_ids", None),
                "module=", command.module,
            )

        print("tree global:", self.bot.tree._global_commands)
        print("tree disabled:", self.bot.tree._disabled_global_commands)

        print("\n=== VERSIONS ===")
        import redbot
        print("Red:", redbot.__version__)
        print("discord.py:", discord.__version__)

        print("\n=== MANAGE ===")
        print("manage:", self.manage)
        print("type:", type(self.manage))
        print("name:", self.manage.name)
        print("parent:", self.manage.parent)
        print("root_parent:", self.manage.root_parent)
        print("guild_only:", self.manage.guild_only)
        print("extras:", self.manage.extras)

        print("\n=== COG APP COMMANDS ===")
        print("get_app_commands:", self.get_app_commands())

        print("\n=== TREE BEFORE ===")
        print("tree:", self.bot.tree.get_commands())
        print("disabled:", self.bot.tree._disabled_global_commands)

        print("\n=== ADD MANAGE ===")
        self.bot.tree.add_command(self.manage)

        print("tree:", self.bot.tree.get_commands())
        print("disabled:", self.bot.tree._disabled_global_commands)

        print("\n=== TREE LOOKUPS ===")
        print("tag:", self.bot.tree.get_command("tag"))
        print("managetags:", self.bot.tree.get_command("managetags"))


    async def cog_unload(self):
        self.bot.tree.remove_command(self.manage.name)

    # ---------------------------------------------------------------------------
    # Redbot data privacy compliance
    # ---------------------------------------------------------------------------

    async def red_delete_data_for_user(
        self,
        *,
        requester: str,
        user_id: int,
    ) -> typing.NoReturn:
        pass
