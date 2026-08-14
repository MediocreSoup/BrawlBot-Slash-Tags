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

The command name is `/tag` or `[p][tagname]`, and tags default to embed output unless explicitly set to plain text with `/managetags set_tag_embed ... embed:false` or a JSON object using `"embed": false`.

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

These commands are slash-only and restricted to the admin role (lowk hardcoded the role ID im sure its fine, to change the required role ID go to `line 12` of `BrawlBotSlashTags/brawlbotslashtags.py`).

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

You can also right click a message -> Apps -> Add tag from message

> Warning: the slash command sync can take a little while to appear in Discord. If the slash commands do not show up immediately after loading the cog, wait a few minutes and re-run `[p]slash sync` or `ctrl + r` on the discord.

### Importing the repo JSON file

You can import the tag data from the JSON file I left in the repo, such as [BrawlBotTags14-08-2026.json](BrawlBotTags14-08-2026.json).

There are two supported ways to use it:

1. Upload the JSON file as an attachment and run the command with no string value:

```text
/managetags import_json
```

2. Paste the raw JSON payload directly:

```text
/managetags import_json json_data:{"__criticalregistry__":{"hi":"hello, world!"},"newtohelpchat":{"dontasktoask":"https://dontasktoask.com/"}}
```

Then attach the file in Discord when the command prompt asks for it.

The command accepts either a raw JSON string or a JSON attachment, and it merges the imported data into the saved config without deleting existing tags. Legacy plain-string tags still load correctly; plain-text overrides can be stored as `{ "value": "...", "embed": false }`.

## Notes

- Tags are stored in Red's config system, so they persist across bot restarts.
- Tags are automatically backed up as json files every tag change, they are stored in the backups folder inside this cog
- The admin role is currently configured in the cog as the required role for management commands.
- Values can be raw text or a Discord message link; message links are resolved to the linked message content before saving.
- If everything burns down, you have full permission to send angry messages to @MediocreSoup on discord 👍
