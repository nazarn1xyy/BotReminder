#!/usr/bin/env python3
"""Set Telegram webhook"""

import httpx
import sys

BOT_TOKEN = "8926447955:AAEKjSAYuaAFg-8VdS5YBVYNavMwt10QrNM"
WEBHOOK_URL = "https://bot-reminder.vercel.app/api/index"

def set_webhook():
    """Set webhook for Telegram bot"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"

    response = httpx.post(url, json={"url": WEBHOOK_URL})

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    return response.json()

def get_webhook_info():
    """Get webhook info"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"

    response = httpx.get(url)

    print(f"\nWebhook Info:")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

    return response.json()

if __name__ == "__main__":
    print("Setting webhook...")
    set_webhook()
    print("\n" + "="*50)
    get_webhook_info()
