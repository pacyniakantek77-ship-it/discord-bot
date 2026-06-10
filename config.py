"""
config.py – Konfiguracja Discord Cleaner Bot
=============================================
Tutaj zmieniasz WSZYSTKIE ustawienia bota.
Nie musisz dotykać pliku bot.py.
"""

from datetime import time

# ══════════════════════════════════════════════════════════════
#  1. TOKEN BOTA
#     Pobierz na: https://discord.com/developers/applications
#     Zakładka: Bot → Reset Token
# ══════════════════════════════════════════════════════════════

import os
TOKEN = os.environ.get("TOKEN", "")

# ══════════════════════════════════════════════════════════════
#  2. KANAŁY DO CZYSZCZENIA
#
#  Jak znaleźć ID kanału:
#    1. Otwórz Ustawienia Discorda → Zaawansowane → włącz "Tryb dewelopera"
#    2. Kliknij prawym przyciskiem na kanał → "Kopiuj ID"
#
#  Dodaj tyle kanałów ile chcesz, każdy w nowej linii.
# ══════════════════════════════════════════════════════════════

CHANNEL_IDS = [
    1503410241428258857,  # #💬ᴏɢᴏ́ʟɴʏ💬
    1503410582299086850,  # #🦾ʙᴏᴛʏ🦾
    1503411820457627779,  # #🎵ᴍᴜᴢʏᴋᴀ🎵
    # 444555666777888999,  # <- odkomentuj żeby dodać kolejny
]

# ══════════════════════════════════════════════════════════════
#  3. GODZINA CZYSZCZENIA
#
#  Czas podawaj w UTC (skoordynowany czas światowy).
#  Polska strefa czasowa:
#    Zima (CET):  UTC+1  →  północ PL = 24:00 UTC
#    Lato (CEST): UTC+2  →  północ PL = 24:00 UTC
#
#  Przykłady:
#    time(hour=23, minute=0)   → 00:00 czasu polskiego (zima)
#    time(hour=22, minute=0)   → 00:00 czasu polskiego (lato)
#    time(hour=12, minute=30)  → 14:30 czasu polskiego (zima)
# ══════════════════════════════════════════════════════════════

CLEAN_TIME = time(hour=23, minute=0, second=0)  # 00:00 PL (zima)

# ══════════════════════════════════════════════════════════════
#  4. LIMIT WIADOMOŚCI
#
#  MAX_MESSAGES  – maksymalna liczba wiadomości do usunięcia
#                  na kanał w jednym czyszczeniu.
#                  Ustaw None żeby usuwać WSZYSTKIE.
#
#  BATCH_SIZE    – ile wiadomości pobierać na raz (max 100).
#                  Zmniejsz jeśli bot dostaje błędy rate-limit.
#
#  UWAGA: Discord nie pozwala usuwać wiadomości starszych
#         niż 14 dni przez API bots (ograniczenie platformy).
# ══════════════════════════════════════════════════════════════

MAX_MESSAGES = None   # None = wszystkie | np. 500 = max 500
BATCH_SIZE   = 100    # zalecane: 100

# ══════════════════════════════════════════════════════════════
#  5. POZOSTAŁE USTAWIENIA
# ══════════════════════════════════════════════════════════════

PREFIX      = "!"      # Prefix komend, np. !wyczysc
LOG_TO_FILE = True     # True = logi zapisywane też do bot.log

# ══════════════════════════════════════════════════════════════
#  6. KANAŁ DOCELOWY (PRZEPISYWANIE)
#
#  ID kanału na który bot będzie przepisywał wiadomości
#  z kanałów w CHANNEL_IDS (przez webhook, jako klon oryginału).
#  Znajdź ID tak samo jak wyżej (Tryb dewelopera → Kopiuj ID).
# ══════════════════════════════════════════════════════════════

LOG_CHANNEL_ID = 1513944310041804853

