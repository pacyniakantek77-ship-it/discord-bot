"""
Discord Channel Cleaner Bot
============================
Automatycznie czyści wiadomości na wybranych kanałach według harmonogramu.
Przepisuje wiadomości z CHANNEL_IDS na kanał LOG_CHANNEL_ID przez webhook.
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
intents.members = True

bot = commands.Bot(
    command_prefix=config.PREFIX,
    intents=intents,
    help_command=None,
)

# ──────────────────────────────────────────────
#  Stan bota
# ──────────────────────────────────────────────

harmonogram_aktywny = True       # domyślnie włączony
przepisywanie_aktywne = True     # domyślnie włączone

# Cache webhooków: {kanal_id: discord.Webhook}
_webhook_cache: dict[int, discord.Webhook] = {}

# ──────────────────────────────────────────────
#  Webhook helpers
# ──────────────────────────────────────────────

async def pobierz_lub_stworz_webhook(kanal: discord.TextChannel) -> discord.Webhook | None:
    """Zwraca istniejący lub nowy webhook bota na podanym kanale."""
    if kanal.id in _webhook_cache:
        return _webhook_cache[kanal.id]

    try:
        webhooks = await kanal.webhooks()
        # szukaj webhooka stworzonego przez bota
        hook = discord.utils.get(webhooks, user=bot.user)
        if hook is None:
            hook = await kanal.create_webhook(name="Cleaner Mirror")
            log.info(f"Stworzono webhook na #{kanal.name}")
        _webhook_cache[kanal.id] = hook
        return hook
    except discord.Forbidden:
        log.error(f"Brak uprawnień do zarządzania webhookami na #{kanal.name}")
        return None
    except discord.HTTPException as e:
        log.error(f"Błąd tworzenia webhooka na #{kanal.name}: {e}")
        return None


async def przepisz_wiadomosc(wiadomosc: discord.Message) -> bool:
    """
    Przepisuje jedną wiadomość na kanał LOG_CHANNEL_ID przez webhook.
    Zwraca True jeśli się udało.
    """
    if not hasattr(config, "LOG_CHANNEL_ID") or not config.LOG_CHANNEL_ID:
        return False

    kanal_docelowy = bot.get_channel(config.LOG_CHANNEL_ID)
    if kanal_docelowy is None:
        log.warning(f"LOG_CHANNEL_ID ({config.LOG_CHANNEL_ID}) – kanał nie znaleziony!")
        return False

    hook = await pobierz_lub_stworz_webhook(kanal_docelowy)
    if hook is None:
        return False

    autor = wiadomosc.author
    avatar_url = autor.display_avatar.url if autor.display_avatar else None

    # Etykieta z nazwą kanału źródłowego
    nazwa_zrodla = f"#{wiadomosc.channel.name} ({wiadomosc.guild.name})" if wiadomosc.guild else f"#{wiadomosc.channel}"

    # Treść – jeśli pusta (np. sam attachment), zastąp spacją
    tresc = wiadomosc.content or ""

    # Dodaj małą stopkę z informacją o źródle
    if tresc:
        tresc_do_wyslania = f"{tresc}\n-# 📌 z {nazwa_zrodla}"
    else:
        tresc_do_wyslania = f"-# 📌 z {nazwa_zrodla}"

    # Zbierz pliki (attachments)
    files = []
    for attachment in wiadomosc.attachments:
        try:
            files.append(await attachment.to_file())
        except Exception:
            pass  # pomiń niedostępne pliki

    try:
        await hook.send(
            content=tresc_do_wyslania if tresc_do_wyslania.strip() else None,
            username=autor.display_name,
            avatar_url=avatar_url,
            files=files or discord.utils.MISSING,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True
    except discord.HTTPException as e:
        log.error(f"Błąd wysyłania przez webhook: {e}")
        return False


# ──────────────────────────────────────────────
#  Czyszczenie helpers
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
    log.info(f"Kanały do czyszczenia/przepisywania: {config.CHANNEL_IDS}")
    log.info(f"Kanał docelowy (LOG_CHANNEL_ID): {getattr(config, 'LOG_CHANNEL_ID', 'NIE USTAWIONY')}")
    log.info(f"Godzina czyszczenia (UTC): {config.CLEAN_TIME}")
    harmonogram.start()
    log.info("Harmonogram aktywny.\n")


@bot.event
async def on_message(message: discord.Message):
    """Przechwytuje nowe wiadomości i przepisuje je na kanał docelowy."""
    # Ignoruj wiadomości od botów (w tym od siebie) i webhooków
    if message.author.bot or message.webhook_id:
        await bot.process_commands(message)
        return

    # Przepisuj tylko z monitorowanych kanałów
    if przepisywanie_aktywne and message.channel.id in config.CHANNEL_IDS:
        sukces = await przepisz_wiadomosc(message)
        if sukces:
            log.info(
                f"Przepisano wiad. od {message.author} "
                f"z #{message.channel.name} → LOG_CHANNEL"
            )

    await bot.process_commands(message)


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


@bot.command(name="mirror_wlacz", aliases=["mirror_on"])
@commands.has_permissions(manage_messages=True)
async def cmd_mirror_wlacz(ctx):
    """Włącza przepisywanie wiadomości."""
    global przepisywanie_aktywne
    if przepisywanie_aktywne:
        await ctx.send("✅ Przepisywanie jest już **włączone**.")
    else:
        przepisywanie_aktywne = True
        log.info(f"Przepisywanie włączone przez {ctx.author}")
        await ctx.send("✅ Przepisywanie **włączone**! Wiadomości będą kopiowane na kanał docelowy.")


@bot.command(name="mirror_wylacz", aliases=["mirror_off"])
@commands.has_permissions(manage_messages=True)
async def cmd_mirror_wylacz(ctx):
    """Wyłącza przepisywanie wiadomości."""
    global przepisywanie_aktywne
    if not przepisywanie_aktywne:
        await ctx.send("⛔ Przepisywanie jest już **wyłączone**.")
    else:
        przepisywanie_aktywne = False
        log.info(f"Przepisywanie wyłączone przez {ctx.author}")
        await ctx.send("⛔ Przepisywanie **wyłączone**! Użyj `!mirror_wlacz` żeby włączyć ponownie.")


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

    log_ch_id = getattr(config, "LOG_CHANNEL_ID", None)
    log_ch = bot.get_channel(log_ch_id) if log_ch_id else None
    log_ch_str = f"#{log_ch.name}" if log_ch else (f"`{log_ch_id}` ❌ nie znaleziono" if log_ch_id else "❌ nie ustawiony")

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
        log.warning("Brak kanałów w CHANNEL_IDS – bot nie będzie nic czyścił/przepisywał.")

    if not getattr(config, "LOG_CHANNEL_ID", None):
        log.warning("LOG_CHANNEL_ID nie jest ustawiony w config.py – przepisywanie nie zadziała!")

    bot.run(config.TOKEN, log_handler=None)
