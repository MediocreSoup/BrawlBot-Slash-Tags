# BrawlBot-Slash-Tags

A Red-DiscordBot cog that exposes a persistent tag system through Discord slash commands.

WARNING: The following file has been slopped up by copilot and only skimmed over by me

## Installation

This cog is intended for an existing RedBot instance.

This can also replace the default tags cog by enabling text commands with the command `/managetags toggle_text_commands enabled:boolean`

Note: `[p]` is the prefix for the bot, in brawlbot's case "."

```text
[p]repo add BrawlBot-Slash-Tags https://github.com/MediocreSoup/BrawlBot-Slash-Tags
[p]cog install BrawlBot-Slash-Tags BrawlBotSlashTags
[p]load BrawlBotSlashTags
[p]slash sync
```

> Warning: slash command sync can take a little while to appear in Discord. If the commands do not show up immediately, wait a few minutes and re-run `[p]slash sync`.

## Commands

### Retrieve a tag

Tags are organised into categories.

The command name is `/tag` or `[p][tagname]`, and tags default to embed output unless explicitly set to plain text with `/managetags set_tag_embed ... embed:false` or a JSON object using `{ "value": "...", "embed": false }`.

Slash commands:

```text
/tag category:newtohelpchat tag:dontasktoask
/tag category:packages tag:profilestore
/tag category:newtoscripting tag:workspace
```

Text commands:

```text
.dontasktoask
.profilestore
.workspace
```

### Manage tags

These commands are slash-only and restricted to users with Redbot admin permissions or guild administrator permissions.

If you need to grant access in Redbot, set the admin role or add the user/role directly:

```text
[p]setadminrole Admin
[p]permissions addrole @Admins admin
[p]permissions add @SomeUser admin
```

Note: "value" arguments below for adding/editing tags can be either raw text or a discord message link.

```text
/managetags add_category category:newtohelpchat
/managetags add_tag category:newtohelpchat tag:dontasktoask value:https://dontasktoask.com/ embed:true
/managetags edit_tag category:newtohelpchat tag:dontasktoask value:https://example.com/ embed:false
/managetags preview_embed messageLink:https://discord.com/channels/123456789012345678/123456789012345678/123456789012345678
/managetags set_tag_embed category:newtohelpchat tag:dontasktoask embed:false
/managetags rename_tag category:newtohelpchat tag:dontasktoask new_tag:example
/managetags rename_category category:newtohelpchat new_category:help
/managetags move_tag category:newtohelpchat tag:dontasktoask new_category:newtohelpchat2
/managetags list category:newtohelpchat
/managetags delete_tag category:newtohelpchat tag:dontasktoask
/managetags import_json json_data:{"newtohelpchat":{"dontasktoask":"https://dontasktoask.com/"}}
```

> Warning: the slash command sync can take a little while to appear in Discord. If the slash commands do not show up immediately after loading the cog, wait a few minutes and re-run `[p]slash sync` or `ctrl + r` on the discord.

### Importing the repo JSON file

You can import the tag data from the JSON file included in the repo, such as [BrawlBotTags12-09-2026.json](BrawlBotTags12-09-2026.json).

There are two supported ways to use it:

1. Drag and drop the JSON file into the Discord chat bar using the `attachment` parameter:

```text
/managetags import_json attachment:[upload BrawlBotTags12-09-2026.json]
```

2. Paste the raw JSON payload directly:

```text
/managetags import_json json_data:{"__criticalregistry__":{"hi":"hello, world!"},"newtohelpchat":{"dontasktoask":"https://dontasktoask.com/"}}
```

Then attach the file in Discord when the command prompt asks for it.

The command accepts either a raw JSON string or a JSON attachment, and it merges the imported data into the saved config without deleting existing tags. Legacy plain-string tags still load correctly; plain-text overrides can be stored as `{ "value": "...", "embed": false }`.

### Tag arguments

Tag templates can include ordered placeholders such as `{name}` and `{city}`. When a tag uses arguments, the bot validates that the number and order of values match the placeholders in the template.

Example template stored for the tag:

```text
Hello {name}, welcome to {city}! We are in [interaction.guild.name].
```

Examples:

```text
/tag category:welcome tag:greet arguments:"Ava \"Paris, France\""
```

This resolves to:

```text
Hello Ava, welcome to Paris, France! We are in Example Guild.
```

Important behavior:

- Arguments are ordered, so `{name}` must be first and `{city}` second.
- Quoted values keep spaces, for example `"Paris, France"` stays one argument.
- Use backslashes to keep literal braces or brackets in a tag: `\{name}` and `\[interaction.user.name]`.
- Interaction values are supported with bracket syntax, such as `[interaction.user.name]`, `[interaction.guild.name]`, and `[interaction.user.id]`.
- All arguments are required and a mismatch of provided arguments will yield a warning message.

>>> To look up available interaction values, see https://discordpy.readthedocs.io/en/latest/interactions/api.html

## Notes
 
- Tags are scoped per guild and automatically backed up as JSON files in Redbot's data directory upon every modification (retaining the 20 most recent backups per guild).
- Values can be raw text or a Discord message link; message links are resolved to the linked message content before saving.
- If everything burns down, you have full permission to send angry messages to @MediocreSoup on discord 👍
