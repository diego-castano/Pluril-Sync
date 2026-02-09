"""
Sync costos de mano de obra: último CSV del último mes en Drive → Google Sheet.
El CSV tiene columna idObr para separar por obra.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .config import (
    DRIVE_FOLDER_ID_MANO_OBRA,
    SHEET_ID_MANO_OBRA,
    get_google_credentials,
)

# Patrón: Costos_MM_YYYY.CSV (o .csv)
CSV_PATTERN = re.compile(r"Costos_(\d{2})_(\d{4})\.csv$", re.IGNORECASE)

# Nombre de la hoja donde se acumulan los costos de mano de obra
SHEET_NAME_MANO_OBRA = "Mano de obra"


def _get_drive_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = get_google_credentials()
    if not creds:
        raise ValueError("Credenciales Google no configuradas")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    if isinstance(creds, dict):
        credentials = Credentials.from_service_account_info(creds, scopes=scopes)
    else:
        credentials = Credentials.from_service_account_file(creds, scopes=scopes)
    return build("drive", "v3", credentials=credentials)


def list_csv_files_in_folder(folder_id: Optional[str] = None) -> List[dict]:
    """
    Lista archivos CSV en la carpeta de mano de obra.
    Retorna lista de {"id", "name", "modifiedTime", "year", "month"} ordenada por (año, mes) desc.
    """
    fid = folder_id or DRIVE_FOLDER_ID_MANO_OBRA
    drive = _get_drive_service()
    results = (
        drive.files()
        .list(
            q=f"'{fid}' in parents and mimeType='text/csv'",
            fields="files(id,name,modifiedTime)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    files = results.get("files", [])
    out = []
    for f in files:
        name = f.get("name") or ""
        m = CSV_PATTERN.search(name)
        if m:
            month, year = int(m.group(1)), int(m.group(2))
            out.append({
                "id": f["id"],
                "name": name,
                "modifiedTime": f.get("modifiedTime") or "",
                "year": year,
                "month": month,
            })
    # Ordenar por (año, mes) descendente para tomar el "último mes"
    out.sort(key=lambda x: (x["year"], x["month"]), reverse=True)
    return out


def get_latest_month_csv(folder_id: Optional[str] = None) -> Optional[dict]:
    """
    Devuelve el archivo CSV del último mes (el más reciente por año/mes).
    Si hay varios del mismo mes, queda el primero de la lista (ya ordenada por modifiedTime).
    """
    files = list_csv_files_in_folder(folder_id)
    if not files:
        return None
    # Agrupar por (year, month) y quedarnos con el más reciente (modifiedTime) de ese mes
    best = None
    best_key = None
    for f in files:
        key = (f["year"], f["month"])
        if best_key is None or key > best_key:
            best_key = key
            best = f
    return best


def download_csv_file(file_id: str) -> str:
    """Descarga el contenido de un archivo de Drive por ID (CSV como texto)."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    creds = get_google_credentials()
    if not creds:
        raise ValueError("Credenciales Google no configuradas")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    if isinstance(creds, dict):
        credentials = Credentials.from_service_account_info(creds, scopes=scopes)
    else:
        credentials = Credentials.from_service_account_file(creds, scopes=scopes)
    drive = build("drive", "v3", credentials=credentials)
    request = drive.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf.read().decode("utf-8-sig")  # CSV a veces tiene BOM


def parse_csv_content(content: str) -> Tuple[List[str], List[list]]:
    """
    Parsea el CSV y retorna (headers, rows).
    Verifica que exista columna idObr (case-insensitive).
    """
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    # Verificar que exista columna idObr (o id_obr / variantes)
    headers_lower = [h.lower().replace(" ", "") for h in headers]
    if "idobr" not in headers_lower and "id_obr" not in headers_lower:
        if not any("id" in h and "obr" in h for h in headers_lower):
            raise ValueError(
                f"Columna idObr no encontrada en el CSV. Columnas: {headers}"
            )
    return headers, data_rows


def sync_mano_obra(sheet_id: Optional[str] = None, folder_id: Optional[str] = None) -> dict:
    """
    Toma el último CSV del último mes en la carpeta Drive, lo parsea
    y añade las filas al Google Sheet de mano de obra (append).
    Retorna {"ok": bool, "rows_written": int, "file_name": str, "error": str opcional}.
    """
    sid = sheet_id or SHEET_ID_MANO_OBRA
    if not sid:
        return {
            "ok": False,
            "rows_written": 0,
            "file_name": "",
            "error": "SHEET_ID_MANO_OBRA no configurado",
        }

    creds = get_google_credentials()
    if not creds:
        return {
            "ok": False,
            "rows_written": 0,
            "file_name": "",
            "error": "Credenciales Google no configuradas",
        }

    info = get_latest_month_csv(folder_id)
    if not info:
        return {
            "ok": False,
            "rows_written": 0,
            "file_name": "",
            "error": "No se encontró ningún CSV Costos_MM_YYYY en la carpeta",
        }

    content = download_csv_file(info["id"])
    headers, data_rows = parse_csv_content(content)

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
        sheet = doc.worksheet(SHEET_NAME_MANO_OBRA)
    except gspread.WorksheetNotFound:
        sheet = doc.add_worksheet(
            title=SHEET_NAME_MANO_OBRA, rows=2000, cols=len(headers) + 2
        )
        sheet.append_row(["Periodo"] + headers)  # columna extra para mes/año

    existing = sheet.get_all_values()
    # Si está vacío o sin header, escribir header con columna Periodo
    header_row = ["Periodo"] + headers
    if not existing or existing[0] != header_row:
        if not existing:
            sheet.append_row(header_row)

    # Añadir filas con periodo = MM/YYYY
    periodo = f"{info['month']:02d}/{info['year']}"
    new_rows = [[periodo] + row for row in data_rows]
    sheet.append_rows(new_rows, value_input_option="USER_ENTERED")

    return {
        "ok": True,
        "rows_written": len(new_rows),
        "file_name": info["name"],
        "periodo": periodo,
    }
