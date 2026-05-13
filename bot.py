"""
Discord Channel Cleaner Bot
============================
Automatycznie czyści wiadomości na wybranych kanałach według harmonogramu.
Konfiguracja w pliku config.py
"""
 
import discord
from discord.ext import commands, tasks
from datetime import datetime
import logging
import sys
import config
 
# ──────────────────────────────────────────────
#  Logging
# ──────────────────────────────────────────────
 
log_handlers = [logging.StreamHandler(sys.stdout)]
 
if config.LOG_TO_FILE:
    log_handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=log_handlers,
)
log = logging.getLogger("cleaner-bot")
 
# ──────────────────────────────────────────────
#  Bot setup
# ──────────────────────────────────────────────
 
intents = discord.Intents.default()
intents.message_content = True
 
bot = commands.Bot(
    command_prefix=config.PREFIX,
    intents=intents,
    help_command=None,
)
 
# ──────────────────────────────────────────────
#  Stan bota
# ──────────────────────────────────────────────
 
harmonogram_aktywny = True  # domyślnie włączony
 
# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
 
async def wyczysc_kanal(kanal: discord.TextChannel) -> int:
    """Usuwa wiadomości z jednego kanału. Zwraca liczbę usuniętych wiadomości."""
    usuniete_lacznie = 0
 
    while True:
        batch = await kanal.purge(limit=config.BATCH_SIZE, bulk=True)
        usuniete_lacznie += len(batch)
 
        if len(batch) < config.BATCH_SIZE:
            break  # koniec wiadomości
 
        if config.MAX_MESSAGES and usuniete_lacznie >= config.MAX_MESSAGES:
            break
 
    return usuniete_lacznie
 
 
async def wykonaj_czyszczenie(source: str = "harmonogram"):
    """Czyści wszystkie skonfigurowane kanały."""
    log.info(f"=== START CZYSZCZENIA ({source}) ===")
    total = 0
 
    for kanal_id in config.CHANNEL_IDS:
        kanal = bot.get_channel(kanal_id)
 
        if kanal is None:
            log.warning(f"Kanał ID {kanal_id} – nie znaleziono (sprawdź ID lub uprawnienia bota)")
            continue
 
        try:
            n = await wyczysc_kanal(kanal)
            total += n
            log.info(f"  ✓ #{kanal.name} ({kanal.guild.name}) – usunięto {n} wiad.")
        except discord.Forbidden:
            log.error(f"  ✗ #{kanal.name} – brak uprawnień 'Manage Messages'!")
        except discord.HTTPException as e:
            log.error(f"  ✗ #{kanal.name} – błąd API: {e}")
 
    log.info(f"=== KONIEC CZYSZCZENIA | Łącznie: {total} wiadomości ===\n")
    return total
 
# ──────────────────────────────────────────────
#  Zaplanowane zadanie
# ──────────────────────────────────────────────
 
@tasks.loop(time=config.CLEAN_TIME)
async def harmonogram():
    if harmonogram_aktywny:
        await wykonaj_czyszczenie(source="harmonogram")
    else:
        log.info("Harmonogram jest wyłączony – pomijam czyszczenie.")
 
 
@harmonogram.before_loop
async def przed_harmonogramem():
    await bot.wait_until_ready()
 
# ──────────────────────────────────────────────
#  Eventy
# ──────────────────────────────────────────────
 
@bot.event
async def on_ready():
    log.info(f"Bot zalogowany: {bot.user} (ID: {bot.user.id})")
    log.info(f"Kanały do czyszczenia: {config.CHANNEL_IDS}")
    log.info(f"Godzina czyszczenia (UTC): {config.CLEAN_TIME}")
    harmonogram.start()
    log.info("Harmonogram aktywny.\n")
 
 
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ Nie masz uprawnień do tej komendy.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # ignoruj nieznane komendy
    else:
        log.error(f"Błąd komendy '{ctx.command}': {error}")
        await ctx.reply(f"❌ Wystąpił błąd: `{error}`")
 
# ──────────────────────────────────────────────
#  Komendy
# ──────────────────────────────────────────────
 
@bot.command(name="wlacz", aliases=["enable", "start"])
@commands.has_permissions(manage_messages=True)
async def cmd_wlacz(ctx):
    """Włącza automatyczne czyszczenie według harmonogramu."""
    global harmonogram_aktywny
    if harmonogram_aktywny:
        await ctx.send("✅ Harmonogram jest już **włączony**.")
    else:
        harmonogram_aktywny = True
        log.info(f"Harmonogram włączony przez {ctx.author}")
        await ctx.send("✅ Harmonogram **włączony**! Bot będzie czyścił kanały automatycznie.")
 
 
@bot.command(name="wylacz", aliases=["disable", "stop"])
@commands.has_permissions(manage_messages=True)
async def cmd_wylacz(ctx):
    """Wyłącza automatyczne czyszczenie według harmonogramu."""
    global harmonogram_aktywny
    if not harmonogram_aktywny:
        await ctx.send("⛔ Harmonogram jest już **wyłączony**.")
    else:
        harmonogram_aktywny = False
        log.info(f"Harmonogram wyłączony przez {ctx.author}")
        await ctx.send("⛔ Harmonogram **wyłączony**! Bot nie będzie czyścił kanałów automatycznie.\nUżyj `!wlacz` żeby włączyć ponownie.")
 
 
@bot.command(name="wyczysc", aliases=["clean", "purge"])
@commands.has_permissions(manage_messages=True)
async def cmd_wyczysc(ctx):
    """Ręcznie uruchamia czyszczenie wszystkich kanałów."""
    msg = await ctx.send("🧹 Czyszczenie w toku...")
    total = await wykonaj_czyszczenie(source=f"komenda ({ctx.author})")
    await msg.edit(content=f"✅ Gotowe! Usunięto **{total}** wiadomości.")
 
 
@bot.command(name="status")
@commands.has_permissions(manage_messages=True)
async def cmd_status(ctx):
    """Wyświetla aktualną konfigurację bota."""
    kanaly = []
    for cid in config.CHANNEL_IDS:
        ch = bot.get_channel(cid)
        kanaly.append(f"• `{cid}` – {'#' + ch.name if ch else '❌ nie znaleziono'}")
 
    embed = discord.Embed(
        title="🤖 Discord Cleaner Bot – status",
        color=0x23a559 if harmonogram_aktywny else 0xf23f42,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Harmonogram", value="✅ Włączony" if harmonogram_aktywny else "⛔ Wyłączony", inline=True)
    embed.add_field(name="Godzina czyszczenia (UTC)", value=str(config.CLEAN_TIME), inline=True)
    embed.add_field(name="Limit wiad./kanał", value=str(config.MAX_MESSAGES or "bez limitu"), inline=True)
    embed.add_field(name="Batch size", value=str(config.BATCH_SIZE), inline=True)
    embed.add_field(name=f"Kanały ({len(config.CHANNEL_IDS)})", value="\n".join(kanaly) or "brak", inline=False)
    embed.set_footer(text=f"Prefix: {config.PREFIX}")
    await ctx.send(embed=embed)
 
 
@bot.command(name="pomoc", aliases=["help"])
async def cmd_pomoc(ctx):
    """Wyświetla listę komend."""
    embed = discord.Embed(title="📋 Komendy bota", color=0x5865F2)
    embed.add_field(
        name=f"`{config.PREFIX}wyczysc`",
        value="Ręcznie czyści wszystkie skonfigurowane kanały.",
        inline=False,
    )
    embed.add_field(
        name=f"`{config.PREFIX}wlacz`",
        value="Włącza automatyczne czyszczenie według harmonogramu.",
        inline=False,
    )
    embed.add_field(
        name=f"`{config.PREFIX}wylacz`",
        value="Wyłącza automatyczne czyszczenie według harmonogramu.",
        inline=False,
    )
    embed.add_field(
        name=f"`{config.PREFIX}status`",
        value="Pokazuje aktualną konfigurację i stan harmonogramu.",
        inline=False,
    )
    embed.add_field(
        name=f"`{config.PREFIX}pomoc`",
        value="Wyświetla tę wiadomość.",
        inline=False,
    )
    embed.set_footer(text="Komendy wymagają uprawnienia 'Manage Messages' (oprócz !pomoc)")
    await ctx.send(embed=embed)
 
# ──────────────────────────────────────────────
#  Start
# ──────────────────────────────────────────────
 
if __name__ == "__main__":
    if not config.TOKEN or config.TOKEN == "TWÓJ_TOKEN_TUTAJ":
        log.critical("TOKEN nie jest ustawiony w config.py! Bot nie wystartuje.")
        sys.exit(1)
 
    if not config.CHANNEL_IDS:
        log.warning("Brak kanałów w CHANNEL_IDS – bot nie będzie nic czyścił.")
 
    bot.run(config.TOKEN, log_handler=None)