"""
One-time Telegram session setup script.

Run this ONCE locally to generate a session string:
  python backend/telegram_setup.py

It will:
  1. Ask for your phone number
  2. Send a Telegram OTP to your account
  3. Ask you to enter the OTP
  4. Print the SESSION_STRING

Copy the SESSION_STRING and add it to:
  - backend/.env  →  TELEGRAM_SESSION_STRING=<string>
  - Render env    →  TELEGRAM_SESSION_STRING=<string>

You never need to run this again unless you log out of Telegram
or the session expires.
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


async def main():
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("ERROR: telethon not installed.\nRun: pip install telethon")
        return

    api_id   = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()

    if not api_id or not api_hash:
        print("\nTELEGRAM_API_ID and TELEGRAM_API_HASH must be set in backend/.env first.")
        print("Get them from: https://my.telegram.org → API Development Tools\n")
        return

    print("\n=== Rhino Drishti — Telegram Session Setup ===\n")
    print("This will log into Telegram using your personal account.")
    print("Your credentials are NEVER stored — only a session token is saved.\n")

    client = TelegramClient(StringSession(), int(api_id), api_hash)

    await client.start()  # prompts for phone + OTP interactively

    session_string = client.session.save()
    await client.disconnect()

    print("\n" + "=" * 60)
    print("SUCCESS! Copy this session string into your .env and Render:")
    print("=" * 60)
    print(f"\nTELEGRAM_SESSION_STRING={session_string}\n")
    print("=" * 60)

    # Optionally write directly to .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if "TELEGRAM_SESSION_STRING=" in content:
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith("TELEGRAM_SESSION_STRING="):
                    new_lines.append(f"TELEGRAM_SESSION_STRING={session_string}")
                else:
                    new_lines.append(line)
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print("\n✅ Automatically updated TELEGRAM_SESSION_STRING in backend/.env")
        else:
            print("\nAdd the above line to backend/.env manually.")


if __name__ == "__main__":
    asyncio.run(main())
