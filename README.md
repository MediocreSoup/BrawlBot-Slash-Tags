# BrawlBot-Slash-Tags

A Red-DiscordBot cog that exposes a persistent tag system through Discord slash commands.

## Installation

This cog is intended for an existing RedBot instance.

```text
.repo add BrawlBot-Slash-Tags https://github.com/MediocreSoup/BrawlBot-Slash-Tags
.cog install BrawlBot-Slash-Tags BrawlBotSlashTags
.load BrawlBotSlashTags
.slash sync
```

## Commands

### Retrieve a tag

```text
/tag category:newtohelpchat tag:dontasktoask
/tag category:packages tag:profilestore
/tag category:newtoscripting tag:workspace
```

The command name is `/tag`, and the tag value is returned as an embed when possible.

### Manage tags

These commands are restricted to the configured admin role.

```text
/managetags add_category category:newtohelpchat
/managetags add_tag category:newtohelpchat tag:dontasktoask value:https://dontasktoask.com/
/managetags list category:newtohelpchat
/managetags delete_tag category:newtohelpchat tag:dontasktoask
/managetags import_json json_data:{"newtohelpchat":{"dontasktoask":"https://dontasktoask.com/"}}
```

Use `.slash sync` or `ctrl + r` on discord client to see new slash commands faster

### Importing the repo JSON file

You can import the tag data from the JSON file you left in the repo, such as [BrawlBotTags14-08-2026.json](BrawlBotTags14-08-2026.json).

There are two supported ways to use it:

1. Paste the raw JSON payload directly:

```text
/managetags import_json json_data:{"__criticalregistry__":{"hi":"hello, world!"},"newtohelpchat":{"dontasktoask":"https://dontasktoask.com/"}}
```

2. Upload the JSON file as an attachment and run the command with no string value:

```text
/managetags import_json
```

Then attach the file in Discord when the command prompt asks for it. The command accepts either a raw JSON string or a JSON attachment, and it merges the imported data into the saved config without deleting existing tags.

## Notes

- Tags are stored in Red's config system, so they persist across bot restarts.
- The admin role is currently configured in the cog as the required role for management commands.
- Values can be raw text or a Discord message link; message links are resolved to the linked message content before saving.
