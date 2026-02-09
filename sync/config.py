"""
Configuration from environment variables.
Use in Railway or .env for local runs.
"""
import os
from pathlib import Path

# Cargar .env si existe (para pruebas locales)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Remitos API (costos de materiales) ---
REMITOS_API_URL = os.environ.get(
    "REMITOS_API_URL",
    "https://642f0538ae6d.sn.mynetname.net:5010/api/Remitos",
)
REMITOS_BEARER_TOKEN = os.environ.get("REMITOS_BEARER_TOKEN", "")

# --- Google Drive (CSV mano de obra) ---
DRIVE_FOLDER_ID_MANO_OBRA = os.environ.get(
    "DRIVE_FOLDER_ID_MANO_OBRA",
    "1iEuqLWPnE8i-XJWPp-CF1B1r-X-5-yDu",
)

# --- Carpeta de destino (Sync - Costos Materiales & Mano de Obra) ---
DRIVE_FOLDER_ID_SYNC = os.environ.get(
    "DRIVE_FOLDER_ID_SYNC",
    "1ATAyoexZYqlpYbcn3md27zo1NLezdsb5",
)

# --- Google Sheets (destino publish, dentro de esa carpeta) ---
# Costos de Materiales / Sistema Interno
SHEET_ID_MATERIALES = os.environ.get(
    "SHEET_ID_MATERIALES",
    "16rVICcrR5LyNn5VEgxehkYs9E7gIe6fbyP1covq2s14",
)
# GNS - Costos de Mano de Obra
SHEET_ID_MANO_OBRA = os.environ.get(
    "SHEET_ID_MANO_OBRA",
    "1KdhF5-q6WKRKkwyrh4LhK0itm-DDyQc6TH7eJ2dKihU",
)

# Service account JSON (content as string or path to file)
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH",
    str(Path(__file__).resolve().parents[1] / "credentials" / "service_account.json"),
)


def get_google_credentials():
    """Return credentials for gspread/Drive: dict or path."""
    if GOOGLE_CREDENTIALS_JSON.strip():
        import json
        return json.loads(GOOGLE_CREDENTIALS_JSON)
    path = Path(GOOGLE_CREDENTIALS_PATH)
    if not path.is_absolute():
        # Resolver relativamente a la raíz del proyecto (carpeta donde está sync/)
        root = Path(__file__).resolve().parents[1]
        path = (root / path).resolve()
    if path.exists():
        return str(path)
    return None
