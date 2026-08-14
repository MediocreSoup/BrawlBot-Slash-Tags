# BrawlBot-Slash-Tags

A Red-DiscordBot cog that exposes a persistent tag system through Discord slash commands.

## Installation

This cog is intended for an existing RedBot instance.

1. Add the repository:

```text
[p]repo add BrawlBot-Slash-Tags https://github.com/MediocreSoup/BrawlBot-Slash-Tags
```

2. Install the cog:

```text
[p]cog install BrawlBot-Slash-Tags BrawlBotSlashTags
```

3. Load the cog:

```text
[p]load BrawlBotSlashTags
```

4. Sync slash commands:

```text
[p]slash sync
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

### Importing the repo JSON file

You can import the tag data from the JSON file you left in the repo, such as [BrawlBotTags14-08-2026.json](BrawlBotTags14-08-2026.json).

Use the import command with the file's raw JSON payload:

```text
/managetags import_json json_data:{"__criticalregistry__":{"hi":"hello, world!"},"newtohelpchat":{"dontasktoask":"https://dontasktoask.com/"}}
```

If you want to import the entire file contents, paste the file's object JSON exactly as the value for `json_data`.

The JSON import command merges category/tag data into the saved config without deleting existing values.

## Notes

- Tags are stored in Red's config system, so they persist across bot restarts.
- The admin role is currently configured in the cog as the required role for management commands.
- Values can be raw text or a Discord message link; message links are resolved to the linked message content before saving.
