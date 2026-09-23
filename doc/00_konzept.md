# MqlGoldscanner — Konzept (v0.2.5, Stand 23.09.2026)

Multi-Agenten-Tool, das den Goldmarkt (XAUUSD) recherchiert und für jede Kalenderwoche
eine Übersicht erstellt. **Hauptziel: Für jeden Wochentag eine kalibrierte Aussage zu
(a) Wahrscheinlichkeit einer überdurchschnittlichen Bewegung, (b) erwarteter Stärke
(Range in USD mit Unsicherheitsband) und (c) Richtung (hoch/runter/neutral) — egal
über welchen Weg die Agentenkette dorthin kommt.**

Grundlagen:
- Vorbild `D:\git\MQL\MqlKiScanner` — und seit dem 23.09.2026 auch **gleiche Technik**:
  **Python/Streamlit** (Nutzer-Entscheidung nach UI-Vergleich; der Java/JavaFX-Prototyp
  wurde auf Nutzer-Wunsch komplett entfernt). Design (`ui_design.py`-Port mit
  Gold-Akzenten, Radar-Grid, Stepper), GLM-Client, Lock, Secrets und MT5-Zugang sind
  direkt aus dem KiScanner portiert; `MetaTrader5` ist Python-nativ (keine Bridge mehr).
- Deep-Research-Berichte 23.09.2026 in `doc/DeepResaearch/` (Astra = live-getestete
  Quellen mit Prüfprotokollen; Opus = eigener URL-Testlauf `testlauf/` + Methodik;
  Gemini = Methodik/Agenten-Ideen). Bei Widersprüchen gewinnen die Live-Tests
  (Astra/Opus); unverifizierte Gemini-Angaben sind mit **(U)** markiert.

---

## 1. Wichtigste Erkenntnisse aus der Deep Research (betriebsentscheidend)

1. **Basisrate liegt bei ~43 %, nicht 50 %.** Eigene Rechnung (Opus, GC=F, 5 Jahre,
   1.257 Handelstage): P(Bewegungstag) gesamt 43,0 % — Mo 41,2 %, Di 43,7 %,
   Mi 45,7 %, Do 42,7 %, Fr 41,7 %. Ursache: TR ist rechtsschief → Median < Mittelwert.
   **Jede Prognose muss diese „Klimatologie" im Brier-Skill-Score schlagen**, sonst hat
   sie keinen Mehrwert. (Mit MT5-XAUUSD-Daten wiederholen — Futures enthalten
   Roll-Artefakte.)
2. **ForexFactory-Feed lebt, liefert aber KEINE Ist-Werte.** `ff_calendar_thisweek.json`
   (auch .xml/.csv) funktioniert; `nextweek`/`expired`-Varianten existieren nicht (404)
   → **Wochenfeeds selbst täglich archivieren** (Point-in-time-Snapshots).
3. **Ist-Werte (Actuals) kommen über zwei Wege:** den offiziellen **MT5-Wirtschaftskalender**
   (MQL5 `CalendarValueHistory` — historisch, offiziell, kostenlos; das Python-Paket
   `MetaTrader5` hat KEINE Kalenderfunktionen → kleines MQL5-Exportskript nötig) oder
   den inoffiziellen **Nasdaq-JSON** (`api.nasdaq.com/api/calendar/economicevents`,
   liefert `actual`/`consensus`; robots.txt sperrt `/api/` → ToS-grau, nur als Fallback).
4. **Blockiert für Java-Clients (Cloudflare/DataDome/401):** Myfxbook (Web UND RSS; die
   offizielle API hat **keinen** Kalender-Endpunkt), Investing-Web (RSS geht!),
   ForexFactory-Web, Reuters, MarketWatch-Web, BabyPips, Reddit, Stooq, goldseiten.de,
   Trading-Economics-Guest (410), CME-Web (Akamai 403 + explizites Scraping-Verbot).
   **DailyFX ist tot** (2024 in IG aufgegangen).
5. **Behörden-APIs sind die stärkste Basis (alles verifiziert 200):** Fed `calendar.json`
   (UTF-8-BOM!), Fed-RSS, BLS-ICS, BEA-ICS/JSON, TreasuryDirect-Auktions-JSON,
   FiscalData, CFTC-Socrata (Gold-Code `088691` verifiziert), FRED-CSV ohne Key
   (DFII10, DTWEXBGS, …), Treasury-Real-Yield-CSV (schneller als FRED).
6. **Implizite Volatilität kostenlos:** Cboe GVZ-Historie als CSV UND das
   GLD-Options-JSON mit **`iv30` direkt im Header**. Opus-Plausibilitätscheck am
   23.09.2026: σ_Tag = iv30/√252 = 1,32 % → erwartete Range ≈ 1,596σ ≈ 92 USD, während
   ATR(14) bei 94,7 USD lag (±3 % Übereinstimmung). **Stärkster Einzelprädiktor.**
7. **Suche ohne Key:** Google-News-RSS + Bing-News-RSS (beide verifiziert) decken den
   Scout-Bedarf; Tavily funktioniert sogar keyless bzw. mit 1.000 freien Credits/Monat.
   DuckDuckGo ist im Test blockiert; Bing-Such-API eingestellt (11.08.2025); Google CSE
   für Neukunden geschlossen; Brave ohne Free-Tier seit Feb. 2026.
8. **Richtung ist ein eigenes Kalibrierziel.** P(TR > Schwelle) sagt nichts über die
   Richtung. Richtung wird als separates Ziel P(Close > Vortages-Close) modelliert,
   kalibriert und angezeigt (Astra-Methodikteil, Gneiting/Raftery).
9. **Architektur-Empfehlung aller Berichte:** Sammel-Adapter schreiben asynchron in
   lokale SQLite-Snapshots; **der Analytiker greift nie selbst live auf das Internet
   zu.** Schützt vor Rate-Limits, macht Backtests möglich und das System
   netzausfallfest.
10. **Zwei Stolperfallen:** HTTP 200 beweist nichts (alte GLD-CSV-URL liefert heute ein
    PDF mit Content-Type application/pdf!) → jede Antwort auf Content-Type und
    Dateisignatur prüfen (Wächter-Dienst). Und: Java-Default-User-Agent wird von
    mehreren Quellen blockiert (Yahoo, mining.com, investinglive, SilverSeek) →
    **ehrlicher eigener User-Agent** `MqlGoldscanner/0.1 (+Kontakt)`, kein Browser-UA-Spoofing.

---

## 2. Zielgrößen (vertragliche Definitionen)

| Ziel | Definition | Ausgabe |
|---|---|---|
| **Bewegungstag** | True Range > k × Ø-TR desselben Wochentags der letzten 13 Wochen (k = 1,0, konfigurierbar) | `P(TR > B)` 0–100 % |
| **Schwelle B** | der konkrete Schwellwert | in USD angezeigt |
| **Stärke** | erwartete High-Low-Range | Q10/Q50/Q90-Band in USD |
| **Richtung** | separater Zielwert | `P(Close > Vortages-Close)` + qualitative Tendenz (▲▲/▲/▬/▼/▼▼) mit Begründung |

Präzisierungen aus der Forschung:
- TR = max(H−L, |H−C_prev|, |L−C_prev|); H−L und |C−C_prev| getrennt mitausweisen.
- **Relative TR (TR/Close)** für lange Historien nutzen (Goldpreis hat sich seit 2022
  mehr als verdoppelt → absolute TR langfristig nicht vergleichbar); absolute TR nur
  im 13-Wochen-Fenster.
- Tagesschnitt festlegen: **NY-Close 17:00 ET** als Tagesgrenze; MT5-Serverzeit
  (meist UTC+2/+3, DST-Lücken US/EU im März/Okt–Nov) dokumentieren und versionieren.
- Fehlende Tage (Feiertage, keine Broker-Bars) nicht als 0 werten; Anzahl Beobachtungen
  und Sessiondefinition ausweisen.
- „Mindestens ein Bewegungstag diese Woche" nur aus einer gemeinsamen Verteilung
  schätzen (1−∏(1−p) setzt Unabhängigkeit voraus, die nicht belegt ist) → Phase 2.

---

## 3. Prognose-Kern: Statistik zuerst, LLM gewichtet erklärt

Weiterentwicklung des KiScanner-Prinzips „Engine rechnet, LLM zitiert":

```
Schicht 1  Adapter (deterministisch, Java)      → Rohdaten-Snapshots in SQLite
Schicht 2  Statistik-Kern (Java)                → P(TR>B), Range-Quantile, P(Richtung)
Schicht 3  LLM-Agenten (GLM)                    → Destillation, qualitative Anpassung
                                                      im Config-Band (Default ±10 pp),
                                                      Treiber-Erklärung, Begründung
Schicht 4  Verifikation (Java)                  → Brier/BSS, Reliability, Rekalibrierung,
                                                      LLM-Delta-Nutzzwert-Messung
```

### 3.1 Statistik-Modelle (alle in Java, chronologisch walk-forward)

1. **Klimatologie (Baseline, Pflicht):** Wochentags-Basisraten aus eigener Historie
   (~43 %). Referenz für den Brier Skill Score. Shrinkage p=(k+α)/(n+α+β).
2. **HAR auf ln(TR)** (Corsi 2009) — Kernmodell:
   `ln TR_t+1 ~ β0 + βd·TR_t + βw·mean(TR_{t-4..t}) + βm·mean(TR_{t-21..t}) + γ·Wochentags-/Event-Dummies + δ·GVZ_t`
   OLS mit `commons-math3` (`OLSMultipleLinearRegression`); Residuen in Log-Form nahezu
   normal → `P(TR > B) = 1 − Φ((ln B − μ̂)/σ̂)`. In der Literatur erhöht GVZ im HAR das
   R² deutlich (Hysa 2026 (U), Qiao et al. 2026 (U)).
3. **Range-Volatilitätsschätzer aus OHLC** (ohne externe Daten): Parkinson, Garman-Klass,
   Rogers-Satchell, **Yang-Zhang** (bevorzugt: robust gegen Sonntags-Gaps, driftfrei).
4. **Event-Multiplikatoren (gemessen statt „High Impact"):** Ø-TR an historischen
   NFP-/CPI-/FOMC-/PCE-/GDP-/ISM-/Auktions-/Powell-Tagen ÷ Ø-TR sonst, je ATR-Regime,
   aus MT5-Kalenderhistorie + MT5-Kursen. NFP-Proxy-Vorbefund (Opus): Ø TR 56,9 vs.
   52,4 USD an anderen Freitagen — Effekt real, aber kleiner als landläufig angenommen.
   Evidenz: Elder/Miao/Ramchander 2012 (NFP größter Effekt), Roache/Rossi 2009,
   Smales/Lucey 2019 (FOMC).
5. **Implizite Volatilität → Expected Move:** σ_Tag = IV/√252; E[Range] ≈ 1,596·σ·S
   (Brownsche Näherung, gegen ATR(14) validiert ±3 %). Quellen: GVZ-CSV, GLD-Options-
   JSON `iv30`. Event-Premium: IV der Weekly-Option vor NFP/FOMC vs. `iv30`.
6. **Klassifikator:** Logistische Regression (Baseline, interpretierbar) und Gradient
   Boosting (Smile `GradientTreeBoost`; Smile 4.x = Java 21, 5.x = Java 25 beachten)
   mit Features: TR-Lags (HAR), Yang-Zhang, GVZ/iv30 + Δ, Event-Dummies mit gemessenen
   Multiplikatoren, Wochentag, ΔDFII10, ΔDollar, COT-Perzentil, Asia-Session-Range
   (Intraday-Update!), Wochenend-Gap.
7. **Richtungsmodell:** eigene logistische Regression für P(Close > PrevClose) mit
   Trend/SMA-Lage, ΔRealzins, ΔDollar, COT-Extremen, News-Sentiment-Bilanz,
   Community-Bias (Retail-Bias als Kontraindikator).
8. **Kalibrierung:** Brier-Score + Murphy-Zerlegung (Reliability/Resolution/Uncertainty),
   **BSS gegen die 43-%-Klimatologie**, Log-Loss, Pinball-Loss für Range-Quantile,
   Q10–Q90-Coverage. Reliability-Diagramm mit Konsistenzbalken (Bröcker/Smith 2007).
   Nachkalibrierung Platt/Isotonic (ab ~500 Beobachtungen Isotonic vorziehen).
9. **Agenten-Kombination:** Stacking/logistische Kombination der Teilsignale statt
   fester Gewichte; Feature-/Feed-Zuwachs einzeln per Walk-forward gegen identische
   Testtage prüfen (Astra-Evaluationsdesign: Baseline → Events → ATR-Regime → GVZ →
   Makro → COT/ETF → News).
10. **Optional Phase 2:** GJR-GARCH mit invertierter Asymmetrie (positive Schocks
    erhöhen Gold-Vola stärker — Safe Haven, Baur 2012) und CARR (Range-GARCH, Chou
    2005) via Maximum-Likelihood (`BOBYQAOptimizer`/`NelderMeadSimplex`, ~150 Zeilen).
    Priorität unter HAR, weil HAR für Tages-TR in der Literatur mindestens gleichwertig ist.

### 3.2 Rolle des LLM-Analytikers (sauber begrenzt)

- Erhält: Modell-P(TR>B), Range-Band, P(Richtung), Klimatologie, Eventliste,
  destillierte News-Treiber, Chart-Community-Konsens, Positionierungs-/Makro-Lage,
  Kalibrierhistorie („System zuletzt overconfident").
- Liefert (JSON, Pflichtfelder, von Java validiert): finale Wahrscheinlichkeit **im
  Config-Band um P_stat** (Default ±10 Prozentpunkte; jede Abweichung mit Begründung),
  Richtungstendenz, Treiber-Wasserfall (siehe §6), Konfidenz, Textbegründung je Tag.
- Der Verifikations-Agent misst separat, ob die LLM-Abweichungen historisch Mehrwert
  bringen („LLM-Delta"). Falls nicht: Band auf 0 stellen → reines Statistikmodell.

---

## 4. Architektur

```
                     ┌─────────────────────────────────────────────────┐
                     │              JavaFX-Oberfläche                   │
                     │ Dashboard · Tagessicht · Chart · Quellen ·       │
                     │ Agenten · Konfig · Journal · Track-Record        │
                     └───────────────────────┬─────────────────────────┘
                                             │
                     ┌───────────────────────▼─────────────────────────┐
                     │  Dirigent (Orchestrierung, Budgets, Whitelist)   │
                     │  + Quellen-Wächter (Provenienz & Gesundheit)     │
                     └──┬──────────────────────────────────────────────┘
                        │
   ┌────────────────────▼──────────────── Snapshot-Store (SQLite) ────┐
   │ Adapter (async, Cron-Takt, deterministisch, kein LLM):           │
   │  ① Kurse:   MT5-Python-Bridge (D1/H4/H1, read-only)              │
   │  ② Kalender:FF-Feed · BLS/BEA-ICS · Fed-JSON/RSS · EZB ·         │
   │             TreasuryDirect · CFTC-Releaseplan · Regeltermine     │
   │ ③ Actuals:  MT5-MQL5-Kalender-Exporter (primär) · Nasdaq-JSON    │
   │ ④ News:     RSS-Liste EN/DE · Google/Bing-News-RSS               │
   │ ⑤ Quant:    GVZ · GLD-iv30 · FRED · RealYield · COT · GLD-XLSX · │
   │             LBMA-JSON                                             │
   │ ⑥ Community:TradingView-RSS · FXStreet · Kitco-Survey · FXEmpire │
   └──┬───────────────────────────────────────────────┬───────────────┘
      │                                               │
┌─────▼──────────────────┐              ┌─────────────▼──────────────┐
│ Statistik-Kern (Java)  │              │ LLM-Agenten (GLM)          │
│ Klimatologie · HAR ·   │              │ News-Destillation ·        │
│ Event-Multiplikatoren ·│              │ Community-Destillation ·   │
│ IV-Expected-Move ·     │◄────────────►│ Analytiker (Fusion, Band)  │
│ Klassifikator ·        │              │ Meldungen/Reporter (PDF)   │
│ Richtungsmodell ·      │              └────────────────────────────┘
│ Kalibrierung           │
└─────┬──────────────────┘
      │
┌─────▼──────────────────────────────────────────────────────────────┐
│ Wochenmatrix (P je Tag · Range-Band · Richtung · Treiber)          │
│ + Verifikations-/Backtest-Agent (Brier, BSS, Reliability, Plume)   │
└────────────────────────────────────────────────────────────────────┘
```

LLM-Zugang wie KiScanner: `java.net.http.HttpClient` gegen
`https://api.z.ai/api/coding/paas/v4` (Abo, Default) bzw. `/api/paas/v4` (PAYG),
Bearer-Key, `/chat/completions`, kein Streaming; zwei Stufen `glm-5.3-flash`
(Destillation) / `glm-5.3` (Analytiker, Reporter); Fehler-Taxonomie 1113/429·1302/
finish_reason≠stop; Token-Budgets je Lauf/Tag/Woche thread-sicher; Rate-Limiter,
Backoff, Fail-Fast; Audit-Journal mit vollen Prompts/Antworten in SQLite;
Prompts als externe Markdown-Dateien mit Zwei-Phasen-Slot-Füllung.

---

## 5. Agenten und Adapter

### Schicht 1 — Daten-Adapter (deterministisch, Java)

| Adapter | Quellen (§7) | Takt |
|---|---|---|
| **Kurse** | MT5-Python-Bridge `mt5bridge/fetch_gold.py` (Whitelist read-only, portable Terminal, PID-genau beendet; aus KiScanner `marktdata.py`) | werktäglich 06:25 + nach US-Close |
| **Kalender** | FF thisweek (4×/Tag, selbst archivieren) + BLS/BEA-ICS + Fed calendar.json/RSS + EZB + TreasuryDirect + CFTC-Releaseplan | 1–2×/Tag; Jahrespläne wöchentlich |
| **Regeltermine** | **in Java berechnet statt gescraped:** GC First Notice Day (1. Geschäftstag des Liefermonats), Last Trade Day (drittletzter Geschäftstag), Options-Verfall (4 Geschäftstage vor Ende des Vormonats; Liefermonate Feb/Apr/Jun/Aug/Okt/Dez), Quartalsende, US/UK-Feiertage, DST-Übergänge | rein rechnerisch |
| **Actuals** | MT5-MQL5-Exporter (`CalendarValueHistory`, Werte ×10⁶ skaliert, Serverzeit!) primär; Nasdaq-JSON sekundär | intraday nach 14:30-ET-Releases |
| **News** | RSS-Liste (§7.2) + Google-News-RSS/Bing-News-RSS (EN/DE) | RSS alle 1–3 h; Such-RSS ≤ 1×/10 min |
| **Quant** | GVZ-CSV + GLD-Options-JSON (iv30), FRED-CSVs, Treasury Real Yield, CFTC-Socrata 088691, SPDR-GLD-XLSX, LBMA-JSON | je Quelle 1×/Tag; CFTC Fr nach 21:30 MESZ |
| **Community** | TradingView-Ideas-RSS, FXStreet, Kitco Weekly Survey, FXEmpire, ActionForex | 1–2×/Tag; Kitco Fr/Sa |

Dazu der **Quellen-Wächter (P0, aus Astra übernommen):** überwacht je Quelle
HTTP-Status, Content-Type, Dateisignatur (200+HTML statt CSV = gestört, nicht
„leerer Markttag"), Datenalter, Feldänderungen, Duplikate; protokolliert
`observed_at/published_at/retrieved_at`. Ein wiederholt unveränderter Datensatz ist
nicht automatisch frisch. Originalquellen-Dublettenprüfung: dieselbe Agenturmeldung
auf fünf Portalen zählt einmal (Autoren/Original-URL deduplizieren).

### Schicht 2/3 — Analyse- und LLM-Agenten

| Agent | Aufgabe | Modell |
|---|---|---|
| **Statistik-Kern** | §3.1 Modelle 1–8 | Java, kein LLM |
| **News-Destillations-Agent** | RSS-Snapshots → Gold-Treiber mit Stimmung, Quellenangabe; Delta-Prinzip (SHA-256, unverändert = kein Aufruf); Dubletten ausfiltern | glm-5.3-flash |
| **Community-Destillations-Agent** | fremde Chartanalysen → Level-Cluster (Instrument/Datum/Horizont/ATR-normierte Distanz), Konsens-Richtung, Dissens; Retail-Bias als Kontraindikator kennzeichnen | glm-5.3-flash |
| **Event-Impact-Agent** | liefert die gemessenen TR-Multiplikatoren + Surprise-Historie (Actual−Forecast normalisiert); formuliert Event-Lage | glm-5.3 |
| **Vola-/Options-Agent** | iv30/GVZ → implizite Tagesrange vs. Schwelle B; Event-Premium (Weekly-IV vs. 30d); „Markt erwartet Bewegung X" | glm-5.3 (Java rechnet) |
| **Makro-/Regime-Agent** | ΔRealzins, ΔDollar, VIX; rollierende Korrelationen aus Renditen (nie aus Preisniveaus); Regime „realzinsgetrieben vs. risk-off"; warnt bei Korrelationsbruch (Regime-Shift) | glm-5.3 |
| **Positionierungs-Agent** | COT Managed-Money-Netto + 3-Jahres-Perzentil (Stichtag ≠ Veröffentlichung!), GLD-Tonnen-Δ 5 Tage → Crowding/Squeeze-Risiko | glm-5.3-flash |
| **Session-/Gap-Agent** | Asia-Range bis 08:00 MEZ, Wochenend-Gap, London-Open → **Intraday-Update der Tagesprognose** (deutlich früher Informationsgewinn) | Java + flash |
| **Analytiker (Fusion)** | §3.2 — Wochenmatrix + Tagesbewertungen | glm-5.3, großes Budget |
| **Verifikations-/Backtest-Agent** | §3.1 Nr. 8/9; historischer Replay mit archivierten Snapshots (point-in-time), BSS vs. Klimatologie, LLM-Delta-Nutztwert, Rekalibrierung | Java |
| **Dirigent** | Orchestrierung, Budgets; LLM-Aktionen nur über Code-Whitelist | glm-5.3 |
| **Reporter/Melder** | Wochen-PDF (OpenPDF), Tagesdigest, Warnung bei Prognoseänderung ≥ Schwelle | glm-5.3 |
| **URL-Scout** | neue Quellen via Google/Bing-News-RSS + optional Tavily; Bewertung (Gold-Anteil, Frequenz, Format, Rechte) → Vorschlag, Nutzer entscheidet | glm-5.3-flash |

Zurückgestellt (Phase 2+): GARCH/CARR, China/SGE-Agent (technisch derzeit schwer),
Google-Trends (API nur Alpha), WGC-Flows (Downloads 403/Registrierung), IMF
(monatlich, für Tagesprognosen irrelevant), Optionsketten-Vollausbau (Skew/Termstruktur).

---

## 6. Das Kernprodukt: Wochenmatrix v2

Pro Wochentag **sechs getrennte Informationen** (Astra-Forderung: Wahrscheinlichkeit,
Schwelle, Range-Band, Richtung, Top-Events, Datenstand):

```
Woche 40 · 28.09.–02.10.2026                        [Scan läuft ▸]   Datenstand: So 18:02
┌────────────────────────────────────────────────────────────────────────────────┐
│ MO 28.09.                                        P(Bewegung)  ▓▓▓▓▓▓░░░ 62 %      │
│ Schwelle B: 96 USD (Ø-TR Mi, 13W)   normal: 44 % ▏▲ überdurchschnittlich         │
│ Range Q10–Q90: ████████████░░ 78–135 USD   (Q50: 104)                           │
│ Richtung: ▲▲ bullish  P(hoch) 58 %                                               │
│ Treiber:  Klimatologie 43% ▸ +12 NFP-Morgen ▸ +8 iv30 über Schwelle ▸ −3 COT-   │
│           Crowding ▸ +2 FOMC-Vorwoche  = 62 %                                    │
│ Events:   14:30 NFP (Konsens 140k) · 16:00 ISM · Reden 18:00                     │
└────────────────────────────────────────────────────────────────────────────────┘
… (Di–Fr analog) …
```

Elemente (Vorbilder NOAA-Wetter, USGS-Erdbeben, CME-FedWatch, BoE-Fan-Chart):

1. **Wahrscheinlichkeit + Klimatologie im selben Balken:** „62 % (normal: 44 %)" —
   sofort erkennbar, ob der Tag auffällig ist.
2. **Schwellen-Tabelle** Wochentag × Faktor: P(TR > 1,0× / 1,5× / 2,0× Ø-TR) — zeigt
   auch das Extremrisiko (USGS-Vorbild).
3. **Range als Fan/Band:** Q10–Q90 horizontal, Q50 und Mittelwert getrennt markiert;
   keine Dezimal-Scheinpräzision aus dünnen Daten.
4. **Richtung eigenständig:** P(hoch) + qualitative Tendenz (▲▲/▲/▬/▼/▼▼); bei hoher
   Bewegungswahrscheinlichkeit darf Richtungstrahlität „neutral" sichtbar sein.
5. **Treiber-Wasserfall** je Tag: Klimatologie → ± Beiträge der Faktoren (NFP, iv30,
   COT, Gap …) = Endwert (SHAP-artige Erklärung, für Vertrauen zentral).
6. **5-stufige Warnskala** (ruhig/normal/erhöht/hoch/extrem) als Ampel-Schnellansicht.
7. **Prognose-Plume:** Wie hat sich die P(Freitag)-Prognose seit Montag entwickelt
   (Ensemble-Plume-Vorbild) — Wochen-Vorabprognose bleibt neben Revision sichtbar.
8. **Track-Record-Seite:** Reliability-Diagramm mit Konsistenzbalken, BSS vs. 43 %
   der letzten 13/52 Wochen, Richtungstrefferquote, LLM-Delta-Nutztwert.
9. **MT5-Export:** Wahrscheinlichkeiten als CSV/Datei für eigene EAs (Handelsfilter/
   Lot-Größe) — Option in Config.

Tagessicht, Chart (Candlestick D1/H1, SMA-Overlays, Level-Cluster, Wochentags-TR-
Balken, GVZ-Verlauf), Quellen-, Agenten-, Konfig- und Journal-Bereiche wie in v0.1
(7 Bereiche + Track-Record als 8.).

---

## 7. Datenquellen (verifiziert am 23.09.2026, Auszug je Adapter)

> Vollständige Kataloge mit Formatbeispielen, Testprotokollen und Belegen:
> `doc/DeepResaearch/` (Astra, Opus). Legende: ✅ verifiziert maschinenlesbar ·
> 🟡 nutzbar mit Einschränkungen (ToS/Rate/HTML) · ❌ nicht verwenden.

### 7.1 Kalender & Termine
| Quelle | URL | Format | Status/Frequenz |
|---|---|---|---|
| ForexFactory thisweek | `https://nfs.faireconomy.media/ff_calendar_thisweek.json` (.xml/.csv) | JSON/XML/CSV | ✅ 200; **kein actual**; ≤ 4×/Tag; selfarchivieren; ToS restriktiv |
| BLS Release-Kalender | `https://www.bls.gov/schedule/news_release/bls.ics` | ICS | ✅ 200 (Astra: 403 — bei uns erneut testen) — NFP/CPI/PPI/JOLTS mit Uhrzeit |
| BEA Release-Kalender | `https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics` · `https://apps.bea.gov/API/signup/release_dates.json` | ICS/JSON | ✅ 200 — GDP/PCE |
| Fed Terminkalender | `https://www.federalreserve.gov/json/calendar.json` (BOM!) · `…/monetarypolicy/fomccalendars.htm` | JSON/HTML | ✅ 200 — FOMC/Minutes/Reden |
| Fed RSS | `https://www.federalreserve.gov/feeds/speeches.xml` · `press_monetary.xml` · `press_all.xml` (alle: `/feeds/feeds.htm`) | RSS | ✅ 200 |
| EZB | `https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html` · RSS `/rss/press.html` | HTML/RSS | ✅ 200 |
| Treasury-Auktionen | `https://www.treasurydirect.gov/TA_WS/securities/announced?format=json` · FiscalData `…/od/upcoming_auctions` | JSON | ✅ 200 — 2y–30y filtern, FRN ausschließen |
| CFTC-Releaseplan | `https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm` | HTML | ✅ — Fr 15:30 ET, Datenstand Dienstag |
| Actuals primär | MT5-MQL5-Kalender: `CalendarValueHistory` (Doku `mql5.com/en/docs/calendar`) | CSV-Export | ✅ offiziell; ×10⁶-Skalierung, Serverzeit; Exportskript bauen |
| Actuals sekundär | `https://api.nasdaq.com/api/calendar/economicevents?date=YYYY-MM-DD` | JSON | ✅ 200 mit actual/consensus; robots sperrt `/api/` → ToS-grau, 1–3×/Tag |
| ❌ Negativ | FF-Web, Myfxbook (Web/RSS/API ohne Kalender-Endpunkt), Investing-Web, Trading-Economics-Guest (410), Reuters, MarketWatch, BabyPips, DailyFX (tot), FXMacroData **(U, nur Gemini, ungeprüft)**, CME-Kalender (Akamai; stattdessen regelbasiert rechnen) | – | nicht verwenden |

### 7.2 News & Analyse (RSS bevorzugt)
| Quelle | URL | Status |
|---|---|---|
| FXStreet RSS | `https://www.fxstreet.com/rss/news` · `…/rss/analysis` | ✅ je 30 Items; nach „Gold\|XAU" filtern; ≤ 1×/15 min (Cloudflare-429) |
| **Google News RSS** | `https://news.google.com/rss/search?q=gold+price+when:7d&hl=en-US&gl=US&ceid=US:en` (+ DE-Variante, + `site:kitco.com` …) | ✅ 100 Items; Links sind Redirects (auflösen); ≤ 1×/10 min |
| **Bing News RSS** | `https://www.bing.com/news/search?q=gold+price&format=rss` | ✅ 6–8 Items, direkte Links |
| FXEmpire RSS | `https://www.fxempire.com/api/v1/en/articles/rss/news` · `…/rss/forecasts` · DE: `…/de/articles/rss/news` | ✅ je 20 Items |
| Investing RSS | `https://www.investing.com/rss/news_11.rss` · `commodities_Technical.rss` · `commodities_Fundamental.rss` | ✅ RSS frei (Website 403); Artikel-Links teils geschützt |
| ING THINK | `https://think.ing.com/rss/` | ✅ täglich „The Commodities Feed" mit Gold-Absatz |
| Nasdaq Commodities RSS | `https://www.nasdaq.com/feed/rssoutbound?category=Commodities` · `?symbol=GLD` | ✅ kurze Gold-Tagesberichte |
| ActionForex Gold | `https://www.actionforex.com/tag/gold/feed/` | ✅ 18/20 Goldtitel — bester Gold-Tag-Feed |
| Goldreporter (DE) | `https://www.goldreporter.de/feed/` | ✅ 16/20 Goldtitel — beste DE-Quelle |
| GOLD.DE (DE) | `https://www.gold.de/rss.php` | ✅ offizieller Feed; Münzwerbung filtern |
| Weitere ✅ | Gold-Eagle `rss.xml` (Crawl-delay 10 s), GoldSeek `rss.xml`, Invezz `/feed/`, OANDA MarketPulse `/feed/`, investingLive `/feed` (Browser-UA-Pflicht → ehrlicher UA testen), wallstreet-online Rohstoffe (DE), finanzen.net news/analysen | ✅ gemischt, filtern |
| 🟡 HTML | Kitco `kitco.com/news/category/commodities/gold` (kein RSS → Ersatz: Google-News `site:kitco.com`), BullionVault, WGC Goldhub, Heraeus Weekly, Saxo/Sprott/Heraeus Research | 🟡 1–2×/Tag, Jsoup |
| ❌ Negativ | Reuters (401), MarketWatch-Web (401; RSS `feeds.content.dowjones.io/public/rss/mw_topstories` ist kein Goldfeed), mining.com (403), goldseiten.de (403), Myfxbook-News, Degussa alt | – |

### 7.3 Chart-Community & Sentiment
| Quelle | URL | Status |
|---|---|---|
| **TradingView Ideas RSS** | `https://www.tradingview.com/feed/?symbol=OANDA:XAUUSD` | ✅ 30 Items mit Beschreibung inkl. Kursmarken + Long/Short — **ToS: nur privat/display** |
| TradingView Scanner | `https://scanner.tradingview.com/symbol?symbol=OANDA:XAUUSD&fields=Recommend.All,RSI,ATR` | ✅ JSON mit ATR (Plausibilitätscheck) — ToS wie oben |
| Kitco Weekly Gold Survey | `https://www.kitco.com/news/category/weekly-gold-survey` | ✅ strukturierte bullish/bearish/neutral-Prozente, wöchentlich Fr/Sa |
| FXStreet Gold + Poll | `https://www.fxstreet.com/commodities/gold` · `…/rss/analysis` | ✅ Technik-Absätze + Forecast-Poll (Struktur U → parsen testen) |
| FXEmpire Forecasts | `https://www.fxempire.com/forecasts/gold` | ✅ täglich, mehrere Autoren |
| 🟡 | ActionForex Technical, IG Commodities (DailyFX-Ersatz), Saxo Research, economies.com, DailyForex | 🟡 HTML |
| ❌ | Investing Technical-Seite (403), Myfxbook Community Outlook (Web 403; API nur mit Login-Account `get-community-outlook.json` — optional konfigurierbar), Reddit (429/robots), Barchart (202-Challenge), IG Client Sentiment (Login) | – |

### 7.4 Quant-Marktdaten
| Metrik | URL | Status |
|---|---|---|
| **GVZ-Historie** | `https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv` | ✅ täglich, seit 2009; Backup FRED `fredgraph.csv?id=GVZCLS` |
| **GLD-Options-JSON (iv30!)** | `https://cdn.cboe.com/api/global/delayed_quotes/options/GLD.json` | ✅ 15 min verzögert; `iv30`, IV/OI/Greeks je Option (3,4 MB) |
| FRED ohne Key | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10` (Realzins 10J — wichtigster Makrotreiber) · `T10YIE` · `DTWEXBGS` (breiter USD, **nicht DXY**) · `DGS10` · `VIXCLS` | ✅ CSV; 1 Tag Verzug; SP500-Rechte beachten |
| Treasury Real Yield | `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_real_yield_curve…` | ✅ schneller als FRED (gleicher Tag) |
| **CFTC COT** | Socrata: `https://publicreporting.cftc.gov/resource/6dca-aqww.json?cftc_contract_market_code=088691…` (Legacy F+O) · Dataset `72hh-3qpy` (Disaggregated, `m_money_positions_long_all`) · Flatfiles `cftc.gov/files/dea/history/fut_disagg_txt_2026.zip` (Historien-Import) | ✅ Gold-Code 088691 verifiziert; Abruf Fr nach 21:30 MESZ; Socrata-App-Token kostenlos |
| **GLD-Bestände** | `https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en` | ✅ XLSX täglich (alte CSV-URL liefert heute PDF — nur ein Beispiel der 200-Falle); Apache POI; Weiterverbreitung untersagt (privat ok) |
| LBMA Fixing | `https://prices.lbma.org.uk/json/gold_pm.json` · `gold_am.json` | ✅ JSON seit 1968 (Opus-Test); Lizenz für Produktweiterverwendung klären |
| iShares IAU | Fondsseite HTML/Download | 🟲 BlackRock-ToS verbietet Agents — zurückgestellt |
| ❌ | Yahoo Chart-API (inoffiziell, 429 bei Java-UA — nur Backup), Stooq (JS-Challenge), CME-Web-JSONs (403 + AI-Verbot), Nasdaq Data Link LBMA (403), SGE (TLS/JS; Astra fand JSON-Endpunkt `sge.com.cn/graph/DayilyJzj` — Rechte unklar → zurückgestellt), Google Trends (API Alpha), CME FedWatch (API ab 25 $/Monat; Alternative Atlanta-Fed-Tracker (U)) | – |

### 7.5 Websuche für den Scout
| Weg | Details |
|---|---|
| **Default ohne Key** | Google-News-RSS + Bing-News-RSS (beide ✅), dedupliziert über aufgelöste Ziel-URL — deckt ~90 % des Scout-Bedarfs |
| Optional mit Key | Tavily (`api.tavily.com/search`; keyless ✅ von Astra getestet, mit Konto 1.000 Credits/Monat frei; liefert extrahierten Content, spart Jsoup) · Serper.dev (2.500 Gratis-Credits, Google-Qualität) |
| ❌ | DuckDuckGo HTML/Lite (202/403 im Test), Bing-Such-API (eingestellt 11.08.2025), Google CSE (Neukunden geschlossen), öffentliche SearXNG (Challenge/429); SearXNG nur self-hosted sinnvoll |

---

## 8. Datenmodell (SQLite `data/goldscanner.db`)

| Tabelle | Inhalt |
|---|---|
| `calendar_events` | Quelle, Zeitpunkt UTC + Quellzeitzone, Event-Typ-Klasse, Wichtigkeit, Forecast/Previous, `actual_first`/`actual_latest`, `forecast_asof`, Revisionen — point-in-time |
| `calendar_snapshots` | rohe Wochenfeeds (FF) je Abruf — eigenes Archiv, da keine Historie lieferbar |
| `rates` | MT5 OHLC D1/H4/H1 mit Broker-/Serverzeit-Versionierung |
| `quant_series` | GVZ, iv30, DFII10, T10YIE, DTWEXBGS, RealYield, COT (observed/published getrennt), GLD-Tonnen, LBMA |
| `quellen` / `url_vorschlaege` | URL-Listen mit Typ, aktiv, Score, letztem Hash, Wächter-Status / Scout-Vorschläge |
| `news_items` | RSS-Items mit Original-URL, Autor, Dedup-Hash, Destillat |
| `community_levels` | Level-Cluster mit Instrument, Horizont, Quelle, ATR-normierter Distanz, Richtung |
| `modell_runs` | je Lauf: Features, P_stat je Tag, Quantile, P_richtung, Kalibrierungsstand |
| `analysen` | LLM-Texte: kind, modell, tokens, basis_hash, llm_delta (Abweichung von P_stat) |
| `wochen_prognose` | Woche, Tag: P_final, P_stat, schwelle_b, q10/q50/q90, richtung, p_hoch, treiber_json, begruendung, konfidenz |
| `prognose_versionen` | as_of-versioniert (Sonntags-Vorab vs. Tagesrevisionen → Plume) |
| `prognose_verifikation` | Tag: vorhergesagt vs. tatsächlich (TR, H−L, Close-Richtung), Brier-Beitrag |
| `kalibrierung` | Brier/BSS-Verlauf, Reliability-Bins, Isotonic/Platt-Parameter, LLM-Delta-Nutztwert |
| `agenten_laeufe/schritte` | Journal mit vollständigen Prompts/Antworten (Audit) |
| `budget_token` | Verbrauch je Tag/Woche/Lauf |

---

## 9. UI (Streamlit, dunkles „Forensic Dashboard" mit Gold-Akzenten, 8 Bereiche)

1. **Dashboard** — Wochenmatrix v2 (§6) inkl. Warnskala, KPI-Karten (stärkster Tag,
   Ø-P der Woche, nächste High-Impact-Events, BSS letzte 13 Wochen), Workflow-Stepper
   des laufenden Scans, Meldungs-Postfach.
2. **Tagessicht** — Event-Zeitleiste (Europe/Berlin; High-Impact markiert; Actuals mit
   Surprise), Treiber-Karten, Ampel-Matrix der Faktoren mit Berechnungstext im Tooltip.
3. **Chart** — Candlestick D1/H1 (~180 Tage) mit SMA10/50/200 + Level-Clustern;
   Wochentags-Ø-TR-Balken; GVZ-Verlauf; Asia-Range-Intraday-Ansicht.
4. **Quellen** — Listen je Adaptertyp mit Wächter-Status (grün/gelb/rot + letzter
   Check, Hash, Datenalter); Scout-Vorschläge annehmen/ablehnen; „Jetzt testen"-Button.
5. **Agenten** — Status je Rolle, Journal-Browser (Prompts/Antworten), Daemon-Steuerung,
   Budget-Anzeige.
6. **Konfig** — Tabs: Zugänge (GLM-Key, MT5-Pfad/Symbol, Such-API-Key, optional
   Myfxbook-Account) · Scanprofil (Symbol/Suffix, k, Fenster, Wochentage, Zeitzone) ·
   Quellen · Kalender (Quellen-Prioritäten, Relevanz-Gewichte, LLM-Band ±pp) · Agenten
   (aktiv/Modell/Max-Tokens/Takt) · Zeitplan · Prompts (externe MD-Dateien).
7. **Journal/Ergebnisse** — Lauf-Historie, PDF-Archiv, Prognose-Plumes.
8. **Track-Record** — Reliability-Diagramm, BSS-Verlauf vs. Klimatologie,
   Richtungstreffer, LLM-Delta-Nutztwert, Coverage der Range-Bänder.

Erster Start: Einrichtungsdialog (GLM-Key, MT5-Terminalpfad, Broker-Symbol inkl.
Suffix, Zeitzone, Python-Pfad für Bridge); leerer Zustand zeigt „Was tun"-Karte.

---

## 10. Betriebsrhythmus

| Wann | Was |
|---|---|
| So 17:00 | URL-Scout (Google/Bing-News-RSS, ggf. Tavily) → Vorschläge |
| So 18:00 | **Wochenlauf:** Kurse → Regeltermine → Kalender → News → Community → Quant (CFTC wenn fällig) → Statistik-Kern → Analytiker-Fusion → Wochenmatrix v2 + PDF |
| Mo–Fr 06:30 | Tageslauf: Kurse + Actuals + Delta-News → Tagesbewertung aktualisieren (Version + Plume), Meldung bei Änderung |
| Mo–Fr 08:00 MEZ | Session-/Gap-Update (Asia-Range) → Intraday-Revision der heutigen P |
| Mo–Fr nach 14:30-ET-Releases | Actuals nachtragen → Surprise → Kurz-Revision Folgetage |
| Fr 21:30 MESZ | CFTC-COT abrufen (Releaseplan beachten) |
| nach US-Close | GVZ/iv30, FRED/RealYield, GLD-XLSX aktualisieren |
| Sa 09:00 | Verifikations-Agent: Woche bewerten, Brier/BSS, Rekalibrierung prüfen |
| 1. Werktag/Monat | Haushaltung, Kalender-Jahrespläne, ToS/robots-Stichprobe |

Daemon wie KiScanner (DETACHED-Prozess, Herzschlag 30 s, Tages-/Wochen-Merker,
Datei-Lock PID + Stale-Schwelle 3600 s, kooperativer Stopp, Start/Status aus UI).

## 11. Kosten-, Rechts- und Betriebsschutz

- **Ehrlicher User-Agent** `MqlGoldscanner/0.1 (+mailto:…)`; kein Browser-UA-Veto;
  keine Cloudflare/DataDome-Umgehung; bei 401/403/Challenge Adapter stoppen.
- **Ein Abruf je Quelle, zentral gecacht** (Rohantwort + Hash, ETag/If-Modified-Since),
  Wiederverwendung durch alle Agenten; Frequenzen aus §7; exponentielles Backoff bei
  429/503, Retry-After beachten, danach Tag Pause.
- Höfliche Frequenzen: Regierungs-APIs 1×/Tag; Gold-RSS 1–3 h; FXStreet ≤ 1/15 min;
  Google-News-RSS ≤ 1/10 min; FF ≤ 4×/Tag; Gold-Eagle Crawl-delay 10 s; Nasdaq 1–3×/Tag.
- **Untrusted Content:** News-Texte steuern nie Konfiguration oder Tool-Aufrufe des
  Agenten; LLM-Extrakte nur als Strukturdaten (Level/Bias/Stimmung) mit Quellenlink,
  stichprobenartig prüfen (Halluzinationsrisiko).
- Rechte-Clippen je Quelle dokumentiert (§7): SPDR/Cboe/LBMA persönliche Nutzung;
  TradingView nur privat; FF/Investing restriktiv; CME gar nicht scrapen; WGC-Downloads
  403 → nicht umgehen. robots.txt-Allow ist keine Lizenz (RFC 9309).
- GLM-Budgets (Lauf/Tag/Woche), Delta-Prinzip, Fail-Fast, Audit-Journal, Lock — wie
  KiScanner; zusätzlich LLM-Band-Konfiguration (±pp) und LLM-Delta-Messung.
- Intern **alles in UTC** speichern; Quellzeitzone (FF Eastern-Offset, BLS/BEA ET,
  MT5 Serverzeit, CFTC America/New_York) nur bei Anzeige nach Europe/Berlin wandeln.

## 12. Projektstruktur

```
MqlGoldscanner/
├─ streamlit_app.py             (Einstieg: Navigation + Sidebar-Status)
├─ app_pages/                   (dashboard, tagesicht, chart, quellen, agenten,
│                                journal, track_record, einstellungen)
├─ src/goldscanner/
│  ├─ config.py                 (Pfade, Defaults, GLM-Endpunkte, ehrlicher UA)
│  ├─ secrets_store.py          (Env > .env > secrets.local.json)
│  ├─ db.py                     (SQLite versioniert; Journal + Budget inklusive)
│  ├─ lock.py                   (Datei-Lock, PID + Stale; Windows-sichere PID-Prüfung)
│  ├─ kennzahlen.py             (TR/ATR/RSI/SMA — reiner Code, Ankertests)
│  ├─ ui_design.py              (Theme/Hero/Stepper — KiScanner-Port, Gold)
│  ├─ app_state.py              (prozessweite Singletons)
│  ├─ quellen_check.py          (Launch-Check: Status + Typ + Signatur)
│  ├─ llm/client.py             (GlmClient m. Fehler-Taxonomie + Tagesbudget)
│  ├─ mt5/kurse.py              (MT5 read-only; nur Selbststarts beenden)
│  └─ (S2+: adapter/ [kalender, regeltermine, actuals, news, quant, community],
│       modell/ [klimatologie, har, eventmultiplikatoren, expectedmove,
│       klassifikator, richtung, kalibrierung, walkforward],
│       agents/, report/, mt5bridge/CalendarExport.mq5 [Kalender → CSV])
├─ assets/radar-grid.svg        (Hero-Hintergrund, aus dem KiScanner)
├─ tests/                       (pytest: Ankertests, Whitelist-Statik, Fakes)
├─ config/                      (app_settings.json; secrets.local.json gitignored)
├─ data/                        (goldscanner.db)
├─ archiv/java-prototyp/        (abgelöster JavaFX-Versuch, 23.09.2026)
├─ requirements.txt · start.bat · .streamlit/config.toml
└─ doc/                         (00_konzept, 01_deep-research-prompt, 02_stufenplan,
                                  DeepResaearch/)
```

## 13. Phasenplan

> Ausgearbeitet mit Abnahmekriterien, Entscheidungstoren und Aufwandsschätzung in
> **`doc/02_stufenplan.md`** (Stufen S1–S7). Kurzform:

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **1 — Gerüst & Kurse** ✅ | Streamlit-App (8 Bereiche, KiScanner-Design in Gold), Config+Secrets+SQLite, GlmClient m. Fehler-Taxonomie+Budget, MT5 nativ (Kurse D1/H4/H1), Plotly-Candlestick-Chart, Quellen-Launch-Check — **umgesetzt am 23.09.2026 (Python-Neubau nach Nutzer-Entscheidung)** | App läuft, Kurse sichtbar |
| **2 — Statistik zuerst** ✅ | Kalender-Adapter (FF/BLS/BEA/Fed/Treasury, Hash-Snapshot-Archiv), Regeltermine, Actuals (MQL5-Exporter bereit + Nasdaq-Fallback), **Klimatologie-Baseline**, erste Wochenmatrix **rein statistisch** mit Schwellen-Tabelle — **umgesetzt 23.09.2026: Tor T2 bestanden (39,5 % auf Brokerdaten, Struktur wie Bericht)** | erste belastbare Matrix |
| **3 — Prognosemodell** ✅ | HAR auf ln(TR) + Wochentags-Dummies, Event-Features (NFP-Proxy ×1,24 / FOMC ×1,40 gemessen), GVZ-Historie (4.276 Tage), Walk-Forward über 850 Testtage, Platt-Skalierung — **Tor T3 bestanden 23.09.2026: B_har BSS +0,161** (Brier 0,244→0,205); Matrix zeigt P_stat + Modell-Range-Band | kalibrierte Prognose |
| **4 — LLM-Schicht** ✅ | News-RSS-Adapter (8 Quellen, Delta-Hash), Community (TradingView/Analysten/Kitco-Best-Effort), Destillation (glm-5.3-flash, JSON-validiert, Fail-Fast), **Analytiker-Fusion im ±10-pp-Band mit Pflichtbegründung** (Verstöße werden systemseitig abgewiesen + geloggt), Treiber-Wasserfall, Wochen-PDF, Postfach — **umgesetzt 23.09.2026: 246 News-Items (Delta-Prinzip), Fusion Δmax 3,0 pp ohne Verstoß, PDF 2 Seiten** | vollständig erklärte Matrix |
| **5 — Quant-Feeds & Kalibrierung** ✅ | FRED ohne Key (DFII10/T10YIE/DGS10/DTWEXBGS/VIXCLS), CFTC Managed-Money (T+4-Veröffentlichungsregel), GLD-Tonnen (XLSX); Logit-Richtungsmodell R1→R3 mit Walk-Forward-Ablation; Platt+Isotonic(PAVA) versioniert in kalibrierung (DB v5); Asia-Range-/Gap-Session-Update auf der Tagessicht — **umgesetzt 23.09.2026, Tor T5 ehrlich NICHT bestanden**: Richtung schlägt die Ø-Aufwärtswahrrscheinlichkeit 52,4 % nicht (BSS −0.003 bis −0.010 auf 4.078 Testtagen) → Symbole als „nicht verifiziert" gekennzeichnet, keine weiteren Feed-Ausbauten fürs Richtungsmodell; Quant-Feeds bleiben als Marktlage-Infrastruktur wertvoll | Richtung (gekennzeichnet) + Marktlage |
| **6 — Betrieb & Qualität** ✅ | Daemon (detached, Herzschlag, Locks, kooperativer Stopp; Zeitplan: Tageslauf 06:30 · Scout So 17:00 · Wochenlauf So 18:00 · Verifikation Sa 09:00), **Verifikations-Agent** (point-in-time: Prognose vs. echte Kerze → verifikationen-Tabelle), **Track-Record-Seite** (Reliability-Diagramm, Brier je Ebene, **LLM-Delta-Nutzt = Tor T4**, Richtungstreffer, Range-Coverage), **MT5-Export** (Prognose-CSV in Common/Files für eigene EAs), **URL-Scout** (Google-News-RSS-Domänen, bewertete Vorschläge, Annehmen/Ablehnen in der Quellen-UI); DB v6 — **umgesetzt 23.09.2026: Daemon live, Track-Record füllt sich ab dem ersten bewertbaren Tag (Prognose-Vergangenheit beginnt erst mit S2), Dauerbetrieb-Nachweis (14 Tage) läuft** | messbarer, selbstkalibrierender Betrieb |

## 14. Offene Punkte (vor/nach Implementierung verifizieren)

1. FF-Rate-Limit „~2 Requests/5 min" ist nur Community-Aussage → konservativ 4×/Tag.
2. MT5-Kalenderexport live testen (Abdeckung Actuals/Forecast beim eigenen Broker).
3. ~~BLS-ICS bei uns erneut testen~~ ✅ geklärt 23.09.2026: 403 nur ohne Kontakt-Adresse
   im User-Agent; mit `+mailto:` → 200 (BLS-Adapter läuft grün).
4. ~~Klimatologie-Zahlen mit MT5-XAUUSD wiederholen~~ ✅ 23.09.2026: 1.001 Broker-Tage
   (Tickmill XAUUSD, k=1,0) → Basisrate gesamt 41,2 % statt 43,0 % (GC=F) — Struktur
   gleich (Mi am höchsten); Differenz passt zu Broker-/Roll-Definition. Tor T2 passt.
5. FXStreet-Forecast-Poll-Struktur parsen; CNBC-Gold-RSS-ID klären.
6. Cboe-CDN-Nutzungsbedingungen (verzögerte Daten, private Nutzung) und LBMA-Lizenz.
7. Smile-vs-eigene-Implementierung für GBM entscheiden (Java-21-Kompatibilität 4.x).
8. Rosenstein: Wie viele Wochen Historie nötig, bis Isotonic stabiler ist als Platt
   (Faustregel ~500 Beobachtungen ≈ 2 Jahre Handelstage)?
9. Brave/Serper/Tavily-Preise Stand 2026 können sich ändern — vor Aktivierung prüfen.
