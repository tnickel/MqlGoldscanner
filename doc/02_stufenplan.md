# MqlGoldscanner — Stufenplan (v1.1, 23.09.2026)

> **Technologie-Wechsel 23.09.2026:** Nach Nutzer-Entscheidung läuft die Umsetzung auf
> **Python/Streamlit** (wie der MqlKiScanner), nicht mehr Java/JavaFX. Stufe S1 ist in
> Python fertig abgenommen (19 pytest grün, MT5 live, GLM-Ping OK, Quellen-Check 16/16,
> Design im Browser visuell verifiziert). Die Java-Inhalte der Stufenbeschreibungen
> unten (JavaFX, Maven, Bridge) sind historisch zu lesen; Funktionsumfang und Abnahmen
> gelten unverändert. Java-Prototyp: `archiv/java-prototyp/`.

Verfeinerung von §13 des Konzepts (`doc/00_konzept.md`). Ziel: Umsetzung in **7 Stufen**,
die jeweils für sich abgeschlossen, testbar und **nutzbar** sind — die App bleibt nach
jeder Stunde startbar und zeigt einen echten Mehrwert. Zwischen den Stufen stehen
**Entscheidungstore (Go/No-Go)** mit messbaren Kriterien, damit frühe Fehler nicht in
späte Stufen getragen werden.

Aufwandsangaben sind Richtwerte in Personentagen (PT) für einen erfahrenen Java-Entwickler
auf der KiScanner-Grundlage — keine Lieferzusagen. Bausteine je Stufe bauen nur auf
abgeschlossenen Stufen auf; innerhalb einer Stufe ist die Reihenfolge flexibel.

---

## Übersicht

```
S1 Gerüst & Kurse      S2 Daten & Klimatologie   S3 Prognosemodell
   App läuft,            Wochenmatrix (nur         kalibriertes P(TR>B),
   Chart, GLM-Ping       Statistik), Kalender      Backtest im Journal
        │                       │                        │
        └── Tor T1: Quellen aus Java erreichbar?         └── Tor T3: BSS > 0?
                                                                │
S4 LLM-Schicht ◄────────────────────────────────────────────────┘
   Begründungen, Treiber, PDF        S5 Richtung & Quant & Kalibrierung
        │                              P(hoch), COT/FRED/GVZ-Feeds, Isotonic
        └── Tor T4: LLM-Delta ≠ Schaden                    │
                                                           ▼
                                    S6 Betrieb & Selbstverbesserung
                                       Daemon, Track-Record, Scout, MT5-Export
                                                           │
                                    S7 Ausbau (optional): GARCH/CARR, Skew, …
```

| Stufe | Kern-Aussage | Nutzer sieht danach | Aufwand |
|---|---|---|---|
| **S1** | App startet, Kurse + GLM funktionieren | Chart, Config, Einrichtung | 8–12 PT |
| **S2** | Erste Wochenmatrix (nur Statistik) | Matrix mit Basiswahrscheinlichkeiten + Kalender | 8–12 PT |
| **S3** | Modell schlägt die Klimatologie | Kalibrierte P je Tag + Backtest-Zahlen | 10–15 PT |
| **S4** | Matrix wird erklärt | Treiber, Begründungen, PDF | 8–12 PT |
| **S5** | Richtung + mehr Feeds + Rekalibrierung | P(hoch), bessere Kalibrierung, Intraday-Update | 10–15 PT |
| **S6** | Läuft von selbst, weist Qualität nach | Daemon, Track-Record, Scout | 8–12 PT |
| **S7** | Ausbau nach Bedarf | optional | nach Bedarf |
| **Σ** | | | **~55–80 PT** |

---

## S1 — Gerüst & Kurse („App lebt")

**Bausteine**
1. Maven-Projekt (Java 21, JavaFX 21, sqlite-jdbc, Jsoup, Jackson, commons-math3,
   Rome für RSS), `start.bat`, dunkles Theme, Navigationsgerüst der 8 Bereiche
   (Platzhalterinhalte mit „Was tun"-Karten für leere Zustände).
2. `core`: Config (`config/app_settings.json` + Defaults), Secrets-Kaskade
   (Env > `.env` > `config/secrets.local.json`), SQLite-Anlage der Kerntabellen
   (`rates`, `quellen`, `agenten_laeufe/schritte`, `budget_token`), Journal, Lock,
   ehrlicher User-Agent `MqlGoldscanner/0.1 (+mailto:…)` als zentraler HttpService.
3. `llm`: GlmClient (chat/completions, Endpunkt-Umschaltung Abo/PAYG,
   Fehler-Taxonomie 1113/429·1302/finish_reason≠stop, Backoff, Token-Budget).
4. Einrichtungsdialog beim ersten Start: GLM-Key, MT5-Terminalpfad, Broker-Symbol
   (inkl. Suffix), Python-Pfad, Zeitzone. „Verbindung testen"-Buttons.
5. `mt5bridge/fetch_gold.py` (Kurse D1/H4/H1, read-only-Whitelist, portable Terminal,
   PID-genau beendet — aus KiScanner `marktdata.py` übernommen) + `mt5/` in Java
   (BridgeProcess, RatenParser, erste Kennzahlen: TR, ATR, SMA, RSI).
6. Chart-Bereich: Candlestick D1 (~180 Tage, eigener JavaFX-Renderer) mit SMA-Overlays
   und Kennzahlen-Panel.
7. **Quellen-Launch-Check** (erster Wächter-Baustein): Button in Quellen-UI, der die
   geplanten Kern-URLs (FF-Feed, BLS/BEA-ICS, Fed-JSON, TreasuryDirect, GVZ, FRED,
   CFTC, ein RSS je Kategorie) mit dem echten UA anpingt und Status/Content-Type zeigt.

**Abnahme (Torgebiet)**
- `start.bat` → App startet, Einrichtung führt einmalig durch, Config wird persistiert.
- GLM-Ping (kleiner Test-Prompt) erfolgreich; Fehlerfälle (falscher Key, Abo-Key auf
  PAYG-Endpunkt → 1113) werden korrekt klassifiziert angezeigt.
- Chart zeigt echte XAUUSD-Kurse aus dem eigenen MT5-Terminal; Kennzahlen stimmen
  gegen Ankertests (JUnit mit kalibrierten Testreihen, Vorbild `verify_engine.py`).
- Quellen-Launch-Check läuft durch und dokumentiert Erreichbarkeit der Kernquellen.

**Tor T1 (vor S2):** Alle Kernquellen §7.1/§7.4 aus dem eigenen Netz/IP mit ehrlichem
UA erreichbar? Ausreißer (z. B. BLS 403, war in den Tests UA-abhängig) bekommen sofort
einen Ersatz-Adapter oder werden auf „optional" zurückgestuft.

---

## S2 — Datengrundlage & Klimatologie („erste Wochenmatrix, rein statistisch")

**Bausteine**
1. Kalender-Adapter: FF `thisweek` (≤ 4×/Tag, **Snapshots selbst archivieren** in
   `calendar_snapshots`), BLS-ICS, BEA-ICS/JSON, Fed `calendar.json` (BOM!) + Fed-RSS,
   EZB, TreasuryDirect-Auktionen (2y–30y, FRN ausfiltern), CFTC-Releaseplan.
2. Regeltermine in Java: GC FND/LTD, Options-Verfall (4 Geschäftstage vor Monatsende
   des Vormonats, Liefermonate Feb/Apr/Jun/Aug/Okt/Dez), Quartalsende, US/UK-Feiertage,
   DST-Übergänge — deterministisch, kein Scraping.
3. Event-Normalisierung: alles → UTC + Quellzeitzone, Gold-Relevanz-Klassen
   (NFP/CPI/PCE/FOMC/ISM/Claims/Auktion/…), Dedup über (Zeitpunkt, Namensähnlichkeit).
4. Snapshot-Store + Wächter Basis: Content-Type-/Signaturprüfung („200+HTML ≠ CSV"),
   Datenalter, Hash; Quellen-UI zeigt Ampel je Quelle.
5. Statistik: Wochentags-Ø-TR/-Median, relative TR (TR/Close) für lange Historien,
   13-Wochen-Fenster je Wochentag → Schwelle B; **Klimatologie** P je Wochentag mit
   Shrinkage; empirische Range-Quantile Q10/50/90.
6. Dashboard: Wochenmatrix v2 im „Statistik-Modus" — P(Klimatologie), Schwelle B in USD,
   Range-Band, Top-Events je Tag, Schwellen-Tabelle 1,0×/1,5×/2,0×, 5-stufige Warnskala.
   Tagessicht mit Event-Zeitleiste (Europe/Berlin). Bewusster Vermerk „unkalibriert".
7. (Vorbereitung S3) **MQL5-Exporter `CalendarExport.mq5`** entwickeln und im Terminal
   installieren — historischer Kalender mit Actuals/Forecasts → CSV.

**Abnahme**
- Wochenlauf (manuell startbar) füllt die Matrix komplett aus lokalen Snapshots;
  zweite Ausführung nutzt Cache/Delta (keine doppelten Abrufe).
- Kalender-Historie ≥ 1 Jahr aus dem MT5-Exporter in `calendar_events` (point-in-time:
  `actual_first`/`actual_latest`).
- Klimatologie-Zahlen der Berichte (~43 %) werden mit eigenen Brokerdaten reproduziert
  oder dokumentiert korrigiert (Abweichung > 5 pp → Tagesschnitt-/Brokerdefinition prüfen).
- JUnit: Wochentags-Statistik und Schwelle B gegen Ankerreihen; Zeitzonentests
  (Eastern-Offset, MT5-Serverzeit, DST-Lücke).

**Tor T2 (vor S3):** Eigene Klimatologie steht und ist plausibel; MT5-Kalenderexport
deckt NFP/CPI/FOMC mit Actuals ab (sonst: Nasdaq-JSON-Fallback in S3 mitnehmen).

---

## S3 — Prognosemodell („das Herzstück wird kalibriert")

**Bausteine**
1. **HAR auf ln(TR)** (commons-math3 OLS): Tages-/Wochen-/Monatsmittel + Wochentags-
   Dummies + Event-Dummies; `P(TR>B) = 1 − Φ((ln B − μ̂)/σ̂)`.
2. **Event-Multiplikatoren:** aus MT5-Kalenderhistorie × Kursen — Ø-TR an Event-Tagen
   ÷ Ø-TR vergleichbarer Normaltage, je ATR-Regime; Surprise-Normalisierung
   (|actual−forecast|/σ) für die Nachanalyse.
3. **Implizite Volatilität:** GVZ-CSV + GLD-Options-JSON (`iv30`) Adapter; Expected
   Move σ_Tag=IV/√252, E[Range]≈1,596σ·S; Event-Premium Weekly-IV vs. `iv30` (erst
   wenn Optionsketten-Auswertung da ist — sonst nur iv30-Level/Δ).
4. **Walk-Forward-Rücktest** (expanding window) über die eigene Historie:
  Brier-Score, Murphy-Zerlegung, **BSS gegen die eigene Klimatologie**, Log-Loss,
  Q10–Q90-Coverage, Pinball-Loss; Ablationsreihenfolge nach Astra-Evaluationsdesign
  (Klimatologie → +Events → +ATR-Regime → +GVZ/iv30).
5. Matrix zeigt `P_stat` je Tag (statt Klimatologie) + Modellversion; Journal/Bereich
   „Ergebnisse" zeigt die Backtest-Kennzahlen je Konfiguration.

**Abnahme**
- BSS des Modells (Klimatologie + Events + mindestens ein Volatilitäts-Feature) gegen
  die reine Klimatologie ist im Walk-forward **> 0** — nachweisbar im Journal.
- Reliability-Diagramm des Rohmodells existiert; erste Platt-Skalierung greift.
- Kein Look-ahead: Tests prüfen, dass für Tag t nur Informationen bis t−1 EOD fließen
  (point-in-time-Snapshots; DTWEXBGS-Wochenlatenz als Beispieltest).

**Tor T3 = Abnahme:** BSS > 0 stabil (z. B. positiv in ≥ 3 von 4 Walk-forward-Folds)?
Wenn nein: Modell/Features iterieren, **nicht** mit S4 fortfahren — sonst erklärt das
LLM später Rauschen. (Astra-Warnung: ein sauberer Range-/Event-Baseline-Ansatz könnte
einem komplexen Agentensystem überlegen sein — genau das misst dieser Tor-Kriterium.)

---

## S4 — LLM-Schicht („die Matrix wird erklärt")

**Bausteine**
1. News-Adapter: RSS-Liste (§7.2 Kernmenge: FXStreet, Google/Bing-News-RSS, FXEmpire,
   ING, ActionForex, Goldreporter, GOLD.DE, Investing-RSS) mit Delta-Prinzip
   (SHA-Hash je Item), Originalquellen-Dedup.
2. News-Destillations-Agent (glm-5.3-flash): Treiber mit Stimmung + Quellenlink,
   nur Strukturdaten; Prompts als externe MD-Dateien mit Slot-Füllung.
3. Community-Adapter + Destillation: TradingView-Ideas-RSS (privat/ToS-Hinweis),
   Kitco Weekly Survey, FXStreet Analysis, FXEmpire — Level-Cluster, Konsens-Richtung,
   Retail-Bias als Kontraindikator-Flag.
4. **Analytiker-Fusion** (glm-5.3, großes Budget): Inputs = P_stat, Range-Band,
   Klimatologie, Events, Destillate, Community-Konsens. Output-JSON (validiert):
   finale P im **Config-Band ±10 pp um P_stat** mit Pflichtbegründung je Abweichung,
   qualitative Richtung + Konfidenz, **Treiber-Wasserfall** je Tag, Textbegründung.
   Ungültige/unvollständige Antworten werden nie gespeichert (finish_reason≠stop etc.).
5. Reporter/Melder: Wochen-PDF (OpenPDF, Unicode-Fonts), Tagesdigest, Meldung bei
   Prognoseänderung ≥ Schwelle; Postfach im Dashboard.
6. Audit-Journal komplett: jeder LLM-Schritt mit vollem Prompt/Antwort/Modell/Tokens.

**Abnahme**
- Wochenlauf S3→S4 durchgängig: Matrix mit Treiber-Wasserfall, Begründungstext und PDF.
- Band-Disziplin greift: LLM-Abweichungen > Band werden abgewiesen und geloggt (Test
  mit absichtlich abweichender Model-Antwort).
- Token-Budgets je Lauf/Tag greifen; Fail-Fast nach 3 systemischen Fehlern.

**Tor T4 (vor S5):** Erste Plausibilitätsprüfung des **LLM-Deltas** (Abweichung von
P_stat): bewegt es sich begründet und selten (> 0 und < Band-Hälfte im Schnitt)?
Auffällig systematisches „immer +10 pp" → Prompt nachbessern, bevor Feeds erweitert werden.

---

## S5 — Richtung, Quant-Feeds & Kalibrierung („Vollständigkeit + Schärfe")

**Bausteine**
1. Quant-Adapter: FRED-CSVs (DFII10, T10YIE, DTWEXBGS, DGS10, VIXCLS), Treasury
   Real-Yield-CSV, CFTC-Socrata `088691` (Freitag 21:30 MESZ; Stichtag ≠ Veröffentlichung
   sauber speichern), SPDR-GLD-XLSX (Apache POI), LBMA-JSON.
2. Makro-/Regime-Agent: ΔRealzins/ΔDollar/VIX, rollierende Rendite-Korrelationen
   (nie Preisniveaus!), Regime „realzinsgetrieben vs. risk-off", Korrelationsbruch-Warnung.
3. Positionierungs-Agent: COT Managed-Money-Netto + 3-Jahres-Perzentil, GLD-Tonnen-Δ
   5 Tage → Crowding-Flag.
4. **Richtungsmodell:** logistische Regression P(Close > Vortag) mit Trend/SMA-Lage,
   ΔRealzins, ΔDollar, COT-Extremen, News-Sentiment-Bilanz, Community-Bias (Kontra);
   eigene Kalibrierung + eigene Baseline (Drift/Ø-Aufwärtstage). Matrix-Spalte
   „Richtung: ▲▲/▲/▬/▼/▼▼ + P(hoch)".
5. Klassifikator-Ausbau: Gradient Boosting (Smile 4.x — Java-21-Kompatibilität
   verifizieren) neben logistischer Regression; Feature-Auswahl nur im Trainingsfenster.
6. **Nachkalibrierung:** Platt-Skalierung sofort, Isotonic ab ~500 Beobachtungen;
   Kalibrierparameter versioniert in `kalibrierung`.
7. Session-/Gap-Agent: Asia-Range bis 08:00 MEZ, Wochenend-Gap → **Intraday-Revision**
   der heutigen P (Tageslauf-Erweiterung + eigene Meldung).

**Abnahme**
- Richtung: P(hoch) eigenes kalibriertes Feld; Brier des Richtungsmodells < Baseline
  („immer Ø-Aufwärtswahrscheinlichkeit") im Walk-forward.
- Feed-Nutztest: Hinzufügen jeder Quant-Gruppe einzeln per Walk-forward gegen
  identische Testtage geprüft und in `kalibrierung` dokumentiert (Ablation).
- Intraday-Update 08:00 messbar: Revision der heutigen P nach Asia-Range mit Brier-
  Vergleich „06:30-Prognose vs. 08:00-Prognose" über Zeit.

**Tor T5:** Mind. ein Quant-Feed verbessert BSS messbar; Richtung schlägt ihre
Baseline. Stillstand → Feeds kürzen statt erweitern (Kosten-/Komplexitätsersparnis).

---

## S6 — Betrieb & Selbstverbesserung („läuft allein und weist es nach")

**Bausteine**
1. Daemon + Scheduler komplett (Rhythmus §10 des Konzepts: Wochenlauf So 18:00,
   Tageslauf 06:30, Session-Update 08:00, Actuals nach 14:30-ET-Release, CFTC Fr
   21:30 MESZ, Verifikation Sa 09:00, Haushaltung monatlich) — DETACHED-Prozess,
   Herzschlag, Merker gegen Wiederholung, Lock gegen GUI-Doppelläufe.
2. Verifikations-/Backtest-Agent: tägliche Auswertung (TR, H−L, Close-Richtung vs.
   Prognoseversion), Brier/BSS-Verlauf, Reliability-Bins, **LLM-Delta-Nutztwert**
   („bringt die LLM-Anpassung historisch etwas?" → sonst Band auf 0).
3. Track-Record-Bereich: Reliability-Diagramm mit Konsistenzbalken, BSS-Verlauf
   13/52 Wochen, Richtungstreffer, Coverage der Range-Bänder, Prognose-Plumes
   (Sonntags-Vorab vs. Tagesrevisionen sichtbar).
4. URL-Scout: Google/Bing-News-RSS als Default, Tavily optional (Key in Config);
   Bewertung (Gold-Anteil, Frequenz, Format, Rechte) → Vorschlagsliste mit
   Annehmen/Ablehnen in der Quellen-UI; „Jetzt testen"-Probeabruf je Vorschlag.
5. MT5-Export: Wahrscheinlichkeiten/Range/Richtung je Tag als CSV-Datei (Pfad in
   Config) für eigene EAs (Handelsfilter/Lot-Größe).
6. Wächter komplett: Provenienz-protokoll je Quelle, Alarm bei stiller Veränderung
   (Feldänderungen, Formatwechsel), robots/ToS-Stichprobe monatlich.

**Abnahme**
- 14-Tage-Dauerbetrieb ohne manuellen Eingriff; Daemon überlebt UI-Schließung;
  kooperativer Stopp funktioniert.
- Track-Record füllt sich automatisch; eine komplett vergangene Woche ist durchgerechnet
  (Prognose → Verifikation → Rekalibrierungsvorschlag).
- Scout liefert wöchentlich ≥ 1 bewerteten Vorschlag; Annehmen/Ablehnen ändert die
  aktive Quellenliste inkl. Wächter-Registrierung.

---

## S7 — Optionaler Ausbau (nach Bedarf, einzeln beauftragbar)

| Baustein | Nutzen | Voraussetzung |
|---|---|---|
| GJR-GARCH / CARR (ML-Schätzung) | alternatives Vola-Feature | S3-Ergebnisse lassen Luft nach oben |
| Options-Skew/Termstruktur (GLD-Kette) | Event-Premium, Rich-Cheap-Signale | Cboe-CDN-Rechte geprüft |
| „Mindestens ein Bewegungstag diese Woche" | Wochen-Summenwert | gemeinsame Verteilung modellieren |
| Was-wäre-wenn-Modus | Szenario-Simulation (klar als Simulation gekennzeichnet) | S5 |
| Myfxbook Community Outlook (eigener Account) | Retail-Kontra-Indicator | Account + API-Login |
| WGC/Makro-Quellen mit Zugang | Regime-Kontext | Registrierung/Rechte geklärt |
| REST-API (wie KiScanner) | Anbindung anderer Tools | Bedarf |

---

## Querschnittsregeln (gelten in jeder Stufe)

1. **App bleibt startbar:** jede Lieferung durchläuft `start.bat`-Smoke-Test;
   Config-/DB-Schema wird versioniert migriert (nie blind überschreiben).
2. **Engine rechnet, LLM zitiert:** neue Zahlen immer zuerst in Java deterministisch,
   LLM nur in Destillation/Erklärung — freie LLM-Prozentwerte fließen nie unbegrenzt ein
   (Band-Konfiguration).
3. **Tests je Stufe:** JUnit-Ankertests für Kennzahlen/Modelle, Zeitzone-/DST-Tests,
   Adapter-Tests mit aufgezeichneten Antwortmustern (inkl. Störfall „200+HTML"),
   Whitelist-Statiktest für die Bridge; jede Abnahmekriterium der Stufe hat einen Test.
4. **Budget & Höflichkeit:** Abruffrequenzen §7/§11 des Konzepts sind Bestandteil der
   Abnahme; der Wächter protokolliert Verstöße sofort sichtbar.
5. **Journal vor Trockenmodus:** jeder LLM- und Modelllauf vollständig in SQLite —
   Grundlage für Backtests und die Tor-Entscheidungen.
