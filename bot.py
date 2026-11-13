import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random

# =====================================
# CONFIGURATION
# =====================================

TOKEN = "DISCORD_TOKEN"
OWNER_ID = 1460197196409344082
LEVEL_FILE = "levels.json"
WARNING_FILE = "warnings.json"
LOG_CHANNEL_NAME = "mod-logs"

# =====================================
# JSON DATABASE HELPERS (LEVELS & WARNINGS)
# =====================================

def load_data(file_path):
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# =====================================
# BOT SETUP
# =====================================

intents = discord.Intents.default()
intents.message_content = True  # Required for message content logs & XP tracking
intents.members = True          # Required for join/leave logs & member stats

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =====================================
# HELPERS (LOGS & ROLES)
# =====================================

async def get_or_create_log_channel(guild):
    """Finds the log channel, or auto-creates it if missing"""
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel is None:
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            log_channel = await guild.create_text_channel(
                LOG_CHANNEL_NAME, 
                overwrites=overwrites, 
                reason="Auto-created mod-logs channel"
            )
        except discord.Forbidden:
            pass
    return log_channel

async def get_or_create_level_role(guild, level):
    """Automatically creates milestone roles (Level 5, 10, 15, etc.) if they don't exist"""
    role_name = f"Level {level}"
    role = discord.utils.get(guild.roles, name=role_name)
    
    if role is None:
        try:
            role = await guild.create_role(
                name=role_name,
                reason=f"Auto-created milestone role for Level {level}",
                hoist=True
            )
        except discord.Forbidden:
            return None
    return role

def ordinal(n):
    """Converts a number to an ordinal string (1st, 2nd, 3rd, etc.)"""
    return str(n) + ("th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))

# =====================================
# LEVELING SYSTEM & EVENT LISTENERS
# =====================================

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        await bot.process_commands(message)
        return

    data = load_data(LEVEL_FILE)
    guild_id = str(message.guild.id)
    user_id = str(message.author.id)

    if guild_id not in data:
        data[guild_id] = {}

    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {"xp": 0, "level": 1}

    user_data = data[guild_id][user_id]
    
    # Cap max level at 100
    if user_data["level"] < 100:
        xp_gain = random.randint(15, 25)
        user_data["xp"] += xp_gain

        xp_needed = int(100 * (user_data["level"] ** 1.5))

        if user_data["xp"] >= xp_needed:
            user_data["xp"] -= xp_needed
            user_data["level"] += 1
            new_level = user_data["level"]

            await message.channel.send(
                f"🎉 Congrats {message.author.mention}, you leveled up to **Level {new_level}**!"
            )

            # Check if this level is a milestone (multiple of 5)
            if new_level % 5 == 0:
                role = await get_or_create_level_role(message.guild, new_level)
                if role:
                    # Remove older level roles so they only keep their highest tier
                    for r in message.author.roles:
                        if r.name.startswith("Level ") and r != role:
                            try:
                                await message.author.remove_roles(r)
                            except:
                                pass
                    
                    # Assign the new milestone role
                    try:
                        await message.author.add_roles(role)
                        await message.channel.send(f"🛡️ {message.author.mention} unlocked the **{role.name}** role!")
                    except discord.Forbidden:
                        pass

        save_data(LEVEL_FILE, data)

    await bot.process_commands(message)


# =====================================
# MOD LOGS & SERVER EVENT LISTENERS
# =====================================

@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None:
        return

    log_channel = discord.utils.get(message.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    embed = discord.Embed(
        title="🗑️ Message Deleted",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Author", value=f"{message.author} (`{message.author.id}`)", inline=False)
    embed.add_field(name="Channel", value=message.channel.mention, inline=False)
    
    content = message.content if message.content else "*[Embed or Attachment without text]*"
    embed.add_field(name="Content", value=content[:1024], inline=False)
    embed.set_footer(text=f"User ID: {message.author.id}")
    
    await log_channel.send(embed=embed)


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.guild is None:
        return
    if before.content == after.content:
        return

    log_channel = discord.utils.get(before.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    embed = discord.Embed(
        title="✏️ Message Edited",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Author", value=f"{before.author} (`{before.author.id}`)", inline=False)
    embed.add_field(name="Channel", value=before.channel.mention, inline=False)
    embed.add_field(name="Before", value=before.content[:1024] if before.content else "*[None]*", inline=False)
    embed.add_field(name="After", value=after.content[:1024] if after.content else "*[None]*", inline=False)
    
    await log_channel.send(embed=embed)


@bot.event
async def on_member_join(member):
    log_channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    embed = discord.Embed(
        title="📥 Member Joined",
        description=f"{member.mention} ({member})",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
    embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
    
    await log_channel.send(embed=embed)


@bot.event
async def on_member_remove(member):
    log_channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    embed = discord.Embed(
        title="📤 Member Left / Kicked",
        description=f"{member.mention} ({member})",
        color=discord.Color.dark_red(),
        timestamp=discord.utils.utcnow()
    )
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
    
    await log_channel.send(embed=embed)


@bot.event
async def on_guild_channel_delete(channel):
    log_channel = discord.utils.get(channel.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    embed = discord.Embed(
        title="📁 Channel Deleted",
        description=f"**#{channel.name}** was deleted.",
        color=discord.Color.dark_red(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Type", value=str(channel.type).capitalize(), inline=True)
    embed.add_field(name="Channel ID", value=str(channel.id), inline=True)
    
    await log_channel.send(embed=embed)


@bot.event
async def on_guild_join(guild):
    await get_or_create_log_channel(guild)


# =====================================
# GENERAL / FUN COMMANDS
# =====================================

@bot.tree.command(
    name="greet",
    description="Greets you with a random friendly phrase!"
)
async def greet(interaction: discord.Interaction):
    greetings = [
        "hi gng",
        "hello to you too",
        "wsg my man",
        "hi i am a bot in this world full of humans..."
    ]
    chosen_greeting = random.choice(greetings)
    await interaction.response.send_message(chosen_greeting)


# =====================================
# BOT INFORMATION COMMANDS
# =====================================

bot_group = app_commands.Group(
    name="bot",
    description="Commands related to the bot"
)


@bot_group.command(
    name="about",
    description="Learn more about this bot and its features"
)
async def bot_about(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"🤖 About {bot.user.name}",
        description="A multi-purpose server helper bot built with `discord.py` featuring automated leveling, role milestones, moderation tools, and server logging.",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)

    embed.add_field(name="Developer", value=f"<@{OWNER_ID}>", inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(
        name="Features",
        value="• XP & Leveling (Auto-roles every 5 levels)\n• Moderation Suite (Warn, Timeout, Kick, Ban, Purge, Roles)\n• Automated Mod-Logs\n• Server & User Info",
        inline=False
    )
    embed.set_footer(text=f"Bot ID: {bot.user.id}")

    await interaction.response.send_message(embed=embed)


# =====================================
# MODERATION COMMANDS
# =====================================

moderation = app_commands.Group(
    name="moderation",
    description="Server moderation commands"
)


@moderation.command(
    name="warn",
    description="Warn a member for breaking rules"
)
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    member="Member to warn",
    reason="Reason for the warning"
)
async def warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("You cannot warn yourself!", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("You cannot warn bots!", ephemeral=True)
        return

    data = load_data(WARNING_FILE)
    guild_id = str(guild.id)
    user_id = str(member.id)

    if guild_id not in data:
        data[guild_id] = {}

    if user_id not in data[guild_id]:
        data[guild_id][user_id] = []

    data[guild_id][user_id].append({
        "moderator": interaction.user.id,
        "reason": reason,
        "timestamp": str(discord.utils.utcnow())
    })
    save_data(WARNING_FILE, data)

    warn_count = len(data[guild_id][user_id])
    warn_text = ordinal(warn_count)

    await interaction.response.send_message(
        f"⚠️ {member.mention} has been warned. This is their **{warn_text}** warning.\n**Reason:** {reason}"
    )

    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title="⚠️ Member Warned",
            color=discord.Color.yellow(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Warning Count", value=warn_text, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await log_channel.send(embed=embed)


@moderation.command(
    name="remove-warn",
    description="Remove a warning (or all warnings) from a member"
)
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    member="Member to remove warning from",
    warning_number="Warning number to remove (leave blank to clear all warnings)"
)
async def remove_warn(
    interaction: discord.Interaction,
    member: discord.Member,
    warning_number: int = None
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    data = load_data(WARNING_FILE)
    guild_id = str(guild.id)
    user_id = str(member.id)

    user_warnings = data.get(guild_id, {}).get(user_id, [])

    if not user_warnings:
        await interaction.response.send_message(f"{member.mention} has no warnings to remove.", ephemeral=True)
        return

    if warning_number is None:
        data[guild_id][user_id] = []
        save_data(WARNING_FILE, data)
        msg = f"✅ Cleared **all** warnings for {member.mention}."
        log_detail = "Cleared all warnings"
    else:
        if warning_number < 1 or warning_number > len(user_warnings):
            await interaction.response.send_message(
                f"Invalid warning number. {member.mention} currently has **{len(user_warnings)}** warning(s).",
                ephemeral=True
            )
            return

        removed = user_warnings.pop(warning_number - 1)
        save_data(WARNING_FILE, data)
        msg = f"✅ Removed warning **#{warning_number}** (`{removed['reason']}`) from {member.mention}. They now have **{len(user_warnings)}** warning(s)."
        log_detail = f"Removed warning #{warning_number} ({removed['reason']})"

    await interaction.response.send_message(msg)

    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title="🧹 Warning Removed",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Action", value=log_detail, inline=False)
        await log_channel.send(embed=embed)


@moderation.command(
    name="ban",
    description="Ban a member from the server"
)
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(
    member="Member to ban",
    reason="Reason for the ban"
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("You cannot ban yourself!", ephemeral=True)
        return

    bot_member = guild.me
    if bot_member is None or member.top_role >= bot_member.top_role:
        await interaction.response.send_message("I cannot ban this member because of role hierarchy!", ephemeral=True)
        return

    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"Successfully banned {member.mention}.\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to ban this member!", ephemeral=True)


@moderation.command(
    name="unban",
    description="Unban a user from the server using their User ID"
)
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(
    user_id="The Discord User ID of the banned user",
    reason="Reason for unbanning"
)
async def unban(
    interaction: discord.Interaction,
    user_id: str,
    reason: str = "No reason provided"
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if not user_id.isdigit():
        await interaction.response.send_message("Please provide a valid numeric User ID.", ephemeral=True)
        return

    try:
        user = await bot.fetch_user(int(user_id))
        await guild.unban(user, reason=reason)
        await interaction.response.send_message(f"✅ Successfully unbanned **{user}** (`{user.id}`).\n**Reason:** {reason}")
    except discord.NotFound:
        await interaction.response.send_message("That user ID was not found or is not banned.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to unban users!", ephemeral=True)


@moderation.command(
    name="kick",
    description="Kick a member from the server"
)
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(
    member="Member to kick",
    reason="Reason for the kick"
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("You cannot kick yourself!", ephemeral=True)
        return

    bot_member = guild.me
    if bot_member is None or member.top_role >= bot_member.top_role:
        await interaction.response.send_message("I cannot kick this member because of role hierarchy!", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"Successfully kicked {member.mention}.\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to kick this member!", ephemeral=True)


@moderation.command(
    name="timeout",
    description="Timeout a member for a specified duration"
)
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    member="Member to timeout",
    minutes="Duration of the timeout in minutes",
    reason="Reason for the timeout"
)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: int,
    reason: str = "No reason provided"
):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("You cannot timeout yourself!", ephemeral=True)
        return

    bot_member = guild.me
    if bot_member is None or member.top_role >= bot_member.top_role:
        await interaction.response.send_message("I cannot timeout this member because of role hierarchy!", ephemeral=True)
        return

    try:
        duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"Successfully timed out {member.mention} for {minutes} minute(s).\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout this member!", ephemeral=True)


@moderation.command(
    name="remove-timeout",
    description="Remove an active timeout from a member"
)
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    member="Member to remove timeout from",
    reason="Reason for removing the timeout"
)
async def remove_timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if not member.is_timed_out():
        await interaction.response.send_message(f"{member.mention} is not currently timed out.", ephemeral=True)
        return

    try:
        await member.timeout(None, reason=reason)
        await interaction.response.send_message(f"✅ Removed timeout from {member.mention}.\n**Reason:** {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to remove timeouts!", ephemeral=True)


@moderation.command(
    name="add-role",
    description="Add a role to a server member"
)
@app_commands.default_permissions(manage_roles=True)
@app_commands.describe(
    member="Member to give the role to",
    role="The role to assign"
)
async def add_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if role >= guild.me.top_role:
        await interaction.response.send_message("I cannot assign that role because it is higher than or equal to my highest role!", ephemeral=True)
        return

    if role in member.roles:
        await interaction.response.send_message(f"{member.mention} already has the **{role.name}** role.", ephemeral=True)
        return

    try:
        await member.add_roles(role, reason=f"Added by {interaction.user}")
        await interaction.response.send_message(f"✅ Added **{role.name}** to {member.mention}.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage roles!", ephemeral=True)


@moderation.command(
    name="remove-role",
    description="Remove a role from a server member"
)
@app_commands.default_permissions(manage_roles=True)
@app_commands.describe(
    member="Member to remove the role from",
    role="The role to remove"
)
async def remove_role(
    interaction: discord.Interaction,
    member: discord.Member,
    role: discord.Role
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    if role >= guild.me.top_role:
        await interaction.response.send_message("I cannot remove that role because it is higher than or equal to my highest role!", ephemeral=True)
        return

    if role not in member.roles:
        await interaction.response.send_message(f"{member.mention} does not have the **{role.name}** role.", ephemeral=True)
        return

    try:
        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(f"✅ Removed **{role.name}** from {member.mention}.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage roles!", ephemeral=True)


@moderation.command(
    name="purge",
    description="Delete a specified number of messages from a channel"
)
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(
    amount="Number of messages to delete (1 to 100)"
)
async def purge(
    interaction: discord.Interaction,
    amount: int
):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("Please provide a number between 1 and 100.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Successfully deleted **{len(deleted)}** message(s).", ephemeral=True)


# =====================================
# SERVER INFORMATION COMMANDS
# =====================================

server_group = app_commands.Group(
    name="server",
    description="Server information commands"
)


@server_group.command(
    name="info",
    description="Display information about this server"
)
async def server_info(interaction: discord.Interaction):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"{guild.name} - Server Information",
        color=discord.Color.blurple()
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Server ID", value=str(guild.id), inline=False)
    embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)
    embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=False)

    await interaction.response.send_message(embed=embed)


# =====================================
# USER & LEVELING COMMANDS
# =====================================

user_group = app_commands.Group(
    name="user",
    description="User information and leveling commands"
)


@user_group.command(
    name="info",
    description="Display information about a server member"
)
@app_commands.describe(
    member="The member to check (leave blank to check yourself)"
)
async def user_info(
    interaction: discord.Interaction,
    member: discord.Member = None
):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    target = member or interaction.user

    embed = discord.Embed(
        title=f"User Info - {target}",
        color=target.color if target.color != discord.Color.default() else discord.Color.blurple()
    )

    if target.avatar:
        embed.set_thumbnail(url=target.avatar.url)

    embed.add_field(name="Mention", value=target.mention, inline=True)
    embed.add_field(name="User ID", value=str(target.id), inline=True)
    embed.add_field(name="Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:D>" if target.joined_at else "Unknown", inline=False)
    embed.add_field(name="Joined Discord", value=f"<t:{int(target.created_at.timestamp())}:D>", inline=False)

    roles = [role.mention for role in target.roles if role != guild.default_role]
    roles_str = ", ".join(roles) if roles else "None"
    
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_str[:1024], inline=False)

    await interaction.response.send_message(embed=embed)


@user_group.command(
    name="level",
    description="Check your current level and XP progress"
)
@app_commands.describe(
    member="The member to check (leave blank to check yourself)"
)
async def user_level(
    interaction: discord.Interaction,
    member: discord.Member = None
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
        return

    target = member or interaction.user
    data = load_data(LEVEL_FILE)
    guild_id = str(guild.id)
    user_id = str(target.id)

    user_stats = data.get(guild_id, {}).get(user_id, {"xp": 0, "level": 1})
    current_level = user_stats["level"]
    current_xp = user_stats["xp"]
    xp_needed = int(100 * (current_level ** 1.5))

    embed = discord.Embed(
        title=f"⭐ Rank Stats — {target.name}",
        color=discord.Color.gold()
    )
    if target.avatar:
        embed.set_thumbnail(url=target.avatar.url)

    embed.add_field(name="Level", value=str(current_level), inline=True)
    embed.add_field(name="XP Progress", value=f"{current_xp} / {xp_needed} XP", inline=True)
    
    await interaction.response.send_message(embed=embed)


# =====================================
# REGISTER COMMAND GROUPS
# =====================================

bot.tree.add_command(bot_group)
bot.tree.add_command(moderation)
bot.tree.add_command(server_group)
bot.tree.add_command(user_group)


# =====================================
# EMERGENCY INSTANT SYNC COMMAND (PREFIX)
# =====================================

@bot.command(name="sync")
async def sync_commands(ctx):
    if ctx.author.id == OWNER_ID:
        synced = await bot.tree.sync()
        await ctx.send(f"Successfully synced {len(synced)} global commands instantly!")
    else:
        await ctx.send("You don't have permission to use this command.")


# =====================================
# BOT STARTUP
# =====================================

@bot.event
async def on_ready():
    # Sync global commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global commands!")
    except Exception as e:
        print(e)

    # Ensure log channel exists in all servers the bot is in
    for guild in bot.guilds:
        await get_or_create_log_channel(guild)

    print("--------------------------------")
    print(f"Bot online: {bot.user}")
    print("--------------------------------")


# =====================================
# START BOT
# =====================================

bot.run(TOKEN)