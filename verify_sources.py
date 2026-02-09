#!/usr/bin/env python3
"""
Verifica acceso a ambas fuentes:
1) API Remitos (costos materiales) — comprueba token y que la respuesta tenga documentos con CUENTA/DESCCUENTA.
2) Google Drive carpeta mano de obra — lista CSVs y opcionalmente descarga el último para comprobar columna idObr.

Uso:
  python verify_sources.py
  REMITOS_BEARER_TOKEN=xxx python verify_sources.py   # solo materiales
  (con GOOGLE_CREDENTIALS_JSON o GOOGLE_CREDENTIALS_PATH) para probar Drive.
"""
import os
import sys
from datetime import datetime, timedelta

def check_remitos():
    print("--- Costos materiales (API Remitos) ---")
    from sync.config import REMITOS_BEARER_TOKEN, REMITOS_API_URL
    if not REMITOS_BEARER_TOKEN:
        print("  REMITOS_BEARER_TOKEN no configurado. Saltando.")
        return False
    try:
        from sync.materiales import fetch_remitos
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=31)
        fd = from_date.strftime("%Y-%m-%d")
        td = to_date.strftime("%Y-%m-%d")
        docs = fetch_remitos(fd, td)
        print(f"  OK. Rango {fd} .. {td}: {len(docs)} documentos.")
        if docs:
            d = docs[0]
            has_cuenta = "CUENTA" in d and "DESCCUENTA" in d
            print(f"  Muestra: CUENTA={d.get('CUENTA')}, DESCCUENTA={d.get('DESCCUENTA')[:40]}...")
            print(f"  Separación por obra (CUENTA + DESCCUENTA): {'Sí' if has_cuenta else 'No'}")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def check_mano_obra():
    print("--- Costos mano de obra (Drive CSV) ---")
    from sync.config import DRIVE_FOLDER_ID_MANO_OBRA, get_google_credentials
    if not get_google_credentials():
        print("  Credenciales Google no configuradas. Saltando.")
        return False
    try:
        from sync.mano_obra import list_csv_files_in_folder, get_latest_month_csv, download_csv_file, parse_csv_content
        files = list_csv_files_in_folder()
        print(f"  CSVs en carpeta: {len(files)}")
        if not files:
            print("  No se encontraron archivos Costos_MM_YYYY.CSV en la carpeta.")
            return False
        latest = get_latest_month_csv()
        if not latest:
            print("  No se pudo determinar el último mes.")
            return False
        print(f"  Último mes: {latest['name']} (modified: {latest.get('modifiedTime', '')[:19]})")
        content = download_csv_file(latest["id"])
        headers, rows = parse_csv_content(content)
        print(f"  Columnas: {headers}")
        has_idobr = any(
            "idobr" in h.lower().replace(" ", "").replace("_", "") or "id_obr" in h.lower()
            for h in headers
        )
        print(f"  Columna idObr presente: {'Sí' if has_idobr else 'Revisar nombres'}")
        if rows:
            print(f"  Filas de muestra: {len(rows)} (primera: {rows[0][:5]}...)")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    a = check_remitos()
    b = check_mano_obra()
    print()
    if a and b:
        print("Ambas fuentes accesibles.")
        sys.exit(0)
    if not a and not b:
        print("No se pudo acceder a ninguna fuente.")
        sys.exit(1)
    print("Una fuente accesible, otra no (revisar variables de entorno).")
    sys.exit(0)


if __name__ == "__main__":
    main()
