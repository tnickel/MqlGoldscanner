# -*- coding: utf-8 -*-
"""SQLite-Datenbank (data/goldscanner.db) mit versioniertem Schema.

Streamlit-Reruns und spaetere Daemon-Threads teilen sich eine Verbindung;
sqlite3-Verbindungen sind nicht thread-sicher, deshalb Schloss um alles.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import config

SCHEMA_VERSION = 4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS rates (
    symbol TEXT NOT NULL, timeframe TEXT NOT NULL, bar_time INTEGER NOT NULL,
    open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
    close REAL NOT NULL, volumen REAL NOT NULL, abgerufen_am TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, bar_time));
CREATE TABLE IF NOT EXISTS quellen (
    url TEXT PRIMARY KEY, name TEXT, kategorie TEXT, aktiv INTEGER DEFAULT 1,
    letzter_status TEXT, letzter_check TEXT, letzter_hash TEXT,
    score INTEGER, hinweis TEXT);
CREATE TABLE IF NOT EXISTS agenten_laeufe (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, beschreibung TEXT,
    start TEXT NOT NULL, ende TEXT, ok INTEGER);
CREATE TABLE IF NOT EXISTS agenten_schritte (
    id INTEGER PRIMARY KEY AUTOINCREMENT, lauf_id INTEGER NOT NULL,
    zeit TEXT NOT NULL, agent TEXT, art TEXT, prompt TEXT, antwort TEXT,
    modell TEXT, tokens INTEGER, dauer_s REAL, ok INTEGER, fehler TEXT);
CREATE TABLE IF NOT EXISTS budget_token (
    tag TEXT NOT NULL, modell TEXT NOT NULL, tokens INTEGER NOT NULL DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (tag, modell));
CREATE TABLE IF NOT EXISTS calendar_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT, quelle TEXT NOT NULL,
    abgerufen_am TEXT NOT NULL, inhalt_hash TEXT NOT NULL, inhalt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quelle TEXT NOT NULL, prioritaet INTEGER NOT NULL DEFAULT 5,
    zeit_utc TEXT, datum TEXT NOT NULL, titel TEXT NOT NULL,
    klasse TEXT, wichtigkeit INTEGER, gold_relevanz INTEGER, waehrung TEXT,
    forecast TEXT, previous TEXT, actual_first TEXT, actual_latest TEXT);
CREATE INDEX IF NOT EXISTS idx_events_datum ON calendar_events(datum);
CREATE TABLE IF NOT EXISTS prognose_versionen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, as_of TEXT NOT NULL,
    woche TEXT NOT NULL, modell TEXT NOT NULL, inhalt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quant_series (
    tag TEXT NOT NULL, schluessel TEXT NOT NULL, wert REAL NOT NULL,
    PRIMARY KEY (tag, schluessel));
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quelle TEXT NOT NULL, url TEXT NOT NULL, titel TEXT NOT NULL,
    autor TEXT, veroeffentlicht TEXT, geholt_am TEXT NOT NULL,
    dedup_hash TEXT NOT NULL UNIQUE, gold_relevanz INTEGER,
    zusammenfassung TEXT, destilliert INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS fusionen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, as_of TEXT NOT NULL,
    woche TEXT NOT NULL, modell TEXT NOT NULL, band_pp REAL NOT NULL,
    inhalt TEXT NOT NULL, ok INTEGER NOT NULL DEFAULT 1,
    delta_max_pp REAL, verstoesse INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS meldungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, zeit TEXT NOT NULL,
    woche TEXT NOT NULL, art TEXT NOT NULL, text TEXT NOT NULL,
    gelesen INTEGER NOT NULL DEFAULT 0);
"""


def _jetzt() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Db:
    """Dünnes synchronisiertes Zugriffsobjekt um eine SQLite-Verbindung."""

    def __init__(self, datei: Path | None = None):
        self.datei = datei or config.DB_FILE
        self.datei.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(self.datei, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.executescript("PRAGMA journal_mode=WAL;")
            self._con.executescript(_SCHEMA)
            version = self._con.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            if version is None:
                self._con.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
            elif version < SCHEMA_VERSION:
                # CREATE IF NOT EXISTS hat bereits neue Tabellen angelegt —
                # hier nur die Versionsnummer nachziehen (zustandslose Migration).
                self._con.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
            self._con.commit()

    # ── Kurse ────────────────────────────────────────────────────────────
    def raten_speichern(self, symbol: str, timeframe: str, bars: list[dict]) -> int:
        """Insert-or-ignore; liefert Anzahl NEUER Zeilen."""
        zeilen = [(symbol, timeframe, int(b["time"]), float(b["open"]), float(b["high"]),
                   float(b["low"]), float(b["close"]), float(b.get("volumen", 0)), _jetzt())
                  for b in bars]
        with self._lock:
            cur = self._con.executemany(
                "INSERT OR IGNORE INTO rates(symbol,timeframe,bar_time,open,high,low,close,"
                "volumen,abgerufen_am) VALUES (?,?,?,?,?,?,?,?,?)", zeilen)
            self._con.commit()
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    def raten_laden(self, symbol: str, timeframe: str, limit: int | None = None) -> list[dict]:
        sql = ("SELECT bar_time AS time, open, high, low, close, volumen FROM rates "
               "WHERE symbol=? AND timeframe=? ORDER BY bar_time"
               + (f" DESC LIMIT {int(limit)}" if limit else ""))
        with self._lock:
            zeilen = [dict(r) for r in self._con.execute(sql, (symbol, timeframe)).fetchall()]
        if limit:
            zeilen.reverse()
        return zeilen

    def raten_anzahl(self, symbol: str, timeframe: str) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM rates WHERE symbol=? AND timeframe=?",
                                     (symbol, timeframe)).fetchone()[0]

    # ── Quellen-Wächter (S1: Launch-Check-Ergebnisse) ────────────────────
    def quellen_status_speichern(self, ergebnisse: list[dict]) -> None:
        with self._lock:
            for e in ergebnisse:
                self._con.execute(
                    "INSERT INTO quellen(url,name,kategorie,aktiv,letzter_status,letzter_check,"
                    "hinweis) VALUES (?,?,?,1,?,?,?) "
                    "ON CONFLICT(url) DO UPDATE SET letzter_status=excluded.letzter_status,"
                    "letzter_check=excluded.letzter_check, hinweis=excluded.hinweis",
                    (e["url"], e["name"], e["kategorie"],
                     ("ok" if e["ok"] else "fehler") + f" {e['status']}", _jetzt(), e["hinweis"]))
            self._con.commit()

    # ── Journal ──────────────────────────────────────────────────────────
    def lauf_starten(self, name: str, beschreibung: str = "") -> int:
        with self._lock:
            cur = self._con.execute(
                "INSERT INTO agenten_laeufe(name,beschreibung,start) VALUES (?,?,?)",
                (name, beschreibung, _jetzt()))
            self._con.commit()
            return int(cur.lastrowid)

    def lauf_beenden(self, lauf_id: int, ok: bool) -> None:
        with self._lock:
            self._con.execute("UPDATE agenten_laeufe SET ende=?, ok=? WHERE id=?",
                              (_jetzt(), 1 if ok else 0, lauf_id))
            self._con.commit()

    def schritt(self, lauf_id: int, agent: str, art: str, prompt: str = "",
                antwort: str = "", modell: str = "", tokens: int | None = None,
                dauer_s: float | None = None, ok: bool = True, fehler: str = "") -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO agenten_schritte(lauf_id,zeit,agent,art,prompt,antwort,modell,"
                "tokens,dauer_s,ok,fehler) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (lauf_id, _jetzt(), agent, art, prompt, antwort, modell,
                 tokens, dauer_s, 1 if ok else 0, fehler))
            self._con.commit()

    def letzte_schritte(self, n: int = 20) -> list[dict]:
        with self._lock:
            zeilen = self._con.execute(
                "SELECT s.*, l.name AS lauf FROM agenten_schritte s "
                "LEFT JOIN agenten_laeufe l ON l.id=s.lauf_id "
                "ORDER BY s.id DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in zeilen]

    # ── Token-Budget ─────────────────────────────────────────────────────
    def tokens_heute(self) -> int:
        with self._lock:
            return self._con.execute(
                "SELECT COALESCE(SUM(tokens),0) FROM budget_token "
                "WHERE tag=date('now','localtime')").fetchone()[0]

    def token_buchen(self, modell: str, tokens: int) -> None:
        with self._lock:
            self._con.execute(
                "INSERT INTO budget_token(tag,modell,tokens,requests) VALUES "
                "(date('now','localtime'),?,?,1) "
                "ON CONFLICT(tag,modell) DO UPDATE SET tokens=tokens+excluded.tokens,"
                "requests=requests+1", (modell, max(0, tokens)))
            self._con.commit()

    # ── Kalender (S2) ────────────────────────────────────────────────────
    def snapshot_speichern(self, quelle: str, inhalt: str) -> bool:
        """Archiviert einen Roh-Snapshot — nur wenn sich der Hash geändert hat
        (Point-in-time-Archiv ohne Müll). True = neu gespeichert."""
        import hashlib
        hash_ = hashlib.sha256(inhalt.encode("utf-8", errors="replace")).hexdigest()
        with self._lock:
            letzter = self._con.execute(
                "SELECT inhalt_hash FROM calendar_snapshots WHERE quelle=? "
                "ORDER BY id DESC LIMIT 1", (quelle,)).fetchone()
            if letzter and letzter["inhalt_hash"] == hash_:
                return False
            self._con.execute(
                "INSERT INTO calendar_snapshots(quelle,abgerufen_am,inhalt_hash,inhalt) "
                "VALUES (?,?,?,?)", (quelle, _jetzt(), hash_, inhalt))
            self._con.commit()
            return True

    def events_ersetzen(self, quelle: str, events: list[dict]) -> int:
        """Idempotentes Ersetzen des Fensters einer Quelle (Delete+Insert)."""
        with self._lock:
            self._con.execute("DELETE FROM calendar_events WHERE quelle=?", (quelle,))
            self._con.executemany(
                "INSERT INTO calendar_events(quelle,prioritaet,zeit_utc,datum,titel,klasse,"
                "wichtigkeit,gold_relevanz,waehrung,forecast,previous,actual_first,"
                "actual_latest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(e["quelle"], e.get("prioritaet", 5), e.get("zeit_utc"),
                  e["datum"], e["titel"], e.get("klasse"), e.get("wichtigkeit"),
                  e.get("gold_relevanz"), e.get("waehrung"), e.get("forecast"),
                  e.get("previous"), e.get("actual"), e.get("actual"))
                 for e in events])
            self._con.commit()
            return len(events)

    def events_fuer_zeitraum(self, von: str, bis: str) -> list[dict]:
        """Events mit datum zwischen von/bis (ISO-Date), aufsteigend."""
        with self._lock:
            zeilen = self._con.execute(
                "SELECT * FROM calendar_events WHERE datum>=? AND datum<=? "
                "ORDER BY zeit_utc, gold_relevanz DESC, wichtigkeit DESC",
                (von, bis)).fetchall()
        return [dict(r) for r in zeilen]

    def events_anzahl(self) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0]

    def actual_nachziehen(self, quelle: str, datum_von: str, datum_bis: str,
                          actuals: dict[tuple[str, str], str]) -> int:
        """Trägt Ist-Werte nach (Schlüssel: (datum, titel-normalisiert)). Setzt
        actual_first beim ersten Mal, aktualisiert actual_latest."""
        with self._lock:
            zeilen = self._con.execute(
                "SELECT id, datum, titel, actual_first FROM calendar_events "
                "WHERE datum>=? AND datum<=?", (datum_von, datum_bis)).fetchall()
            geaendert = 0
            for z in zeilen:
                schluessel = (z["datum"], _titel_normalisiert(z["titel"]))
                if schluessel in actuals and actuals[schluessel]:
                    if z["actual_first"] is None:
                        self._con.execute(
                            "UPDATE calendar_events SET actual_first=?, actual_latest=? WHERE id=?",
                            (actuals[schluessel], actuals[schluessel], z["id"]))
                        geaendert += 1
                    elif z["actual_first"] != actuals[schluessel]:
                        self._con.execute(
                            "UPDATE calendar_events SET actual_latest=? WHERE id=?",
                            (actuals[schluessel], z["id"]))
            self._con.commit()
            return geaendert

    # ── Quant-Serien (GVZ/iv30/FRED …) ──────────────────────────────────
    def quant_speichern(self, schluessel: str, werte: dict[str, float]) -> int:
        """Upsert Tageswerte (tag → wert). Rückgabe: Anzahl Zeilen."""
        with self._lock:
            self._con.executemany(
                "INSERT INTO quant_series(tag,schluessel,wert) VALUES (?,?,?) "
                "ON CONFLICT(tag,schluessel) DO UPDATE SET wert=excluded.wert",
                [(tag, schluessel, float(w)) for tag, w in werte.items()])
            self._con.commit()
            return len(werte)

    def quant_laden(self, schluessel: str) -> dict[str, float]:
        with self._lock:
            zeilen = self._con.execute(
                "SELECT tag, wert FROM quant_series WHERE schluessel=? ORDER BY tag",
                (schluessel,)).fetchall()
        return {r["tag"]: r["wert"] for r in zeilen}

    # ── Prognose-Versionen (as_of, kein Look-ahead) ─────────────────────
    def prognose_speichern(self, woche: str, modell: str, inhalt: str) -> int:
        with self._lock:
            import json as _json
            cur = self._con.execute(
                "INSERT INTO prognose_versionen(as_of,woche,modell,inhalt) VALUES (?,?,?,?)",
                (_jetzt(), woche, modell, inhalt))
            self._con.commit()
            return int(cur.lastrowid)

    def prognose_letzte(self, woche: str | None = None) -> dict | None:
        """Jüngste gespeicherte Matrix (JSON), je Woche oder gesamt —
        bevorzugt die Version mit LLM-Fusion."""
        sql = ("SELECT * FROM prognose_versionen"
               + (" WHERE woche=?" if woche else "")
               + " ORDER BY id DESC LIMIT 10")
        with self._lock:
            zeilen = self._con.execute(sql, (woche,) if woche else ()).fetchall()
        for zeile in zeilen:                  # neueste zuerst
            if "llm_fusion" in zeile["modell"]:
                return dict(zeile)
        return dict(zeilen[0]) if zeilen else None

    # ── News-Items (S4: Delta-Prinzip über Dedup-Hash) ──────────────────
    def news_speichern(self, items: list[dict]) -> int:
        """Neue News-Items anlegen (INSERT OR IGNORE auf dedup_hash).
        Rückgabe: Anzahl NEUER Zeilen."""
        with self._lock:
            cur = self._con.executemany(
                "INSERT OR IGNORE INTO news_items(quelle,url,titel,autor,veroeffentlicht,"
                "geholt_am,dedup_hash,gold_relevanz,zusammenfassung) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                [(i["quelle"], i["url"], i["titel"], i.get("autor"),
                  i.get("veroeffentlicht"), _jetzt(), i["dedup_hash"],
                  i.get("gold_relevanz", 1), i.get("zusammenfassung"))
                 for i in items])
            self._con.commit()
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    def news_offen(self, limit: int = 80) -> list[dict]:
        """Noch nicht destillierte Items, älteste zuerst (stabile Prompt-Reihenfolge)."""
        with self._lock:
            zeilen = self._con.execute(
                "SELECT * FROM news_items WHERE destilliert=0 "
                "ORDER BY veroeffentlicht, id LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in zeilen]

    def news_destilliert_markieren(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock:
            self._con.executemany(
                "UPDATE news_items SET destilliert=1 WHERE id=?",
                [(int(i),) for i in ids])
            self._con.commit()

    def news_anzahl(self, offen: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM news_items" + (" WHERE destilliert=0" if offen else "")
        with self._lock:
            return self._con.execute(sql).fetchone()[0]

    # ── LLM-Fusionen (S4: Grundlage für Tor T4 — LLM-Delta-Nutztwert) ───
    def fusion_speichern(self, woche: str, modell: str, band_pp: float,
                         inhalt: str, ok: bool, delta_max_pp: float | None,
                         verstoesse: int) -> int:
        with self._lock:
            cur = self._con.execute(
                "INSERT INTO fusionen(as_of,woche,modell,band_pp,inhalt,ok,"
                "delta_max_pp,verstoesse) VALUES (?,?,?,?,?,?,?,?)",
                (_jetzt(), woche, modell, float(band_pp), inhalt,
                 1 if ok else 0, delta_max_pp, int(verstoesse)))
            self._con.commit()
            return int(cur.lastrowid)

    def fusion_letzte(self, woche: str | None = None) -> dict | None:
        """Jüngste Fusion (gesamt oder je Woche) — für Delta-Meldungen."""
        sql = ("SELECT * FROM fusionen" + (" WHERE woche=?" if woche else "")
               + " ORDER BY id DESC LIMIT 1")
        with self._lock:
            zeile = self._con.execute(sql, (woche,) if woche else ()).fetchone()
        return dict(zeile) if zeile else None

    def fusion_vorherige(self, woche: str) -> dict | None:
        """Zweitjüngste Fusion derselben Woche (vor der gerade gespeicherten)
        — Vergleichsbasis für Prognoseänderungs-Meldungen."""
        with self._lock:
            zeile = self._con.execute(
                "SELECT * FROM fusionen WHERE woche=? "
                "ORDER BY id DESC LIMIT 1 OFFSET 1", (woche,)).fetchone()
        return dict(zeile) if zeile else None

    # ── Postfach (S4: Meldungen bei Prognoseänderung) ───────────────────
    def meldung_speichern(self, woche: str, art: str, text: str) -> int:
        with self._lock:
            cur = self._con.execute(
                "INSERT INTO meldungen(zeit,woche,art,text) VALUES (?,?,?,?)",
                (_jetzt(), woche, art, text))
            self._con.commit()
            return int(cur.lastrowid)

    def meldungen(self, nur_offene: bool = False, limit: int = 30) -> list[dict]:
        sql = ("SELECT * FROM meldungen" + (" WHERE gelesen=0" if nur_offene else "")
               + " ORDER BY id DESC LIMIT ?")
        with self._lock:
            zeilen = self._con.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in zeilen]

    def meldung_gelesen_markieren(self, id_: int) -> None:
        with self._lock:
            self._con.execute("UPDATE meldungen SET gelesen=1 WHERE id=?", (id_,))
            self._con.commit()

    def close(self) -> None:
        with self._lock:
            self._con.close()


def _titel_normalisiert(titel: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", (titel or "").lower()).strip()
