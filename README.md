# Pluril-Sync

Sincronización de **costos de materiales** (API Remitos) y **costos de mano de obra** (CSV en Google Drive) hacia dos Google Sheets separados para consumir desde AppSheet.

- **Materiales**: API Remitos → [Costos de Materiales / Sistema Interno](https://docs.google.com/spreadsheets/d/16rVICcrR5LyNn5VEgxehkYs9E7gIe6fbyP1covq2s14) (hoja "Materiales") con columnas Fecha, TipoDoc, Serie, NroDoc, **Cuenta**, **Obra** (DESCCUENTA), Direccion, Total, Moneda.
- **Mano de obra**: Último CSV del último mes en la carpeta Drive → [GNS - Costos de Mano de Obra](https://docs.google.com/spreadsheets/d/1KdhF5-q6WKRKkwyrh4LhK0itm-DDyQc6TH7eJ2dKihU) (hoja "Mano de obra") con columnas del CSV (incluida **idObr**) más Periodo (MM/YYYY).

Ambos Sheets están en la carpeta [Sync - Costos Materiales & Mano de Obra](https://drive.google.com/drive/folders/1ATAyoexZYqlpYbcn3md27zo1NLezdsb5).

## Requisitos

- Python 3.10+
- Cuenta de servicio de Google con acceso a:
  - La carpeta de Drive donde están los CSV de mano de obra (compartir la carpeta con el email del service account).
  - Los dos Google Sheets de destino (compartir cada libro con el email del service account).

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `REMITOS_API_URL` | URL base de la API Remitos (opcional, hay default). |
| `REMITOS_BEARER_TOKEN` | Token Bearer para la API. |
| `DRIVE_FOLDER_ID_MANO_OBRA` | ID de la carpeta de Drive con los CSV (default: carpeta conocida). |
| `SHEET_ID_MATERIALES` | ID del Google Sheet donde publicar costos de materiales. |
| `SHEET_ID_MANO_OBRA` | ID del Google Sheet donde publicar costos de mano de obra. |
| `GOOGLE_CREDENTIALS_JSON` | JSON (string) de la cuenta de servicio. |
| `GOOGLE_CREDENTIALS_PATH` | Ruta al archivo JSON de la cuenta de servicio (alternativa). |
| `SYNC_SECRET` | (Opcional) Secreto para proteger `POST /sync`. |
| `SKIP_MATERIALES_SYNC` | Si está en `1` o `true`, no se llama a la API Remitos (útil si el servidor no soporta TLS 1.2+ desde la nube). |

## Uso local

```bash
python -m venv .venv
source .venv/bin/activate   # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus valores

# Verificar acceso a ambas fuentes
python verify_sources.py

# Ejecutar sync manualmente (desde código o llamando a sync.materiales / sync.mano_obra)
# O levantar el servidor y llamar a /sync
python main.py
# POST http://localhost:5000/sync  (o con ?secret=SYNC_SECRET)
```

## Railway

1. Conectar el repo y desplegar.
2. En Variables de entorno de Railway configurar todas las anteriores (en especial `REMITOS_BEARER_TOKEN`, `GOOGLE_CREDENTIALS_JSON`, `SHEET_ID_MATERIALES`, `SHEET_ID_MANO_OBRA`).
3. El `Procfile` expone la app con Gunicorn; Railway asigna `PORT`.
4. Para ejecutar el sync periódicamente: más adelante configurar un cron externo que llame a `POST https://tu-app.railway.app/sync` con el header `X-Sync-Secret` (o `?secret=...`).

## Estructura del proyecto

```
Pluril-Sync/
├── main.py              # Flask: /health, /sync
├── verify_sources.py    # Comprueba acceso API Remitos y Drive
├── requirements.txt
├── Procfile
├── .env.example
├── sync/
│   ├── config.py        # Variables de entorno
│   ├── materiales.py    # API Remitos → Sheet (por obra: Cuenta + DESCCUENTA)
│   └── mano_obra.py     # Drive último CSV → Sheet (columna idObr)
└── credentials/         # (opcional) service_account.json si no usas JSON en env
```

## Notas

- **API Remitos (materiales)**: el servidor actual puede no aceptar conexiones TLS desde la nube (error `TLSV1_ALERT_PROTOCOL_VERSION`). Solución de fondo: que el dueño del servidor habilite **TLS 1.2 o superior**. Mientras tanto, en Railway podés poner `SKIP_MATERIALES_SYNC=1` para que el sync solo ejecute mano de obra y responda más rápido.
- **Materiales**: cada ejecución de sync añade filas al Sheet (append). Si querés reemplazar el mes, hay que limpiar la hoja "Materiales" antes o implementar lógica de “upsert” por periodo.
- **Mano de obra**: se toma el archivo del **último mes** disponible (por nombre `Costos_MM_YYYY.CSV`). Cada ejecución append esas filas con columna Periodo; si ejecutás dos veces el mismo mes, se duplican filas (podés añadir dedup por periodo si hace falta).
