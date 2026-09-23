# MQL5-Kalender-Exporter (Stufe 2)

Der ForexFactory-Feed liefert keine Ist-Werte (Deep-Research-Befund), und das
Python-Paket `MetaTrader5` hat keine Kalenderfunktionen. Deshalb exportiert
dieses kleine Skript den **offiziellen MT5-Wirtschaftskalender** — historisch
mit Actual/Forecast/Previous — in eine CSV, die der Goldscanner einliest
(`src/goldscanner/adapter/actuals.py`).

## Einmalige Installation

1. `CalendarExport.mq5` nach `<Terminal-Datenordner>\MQL5\Scripts\` kopieren
   (im Terminal: Datei → Datenordner öffnen).
2. Im MetaEditor öffnen und mit **F7** kompilieren.
3. Im Navigator (Terminal) unter Skripte das Skript **einmal auf ein beliebiges
   Chart ziehen** — es läuft sofort durch (nur Lesen, keine Order).

Die Datei liegt danach unter
`%APPDATA%\MetaQuotes\Terminal\Common\Files\goldscanner_calendar.csv`.

## Betrieb

Einmal wöchentlich erneut ausführen (z. B. samstags) — die Historie wächst mit,
der Goldscanner trägt Ist-Werte damit point-in-time nach (`actual_first` bleibt
der Ersteintrag). Zeiten sind MT5-**Serverzeit**; Werte sind durch 1e6 geteilt
(MQL5-Skalierung der Kalenderwerte).

Hinweis: Ohne laufenden Exporter nutzt der Goldscanner den Nasdaq-Fallback
(toS-grau, wenige gezielte Abrufe) — Primärweg bleibt der MT5-Kalender.
