# -*- coding: utf-8 -*-
"""Schreibgeschütztes REST-Interface (S7, Vorbild: KiScanner rest_api.py).

Läuft als Hintergrund-Thread in der Streamlit-App und bindet NUR an
127.0.0.1 — andere Tools (Monitore, EAs mitWebRequest, Skripte) können
lesen, niemals schreiben:

  GET /status        → JSON: App/Version/DB-Bestände/letzter Lauf/Daemon
  GET /matrix        → jüngste gespeicherte Matrix (JSON, inkl. llm-Fusion)
  GET /prognose.csv  → dieselbe CSV wie der MT5-Export
  GET /health        → {"ok": true}

Port: Einstellung "rest_api_port" (Standard 8606; 0 = aus). Ist der Port
belegt, startet die App ohne REST weiter (Badge zeigt es).
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config

PORT_DEFAULT = 8606


class _Handler(BaseHTTPRequestHandler):
    server_version = "MqlGoldscannerREST/1.0"

    def log_message(self, fmt, *args):  # kein Stderr-Spam in der App
        pass

    def _sende(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj) -> None:
        self._sende(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802 (http.server-API)
        pfad = self.path.split("?")[0].rstrip("/")
        try:
            if pfad in ("", "/health"):
                self._json({"ok": True, "app": config.APP_NAME,
                            "version": config.APP_VERSION})
            elif pfad == "/status":
                self._json(_status())
            elif pfad == "/matrix":
                letzte = _db().prognose_letzte()
                if letzte is None:
                    self._sende(503, b'{"grund": "noch keine Matrix"}',
                                "application/json; charset=utf-8")
                    return
                try:
                    matrix = json.loads(letzte["inhalt"])
                except json.JSONDecodeError:
                    self._sende(503, b'{"grund": "Matrix-JSON defekt"}',
                                "application/json; charset=utf-8")
                    return
                self._json({"as_of": letzte["as_of"], "woche": letzte["woche"],
                            "modell": letzte["modell"], "matrix": matrix})
            elif pfad == "/prognose.csv":
                from pathlib import Path
                csv_pfad = config.DATA_DIR / "exports" / "goldscanner_prognose.csv"
                if not csv_pfad.exists():
                    self._sende(503, b"noch keine Prognose exportiert",
                                "text/plain; charset=utf-8")
                    return
                self._sende(200, csv_pfad.read_bytes(), "text/csv; charset=utf-8")
            else:
                self._sende(404, b'{"grund": "unbekannter Pfad"}',
                            "application/json; charset=utf-8")
        except BrokenPipeError:
            pass          # Client weg — egal
        except Exception as exc:  # Reader darf niemals die App reißen
            try:
                self._sende(500, json.dumps({"grund": f"{type(exc).__name__}: {exc}"
                                             }).encode("utf-8"),
                            "application/json; charset=utf-8")
            except Exception:
                pass


def _db():
    from .db import Db
    return Db()


def _status() -> dict:
    from .betrieb import daemon
    db = _db()
    try:
        settings = config.load_settings()
        symbol = settings.get("mt5_symbol", "XAUUSD")
        letzte_matrix = db.prognose_letzte()
        stat = daemon.status()
        return {
            "app": config.APP_NAME, "version": config.APP_VERSION,
            "symbol": symbol,
            "db": {"d1": db.raten_anzahl(symbol, "d1"),
                   "h1": db.raten_anzahl(symbol, "h1"),
                   "events": db.events_anzahl(),
                   "news": db.news_anzahl(),
                   "verifikationen": len(db.verifikationen())},
            "letzte_matrix": ({ "as_of": letzte_matrix["as_of"],
                                "woche": letzte_matrix["woche"],
                                "modell": letzte_matrix["modell"]}
                              if letzte_matrix else None),
            "daemon": {"laeuft": stat["laeuft"],
                       "herzschlag_alt_s": stat["herzschlag_alt_s"]},
            "token_heute": db.tokens_heute(),
        }
    finally:
        db.close()


class RestServer:
    def __init__(self, port: int):
        self.port = port
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        self.httpd.daemon_threads = True
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        name="goldscanner-rest", daemon=True)

    @property
    def adresse(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "RestServer":
        self._thread.start()
        return self


def start_background(settings: dict | None = None) -> RestServer | None:
    """REST-Server starten — oder None (deaktiviert/Port belegt)."""
    settings = settings or config.load_settings()
    port = int(settings.get("rest_api_port", PORT_DEFAULT))
    if port <= 0:
        return None
    try:
        return RestServer(port).start()
    except OSError:
        return None
