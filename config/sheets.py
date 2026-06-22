"""
config/sheets.py — koneksi ke Google Sheets via gspread (service account).

Kredensial dibaca dari .env (service account yang sama dengan program 01/02).
"""

import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _service_account_info() -> dict:
    client_email = os.getenv("GOOGLE_CLIENT_EMAIL", "")
    return {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID", ""),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID", ""),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
        "client_email": client_email,
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"
        + client_email.replace("@", "%40"),
        "universe_domain": "googleapis.com",
    }


def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(_service_account_info(), scopes=SCOPES)
    return gspread.authorize(creds)


# ID Sheet sumber (dari .env).
SHEET_IKLAN = os.getenv("SHEET_IKLAN", "")
SHEET_HARGA = os.getenv("SHEET_HARGA", "")
SHEET_KOMPETITOR = os.getenv("SHEET_KOMPETITOR", "")
