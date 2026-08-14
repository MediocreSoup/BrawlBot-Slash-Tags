import discord
from redbot.core import commands, app_commands

# all tags are wrapped inside embeds

__criticalregistry__ = {
    "hi": "hello, world!",
    "secret_tag_do_not_run": ":SECRETEMOTE:",
    "froggers": "https://tenor.com/view/bro-frogs-tree-frog-gif-5275848"
}

newtohelpchat = {
    "dontasktoask": "https://dontasktoask.com/",
    "return": "https://cdn.discordapp.com/attachments/1138164798652166264/1390151984148910090/output.gif?ex=6a7f212c&is=6a7dcfac&hm=3bcf97d4c61e2fcad70efcea8d427df3d5c5f817357ad6ecc24aec83fee089fa&",
    "codeblock": """
```lua
-- your code goes here
```
https://media.discordapp.net/attachments/428675939572908032/847863317162360862/How_To_Format_Code_In_Discord.gif?ex=6a7f383f&is=6a7de6bf&hm=6a64d68b9935e07aea89fa96625ed3d00aaf703e3b17e04d2abaed2af4a5e927&
""",
    "notyourslave": """The people answering questions here are volunteers, not your personal coders. Posting \"make this script for me\" or \"fix it\" with no context isn't enough for anyone to help.

If you want useful answers, show that you've put in some effort:

- Explain what you're trying to achieve.
- Share the code you've written so far.
- Include any errors from the console or output window.
- Describe what you've already tried and what happened.

The more information you provide, the faster and more accurately people can help you. We don't expect you to know everything—that's why you're asking—but we do expect you to meet us halfway.

A little effort on your part goes a long way toward getting the help you need.
""",
    "lookingforlabor": "Head to <#1516084938443591690> if you want to work alongside someone for free. If you want to pay someone to work for you, then take a look at <#1477672520172962053>!",
    "nometa": "https://nometa.xyz/index.html"
}

packages = {
    "profilestore": "**ProfileStore Tutorial** \n https://www.youtube.com/watch?v=evBhoqeYegQ",
    "bytenetmax": "ByteNetMax is a networking module which converts content to a buffer, which reduces memory usage significantly, helping optimise and speed up data transfer. \n https://devforum.roblox.com/t/bytenet-max-upgraded-networking-library-w-buffer-serialisation-strict-luau-and-remotefunction-support-v021/3268469",
    "packet": "Packet is a networking module which serializes data into a buffer, reducing network usage significantly. \n https://www.youtube.com/watch?v=WoIElUdj64A \n https://devforum.roblox.com/t/packet-networking-library/3573907",
    "signal": "Signal modules are a full replacement of BindableEvents. They are easier to use, and extremely fast. \n https://devforum.roblox.com/t/signal-super-fast-elegant-signals/3552231/1"
}

newtoscripting = {
    "workspace": "It is highly recommended to use `workspace` instead of `game.Workspace`. It does exactly the same thing, but is slightly more performant and keeps your code cleaner.",
    "aicode": "https://media.discordapp.net/attachments/1353132454801571950/1521562218796286232/AIcode.jpg?ex=6a7ea1fe&is=6a7d507e&hm=f62f12b1b581da1b3ee8a5f6f1efbc446a0635e5113f23fac91d428cdd698076&format=webp&width=1521&height=856&",
    "aicodebutevil": "https://media.discordapp.net/attachments/1353132454801571950/1521564448593281064/AIcodeEvil.jpg?ex=6a7ea411&is=6a7d5291&hm=403e7f77af3afa09277b426d31d77085c7979d6017edfb182634140f14937553&format=webp&width=1521&height=856&",
    "tutorialguide": """
# Reccommended Watch Order + What to Skip

## Watch First: Beginner Scripting Tutorials

**Videos to Skip:**
- **[OPTIONAL] #18 - Final Game:**
> This video is considered optional by the community, due to its confusing practices e.g. using ValueBase instances for no reason, and using FindFirstChild where it is simply not needed. Due to these issues, it can be very difficult and confusing to debug.

## Watch Next: GUI Tutorials
The GUI tutorials should be watch after the beginner tutorials to give your mind a break from scripting.
**Videos to Skip:**
All topics in the GUI tutorial are incredibly useful, and none of them should be skipped.

## Watch Last: Advanced Scripting Tutorials
**Videos to Skip:**
- **#8 - Coroutines:**
> Coroutines have very niche use cases, and have essentially been replaced by task library. Additionally, coroutine.yield can be used on task threads, giving you the same level of control if needed.
- **#14 - ContextActionService:**
> ContextActionService is effectively deprecated, and has been replaced with InputActionSystem.
- **#16 - BindableEvents:**
> BindableEvent and BindableFunction are generally not worth using at all. If you ever need events, you are much better off using any Signal module instead, e.g. [SignalPlus](https://devforum.roblox.com/t/signal-super-fast-elegant-signals/3552231).
- **#28 - Time:** *(Don't fully skip - read below!)*
> Time is incredibly useful, though this tutorial is a bit bloated and teaches you time methods that are either deprecated (tick) or redundant (DateTime). You only really need to know os.time(), os.clock(), and workspace:GetServerTimeNow().
- **#33 - HapticService:**
> HapticService is deprecated. It has been superseded by HapticEffects, which is much better and easier to use.
""",
    "waitforchild": "https://www.youtube.com/watch?v=7tzy1DuPcBQ",
    "guidedlearning": """# Guided Learning
    Gemini Guided Learning mode is an interactive AI tutoring feature designed to **build genuine comprehension** rather than just giving you the answers.
    Instead of a quick fix, Gemini breaks concepts into **steps**, asks **probing questions**, and offers **multimodal resources (like diagrams and quizzes)** to teach at your own pace, in your own learning style.

    ## How to Access **
    - 1. Open Google Gemini
    - 2. Look at the prompt field and click the Tools icon
    - 3. On the dropdown menu, select Guided Learning
    - 4. Enter your question or topic, and begin learning **
    """,
    "getstarted": "Here is the best tutorial series for starting Roblox Studio Luau scripting: \n https://www.youtube.com/watch?v=9MUgLaF22Yo&list=PLQ1Qd31Hmi3W_CGDzYOp7enyHlOuO3MtC \n Start on Episode 1. Run `.tutorialguide` or `/tag newtoscripting tutorialguide` command for more guidance!",
    "cframe": "A CFrame is an object that stores position and rotation, learn more here: \n https://devforum.roblox.com/t/comprehensive-beginners-guide-to-cframes-and-how-to-use-them-cframe-guide/1334085" 
}

scripting = {
    "learnoptimization": "https://discord.com/channels/1162762428342358158/1453210464086655046 \n https://discord.com/channels/1162762428342358158/1453210464086655046"
}

tagStructure = {
    "__criticalregistry__": __criticalregistry__,
    "newtohelpchat": newtohelpchat,
    "packages": packages,
    "newtoscripting": newtoscripting,
    "scripting": scripting,
}

class SlashTags(commands.Cog):
    """Me when I cog:"""

    def __init__(self, bot):
        self.bot = bot
        self.tag_structure = tagStructure
        self.group = app_commands.Group(name="tag", description="Choose a preset tag to send to chat")
        
        for category, tags in self.tag_structure.items():

            def make_callback(cat):
                async def callback(interaction: discord.Interaction, tag: str):
                    content = self.tag_structure[cat].get(tag)
                    if not content:
                        await interaction.response.send_message(f"Unknown tag `{tag}` in `{cat}`", ephemeral=True)
                        return

                    # Fetch the server's RedBot embed color theme dynamically
                    embed_color = await self.bot.get_embed_color(interaction.channel)

                    # Build the embed using the content as the description
                    embed = discord.Embed(
                        description=content,
                        color=embed_color
                    )
                    
                    await interaction.response.send_message(embed=embed)
                return callback

            def make_autocomplete(tag_dict):
                async def autocomplete(interaction: discord.Interaction, current: str):
                    return [
                        app_commands.Choice(name=k, value=k)
                        for k in tag_dict.keys()
                        if current.lower() in k.lower()
                    ][:25]
                return autocomplete

            func = make_callback(category)
            func = app_commands.autocomplete(tag=make_autocomplete(tags))(func)
            cmd = app_commands.command(name=category, description=f"Tags for {category}")(func)
            self.group.add_command(cmd)

    async def cog_load(self):
        self.bot.tree.add_command(self.group)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.group.name)
