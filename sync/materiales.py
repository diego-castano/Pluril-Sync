"""
Sync costos de materiales: API Remitos → Google Sheet.
Cada documento tiene CUENTA + DESCCUENTA = obra; el sheet se organiza por obra.
"""
from __future__ import annotations

import ssl
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from typing import List, Optional

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .config import (
    REMITOS_API_URL,
    REMITOS_BEARER_TOKEN,
    SHEET_ID_MATERIALES,
    get_google_credentials,
)

# Moneda: 1 = pesos, 2 = dólares
MONEDA_LABEL = {1: "Pesos", 2: "Dólares"}

# Nombre de la hoja donde escribimos (una sola hoja con todos los documentos, columna Obra)
SHEET_NAME_MATERIALES = "Materiales"


def _remitos_ssl_context() -> ssl.SSLContext:
    """Contexto SSL para API Remitos: TLS 1.0+ y sin verificación (servidor legacy)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1
    return ctx


class _TLSCompatAdapter(HTTPAdapter):
    """Adapter para API Remitos usando contexto sin verificación."""

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = _remitos_ssl_context()
        return super().init_poolmanager(*args, **kwargs)


def fetch_remitos(from_date: str, to_date: str) -> List[dict]:
    """
    Llama a la API Remitos y devuelve la lista de documentos.
    from_date / to_date: YYYY-MM-DD
    El servidor Remitos puede usar TLS antiguo; usamos un adapter que lo permite.
    """
    if not REMITOS_BEARER_TOKEN:
        raise ValueError("REMITOS_BEARER_TOKEN no configurado")
    url = REMITOS_API_URL.strip()
    if "?" in url:
        url += "&"
    else:
        url += "?"
    url += f"fromDate={from_date}&toDate={to_date}"
    session = requests.Session()
    session.mount("https://", _TLSCompatAdapter())
    # Verificación desactivada en el adapter (CERT_NONE + check_hostname=False)
    resp = session.get(
        url,
        headers={"Authorization": f"Bearer {REMITOS_BEARER_TOKEN}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    documentos = data.get("documentos") or []
    return documentos


def documentos_to_rows(documentos: List[dict]) -> List[list]:
    """
    Convierte documentos API en filas para el Sheet.
    Incluye columna Obra (DESCCUENTA) y Cuenta para separación por obra.
    """
    rows = []
    for d in documentos:
        fecha = d.get("FECHA") or ""
        if fecha and "T" in str(fecha):
            fecha = str(fecha).split("T")[0]
        moneda = d.get("MONEDA", 0)
        rows.append([
            fecha,
            (d.get("TIPDOCUM") or "").strip(),
            (d.get("SERIEDOCUM") or "").strip(),
            (d.get("NRODOCUM") or "").strip(),
            (d.get("CUENTA") or "").strip(),
            (d.get("DESCCUENTA") or "").strip(),  # Obra
            (d.get("DIRCUENTA") or "").strip(),
            d.get("TOTAL"),
            MONEDA_LABEL.get(moneda, str(moneda)),
        ])
    return rows


def get_headers_materiales() -> List[str]:
    return [
        "Fecha",
        "TipoDoc",
        "Serie",
        "NroDoc",
        "Cuenta",
        "Obra",
        "Direccion",
        "Total",
        "Moneda",
    ]


def sync_materiales(from_date: str, to_date: str, sheet_id: Optional[str] = None) -> dict:
    """
    Obtiene remitos del rango de fechas y escribe/actualiza el Google Sheet de materiales.
    sheet_id: opcional; si no se pasa usa SHEET_ID_MATERIALES.
    Retorna {"ok": bool, "rows_written": int, "error": str opcional}.
    """
    sid = sheet_id or SHEET_ID_MATERIALES
    if not sid:
        return {"ok": False, "rows_written": 0, "error": "SHEET_ID_MATERIALES no configurado"}

    creds = get_google_credentials()
    if not creds:
        return {"ok": False, "rows_written": 0, "error": "Credenciales Google no configuradas"}

    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if isinstance(creds, dict):
        credentials = Credentials.from_service_account_info(creds, scopes=scopes)
    else:
        credentials = Credentials.from_service_account_file(creds, scopes=scopes)

    client = gspread.authorize(credentials)
    doc = client.open_by_key(sid)
    try:
        sheet = doc.worksheet(SHEET_NAME_MATERIALES)
    except gspread.WorksheetNotFound:
        sheet = doc.add_worksheet(title=SHEET_NAME_MATERIALES, rows=1000, cols=len(get_headers_materiales()))
        sheet.append_row(get_headers_materiales())

    documentos = fetch_remitos(from_date, to_date)
    rows = documentos_to_rows(documentos)
    if not rows:
        return {"ok": True, "rows_written": 0}

    # Si la primera fila no son headers, insertar headers
    existing = sheet.get_all_values()
    if not existing or existing[0] != get_headers_materiales():
        sheet.clear()
        sheet.append_row(get_headers_materiales())
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    return {"ok": True, "rows_written": len(rows)}


def run_sync_materiales_month(year: int, month: int, sheet_id: Optional[str] = None) -> dict:
    """Helper: sincroniza un mes completo (primer y último día)."""
    from calendar import monthrange
    last = monthrange(year, month)[1]
    from_date = f"{year}-{month:02d}-01"
    to_date = f"{year}-{month:02d}-{last}"
    return sync_materiales(from_date, to_date, sheet_id)
