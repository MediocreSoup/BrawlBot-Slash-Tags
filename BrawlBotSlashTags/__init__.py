from .brawlbotslashtags import SlashTags


async def setup(bot):
    await bot.add_cog(SlashTags(bot))