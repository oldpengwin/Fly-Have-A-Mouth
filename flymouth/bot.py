"""Discord bot: get pinged, and a small slash-command control panel.

Pings (in the watched text channel):
  @FlyHaveAMouth            -> a typing request (RNG 1-10 words), fly's real brain.
  @FlyHaveAMouth poke       -> tap the glass (startle the fly), not a request.

Control panel (needs Manage Server; set live, persisted to settings.json):
  /fly watch  #text-channel     which channel the fly listens in
  /fly vc     voice-channel      which voice channel the bot joins (+ joins it)
  /fly join                      join the configured voice channel
  /fly leave                     leave voice
  /fly status                    show config, brain, queue

Joining a VC just puts the bot in the channel (voice presence). It does NOT
stream the fly video -- that's your screen-share / Go-Live of the web viewer.
"""

from __future__ import annotations

import asyncio
import re

import discord
from discord import app_commands
from discord.ext import commands

from .controller import MouthController, Request
from .settings import Settings


def make_bot(controller: MouthController, cfg, settings: Settings):
    intents = discord.Intents.default()
    intents.message_content = True      # privileged -- enable in the Dev Portal
    intents.voice_states = True
    bot = commands.Bot(command_prefix="!fly ", intents=intents)

    def _strip_mentions(msg):
        return re.sub(r"<@!?\d+>", "", msg.content or "").strip().lower()

    async def _join_voice(guild: discord.Guild):
        """Connect (or move) to the configured voice channel of this guild."""
        vc_id = settings.voice_channel_id
        if not vc_id:
            return None, "no voice channel set -- use /fly vc first"
        ch = guild.get_channel(vc_id)
        if not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            return None, f"channel {vc_id} isn't a voice channel in this server"
        existing = guild.voice_client
        try:
            if existing and existing.is_connected():
                await existing.move_to(ch)
            else:
                await ch.connect()
            return ch, None
        except discord.ClientException as e:
            return None, str(e)
        except Exception as e:  # PyNaCl missing, perms, etc.
            return None, f"couldn't join voice ({e}). Is PyNaCl installed?"

    # ---- lifecycle ------------------------------------------------------
    @bot.event
    async def on_ready():
        watch = settings.watch_channel_id or "any channel"
        print(f"[bot] logged in as {bot.user} | watching {watch} | brain: {controller.brain.label}")
        # per-guild sync = slash commands show up immediately
        for g in bot.guilds:
            try:
                bot.tree.copy_global_to(guild=g)
                await bot.tree.sync(guild=g)
            except Exception as e:
                print(f"[bot] slash sync failed for {g}: {e}")
        if settings.voice_channel_id:
            for g in bot.guilds:
                ch, err = await _join_voice(g)
                if ch:
                    print(f"[bot] joined voice: {ch.name}")

    @bot.event
    async def on_message(msg: discord.Message):
        if msg.author.bot or bot.user is None:
            return
        if settings.watch_channel_id and msg.channel.id != settings.watch_channel_id:
            return
        if bot.user not in msg.mentions:
            return
        rest = _strip_mentions(msg)
        name = msg.author.display_name

        if rest.startswith(cfg.POKE_KEYWORD):
            controller.poke(name)
            try:
                await msg.add_reaction("\U0001FAB0")
            except Exception:
                pass
            await msg.channel.send(f"*{name} taps the glass — the fly panics briefly* \U0001FAB0")
            return

        busy = controller.is_busy()
        pos = controller.submit(Request(name, msg.author.id, msg.channel.id))
        if not busy and pos == 0:
            await msg.channel.send(f"\U0001FAB0 the fly turns to the keyboard for {name}…")
        elif pos == 0:
            await msg.channel.send(f"\U0001FAB0 you're next, {name} — the fly is finishing up.")
        else:
            await msg.channel.send(f"\U0001FAB0 the fly is busy — {name}, you're #{pos} in line.")

    # ---- slash control panel -------------------------------------------
    fly = app_commands.Group(name="fly", description="Configure the fly bot",
                             default_permissions=discord.Permissions(manage_guild=True))

    @fly.command(name="watch", description="Set the text channel the fly listens for pings in")
    @app_commands.describe(channel="Text channel to watch")
    async def fly_watch(inter: discord.Interaction, channel: discord.TextChannel):
        settings.set_watch(channel.id)
        await inter.response.send_message(f"\U0001FAB0 now listening for pings in {channel.mention}.", ephemeral=True)

    @fly.command(name="vc", description="Set (and join) the voice channel the bot sits in")
    @app_commands.describe(channel="Voice channel to join")
    async def fly_vc(inter: discord.Interaction, channel: discord.VoiceChannel):
        settings.set_voice(channel.id)
        await inter.response.defer(ephemeral=True)
        ch, err = await _join_voice(inter.guild)
        if ch:
            await inter.followup.send(f"\U0001FAB0 voice channel set to **{channel.name}** and joined it.", ephemeral=True)
        else:
            await inter.followup.send(f"\U0001FAB0 voice channel set to **{channel.name}**, but couldn't join: {err}", ephemeral=True)

    @fly.command(name="join", description="Join the configured voice channel")
    async def fly_join(inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        ch, err = await _join_voice(inter.guild)
        await inter.followup.send(f"\U0001FAB0 joined **{ch.name}**." if ch else f"\U0001FAB0 {err}", ephemeral=True)

    @fly.command(name="leave", description="Leave the voice channel")
    async def fly_leave(inter: discord.Interaction):
        vc = inter.guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect(force=False)
            await inter.response.send_message("\U0001FAB0 left voice.", ephemeral=True)
        else:
            await inter.response.send_message("\U0001FAB0 not in a voice channel.", ephemeral=True)

    @fly.command(name="status", description="Show the fly's current config and state")
    async def fly_status(inter: discord.Interaction):
        s = controller.state
        watch = f"<#{settings.watch_channel_id}>" if settings.watch_channel_id else "any channel"
        voice = f"<#{settings.voice_channel_id}>" if settings.voice_channel_id else "not set"
        connected = bool(inter.guild.voice_client and inter.guild.voice_client.is_connected())
        await inter.response.send_message(
            f"\U0001FAB0 **fly status**\n"
            f"brain: `{controller.brain.label}`\n"
            f"listening in: {watch}\n"
            f"voice channel: {voice} ({'connected' if connected else 'not connected'})\n"
            f"mode: `{s.mode}`  queue: `{s.queue_len}`\n"
            f"viewer: `http://{cfg.WEB_HOST}:{cfg.WEB_PORT}` (screen-share this into the VC)",
            ephemeral=True)

    bot.tree.add_command(fly)

    async def completion_poster():
        await bot.wait_until_ready()
        loop = asyncio.get_running_loop()
        while not bot.is_closed():
            comp = await loop.run_in_executor(None, controller.completions.get)
            channel = bot.get_channel(comp.channel_id)
            if channel is None:
                try:
                    channel = await bot.fetch_channel(comp.channel_id)
                except Exception:
                    continue
            await channel.send(
                f"\U0001FAB0 <@{comp.requester_id}> the fly's brain legibly typed "
                f"**{comp.word_count}** word(s):\n> {comp.sentence}\n"
                f"*(the bowl is full. good fly.)*")

    return bot, completion_poster
