"""
App Flask para Railway: expone un endpoint que ejecuta la sincronización
(materiales + mano de obra). El cron se puede configurar después para llamar a este endpoint.
"""
import os
import sys
import traceback
from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

# Opcional: proteger el endpoint con un secreto
SYNC_SECRET = os.environ.get("SYNC_SECRET", "")


def _run_sync():
    from sync.materiales import run_sync_materiales_month
    from sync.mano_obra import sync_mano_obra
    from sync.config import SHEET_ID_MATERIALES, SHEET_ID_MANO_OBRA

    now = datetime.utcnow()
    result_m = {"ok": False, "rows_written": 0, "error": "no ejecutado"}
    result_l = {"ok": False, "rows_written": 0, "error": "no ejecutado"}

    try:
        result_m = run_sync_materiales_month(now.year, now.month, sheet_id=SHEET_ID_MATERIALES)
    except Exception as e:
        result_m = {"ok": False, "rows_written": 0, "error": str(e)}

    try:
        result_l = sync_mano_obra(sheet_id=SHEET_ID_MANO_OBRA)
    except Exception as e:
        result_l = {"ok": False, "rows_written": 0, "error": str(e), "file_name": ""}

    return {
        "materiales": result_m,
        "mano_obra": result_l,
    }


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/sync", methods=["POST", "GET"])
def sync():
    if SYNC_SECRET:
        auth = request.headers.get("X-Sync-Secret") or request.args.get("secret")
        if auth != SYNC_SECRET:
            return jsonify({"error": "Unauthorized"}), 401
    try:
        out = _run_sync()
        return jsonify(out)
    except Exception as e:
        tb = traceback.format_exc()
        msg = str(e).strip() or repr(e) or f"{type(e).__name__}"
        print("Sync failed:", msg, file=sys.stderr)
        print(tb, file=sys.stderr)
        return jsonify({"error": msg, "traceback": tb}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
