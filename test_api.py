#!/usr/bin/env python3
"""Test bot API endpoint"""

import httpx
import json

# Test GET request
print("Testing GET request...")
response = httpx.get("https://bot-reminder.vercel.app/api")
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
print()

# Test POST request (simulate Telegram update)
print("Testing POST request with /start command...")
test_update = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {
            "id": 123456,
            "is_bot": False,
            "first_name": "Test",
            "username": "testuser"
        },
        "chat": {
            "id": 123456,
            "first_name": "Test",
            "username": "testuser",
            "type": "private"
        },
        "date": 1234567890,
        "text": "/start"
    }
}

response = httpx.post(
    "https://bot-reminder.vercel.app/api",
    json=test_update,
    timeout=30.0
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
