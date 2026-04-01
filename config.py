import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS").split(",")]

# TBC Pay (TBC Checkout / tpay)
TBC_APIKEY = os.getenv("TBC_APIKEY")  # Developer App apikey
TBC_CLIENT_ID = os.getenv("TBC_CLIENT_ID")  # merchant client_id
TBC_CLIENT_SECRET = os.getenv("TBC_CLIENT_SECRET")  # merchant client_secret

TBC_API_BASE = "https://api.tbcbank.ge"
TBC_TOKEN_ENDPOINT = "/v2/tpay/access-token"   # token endpoint
TBC_PAYMENTS_ENDPOINT = "/v1/tpay/payments"    # payments endpoint

# URLs (должны быть публичными HTTPS для callbackUrl)
TBC_RETURN_URL = os.getenv("TBC_RETURN_URL", "https://example.com/return")
TBC_CALLBACK_URL = os.getenv("TBC_CALLBACK_URL", "https://YOUR_DOMAIN/webhook/tbc")

IBAN_TBC = os.getenv("IBAN_TBC")
IBAN_BOG = os.getenv("IBAN_BOG")
RECIPIENT_NAME = os.getenv("RECIPIENT_NAME")