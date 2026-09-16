from .slashtags import SlashTags


async def setup(bot):
    cog = SlashTags(bot)

    print("=== BEFORE ADD COG ===")
    print("app commands:", cog.get_app_commands())
    print("tree:", bot.tree.get_commands())
    print("disabled:", bot.tree._disabled_global_commands)

    await bot.add_cog(cog)

    print("=== AFTER ADD COG ===")
    print("app commands:", cog.get_app_commands())
    print("tree:", bot.tree.get_commands())
    print("disabled:", bot.tree._disabled_global_commands)
    print("global:", bot.tree._global_commands)
    