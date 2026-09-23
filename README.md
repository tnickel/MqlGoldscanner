# MqlGoldscanner

**Multi-Agenten-Goldscanner (XAUUSD)** — recherchiert den Goldmarkt und erstellt für
jede Kalenderwoche eine Übersicht mit der zentralen Frage:

> **Wie hoch ist die Wahrscheinlichkeit, dass sich der Goldpreis an jedem Wochentag
> überdurchschnittlich stark bewegt — wie stark (Range-Band) — und in welche Richtung?**

Python/Streamlit im Stil des bewährten [MqlKiScanner]-Forensic-Designs (dunkles
Dashboard, Gold-Akzente). Statistik zuerst, LLM gewichtet erklärt.

![Dashboard](doc/bilder/dashboard.png)
![Chart](doc/bilder/chart.png)

## Grundprinzipien

- **Engine rechnet, LLM zitiert** — alle Kennzahlen und Prognosekern-Werte werden
  deterministisch in Python berechnet; das LLM (GLM/Z.ai) destilliert Texte und
  verschiebt Prognosen nur in einem konfigurierbaren Band (±10 pp) mit Begründung.
- **Klimatologie als Messlatte** — ein „Bewegungstag" (True Range > 1,0 × Ø-TR des
  Wochentags, 13 Wochen) tritt historisch in ~43 % der Fälle auf. Jede Prognose muss
  diese Basisrate im Brier-Skill-Score schlagen — gemessen im Track-Record.
- **Richtung ist ein eigenes Kalibrierziel** P(Close > Vortages-Close), getrennt von
  der Bewegungswahrscheinlichkeit.
- **Nur lesen, niemals stören** — MT5-Zugriff ausschließlich read-only (statisch
  getestete Whitelist); ein laufendes Terminal wird nie beendet. Ehrlicher
  User-Agent, keine Bot-Schutz-Umgehung, höfliche Abrufabstände.

## Stand (Stufe 2 von 7 — 23.09.2026)

| ✅ | Baustein |
|---|---|
| ✅ | Streamlit-App mit 8 Bereichen (Dashboard, Tagessicht, Chart, Quellen, Agenten, Journal, Track-Record, Einstellungen) |
| ✅ | MetaTrader-5-Anbindung nativ (D1/H4/H1, Whitelist, nur lesend) |
| ✅ | Plotly-Candlestick-Chart mit SMA 10/50/200 + Kennzahlen-Panel (ATR/RSI/TR Wilder) |
| ✅ | GLM-Client mit Fehler-Taxonomie (1113/429·1302/finish_reason), Lauf- und Tagesbudget |
| ✅ | **Wochenmatrix (Klimatologie)**: P(Bewegungstag) je Wochentag mit Shrinkage, Schwelle B, Range-Band Q10–Q90, Warnstufen, Schwellen-Tabelle (1,0×/1,5×/2,0×) |
| ✅ | **Kalender-Adapter**: ForexFactory, BLS, BEA, Fed, TreasuryDirect + regelbasierte Termine (GC FND/LTD/Opex, Feiertage, DST) — Hash-Snapshot-Archiv (point-in-time) |
| ✅ | **Tagessicht**: Event-Zeitleiste (Europe/Berlin) mit Gold-Relevanz-Klassen und Dedup über Quellen |
| ✅ | MQL5-Kalender-Exporter (`mql5/CalendarExport.mq5`) für Ist-Werte + Nasdaq-Fallback |
| ✅ | Quellen-Launch-Check: 16 verifizierte Kern-URLs mit Typ-/Signaturprüfung |
| ✅ | SQLite (versioniert), Audit-Journal, Prognose-Versionen (as_of) |
| ✅ | 37 pytest-Ankertests (u. a. Klimatologie- und Regeltermin-Anker, Kalender-Parsing) |

**Tor T2 bestanden:** eigene Klimatologie auf Brokerdaten = 39,5 % Bewegungstage
(Bericht: ~43 % auf Futures) bei identischer Wochentags-Struktur (Mittwoch höchste Rate).

**Roadmap** (`doc/02_stufenplan.md`): S3 HAR-Prognosemodell mit Walk-forward
(BSS gegen die Basisrate) → S4 LLM-Destillation/Fusion → S5 Richtung & Quant-Feeds
(GVZ/iv30, COT, FRED) → S6 Daemon & Track-Record → S7 Ausbau.

## Schnellstart

```bash
pip install -r requirements.txt          # streamlit, pandas, plotly, MetaTrader5, …
start.bat                                 # oder: streamlit run streamlit_app.py
```

Voraussetzungen: Windows mit laufendem MetaTrader-5-Terminal (Symbol `XAUUSD`) und
ein GLM-API-Key (Z.ai). Key ablegen — **niemals committen** — in
`config/secrets.local.json`:

```json
{ "glm_api_key": "dein-key" }
```

(alternativ Umgebungsvariable `GLM_API_KEY` oder `.env`; Abo-Keys = Coding-Endpunkt,
PAYG-Keys = Standard-Endpunkt — in den Einstellungen umschaltbar).

## Architektur

```
streamlit_app.py + app_pages/     dünne UI-Seiten (8 Bereiche)
src/goldscanner/
  ├─ ui_design.py                 KiScanner-Forensic-Design, Gold-Variante
  ├─ llm/client.py                GLM-Client, Fehler-Taxonomie, Budgets
  ├─ mt5/kurse.py                 MT5 read-only (nativ, Whitelist-geprüft)
  ├─ kennzahlen.py                TR/ATR/RSI/SMA — reiner Code, Ankertests
  ├─ quellen_check.py             Wächter: Status + Content-Type + Signatur
  ├─ db.py / lock.py / config.py  SQLite, Lauf-Lock, Einstellungen
tests/                            pytest
doc/                             Konzept, Deep-Research-Berichte, Stufenplan
```

Dokumentation: [Konzept](doc/00_konzept.md) · [Stufenplan](doc/02_stufenplan.md) ·
[Deep-Research](doc/DeepResaearch/) (drei Berichte mit live verifizierten Quellen)

## Sicherheit & Quellen

- Geheimnisse (API-Keys) liegen ausschließlich in gitignorierten Dateien
  (`config/secrets.local.json`, `.env`) — die Kaskade ist
  Umgebungsvariable > `.env` > `secrets.local.json`.
- Datenquellen sind maschinenlesbare offizielle Feeds (ForexFactory-Export, BLS/BEA,
  Federal Reserve, TreasuryDirect, CFTC, FRED, Cboe, LBMA, RSS-Feeds); auf
  gesperrte Seiten (Cloudflare/ToS) wird bewusst verzichtet.
- Konventionen aus dem Deep Research: HTTP 200 beweist nichts (Content-Type und
  Signatur werden geprüft), robots/ToS werden respektiert.

## Disclaimer

Forschungs- und Projektionswerkzeug. Keine Anlageberatung, keine Garantie für
Prognosen. Alle Wahrscheinlichkeiten werden gegen historische Baselines kalibriert
und ihr Track-Record transparent ausgewiesen (ab Stufe 6).

[MqlKiScanner]: https://github.com/tnickel  (Vorlage-Projekt, lokal D:\git\MQL\MqlKiScanner)
