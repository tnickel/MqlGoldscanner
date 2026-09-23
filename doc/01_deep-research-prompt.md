# Deep-Research-Prompt für Gemini / Astra Deep Research (MqlGoldscanner)

> Verwendung: Den gesamten Kasten unten in Gemini bzw. Astra (Deep Research) kopieren
> und starten. Ergebnis anschließend unter `doc/02_recherche-ergebnis.md` ablegen,
> damit die URL-Listen in die Config übernommen werden können.
> Stand: 23.09.2026 · Sprache: Deutsch

---

```text
DU BIST: ein erfahrener Rechercheanalyst für Finanzdatenquellen und
Marktinformationssysteme mit Schwerpunkt Edelmetalle/Devisen und praktischer
Erfahrung im Aufbau automatisierter Marktdaten-Pipelines.

## PROJEKTKONTEXT

Ich baue einen "MqlGoldscanner": ein Multi-Agenten-Desktop-Tool (Java), das
ausschließlich den Goldmarkt (XAUUSD) recherchiert und für jede Kalenderwoche eine
Übersicht erstellt: Wie hoch ist die Wahrscheinlichkeit, dass sich der Goldpreis an
jedem Wochentag spürbar bewegt (0–100 %, plus erwartete Tagesrange in USD,
Richtungstendenz und Begründung mit Treibern)?

Das Tool arbeitet mit spezialisierten Agenten (LLM-gestützt):
- Kalender-Agent: wertet Wirtschafts­kalender aus (myfxbook, ForexFactory) und
  gewichtet Events nach Gold-Relevanz (NFP, CPI, PCE, FOMC, ISM, Claims, EZB ...),
  inkl. Nachtrag von Ist-Werten (Actual vs. Forecast).
- News-Recherche-Agent: arbeitet eine kuratierte URL-Liste von Gold-News-Seiten ab
  und destilliert bullische/bärische Treiber.
- URL-Scout-Agent: durchsucht das Web nach NEUEN, dauerhaft nützlichen Quellen-URLs
  für die beiden anderen Agenten und schlägt sie zur Aufnahme vor.
- Chart-Technik-Agent: holt Goldkurse (D1/H4/H1) aus MetaTrader 5 und Java berechnet
  Kennzahlen (ATR, SMA, RSI, Wochentags-Range-Statistik, Levels, ATR-Regime).
- Chart-Community-Agent: liest fremde Chartanalysen (TradingView, FXStreet, ...)
  und destilliert Konsens-Levels.
- Analytiker-Agent (Fusion): kombiniert alles zu Wochenmatrix und Tagesbewertung.
- Verifikations-Agent: vergleicht Prognosen mit der tatsächlichen Bewegung und
  berechnet Trefferquote/Kalibrierung.

Definition "Bewegungstag" im Tool: True Range > 1,0 × Ø-True-Range desselben
Wochentags der letzten 13 Wochen.

Technik: Java 21, JavaFX, SQLite, HTML-Parsing mit Jsoup, Http-Client; scraping-freundliche
Formate (JSON/RSS) werden klar bevorzugt. Kein Budget für teure Datenabo-Käufe
(Kostenloses und Freemium bevorzugt; Bezahloptionen nur ergänzend dokumentieren).

## DEIN RECHERCHEAUFTRAG

### Block 1 — Wirtschafts­kalender (maschinenlesbar priorisieren)
Finde und bewerte ALLE praktisch nutzbaren Wirtschafts­kalender-Quellen für
USD-Makrodaten und Gold-relevante Termine. Verifiziere insbesondere:
- https://www.myfxbook.com/forex-economic-calendar (gibt es JSON-/API-Endpunkte,
  die die Seite selbst nutzt? Zugangswege, Parameter)
- https://nfs.faireconomy.media/ff_calendar_thisweek.json (ForexFactory-Feed: noch
  aktiv? Feldstruktur? Gibt es thisweek/nextweek/expired-Varianten?)
- DailyFX-Kalender, Investing.com-Kalender, Trading Economics, Finnhub, TradingEconomics,
  Econoday, Barki-Alternativen: dokumentiere je Zugangsweg (offizielle API, inoffizieller
  JSON-Endpunkt, RSS, nur HTML), Formatbeispiel, Kosten, Rate-Limits, Zuverlässigkeit.
- Ergänze Spezialkalender, die für Gold-Bewegungstage wichtig sind: FOMC-Sitzungs- und
  Redenkalender (federalreserve.gov), EZB-Termine, US-Treasury-Auktionskalender
  (2y/5y/10y/30y), Termine für COT-Release (CFTC), Quadruple Witching / Optionsexpiry
  auf Gold (COMEX First Notice Day, Opex-Termine).

### Block 2 — Gold-News- und Analyse-Quellen (URL-Liste erweitern)
Meine aktuelle Startliste lautet: kitco.com/news, fxstreet.com (Gold-Sektion),
reuters.com/markets/commodities, marketwatch.com (Gold Future), cnbc.com (Gold),
dailyfx.com/gold-price, gold.org (World Gold Council), bullionvault.com,
fxempire.com, invezz.com.
Aufträge: (a) prüfe jede dieser Quellen auf Aktualität, Gold-Anteil, Update-Frequenz
und ob ein RSS-Feed existiert (Feed-URL angeben!); (b) finde mindestens 10–15 WEITERE
hochwertige, regelmäßig aktualisierte Quellen für Gold-News/Gold-Analyse (englisch
UND deutsch), jeweils mit konkreter Einstiegs-URL und RSS-Feed falls vorhanden;
(c) markiere Quellen mit Paywall/Anmeldepflicht oder aggressiver Bot-Erkennung.

### Block 3 — Chartanalyse-/Community-Quellen für Gold
Meine Startliste: tradingview.com/symbols/XAUUSD/ideas, fxstreet.com Gold Technical
Forecast, investing.com Gold Technical Analysis, dailyfx.com Gold Technical.
Aufträge: verifiziere diese (sind die Inhalte ohne Login abrufbar? wie tief muss man
navigieren?), finde weitere Quellen für fremde Chartanalysen, Level-Übernahmen und
Konsens-Stimmung zu XAUUSD (z. B. Bank-Research-Seiten mit kostenlosen Schnipseln,
Goldkit-Anbieter, Subreddit-/Forum-Quellen wenn sinnvoll kuratierbar) und bewerte,
wie gut sie sich für automatisiertes Abholen eignen.

### Block 4 — Sentiment-, Positionierungs- und Marktdaten (neue Datenkategorien)
Das ist der wichtigste Ideen-Block. Rechercheiere praktisch abholbare Quellen für:
- CFTC COT-Report Gold (exakte URL des Datensatzes, Release-Zeitpunkt, Format
  CSV/JSON, historisch verfügbar?)
- ETF-Flows und -Bestände: SPDR Gold Shares (GLD) Bestände (offizielle Seite,
  täglich?), iShares Gold Trust, Weltgoldrat-Daten (gold.org: Nachfrageberichte,
  Zentralbankkäufe)
- Gold-Volatilität: GLD/XAUUSD-Optionsimplizite Volatilität (kostenlose Quellen?),
  CBOE Gold ETF Volatility Index (GVZ) — noch verfügbar? Historie?
- Korrelations- und Makro-Kontext: DXY, 10J-TIPS-Realyield (FRED-Serie? exakte
  Serienkennung + URL), SPX, US-Zinspfad-Erwartung (CME FedWatch — maschinenlesbar?)
- COMEX/NYMEX-Futures: Open Interest, Terminkurven, EFP-Spreads — kostenlose
  Abrufwege (CME-Website, Barchart, etc.)?
- LBMA-Goldpreis (fixing), Shanghai Gold Exchange, Münzumsätze (US Mint Sales)
- Google Trends "gold price" — API/Abruf ohne Browser sinnvoll möglich?
- Saisonalität Gold (historische Monats-/Wochentags-Muster): kostenlose Datenbasis
- Offizielle Statistik: Zentralbank-Kaufprogramme (WGC quarterly), IMF IFS

### Block 5 — Web-Such-APIs für den URL-Scout-Agent
Vergleiche aktuelle (Stand 2026) Möglichkeiten für automatisierte Websuche:
Google Custom Search JSON API, Bing Web Search, Brave Search API, Serper.dev,
Tavily, DuckDuckGo (HTML/Scrape), Mojeek, Searxng-Instanzen. Je: Kosten/Freikontingent,
Rate-Limits, Anmeldungsart, Ergebnisqualität für Finanzabfragen, Robustheit.
Empfehlung für: Default ohne API-Key + empfohlene Variante mit Key.

### Block 6 — Methoden und Produkt-Ideen (das "was geht noch")
- Wissenschaftlich/praktisch bewährte, in Java umsetzbare Methoden zur Schätzung
  einer Tages-Bewegungswahrscheinlichkeit: GARCH(1,1)-Volatilitätsprognose,
  Ereignisstudien (durchschnittliche Range an NFP-/CPI-/FOMC-Tagen vs. Normaltag),
  Range-Breakout-Wahrscheinlichkeiten, Options-IV-basierte erwartete Bewegung
  (expected move). Welche davon liefern für Gold nachweislich Kalibrierungsgewinn?
- Kalibrierung von Wahrscheinlichkeiten (Brier Score, Reliability-Diagramme) —
  wie nutzt man das im Tagesgeschäft richtig?
- Analyse konkreter Wettbewerber/ähnlicher Angebote: Gold-Forecast-Seiten,
  "gold weekly outlook" Anbieter, FXStreet/Bloomberg-Gold-Outlooks — was bieten
  sie an Darstellung/Methodik an, das über meinen Ansatz hinausgeht?
- Weitere Agenten-Ideen für mein Setup (z. B. Optionsmarkt-Agent, Korrelations-Agent,
  Overnight-Gap-Agent, Backtest-Agent ...) mit jeweils: Nutzen, Datenbasis,
  Aufwandsschätzung.
- UI/Darstellungs-Ideen für eine Wochenmatrix (Mo–Fr Wahrscheinlichkeiten) aus
  anderen Domänen (Wetter-Vorhersagen, Erdbeben-Wahrscheinlichkeiten) die
  übertragbar sind.

## AUSGABEFORMAT (bitte genau einhalten)

1. **Quellenkatalog als Tabellen** (je Block eine Tabelle) mit Spalten:
   | Name | exakte URL | Zugangsweg (offizielle API / inoffizieller JSON-Endpunkt / RSS / HTML) | Formatbeispiel (1 Zeile) | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Relevanz (1–5) | Anmerkung |
   - Nur verifizierte, funktionierende URLs; jede Quelle mit Funddatum/Testergebnis.
   - Markiere maschinenlesbare (JSON/RSS/CSV) ausdrücklich als "PREFERRED".
2. **Top-15-Kurzliste**: die 15 wertvollsten NEUEN Quellen für meinen Use Case,
   sortiert nach Aufwand/Nutzen (unter Annahme: Java-Client, Jsoup, kein Browser).
3. **Methodenkapitel** (Block 6): je Methode 1 Absatz: Funktion, Datenbedarf,
   erwartbarer Kalibrierungsbeitrag für Gold, Java-Umsetzungsschwierigkeit.
4. **Ideenliste**: neue Agenten und Produktideen, priorisiert nach
   Aufwand/Nutzen-Matrix.
5. **Risiken/ToS**: kurze Übersicht, welche Quellen automatisiertes Abholen
   faktisch erlauben bzw. verbieten (robots.txt/ToS), und was die praktische,
   höfliche Abruffrequenz je Quelle wäre.
6. Alle Aussagen mit Quellenlink; bitte nur Informationen, die du aktuell
   verifizieren konntest — kennzeichne alles Unverifizierte explizit.

## RAHMENBEDINGUNGEN
- Zielzeitraum der Recherche: heute (2026) funktionierende Quellen, keine historisch
  totgeglaubten Endpunkte.
- Deutschsprachige Antwort, Fachbegriffe Englisch lassen.
- Priorität: kostenlos/maschinenlesbar/zuverlässig vor Paywall/Scraping/instabil.
- Der Zweck ist volatilitätsbezogene Forschung (Wahrscheinlichkeit starker
  Gold-Tagesbewegungen), NICHT Kursrichtungshandel mit Echtzeit-Ticks —
  Echtzeit-Daten sind nicht nötig, Tages-/Wochen-Genauigkeit genügt.
```
