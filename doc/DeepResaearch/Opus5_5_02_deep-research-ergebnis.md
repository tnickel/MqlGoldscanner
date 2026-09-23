# MqlGoldscanner — Deep-Research-Ergebnis Datenquellen & Methoden

**Stand:** 23.09.2026 · **Grundlage:** Recherche-Prompt `doc/01_deep-research-prompt.md`
**Methodik:** Jede URL in diesem Dokument wurde am 23.09.2026 zwischen ca. 09:35 und 10:30 Uhr MESZ live abgerufen, und zwar zweimal: einmal mit Browser-User-Agent (Chrome 140) und einmal mit dem Default-UA des Java-HttpClient (`Java-http-client/21.0.4`). Browser-Rendering oder Cookies wurden nicht verwendet. Ein Jsoup/HttpClient-Tool sieht die Quellen also genau so. Skript und Rohergebnisse liegen in `doc/DeepResaearch/testlauf/`. Fakten aus Dokumentationen und ToS stammen aus Web-Recherche und sind verlinkt.

## Legende

| Kürzel | Bedeutung |
|---|---|
| ✅ **PREFERRED** | maschinenlesbar (JSON/RSS/CSV/XLSX/ICS), im Test mit 200 erreichbar, stabil |
| 🟡 | nutzbar, aber nur HTML/JS-lastig, rate-limitiert oder rechtlich grau |
| ❌ | im Test blockiert (Cloudflare/Akamai/DataDome/401/403) oder eingestellt |
| **Test B/J** | HTTP-Status mit Browser-UA / mit Java-UA, danach Größe bzw. Anzahl der Items |
| **(U)** | **unverifiziert**: nicht selbst getestet oder nur aus Sekundärquellen |

---

## 0. Die wichtigsten Erkenntnisse vorab (Management Summary)

1. **ForexFactory-Feed lebt, hat aber kein `actual`-Feld.** `ff_calendar_thisweek.json`, `.xml` und `.csv` liefern 200. Die Varianten `nextweek`, `lastweek` und `thismonth` liefern **404**. Ist-Werte müssen deshalb aus einer anderen Quelle kommen.
2. **Ist-Werte kostenlos bekommen Sie über zwei Wege:** den **MT5-eigenen Wirtschaftskalender** (`CalendarValueHistory()`, offiziell und kostenlos, im Python-Paket aber **nicht** enthalten) oder den inoffiziellen **Nasdaq-JSON** (`api.nasdaq.com/api/calendar/economicevents`, mit `actual`/`consensus`/`previous`).
3. **Myfxbook, Investing.com (Web), ForexFactory (Web), Reuters, MarketWatch, BabyPips, US Mint und goldseiten.de** sind für einen Jsoup-Client **komplett blockiert** (Cloudflare/DataDome, auch mit Browser-UA).
4. **Offizielle US-Quellen sind Gold wert und maschinenlesbar:** Fed `calendar.json`, Fed-RSS, BLS-ICS, BEA-ICS, TreasuryDirect-JSON, CFTC-Socrata-JSON (Gold-Code `088691` verifiziert), FRED-CSV ohne Key und Treasury-Real-Yield-CSV.
5. **Implizite Vola geht kostenlos:** Die Cboe-GVZ-Historie als CSV ist aktuell (letzter Wert 22.09.2026: 23,59). Das Cboe-GLD-Options-JSON liefert **`iv30` direkt** (20,96 %). Daraus lässt sich ohne Options-Mathematik eine Expected-Move-Zahl ableiten (Kapitel 3.6).
6. **Die GLD-Bestände (Tonnen) stehen täglich als XLSX bereit**, über den neuen API-Pfad von SPDR. Die alte CSV-URL leitet inzwischen auf ein Barlist-PDF um.
7. **Suche ohne Key:** DuckDuckGo HTML/Lite war im Test **nicht nutzbar** (202-Anomalie bzw. 403). **Google-News-RSS** und **Bing-News-RSS** liefern dagegen zuverlässig Treffer. **Bing Web Search API ist seit 11.08.2025 eingestellt**, **Google CSE nimmt keine Neukunden mehr (Sunset 01.01.2027)** und **Brave hat seit Feb. 2026 kein Free-Tier mehr**.
8. **Empirischer Befund zur Basisrate** (eigene Rechnung, GC=F, 5 Jahre): Ein „Bewegungstag“ nach Ihrer Definition tritt in **43,0 %** der Tage auf (Mo 41,2 %, Di 43,7 %, Mi 45,7 %, Do 42,7 %, Fr 41,7 %). Die **Klimatologie-Baseline liegt also bei ~43 % und nicht bei 50 %**. Diesen Wert muss jede Prognose schlagen.

---

## 1. Quellenkatalog

### 1.1 Block 1: Wirtschaftskalender

| Name | exakte URL | Zugangsweg | Formatbeispiel (1 Zeile) | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Rel. | Anmerkung / Testergebnis |
|---|---|---|---|---|---|---|---|---|
| ✅ **ForexFactory Feed JSON** PREFERRED | https://nfs.faireconomy.media/ff_calendar_thisweek.json | inoffizieller JSON-Endpunkt | `{"title":"Rightmove HPI m/m","country":"GBP","date":"2026-09-20T19:01:00-04:00","impact":"Low","forecast":"","previous":"-2.0%"}` | frei | laufende Woche; Aktualisierungstakt (U) | Community-Wert „~2 Requests/5 min, sonst IP-Sperre“ (U, [Quelle](https://www.pythonanywhere.com/forums/topic/36826/)) | 5 | Test B/J 200/200, 10,8 KB. **Felder: title, country, date, impact, forecast, previous, aber KEIN actual.** Zeiten in US-Eastern mit Offset. |
| ✅ ForexFactory Feed XML | https://nfs.faireconomy.media/ff_calendar_thisweek.xml | inoffizieller XML-Feed | `<event><title>Bank Holiday</title>…` | frei | wie JSON | wie JSON | 5 | Test 200/200, 27 KB |
| ✅ ForexFactory Feed CSV | https://nfs.faireconomy.media/ff_calendar_thisweek.csv | inoffizieller CSV-Feed | `Rightmove HPI m/m,GBP,09-20-2026,11:01pm,Low,,-2.0%,https://www.forexfactory.com/calendar/…` | frei | wie JSON | wie JSON | 5 | Test 200/200. **Enthält zusätzlich die Event-URL** (nützlich für Deduplizierung) |
| ❌ FF-Varianten nextweek/lastweek/thismonth | …/ff_calendar_nextweek.json, …/lastweek.json, …/thismonth.json | – | – | – | – | – | – | **Test 404/404.** Existieren nicht (mehr). Vorwoche und Folgewoche also selbst archivieren. |
| ❌ ForexFactory Web | https://www.forexfactory.com/calendar | HTML | – | – | – | **Cloudflare „Just a moment…“** | 5 | Test 403/403 |
| ❌ Myfxbook Kalender (Web) | https://www.myfxbook.com/forex-economic-calendar | HTML (intern JS/XHR) | – | – | – | **Cloudflare** | 4 | Test 403/403. RSS `https://www.myfxbook.com/rss/forex-economic-calendar-events` ebenfalls 403. Die offizielle [Myfxbook-API](https://www.myfxbook.com/api) hat **keinen** Kalender-Endpunkt. Ohne echten Browser nicht nutzbar. |
| ✅ **Nasdaq Economic Events** PREFERRED (mit ToS-Vorbehalt) | https://api.nasdaq.com/api/calendar/economicevents?date=2026-09-23 | inoffizieller JSON-Endpunkt | `{"gmt":"02:00","country":"Switzerland","eventName":"Trade Balance","actual":"3.786B","consensus":" ","previous":"5.742B","description":"…"}` | frei | intraday, Ist-Werte nachgetragen | robots.txt: `/api/` **disallowed**; kein offizielles API | 4 | Test 200/200, 18,7 KB. **Liefert `actual`**, damit ideal für den Ist-Wert-Nachtrag. Parameter `date=YYYY-MM-DD`. Keine Impact-Gewichtung enthalten. |
| ✅ **MT5 / MQL5 Wirtschaftskalender** PREFERRED | Docs: https://www.mql5.com/en/docs/calendar · Funktion: https://www.mql5.com/en/docs/calendar/calendarvaluehistory | offizielle API (in MQL5) | `MqlCalendarValue{time, event_id, actual_value, forecast_value, prev_value, impact_type}` | frei (im Terminal) | Echtzeit | keine | 5 | Web-Kalender https://www.mql5.com/en/economic-calendar Test 200/200. **Das Python-Paket `MetaTrader5` bietet keine Kalenderfunktionen** ([Doku](https://www.mql5.com/en/docs/python_metatrader5)), also ist ein kleines MQL5-Skript nötig, das Daten nach CSV/SQLite exportiert. Werte sind ×10⁶ skaliert, Zeitbasis ist die Server-Zeit. |
| 🟡 DailyFX-Kalender → IG | https://www.dailyfx.com/economic-calendar → https://www.ig.com/uk/economic-calendar | HTML (JS-lastig) | – | frei | – | – | 3 | Test 200/200 (Redirect, 760 KB). DailyFX wurde 2024 in IG integriert ([IG](https://www.ig.com/ae/trading-strategies/dailyfx--now-get-your-trading-insights-on-ig-240906)). |
| ❌ Investing.com Kalender | https://www.investing.com/economic-calendar/ | HTML | – | – | – | Cloudflare, Body 3 Byte | 4 | Test 403/403. Widget `sslecal2.investing.com` ebenfalls 403/403. ToS verbietet Bots (U). |
| ❌ Trading Economics API (guest) | https://api.tradingeconomics.com/calendar/country/united%20states?c=guest:guest&f=json | offizielle API | Antwort: „guest account has been discontinued“ | nur bezahlt, Angebot auf Anfrage | – | 2 Req/s, 1.000 Zeilen/Kalender-Call ([Docs](https://docs.tradingeconomics.com/get_started/rate-limits/)) | 4 | **Test 410/410 (Gone).** Guest-Zugang eingestellt. Web-Kalender https://tradingeconomics.com/calendar 200 (2 MB HTML). |
| 🟡 Finnhub | https://finnhub.io/api/v1/calendar/economic | offizielle API | `{"error":"Please use an API key."}` | Kalender laut Pricing Premium (U) | – | Free 60/min (U) | 3 | Test 401/401 ohne Key. [Pricing](https://finnhub.io/pricing) |
| 🟡 FXStreet Kalender | https://www.fxstreet.com/economic-calendar | HTML (JS) | – | frei | – | Cloudflare, sporadisch 429 | 4 | Test 200/200 (885 KB). Daten werden per JS nachgeladen (U). |
| 🟡 Econoday | https://www.econoday.com/ | HTML | – | frei/Freemium | – | – | 3 | Test 200/200 |
| ❌ MarketWatch Kalender | https://www.marketwatch.com/economy-politics/calendar | HTML | – | – | – | DataDome/401 | 3 | Test 401/401 |
| ❌ BabyPips Kalender | https://www.babypips.com/economic-calendar | HTML | – | – | – | Cloudflare | 3 | Test 403/403 |
| ✅ **Fed Kalender JSON** PREFERRED | https://www.federalreserve.gov/json/calendar.json | inoffizieller JSON-Endpunkt (Fed-Site) | `{"title":"FOMC Minutes","time":"2:00 p.m.","month":"2026-11","days":"18","type":"FOMC","description":"Meeting of October 27-28"}` | frei | laufend | keine | 5 | Test 200/200, 540 KB, mit BOM. **Maschinenlesbarer Fed-Terminkalender** (FOMC, Minutes, Reden, Releases). |
| ✅ Fed FOMC-Kalender (HTML) | https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm | HTML (statisch) | – | frei | jährlich/ad hoc | keine | 5 | Test 200/200. Sitzungen und SEP-Termine. |
| ✅ **Fed RSS** PREFERRED | https://www.federalreserve.gov/feeds/press_monetary.xml · …/speeches.xml · …/s_t_powell.xml · …/press_all.xml | RSS | `<item><title>Federal Reserve issues FOMC statement</title>…` | frei | ereignisgetrieben | keine | 5 | Test 200/200 (15/15/15/20 Items). Übersicht aller 30+ Feeds: https://www.federalreserve.gov/feeds/feeds.htm |
| ✅ EZB Sitzungskalender | https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html | HTML | – | frei | jährlich | keine | 4 | Test 200/200 (106 KB); Tabellenstruktur nicht geparst (U). Wochentermine: https://www.ecb.europa.eu/press/calendars/weekly/html/index.en.html (200) |
| ✅ **EZB RSS** PREFERRED | https://www.ecb.europa.eu/rss/press.html | RSS | `<item><title>Monetary policy decisions</title>…` | frei | ereignisgetrieben | keine | 4 | Test 200/200 (15 Items). Weitere Feeds: `/rss/pub.html`, `/rss/statpress.html`, `/rss/blog.html` |
| ✅ **TreasuryDirect Auktionen** PREFERRED | https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json | offizielle JSON-API | `{"cusip":"91282CRD5","securityType":"Note","securityTerm":"5-Year","auctionDate":"2026-09-23T00:00:00",…}` | frei | täglich | keine dokumentiert | 4 | Test 200/200 (31 KB). Auch `…/announced?format=json&type=Note&days=14` (200). Filter auf 2y/5y/7y/10y/20y/30y Note/Bond. |
| ✅ FiscalData Upcoming Auctions | https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/upcoming_auctions?sort=-record_date&page[size]=5 | offizielle JSON-API | `{"security_type":"Bill","security_term":"26-Week","announcemt_date":"2026-09-24","auction_date":"2026-09-28",…}` | frei | täglich | keine | 3 | Test 200/200 |
| ✅ **BLS Release-Kalender ICS** PREFERRED | https://www.bls.gov/schedule/news_release/bls.ics | ICS (iCalendar) | `BEGIN:VCALENDAR … SUMMARY:BLS.gov Economic News Release Schedule` | frei | jährlich + Änderungen | keine | 5 | Test 200/200 (80 KB). **NFP, CPI, PPI, JOLTS, ECI mit exakter Uhrzeit.** Monats-HTML: https://www.bls.gov/schedule/news_release/ |
| ✅ **BEA Release-Kalender ICS** PREFERRED | https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics | ICS | `BEGIN:VCALENDAR … X-WR-CALNAME:BEA-Release-Calendar-Subscription` | frei | jährlich + Änderungen | keine | 5 | Test 200/200 (31 KB). **GDP, PCE/Personal Income.** HTML: https://www.bea.gov/news/schedule |
| ✅ CFTC COT-Release-Termine | https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm | HTML (statisch) | – | frei | jährlich | keine | 3 | Test 200/200. Release **freitags 15:30 ET** mit Daten vom Dienstag. Feiertagsverschiebungen sind markiert ([CFTC](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)). |
| 🟡 CME Gold-Kalender (FND/LTD/Opex) | https://www.cmegroup.com/markets/metals/precious/gold.calendar.html | HTML | – | frei | – | **Akamai: erst 200, nach wenigen Requests 403** | 4 | **Empfehlung: regelbasiert in Java berechnen statt scrapen.** GC-FND = 1. Geschäftstag des Liefermonats; GC-LTD = drittletzter Geschäftstag; OG-Optionen verfallen 4 Geschäftstage vor Ende des Vormonats (U, laut CME Rulebook Kap. 113/115). Liefermonate Feb/Apr/Jun/Aug/Okt/Dez. |
| 🟡 CME Expiration Calendar | https://www.cmegroup.com/tools-information/calendars/expiration-calendar/ | HTML (JS) | – | frei | – | Akamai | 3 | Test 200/200 (Redirect auf `.html`), später 403 |

### 1.2 Block 2: Gold-News- und Analysequellen

#### (a) Prüfung Ihrer Startliste

| Name | exakte URL | Zugangsweg | Formatbeispiel | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Rel. | Anmerkung / Testergebnis |
|---|---|---|---|---|---|---|---|---|
| 🟡 Kitco News | https://www.kitco.com/news/category/commodities/gold | HTML (Next.js) | – | frei | mehrmals täglich | robots.txt `Allow: /`; ToS verbietet Bots (U) | 5 | Test 200/200 (195 KB). **Kein RSS gefunden** (`/rss/` und `/feed/rss/news` liefern 404, kein Feed-Link im HTML). **Ersatz: Google-News-RSS `site:kitco.com`** (200, 100 Items). |
| ✅ **FXStreet RSS** PREFERRED | https://www.fxstreet.com/rss/news · https://www.fxstreet.com/rss/analysis | RSS | `<item><title>Gold Price Forecast: XAU/USD …</title>…` | frei | laufend | **Cloudflare-Ratelimit: 429 nach wenigen Abrufen** (`/rss` mit Java-UA, `?category=` blockiert) | 4 | Test 200/200 (je 30 Items). Allgemeiner FX-Feed, **nach „Gold|XAU“ filtern**. Gold-Hub: https://www.fxstreet.com/commodities/gold (200, 923 KB). ToS schließt KI-Training aus (U, [T&C](https://www.fxstreet.com/info/terms-and-conditions-products)). |
| ❌ Reuters Commodities | https://www.reuters.com/markets/commodities/ | HTML | – | – | – | **401**; robots.txt: „automated means prohibited“ | 5 | Test 401/401. Nur Schlagzeilen über Google News `site:reuters.com` (200) |
| ❌ MarketWatch Gold Future | https://www.marketwatch.com/investing/future/gc00 | HTML | – | – | – | **401** (Dow-Jones-Bot-Schutz) | 4 | Test 401/401. Ersatz: ✅ RSS https://feeds.content.dowjones.io/public/rss/mw_marketpulse (200, 30 Items, allgemein) |
| 🟡 CNBC Gold | https://www.cnbc.com/gold/ | HTML | – | frei | laufend | robots.txt sperrt KI-Bots (GPTBot, ClaudeBot, CCBot …) | 3 | Test 200/200. RSS-Endpunkt `search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=<ID>` funktioniert, **die Gold-/Commodities-ID wurde aber nicht gefunden** (10000115 = Real Estate, 10000664 = Finance) (U) |
| 🟡 DailyFX Gold → IG | https://www.dailyfx.com/gold-price → https://www.ig.com/uk/commodities/markets-commodities/gold | HTML (JS) | – | frei | täglich | – | 3 | Test 200/200 (Redirect). DailyFX existiert als Marke nicht mehr. |
| 🟡 World Gold Council Goldhub | https://www.gold.org/goldhub/gold-focus · https://www.gold.org/goldhub/research/library | HTML (Drupal) | – | frei (Daten teils mit Registrierung) | wöchentlich/monatlich | robots.txt ohne Sperren | 5 | Test 200/200. Kein RSS gefunden (U). Goldhub-Blog wöchentlich, Research monatlich/quartalsweise. |
| 🟡 BullionVault Gold News | https://www.bullionvault.com/gold-news | HTML | – | frei | täglich | robots.txt erlaubt | 4 | Test 200/200 (113 KB). `/gold-news/rss` und `/rss.do` liefern **404**. Nur Jsoup-Scraping möglich. |
| ✅ **FXEmpire RSS** PREFERRED | https://www.fxempire.com/api/v1/en/articles/rss/news · …/rss/forecasts · **DE:** https://www.fxempire.com/api/v1/de/articles/rss/news | RSS | `<item><title><![CDATA[Gold (XAU) Daily Forecast: …]]></title>` | frei | laufend | robots.txt sehr offen | 4 | Test 200/200 (je 20 Items). `…/rss/commodities` ist leer (561 B). Seite https://www.fxempire.com/commodities/gold 200. |
| ✅ **Invezz RSS** PREFERRED | https://invezz.com/feed/ | RSS | – | frei | laufend | **HTML mit Cloudflare (403)**, RSS frei | 3 | Test RSS 200/200 (15 Items); https://invezz.com/news/commodities/ 403/403 |

#### (b) Neue Quellen (EN + DE)

| Name | exakte URL | Zugangsweg | Formatbeispiel | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Rel. | Anmerkung / Testergebnis |
|---|---|---|---|---|---|---|---|---|
| ✅ **Google News RSS (EN)** PREFERRED | https://news.google.com/rss/search?q=gold+price+when:7d&hl=en-US&gl=US&ceid=US:en | RSS (Suchfeed) | `<title>Gold price today, … - Yahoo Finance</title><link>https://news.google.com/rss/articles/CBMi…` | frei | laufend | robots.txt: `/rss/search` disallowed (!) | 5 | Test 200/200 (100 Items). **Beliebige Queries möglich, auch `site:kitco.com` oder `site:reuters.com`.** Links sind Google-Redirects und müssen aufgelöst werden. Idealer Rohstoff für den URL-Scout. |
| ✅ **Google News RSS (DE)** PREFERRED | https://news.google.com/rss/search?q=Goldpreis+when:7d&hl=de&gl=DE&ceid=DE:de | RSS | – | frei | laufend | wie oben | 5 | Test 200/200 (100 Items) |
| ✅ **Bing News RSS** PREFERRED | https://www.bing.com/news/search?q=gold+price&format=rss · …?q=XAUUSD&format=rss | RSS | `<item><title>…</title><link>https://…` | frei | laufend | robots.txt erlaubt `/news/search` | 5 | Test 200/200 (6–8 Items), direkte Original-Links |
| ✅ **Investing.com RSS** PREFERRED | https://www.investing.com/rss/news_11.rss · https://www.investing.com/rss/commodities_Technical.rss · https://www.investing.com/rss/commodities_Fundamental.rss · https://www.investing.com/rss/commodities.rss | RSS | `<title>Gold Caught in Trump's Negotiation Impasse…</title><pubDate>Aug 03, 2026 14:12 GMT</pubDate>` | frei | news_11 laufend; Technical/Fundamental selten | **Website 403, RSS aber 200!** | 4 | Test 200/200 (je 10 Items). Die Artikel-Links selbst sind wieder Cloudflare-geschützt. |
| ✅ **Nasdaq Commodities RSS** PREFERRED | https://www.nasdaq.com/feed/rssoutbound?category=Commodities · …?symbol=GLD | RSS | `<title>Gold Extends Weakness As Dollar Rises On Rate Hike Bets</title>` | frei | mehrmals täglich (RTTNews) | Crawl-delay 10–30 s | 4 | Test 200/200 (15/15 Items). Viele kurze Gold-Tagesberichte. |
| ✅ Seeking Alpha GLD RSS | https://seekingalpha.com/api/sa/combined/GLD.xml | RSS | – | frei (Artikel teils Paywall) | täglich | robots.txt sperrt ClaudeBot/CCBot | 3 | Test 200/200 (30 Items) |
| ✅ Yahoo Finance Headlines RSS | https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,GLD&region=US&lang=en-US | RSS | – | frei | laufend | **Java-UA liefert 404, Browser-UA 200** | 3 | Test 200/404 (20 Items) |
| ✅ **ING Think RSS** (Bank-Research) PREFERRED | https://think.ing.com/rss/ | RSS | `<title><![CDATA[The Commodities Feed: Brent drops below $100]]></title>` | frei | täglich | robots.txt sperrt CCBot | 4 | Test 200/200 (10 Items). **„The Commodities Feed“ erscheint täglich und enthält einen Gold-Absatz** mit Bank-Einschätzung. |
| 🟡 Heraeus Weekly Precious Metals Report | https://www.heraeus-precious-metals.com/en/precious-metal-prices-reports/weekly-market-report/ | HTML/PDF | – | frei | wöchentlich | – | 4 | Test 200/200 (371 KB). Die alte Appraisal-URL liefert 404. |
| ✅ investingLive (ex-ForexLive) | https://investinglive.com/feed | RSS | – | frei | laufend (Squawk-artig) | **Java-UA 403**, Browser-UA 200 | 4 | forexlive.com leitet hierher um. Test 200/403 (25 Items). Sehr schnell bei Datenreaktionen. |
| ✅ MINING.COM Gold-Feed | https://www.mining.com/commodity/gold/feed/ | RSS | – | frei | täglich | **Java-UA 403** | 3 | Test 200/403 (36 Items) |
| ✅ OANDA MarketPulse | https://www.marketpulse.com/feed/ | RSS (Volltext) | – | frei | täglich | – | 3 | Test 200/200 (3 Items, 52 KB Volltext) |
| ✅ ActionForex | https://www.actionforex.com/feed/ | RSS | – | frei | laufend | – | 3 | Test 200/200 (20 Items). Enthält Gold-Technik. |
| ✅ Gold-Eagle | https://www.gold-eagle.com/rss.xml | RSS | – | frei | täglich | Crawl-delay 10–15 s | 3 | Test 200/200 (30 Items). Meinungsbeiträge, eher Hintergrund. |
| ✅ GoldSeek / SilverSeek | https://goldseek.com/rss.xml · https://silverseek.com/rss.xml | RSS | – | frei | täglich | SilverSeek: Java-UA Fehler | 3 | Test 200/200 (10 Items) |
| 🟡 Economies.com Gold Analysis | https://www.economies.com/commodities/gold-analysis | HTML | – | frei | täglich | Crawl-delay 2–10 s; sperrt GPTBot/ClaudeBot | 3 | Test 200/200 |
| 🟡 DailyForex Gold | https://www.dailyforex.com/commodities/gold | HTML | – | frei | täglich | – | 3 | Test 200/200. Der Feed `rss/technicalanalysis.xml` liefert 404. |
| 🟡 Saxo Insights (Ole Hansen) | https://www.home.saxo/insights | HTML | – | frei | täglich/wöchentlich | – | 3 | Test 200/200 |
| 🟡 Sprott Insights | https://sprott.com/insights/ | HTML | – | frei | wöchentlich | – | 3 | Test 200/200 |
| 🟡 CME OpenMarkets | https://www.cmegroup.com/openmarkets.html | HTML | – | frei | wöchentlich | Akamai | 3 | Test 200/200, später 403 möglich |
| 🟡 LBMA News | https://www.lbma.org.uk/articles | HTML | – | frei | wöchentlich | – | 3 | Test 200/200 |
| 🟡 GoldBroker / Gainesville Coins / goldpriceforecast.com | https://goldbroker.com/news · https://www.gainesvillecoins.com/blog · https://www.goldpriceforecast.com/ | HTML | – | frei | täglich–wöchentlich | – | 2–3 | Test 200/200 |
| ✅ **DE: Goldreporter** PREFERRED | https://www.goldreporter.de/feed/ | RSS | – | frei | täglich | – | 5 | Test 200/200 (20 Items). **Beste deutschsprachige Gold-Quelle mit Feed.** |
| ✅ **DE: wallstreet-online Rohstoffe** PREFERRED | https://www.wallstreet-online.de/rss/nachrichten-rohstoffe.xml | RSS | – | frei | laufend | – | 4 | Test 200/200 (31 Items) |
| ✅ DE: finanzen.net News/Analysen | https://www.finanzen.net/rss/news · https://www.finanzen.net/rss/analysen | RSS | – | frei | laufend | – | 3 | Test 200/200 (10/15 Items), allgemein, filtern. Goldpreis-Seite https://www.finanzen.net/rohstoffe/goldpreis 200 |
| ✅ DE: Handelsblatt Finanzen / tagesschau Finanzen | https://www.handelsblatt.com/contentexport/feed/finanzen · https://www.tagesschau.de/wirtschaft/finanzen/index~rss2.xml | RSS | – | frei | laufend | – | 2 | Test 200/200 (20/22 Items), allgemein |
| 🟡 DE: boerse.de / finanzen.ch / Kettner / stock3 | https://www.boerse.de/rohstoffe/Goldpreis/XC0009655157 · https://www.finanzen.ch/rohstoffe/goldpreis · https://www.kettner-edelmetalle.de/news · https://stock3.com/ | HTML | – | frei | täglich | – | 2–3 | Test 200/200. godmode-trader.de leitet auf stock3.com um. |

#### (c) Paywall, Anmeldepflicht, Bot-Erkennung (im Test blockiert)

| Quelle | Befund |
|---|---|
| reuters.com, marketwatch.com (Web) | 401 für beide UAs, ToS/robots verbieten automatisierten Abruf |
| investing.com (Web inkl. Technical-Seiten, Fed Rate Monitor) | 403 (Cloudflare). **Nur RSS funktioniert.** |
| forexfactory.com (Web/Forum), myfxbook.com (Web/RSS), babypips.com, forex.com, moneymetals.com, goldseiten.de (inkl. RSS), fxstreet.de | 403 Cloudflare/„Attention Required“ |
| fxleaders.com/feed | „Feeds are disabled on this site.“ |
| barchart.com | 202 mit JS-Challenge |
| reddit.com RSS | 200 beim ersten Abruf, dann **429**; robots.txt verbietet es; nur die offizielle OAuth-API ist sauber |
| mining.com, investinglive.com, Yahoo, SilverSeek | **Sperren nur den Java-Default-UA** (ein eigener, ehrlicher UA ist nötig, siehe Kap. 5) |
| Seeking Alpha | Feed frei, Artikel teils Paywall |
| gold.org | Detaildaten und Downloads teils mit Registrierung (U) |

### 1.3 Block 3: Chart-/Analyse- und Community-Quellen

| Name | exakte URL | Zugangsweg | Formatbeispiel | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Rel. | Anmerkung / Testergebnis |
|---|---|---|---|---|---|---|---|---|
| ✅ **TradingView Ideas RSS** PREFERRED (ToS!) | https://www.tradingview.com/feed/?symbol=OANDA:XAUUSD | RSS (inoffiziell, aber öffentlich verlinkt) | `<item><title>XAUUSD: Sell below 4,378 …</title><description>… resistance 4,358–4,378 …` | frei | laufend | Crawl-delay 5–10 s; KI-Bots auf `/ideas/` gesperrt | 5 | Test 200/200 (30 Items mit Beschreibungstext inkl. Kursmarken). **Ideal für die Extraktion von Levels und Richtung (long/short).** ToS: nur „display“, **non-display usage verboten** ([Policies](https://www.tradingview.com/policies/)). Für ein privates Tool ist das grau, für ein Produkt nicht zulässig. |
| 🟡 TradingView Ideas HTML | https://www.tradingview.com/symbols/XAUUSD/ideas/ | HTML | – | frei | laufend | wie oben | 4 | Test 200/200 (~91 Idea-Links) |
| 🟡 TradingView Scanner (Technicals) | https://scanner.tradingview.com/symbol?symbol=OANDA:XAUUSD&fields=Recommend.All,RSI,ATR | inoffizieller JSON-Endpunkt | `{"ATR":94.73,"RSI":46.78,"Recommend.All":-0.47}` | frei | Echtzeit/verzögert | nicht dokumentiert | 4 | Test 200/200. **Liefert die ATR direkt**, nützlich als Plausibilitätscheck. ToS wie oben. Seite: https://www.tradingview.com/symbols/XAUUSD/technicals/ (200). |
| 🟡 FXStreet XAU/USD Rates & Forecast Poll | https://www.fxstreet.com/rates-charts/xauusd · https://www.fxstreet.com/rates-charts/xauusd/forecast | HTML (JS) | – | frei | wöchentlich (Poll) | Cloudflare-429 möglich | 4 | Chart-Seite Test 200/200. Die Forecast-Poll-Seite (Bias 1W/1M/1Q, Expertenumfrage) wurde nur per Recherche identifiziert (U). |
| ✅ **Kitco Weekly Gold Survey** | https://www.kitco.com/news/category/weekly-gold-survey | HTML | Artikel `/news/article/2026-09-22/…` mit Wall-Street- und Main-Street-Umfrage (bullish/bearish/neutral) | frei | **wöchentlich (Fr/Sa)** | wie Kitco | 5 | Test 200/200. **Strukturierter Sentiment-Wert (Prozentzahlen) direkt extrahierbar.** |
| 🟡 FXEmpire Gold Forecasts | https://www.fxempire.com/forecasts/gold | HTML (+ Forecast-RSS siehe 1.2) | – | frei | täglich | – | 4 | Test 200/200 |
| 🟡 ActionForex Gold-TA | https://www.actionforex.com/technical-analysis/ | HTML/RSS | – | frei | täglich | – | 3 | Test 200/200 |
| ❌ Investing.com Technical Summary | https://www.investing.com/commodities/gold-technical | HTML | – | – | – | Cloudflare | 4 | Test 403/403 |
| ❌ IG Client Sentiment | https://www.ig.com/uk/trading-strategies/client-sentiment | HTML | – | – | – | Redirect auf Login | 4 | Test 200 → Login. Kein freier Zugriff (U) |
| 🟡 Dukascopy SWFX Sentiment | https://www.dukascopy.com/swiss/english/marketwatch/sentiment/ | HTML (Java-Widget/JS) | – | frei | laufend | – | 3 | Test 200/200, Daten per JS/iframe (U) |
| ❌ FX Blue Sentiment | https://www.fxblue.com/market-data/tools/sentiment | HTML | – | frei | – | **robots.txt disallow** | 3 | Test 200/200, aber robots verbietet es |
| ❌ Myfxbook Community Outlook | https://www.myfxbook.com/community/outlook/XAUUSD | HTML / API | API: `{"error":true,"message":"Required fields missing."}` | frei mit Account | laufend | Web: Cloudflare; API: Login-Session, 100 Req/24 h ([API](https://www.myfxbook.com/api)) | 4 | **Einzige saubere Variante:** offizielles `https://www.myfxbook.com/api/get-community-outlook.json?session=…` nach Login über `/api/login.json` (200 erreichbar). Nutzt einen eigenen Account. |
| ❌ ForexFactory Forum | https://www.forexfactory.com/forum/… | HTML | – | – | – | Cloudflare | 2 | Test 403/403 |
| ❌ Reddit r/Gold, r/Forex | https://www.reddit.com/r/Gold/.rss | RSS | – | – | – | 429, robots disallow | 2 | Nur die offizielle API (OAuth, [Reddit Data API](https://support.reddithelp.com/hc/en-us/articles/16160319875092)) (U) |
| ❌ Barchart Gold Opinion | https://www.barchart.com/futures/quotes/GC*0/opinion | HTML | – | – | – | 202 JS-Challenge | 3 | Test 202/202 |

### 1.4 Block 4: Sentiment-, Positionierungs- und Marktdaten

| Name | exakte URL | Zugangsweg | Formatbeispiel | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Rel. | Anmerkung / Testergebnis |
|---|---|---|---|---|---|---|---|---|
| ✅ **CFTC COT Legacy (Futures+Options) – Socrata** PREFERRED | https://publicreporting.cftc.gov/resource/6dca-aqww.json?cftc_contract_market_code=088691&$order=report_date_as_yyyy_mm_dd%20DESC&$limit=2 | offizielle JSON-API (SODA) | `{"market_and_exchange_names":"GOLD - COMMODITY EXCHANGE INC.","report_date_as_yyyy_mm_dd":"2026-09-15T00:00:00.000","open_interest_all":"409899","noncomm_positions_long_all":"258059","noncomm_positions_short_all":"27721",…}` | frei | **wöchentlich, Fr 15:30 ET (21:30 MESZ)**, Stand Dienstag | Socrata-Throttling ohne App-Token; Token kostenlos | 5 | Test 200/200. **Code 088691 = Gold COMEX verifiziert.** Weitere Datasets: `72hh-3qpy` (Disaggregated F+O, `m_money_positions_long_all` …), `jun7-fc8e` (Legacy Futures-only). Doku: https://publicreporting.cftc.gov/ |
| ✅ CFTC COT Flatfiles | https://www.cftc.gov/dea/newcot/deafut.txt · https://www.cftc.gov/dea/newcot/f_disagg.txt · Historie: https://www.cftc.gov/files/dea/history/fut_disagg_txt_2026.zip | CSV/TXT/ZIP | CSV-Zeile mit `"GOLD - COMMODITY EXCHANGE INC.",260915,…` | frei | wöchentlich | keine | 5 | Test 200/200. Gut für den initialen Historien-Import. |
| ✅ **SPDR GLD Holdings (Tonnen) XLSX** PREFERRED | https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en | XLSX-Download | Blatt „US GLD Historical Archive“: `Date, Closing Price, Ounces of Gold per Share, NAV/Share, …, Total Ounces, Tonnes of Gold, Total NAV` | frei | täglich (US-Handelstage) | keine erkannt | 4 | Test 200/200 (540 KB, Daten seit 18.11.2004). **Die alte URL `GLD_US_archive_EN.csv` leitet jetzt auf ein Barlist-PDF um.** Disclaimer: Weiterverbreitung untersagt. In Java mit Apache POI lesen. |
| 🟡 iShares IAU Holdings | https://www.ishares.com/us/products/239561/ishares-gold-trust-fund | HTML (+ Download-Link) | – | frei | täglich | – | 3 | Test 200/200. Download-Link nicht extrahiert (U) |
| 🟡 WGC ETF-Flows | https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows | HTML (Daten mit Login) | – | frei mit Registrierung (U) | wöchentlich/monatlich (U) | – | 4 | Test 200/200. Excel-Download erfordert Registrierung (U) |
| ✅ **Cboe GVZ Historie CSV** PREFERRED | https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv | CSV | `09/22/2026,23.86,24.05,23.12,23.59` (DATE,OPEN,HIGH,LOW,CLOSE) | frei | täglich | keine erkannt | 5 | Test 200/200. **Gold-Vola-Index (implizite 30-Tage-Vola aus GLD-Optionen).** Echtzeitnah: https://cdn.cboe.com/api/global/delayed_quotes/quotes/_GVZ.json (200). Cboe erlaubt verzögerte Daten nur zur persönlichen Nutzung (U). |
| ✅ **Cboe GLD Options Chain JSON** PREFERRED | https://cdn.cboe.com/api/global/delayed_quotes/options/GLD.json | JSON | `{"data":{"current_price":400.07,"iv30":20.962,…,"options":[{"option":"GLD260925C00400000","iv":…,"open_interest":…,"delta":…}]}}` | frei | 15 min verzögert | keine erkannt | 5 | Test 200/200 (3,4 MB). **`iv30` direkt im Header**, pro Option IV/OI/Greeks. Damit lassen sich Expected Move und Straddle-Preis für den Wochenverfall berechnen. |
| ✅ FRED GVZCLS (Backup) | https://fred.stlouisfed.org/graph/fredgraph.csv?id=GVZCLS | CSV ohne Key | `2026-09-22,23.59` | frei | täglich | ~120 Req/min (U); einmal „Remote end closed connection“ → Backoff | 5 | Test 200/200 |
| ✅ **FRED Makro-CSV (ohne Key)** PREFERRED | https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10 · …?id=T10YIE · …?id=DTWEXBGS · …?id=DGS10 · …?id=VIXCLS · …?id=SP500 | CSV | `observation_date,DFII10` / `2026-09-21,2.62` | frei | täglich (1 Tag Verzug) | wie oben | 5 | Test 200/200. **Realzins 10J (DFII10) ist der wichtigste Makrotreiber für Gold.** Die offizielle API (`api.stlouisfed.org`) braucht einen kostenlosen Key (ohne Key: 400). |
| ✅ **US Treasury Real Yield Curve CSV** PREFERRED | https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_real_yield_curve&field_tdr_date_value=2026&page&_format=csv | CSV | `09/22/2026,…,2.63,…` (5/7/10/20/30YR) | frei | täglich ~17 Uhr ET | keine | 5 | Test 200/200. Offizielle Quelle, **schneller als FRED** (am selben Tag verfügbar). |
| 🟡 Yahoo Chart API (GC=F, DX-Y.NYB, ^GVZ) | https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=5d&interval=1d | inoffizieller JSON-Endpunkt | `{"chart":{"result":[{"meta":{"regularMarketPrice":4359.2,…` | frei | Echtzeit/verzögert | **Java-UA 429**, Browser-UA 200 (ohne Crumb) | 4 | Für DXY und Futures praktisch. Inoffiziell und fragil, ToS verbietet es (U). **Für den Kurs selbst gilt: MT5 ist die Primärquelle.** |
| ❌ Stooq CSV | https://stooq.com/q/d/l/?s=xauusd&i=d | CSV | – | – | – | liefert jetzt eine JS-Verifikationsseite statt CSV | 3 | Für Automatisierung tot |
| ✅ **LBMA Gold Price JSON** | https://prices.lbma.org.uk/json/gold_pm.json · …/gold_am.json | JSON | `{"d":"2026-09-22","v":[4329.55,3240.67,3780.13]}` (USD, GBP, EUR) | frei zur Ansicht | 2× täglich | keine erkannt | 4 | Test 200/200 (~915 KB, seit 1968). **Lizenzfrage IBA/LBMA für Weiterverwendung (U).** |
| 🟡 CME FedWatch | https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html | HTML + iframe (QuikStrike) | – | Web frei, API kostenpflichtig | laufend | Akamai (später 403) | 4 | Ohne Browser nicht auslesbar. **Alternative:** ✅ Atlanta Fed Market Probability Tracker https://www.atlantafed.org/research-and-data/data/market-probability-tracker (200, Downloadformat U). rateprobability.com und Investing Fed Monitor liefern 403. |
| 🟡 CME Gold Warehouse Stocks | https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls | XLS (OLE) | Registered/Eligible Unzen je Depot | frei | täglich | Akamai: erst 200, dann 403 | 3 | Test 200 → 403. Höchstens 1× täglich abrufen; ToS verbietet Scraping (U). |
| ❌ CME Volume/OI JSON | https://www.cmegroup.com/CmeWS/mvc/Volume/… | JSON | – | – | – | 404/403 | 3 | Nicht nutzbar. Ersatz: OI aus COT oder MT5-Tickvolumen. |
| ❌ SGE (Shanghai Gold Exchange) | https://en.sge.com.cn/ | HTML (JS) | – | frei | täglich | TLS-Kette „self-signed“ (Python); www.en.sge.com.cn ohne DNS | 3 | Für Automatisierung derzeit nicht empfehlenswert |
| ❌ US Mint Verkaufszahlen | https://www.usmint.gov/ | HTML | – | – | monatlich | Cloudflare 403 | 1 | Geringe Tagesrelevanz |
| ❌ Google Trends | https://trends.google.com/trends/explore?q=gold | HTML/intern | – | – | – | 429; offizielle Trends-API nur Alpha mit Zugangsbeschränkung ([Google](https://developers.google.com/search/blog/2025/07/trends-api)) | 2 | Nicht nutzbar |
| 🟡 IMF SDMX | https://api.imf.org/external/sdmx/2.1/dataflow | XML (SDMX) | – | frei | monatlich | – | 2 | Test 200/200. Zentralbank-Goldreserven (IFS) monatlich, **für Tagesprognosen irrelevant** |
| ❌ Nasdaq Data Link LBMA/GOLD | https://data.nasdaq.com/api/v3/datasets/LBMA/GOLD.json | JSON | – | – | – | 403 | 3 | Dataset nicht mehr frei |

### 1.5 Block 5: Websuche-APIs und Such-Workarounds

| Name | exakte URL | Zugangsweg | Formatbeispiel | Kosten | Update-Frequenz | Rate-Limit/Bot-Schutz | Gold-Rel. | Anmerkung / Testergebnis |
|---|---|---|---|---|---|---|---|---|
| ✅ **Google News RSS** PREFERRED (ohne Key) | https://news.google.com/rss/search?q=%22gold+price%22+forecast+when:1d&hl=en-US&gl=US&ceid=US:en | RSS | siehe 1.2 | frei | Echtzeit | robots `/rss/search` disallow; ab Hunderten Req/h sind Sperren zu erwarten (U) | 5 | **Beste Such-Primärquelle ohne Key.** Operatoren `site:`, `when:1d`, `"…"`, `OR` funktionieren. |
| ✅ **Bing News RSS** PREFERRED (ohne Key) | https://www.bing.com/news/search?q=gold+price+forecast&format=rss | RSS | siehe 1.2 | frei | Echtzeit | robots erlaubt | 5 | Weniger Items (6–8), dafür direkte Links |
| 🟡 Bing Web als RSS | https://www.bing.com/search?q=xauusd+analysis&format=rss | RSS | 10 Items | frei | – | robots.txt: `/search` **disallow** | 3 | Test 200/200. Funktioniert technisch, ist aber regelwidrig, deshalb nur als Notnagel |
| ❌ DuckDuckGo HTML/Lite | https://html.duckduckgo.com/html/?q=gold · https://lite.duckduckgo.com/lite/?q=gold | HTML | – | frei | – | **Browser-UA: 202 „anomaly“-Seite; Java-UA: 403** | – | **Im Test nicht nutzbar.** DDG Instant Answer API (`api.duckduckgo.com/?q=…&format=json`) ist keine Websuche. |
| ❌ Google Custom Search JSON API | https://www.googleapis.com/customsearch/v1 | offizielle API | – | 100/Tag frei, $5/1000 | – | – | – | **Für Neukunden geschlossen, Sunset 01.01.2027**; „Search the entire web“ ist für neue Engines seit 20.01.2026 deaktiviert ([Google](https://developers.google.com/custom-search/v1/overview)). Test 403 ohne Key |
| ❌ Bing Web Search API | https://api.bing.microsoft.com/v7.0/search | offizielle API | – | – | – | – | – | **Eingestellt am 11.08.2025** ([Microsoft](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)). Nachfolger „Grounding with Bing“ gibt es nur in Azure AI Foundry Agents, ~$14/1000 (U). Test 401 |
| 🟡 Brave Search API | https://api.search.brave.com/res/v1/web/search?q=gold | offizielle API | JSON `web.results[]` | **kein Free-Tier seit Feb. 2026**; $5 Guthaben/Monat, Kreditkarte + Attribution nötig (U) | Echtzeit | 1 QPS (Basis) (U) | 4 | Test 422 ohne Key. Eigener Index, gute Qualität |
| 🟡 Serper.dev (Google-SERP) | https://google.serper.dev/search (POST) | offizielle API | JSON `organic[]`, `news[]` | 2.500 Queries einmalig gratis, danach ~$0,30–1/1000 (U) | Echtzeit | – | 4 | Test 403 ohne Key. **Günstigste Google-Qualität** |
| 🟡 **Tavily** (für LLM-Agents) | https://api.tavily.com/search (POST) | offizielle API | JSON `results[{title,url,content,score}]` | **1.000 Credits/Monat frei, ohne Kreditkarte** (U) | Echtzeit | – | 4 | Test 401 ohne Key. Liefert bereits extrahierten Content und spart damit Scraping |
| 🟡 SerpAPI | https://serpapi.com/search.json?engine=google_news&q=gold | offizielle API | JSON | 250 Suchen/Monat frei (U) | – | – | 3 | U |
| 🟡 Exa | https://api.exa.ai/search | offizielle API | JSON | ~$7/1000, Startguthaben (U) | – | – | 3 | Semantische Suche (U) |
| 🟡 Jina Search / Reader | https://s.jina.ai/?q=gold · https://r.jina.ai/https://… | API | Markdown | Key nötig, Freikontingent (U) | – | – | 3 | `s.jina.ai` Test 401 ohne Key. **`r.jina.ai` (Reader) wandelt JS-Seiten in Text um** (U, nicht getestet) |
| 🟡 Firecrawl / LangSearch / Linkup / Parallel.ai / Perplexity Sonar / You.com / Kagi | https://firecrawl.dev · https://langsearch.com · https://linkup.so · https://parallel.ai · https://docs.perplexity.ai · https://you.com · https://kagi.com | APIs | JSON | Freikontingente von 0 bis ~1.000/Monat (U) | – | – | 2–3 | Alle (U), nicht getestet (Key nötig) |
| 🟡 Mojeek | https://www.mojeek.com/search?q=gold | HTML / API | – | API kostenpflichtig (~£2/1000, auf Anfrage) (U) | – | Web: Captcha im Test | 2 | Eigener Index, Web-Zugriff gesperrt |
| 🟡 **SearXNG (self-hosted)** | https://docs.searxng.org/ · Instanzliste: https://searx.space/data/instances.json | Meta-Suche, JSON-API (`?format=json`) | JSON `results[]` | frei (eigener Docker-Container) | – | öffentliche Instanzen haben JSON meist deaktiviert und limitieren | 4 | instances.json Test 200. **Nur self-hosted sinnvoll**, dann eigene Kontrolle über die Frequenz |

**Empfehlung Suche:**
1. **Default ohne Key:** Google-News-RSS plus Bing-News-RSS, dedupliziert über die aufgelöste Ziel-URL. Das deckt 90 % des Bedarfs für einen „Gold-News-Scout“.
2. **Optional mit Key:** Tavily (kostenlos, LLM-freundlich) oder Serper (Google-Qualität, sehr günstig). Brave als Qualitätsalternative.
3. **Power-User:** SearXNG im Docker-Container.
4. **Nicht einplanen:** DDG-Scraping, Google CSE, Bing API.

---

## 2. Top-15 der Quellen mit bestem Nutzen/Aufwand

Sortiert nach Nutzen pro Implementierungsaufwand für MqlGoldscanner:

| # | Quelle | Format | Liefert für Ihre Frage | Aufwand | Agent |
|---|---|---|---|---|---|
| 1 | **MT5-Kurshistorie XAUUSD** (eigenes Terminal) | MT5/CSV | Basis aller Range-Berechnungen, Klimatologie | gering | Kurs-/Statistik-Agent |
| 2 | **Cboe GLD-Options-JSON (`iv30`) + GVZ-CSV** | JSON/CSV | **Marktimplizite Tagesbewegung**, stärkster Einzelprädiktor | gering | Vola-Agent (neu) |
| 3 | **ForexFactory JSON/CSV (thisweek)** | JSON/CSV | Termine, Impact, Forecast der Woche | gering | Termin-Agent |
| 4 | **MT5-Wirtschaftskalender** (MQL5-Export) | CSV/SQLite | Termine **plus Ist-Werte**, historisch, offiziell | mittel (MQL5-Skript) | Termin-Agent/Backtest |
| 5 | **BLS-ICS + BEA-ICS** | ICS | Exakte NFP-, CPI-, PCE- und GDP-Termine ein Jahr im Voraus | gering | Termin-Agent |
| 6 | **Fed `calendar.json` + Fed-RSS** | JSON/RSS | FOMC, Minutes, Powell-Reden | gering | Termin-/News-Agent |
| 7 | **Nasdaq Economic Events JSON** | JSON | Ist-Werte, Surprise-Berechnung | gering (ToS-grau) | Event-Impact-Agent |
| 8 | **FRED-CSV (DFII10, T10YIE, DTWEXBGS, VIXCLS) + Treasury Real Yield CSV** | CSV | Realzins-/Dollar-Regime | gering | Makro-Agent (neu) |
| 9 | **CFTC Socrata (088691)** | JSON | Managed-Money-Positionierung, Crowding | gering | Positionierungs-Agent (neu) |
| 10 | **Google-News-RSS (EN/DE) + Bing-News-RSS** | RSS | Aktuelle Gold-Headlines, URL-Scout | gering | News-/URL-Scout-Agent |
| 11 | **TradingView Ideas RSS (OANDA:XAUUSD)** | RSS | Kursmarken, Long/Short-Bias der Community | gering (ToS!) | Chart-/Community-Agent |
| 12 | **TreasuryDirect JSON** | JSON | 10y/30y-Auktionen (Vola-Treiber am Nachmittag) | gering | Termin-Agent |
| 13 | **SPDR GLD XLSX** | XLSX | ETF-Flows (Tonnen) | gering (POI) | Positionierungs-Agent |
| 14 | **Kitco Weekly Gold Survey + ING Think RSS + FXStreet RSS** | HTML/RSS | Experten-/Bank-Bias | mittel | News-Analyse-Agent |
| 15 | **Investing-RSS + Nasdaq-Commodities-RSS + Goldreporter + wallstreet-online** | RSS | Breite News-Abdeckung EN/DE | gering | News-Agent |

---

## 3. Methodenkapitel: Tagesbewegungs-Wahrscheinlichkeiten

### 3.1 Zielgröße und Baseline (Klimatologie)

**Definition** (aus dem Konzept): Ein Tag *t* ist ein „Bewegungstag“, wenn gilt: True Range (TR) des Tages > Mittelwert der TR desselben Wochentags über die letzten 13 Wochen.

**Eigene Rechnung** (Yahoo GC=F Daily, 5 Jahre, 1.257 Handelstage, Stand 22.09.2026; Vorbehalt: Futures-Roll-Artefakte, mit MT5-XAUUSD wiederholen):

| Wochentag | P(Bewegungstag) | Ø TR letzte 13 Wochen (USD) |
|---|---|---|
| Mo | 41,2 % | 81,7 |
| Di | 43,7 % | 96,0 |
| Mi | 45,7 % | 123,2 |
| Do | 42,7 % | 103,3 |
| Fr | 41,7 % | 104,7 |
| **gesamt** | **43,0 %** | – |

**Folgerungen:**
- Weil TR rechtsschief verteilt ist, liegt der Median unter dem Mittelwert. Deshalb liegt die Basisrate systematisch **unter 50 %**. Eine naive „50 %“-Anzeige wäre falsch kalibriert.
- **Jede Agentenprognose muss die Klimatologie (~43 %, wochentagsabhängig) im Brier Skill Score schlagen.** Sonst hat sie keinen Mehrwert.
- NFP-Proxy (erster Freitag im Monat): Ø TR 56,9 / Median 40,0 (n = 57) gegenüber anderen Freitagen mit 52,4 / 33,4 (n = 196). Das bestätigt einen Event-Effekt, der aber kleiner ist als oft angenommen.
- Mittwoch zeigt die höchste Basisrate und die höchste Ø-TR. Das passt zu FOMC-Terminen (Mi 14:00 ET) und EIA-/Auktionsballung (Mi).

### 3.2 Vola-Schätzer aus OHLC (Range-Estimators)

Aus MT5-OHLC ohne externe Daten berechenbar:

| Schätzer | Formel (täglich, σ²) | Quelle |
|---|---|---|
| Parkinson (1980) | (ln H/L)² / (4 ln 2) | J. Business 53(1) |
| Garman-Klass (1980) | 0,5 (ln H/L)² − (2 ln 2 − 1)(ln C/O)² | J. Business 53(1) |
| Rogers-Satchell (1991) | ln(H/C)·ln(H/O) + ln(L/C)·ln(L/O) | Ann. Appl. Prob. 1(4) |
| Yang-Zhang (2000) | σ²_overnight + k·σ²_open-close + (1−k)·σ²_RS | J. Business 73(3) |

**Empfehlung:** Yang-Zhang als Feature. Er ist robust gegenüber Gaps (Sonntagsöffnung!) und drift-unabhängig.

### 3.3 HAR-Modell (Corsi 2009): Kernmodell für die TR-Prognose

`TR_t+1 = β0 + βd·TR_t + βw·mean(TR_t-4..t) + βm·mean(TR_t-21..t) + γ·Dummies(Wochentag, Event) + δ·GVZ_t + ε`

- Quelle: Corsi, F. (2009), *A Simple Approximate Long-Memory Model of Realized Volatility*, J. Financial Econometrics 7(2), 174–196, [doi:10.1093/jjfinec/nbp001](https://doi.org/10.1093/jjfinec/nbp001).
- **Implementierung in Java:** OLS mit `org.apache.commons.math3.stat.regression.OLSMultipleLinearRegression`. In Log-Form (`ln TR`) gerechnet sind die Residuen nahezu normal, also P(TR > Schwelle) = 1 − Φ((ln S − μ̂)/σ̂).
- **Mehrwert impliziter Vola:** GVZ im HAR erhöht das R² deutlich (Hysa 2026, [SSRN 6978741](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6978741), R² +10–56 %, Peer-Review U). Siehe auch Qiao et al. 2026, *Quantitative Finance and Economics*, [doi:10.3934/QFE.2026009](https://doi.org/10.3934/QFE.2026009) (U).

**Das ist der wichtigste methodische Hebel: Die Schwelle ist bekannt (Ø TR 13 Wochen). Das HAR-Modell liefert eine Verteilung von TR_t+1, und P(Bewegungstag) folgt daraus direkt, statistisch sauber und kalibrierbar.**

### 3.4 GARCH-Familie und CARR

- **GJR-GARCH(1,1)** mit **invertierter Asymmetrie bei Gold:** Positive Schocks erhöhen die Vola stärker als negative (Safe-Haven-Effekt). Baur, D. (2012), *Asymmetric Volatility in the Gold Market*, J. Alternative Investments 14(4), 26–38, [SSRN 1526389](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1526389).
- **CARR** (Conditional Autoregressive Range, Chou 2005, J. Money Credit Banking 37(3), 561–582): GARCH-Struktur direkt auf der Range. Das passt exakt zur Zielgröße TR.
- **Java:** Es gibt keine etablierte GARCH-Bibliothek. Maximum Likelihood per `commons-math3` (`BOBYQAOptimizer`/`NelderMeadSimplex`) umsetzen, etwa 150 Zeilen Code. **Priorität geringer als HAR**, weil HAR mit Features für die Tages-TR in der Literatur mindestens gleichwertig ist.

### 3.5 Event-Studien: Makro-Releases und Gold

| Studie | Kernbefund | Link |
|---|---|---|
| Elder, Miao & Ramchander (2012), J. Banking & Finance 36(1) | Gold reagiert signifikant auf US-Makrosurprises innerhalb von Minuten; **NFP hat den größten Effekt**, auch Durable Goods, GDP, ISM. 8:30-ET-Releases dominieren. | [doi:10.1016/j.jbankfin.2011.06.007](https://doi.org/10.1016/j.jbankfin.2011.06.007) |
| Roache & Rossi (2009), IMF WP 09/140 | Gold reagiert als eines der wenigen Commodities antizyklisch auf Makro-Surprises | [IMF](https://www.imf.org/external/pubs/ft/wp/2009/wp09140.pdf) |
| Smales & Lucey (2019), J. Int. Fin. Markets 60 | FOMC-Ankündigungen verändern Liquidität und Vola im Goldmarkt deutlich | [doi:10.1016/j.intfin.2018.12.003](https://doi.org/10.1016/j.intfin.2018.12.003) |
| Christie-David, Chaudhry & Koch (2000), J. Futures Markets | Gold-Futures reagieren vor allem auf CPI und NFP (Details U) | (U) |

**Umsetzung:** Pro Event-Typ (NFP, CPI, FOMC, PCE, GDP, ISM, 10y/30y-Auktion, Powell-Rede) den **empirischen TR-Multiplikator** berechnen: Ø TR an Event-Tagen / Ø TR sonst, aus MT5-Kalender-Historie plus MT5-Kursen. Zusätzlich die **Surprise-Größe** |actual − forecast| / σ(surprise) für die Nachträglich-Analyse. Das ersetzt das statische „Impact: High“ durch eine gemessene Wirkung.

### 3.6 Implizite Vola → Expected Move (Sanity-Check und Feature)

- σ_Tag = IV / √252. Beispiel am 23.09.2026: GLD `iv30` = 20,96 % → σ_Tag = 1,32 %. Bei 4.359 USD ergibt das **1σ ≈ 57,6 USD**.
- Erwartete High-Low-Range einer Brownschen Bewegung: E[R] = √(8/π)·σ ≈ **1,596 σ ≈ 92 USD**.
- **Plausibilität:** Die TradingView-ATR(14) liegt am selben Tag bei **94,7 USD**. Implizite und realisierte Range stimmen also auf ±3 % überein. Die Methode trägt.
- **P(Bewegungstag) aus IV:** Schwelle S = Ø TR desselben Wochentags über 13 Wochen. Wenn die implizite Range deutlich über S liegt, ist P(Bewegungstag) hoch. Die Abbildung auf P erfolgt über eine Lognormal-Annahme für TR und wird per Isotonic Regression kalibriert (3.8).
- tastytrade-Faustregel für Wochen-Expected-Move: EM ≈ 0,6·ATM-Straddle + 0,3·1.-OTM-Strangle + 0,1·2.-OTM-Strangle (U); alternativ EM = S·IV·√(DTE/365).
- Für ein Event-Premium kann man die Term-Structure nutzen: Die IV der Weekly-Option vor dem Event (NFP/FOMC) liegt über `iv30`, und die Differenz ist die **marktimplizite Event-Vola**.

### 3.7 Saison- und Kalendereffekte

- Wochentagseffekt Gold: Ball, Torous & Tschoegl (1982), *Gold and the Weekend Effect*, J. Futures Markets 2(2), 175–182 (U).
- Herbst-Effekt (Sep–Nov höhere Renditen): Baur, D. (2013), *The Autumn Effect of Gold*, Research in International Business and Finance 27(1), [doi:10.1016/j.ribaf.2012.05.001](https://doi.org/10.1016/j.ribaf.2012.05.001).
- Monats- und Kontrakteffekte: GC-FND/LTD- und Options-Verfallstage (Kap. 1.1, regelbasiert), Quartalsende, US-Feiertage (dünne Liquidität).
- **Umsetzung:** Das sind nur Dummy-Features im HAR bzw. Gradient-Boosting-Modell, keine eigene Methode.

### 3.8 Klassifikator-Ansatz und Kalibrierung

- **Logistische Regression** (Baseline, interpretierbar) und **Gradient Boosting** (Smile `GradientTreeBoost` oder XGBoost4J) mit den Features TR-Lags (HAR), Yang-Zhang, GVZ/iv30, ΔGVZ, Event-Dummies inkl. gemessener Multiplikatoren, Wochentag, DFII10-Δ, DXY-Δ, COT-Perzentil, Asia-Session-Range bis 08:00 MEZ (Intraday-Update!), Gap.
- **Validierung:** Walk-forward (expanding window) statt Zufalls-Split.
- **Scores:** Brier Score (Brier 1950, Monthly Weather Review 78(1)) mit Murphy-Zerlegung in Reliability, Resolution und Uncertainty (Murphy 1973, J. Appl. Meteorology 12(4)). Dazu der **Brier Skill Score gegen die Klimatologie (43 %)**, Log-Loss sowie proper scoring rules nach Gneiting & Raftery (2007), JASA 102(477), [doi:10.1198/016214506000001437](https://doi.org/10.1198/016214506000001437).
- **Reliability-Diagramm mit Konsistenzbalken:** Bröcker & Smith (2007), Weather and Forecasting 22(3), [doi:10.1175/WAF993.1](https://doi.org/10.1175/WAF993.1).
- **Nachkalibrierung:** Platt Scaling (logistisch) oder **Isotonic Regression** (Zadrozny & Elkan 2002, KDD). Ab ~500 Beobachtungen ist Isotonic vorzuziehen.
- **Agenten-Gewichtung:** Stacking bzw. logistische Kombination der Einzelagenten-Wahrscheinlichkeiten, Gewichte walk-forward geschätzt. Das ist besser als feste Gewichte.

### 3.9 Wettbewerber und vergleichbare Produkte

| Produkt | Was es zeigt | Lehre für MqlGoldscanner |
|---|---|---|
| Kitco Weekly Gold Survey | Wall Street vs. Main Street bullish/bearish/neutral in % | Crowd-Sentiment als Feature, keine Vola |
| FXStreet Forecast Poll | Experten-Bias und Durchschnittsziel 1W/1M/1Q | Richtung, keine Bewegungsgröße |
| LBMA Annual Forecast Survey | Jahresprognosen | irrelevant für Tagesprognosen |
| WGC Qaurum / Gold Valuation Framework | Szenarioanalyse | Makro-Rahmen |
| TradingView Technical Ratings | Strong Buy … Strong Sell | Richtung, nicht kalibriert |
| Myfxbook / IG Client Sentiment | Long/Short-Anteil Retail | Kontraindikator (U) |
| CME FedWatch | Zinswahrscheinlichkeiten als Balken | **Vorbild für die Darstellung von Wahrscheinlichkeiten** |
| tastytrade / Options-Broker „Expected Move“ | ±USD-Band aus Optionen | **Vorbild: marktimplizite Range als Zahl** |

**Lücke im Markt:** Kein gefundenes Produkt liefert eine **kalibrierte Wahrscheinlichkeit für „überdurchschnittliche Tagesbewegung“ je Wochentag mit Track Record**. Genau das wäre das Alleinstellungsmerkmal.

---

## 4. Ideenliste (priorisiert)

### 4.1 Neue Agenten

| Prio | Agent | Idee / Input | Nutzen | Aufwand |
|---|---|---|---|---|
| **P1** | **Options-/Vola-Agent** | GLD `iv30`, GVZ-Level und ΔGVZ, Weekly-IV vs. 30-Tage-IV (Event-Premium) → implizite Range vs. Schwelle | Stärkster Einzelprädiktor, Marktkonsens statt Meinung | gering |
| **P1** | **Backtest- und Kalibrier-Agent** | Speichert jede Prognose, rechnet am Folgetag Treffer, Brier, BSS vs. 43 %-Klimatologie und Reliability; passt Agentengewichte walk-forward an | Macht das Tool überprüfbar, ohne ihn ist alles Bauchgefühl | mittel |
| **P1** | **Event-Impact-Agent** | Gemessene TR-Multiplikatoren je Event-Typ aus MT5-Kalender-Historie, Surprise-Nachtrag (Nasdaq/MT5 actual) | Ersetzt statisches „High Impact“ | mittel |
| **P1** | **Regelbasierter Termin-Agent** | Berechnet FND/LTD/Options-Verfall, Quartalsende, US/UK-Feiertage (verkürzter Handel), Zeitumstellung (DST-Lücke US/EU im März/Okt–Nov) | Kein Scraping, deterministisch | gering |
| P2 | Makro-/Korrelations-Agent | ΔDFII10, ΔDXY, VIX, T10YIE; Regime „Realzins-getrieben vs. Risk-off“ | Kontext für Richtung und Größe | gering |
| P2 | Positionierungs-Agent | COT Managed-Money-Perzentil (3 Jahre), GLD-Tonnen-Δ 5 Tage | Crowding → Squeeze-Risiko | gering |
| P2 | Session-/Gap-Agent | Asia-Range bis 08:00 MEZ, Wochenend-Gap, London-Open-Ausbruch → **Intraday-Update der Tagesprognose** | Deutlicher Informationsgewinn am Morgen | mittel |
| P2 | Regime-Agent | Vola-Regime (GVZ-Perzentil, Hidden-Markov oder einfache Schwelle), Trend/Range | Konditioniert alle anderen Agenten | mittel |
| P3 | Sentiment-Agent | Kitco Survey, TradingView-Ideas Long/Short-Quote, FXStreet Poll | schwach, eher Kontraindikator | mittel |
| P3 | Headline-Attention-Agent | Anzahl Gold-Headlines/Stunde (Google-/Bing-News-RSS) als Aufmerksamkeitsmaß, Keyword-Spikes („war“, „tariff“, „central bank buying“) | Frühwarnung bei Geopolitik | gering |
| P4 | China/SGE-Agent | SGE-Premium, PBoC-Käufe | technisch derzeit schwer erreichbar | hoch |

### 4.2 Produkt- und UI-Ideen

| Idee | Vorbild | Beschreibung |
|---|---|---|
| **Wahrscheinlichkeit plus Klimatologie im selben Balken** | NOAA Probability of Precipitation | „62 % (normal: 44 %)“, sofort erkennbar, ob der Tag auffällig ist |
| **Schwellen-Tabelle Wochentag × Faktor** | USGS-Nachbeben-Tabelle | Zeilen Mo–Fr, Spalten P(TR > 1,0×/1,5×/2,0× Ø): zeigt auch Extremrisiko |
| **Unsicherheitskegel für die Range** | NHC Hurricane Cone | Band aus historischen Prognosefehlern statt Scheingenauigkeit |
| **Asymmetrischer Fan-Chart** | Bank of England Inflation Fan Chart | Verteilung der erwarteten TR (Quantile 10/50/90) |
| **5-stufige Warnskala** | Lawinenwarnstufen | „ruhig / normal / erhöht / hoch / extrem“ als Ampel für Trader |
| **Prognose-Verlauf („Plume“)** | ECMWF Ensemble Plume/EFI | Wie hat sich die Prognose für Freitag seit Montag entwickelt? |
| **Balken je Szenario** | CME FedWatch | Verteilung auf TR-Klassen |
| **Track-Record-Seite** | Wetterdienste, Superforecasting | Reliability-Diagramm und BSS der letzten 13/52 Wochen, öffentlich sichtbar |
| **Agenten-Beitrag („Warum?“)** | SHAP / Waterfall | Pro Tag: Klimatologie 43 % +12 (NFP) +8 (GVZ hoch) −3 (Positionierung) = 60 % |
| **MT5-Export** | – | Wahrscheinlichkeiten als CSV/Global Variable für einen EA (z. B. Lot-Größe oder Handels-Filter) |

---

## 5. Risiken, ToS und höfliche Abruffrequenzen

### 5.1 Technische Empfehlungen

- **Eigenen, ehrlichen User-Agent setzen**, z. B. `MqlGoldscanner/0.1 (+mailto:ihre@adresse)`. Der Java-Default-UA wird von mining.com, investinglive, Yahoo und SilverSeek blockiert. **Browser-UAs vorzutäuschen, um Sperren zu umgehen, wird nicht empfohlen** (ToS und Fairness).
- `If-Modified-Since`/`ETag` nutzen, lokal cachen (SQLite), bei 429/503 **exponentielles Backoff** und bei Wiederholung einen Tag Pause.
- **Cloudflare/Akamai/DataDome-Seiten nicht umgehen** (kein Headless-Stealth, keine Captcha-Löser). Stattdessen den RSS- oder API-Ersatz nutzen.
- Windows: Die Fed-`calendar.json` hat ein UTF-8-BOM. Beim Parsen entfernen.
- Zeitzonen: FF liefert US-Eastern mit Offset, MT5 die Server-Zeit (meist UTC+2/+3), BLS/BEA ET in ICS. **Alles intern in UTC speichern.**

### 5.2 Quellen-Risiko und Frequenz

| Quelle | Rechtl. Status | Empfohlene Frequenz | Risiko |
|---|---|---|---|
| Fed, EZB, BLS, BEA, Treasury, TreasuryDirect, FiscalData, CFTC, FRED | öffentlich/Public Domain (US-Regierung) | 1× täglich; CFTC **Fr nach 21:30 MESZ** | sehr gering |
| ForexFactory Feed (faireconomy) | inoffiziell, geduldet | **≤ 1× pro Stunde**, besser 4× täglich | IP-Sperre bei Übernutzung; Feed kann jederzeit verschwinden |
| MT5-Kalender | Broker-/MetaQuotes-Lizenz, lokale Nutzung | beliebig (lokal) | gering |
| Nasdaq API | robots disallow `/api/`, inoffiziell | 1–3× täglich | mittel (Sperre, ToS) |
| Cboe CDN (GVZ, GLD-Options) | verzögerte Daten, persönliche Nutzung (U) | 1× täglich (nach Close) + ggf. 1× morgens | mittel bei kommerzieller Nutzung |
| SPDR XLSX | Weiterverbreitung untersagt | 1× täglich | gering bei privater Nutzung |
| LBMA JSON | IBA-Lizenz für Benchmark-Nutzung (U) | 1× täglich | mittel bei Produkt |
| Google News RSS | robots disallow `/rss/search` | **≤ 1× pro 10 min**, wenige Queries | mittel (Sperre) |
| Bing News RSS | robots erlaubt | ≤ 1× pro 10 min | gering |
| FXStreet RSS | ToS: kein KI-Training (U); Cloudflare-429 | **≤ 1× pro 15 min** | mittel |
| TradingView RSS/Scanner | ToS: non-display usage verboten | **alle 2–4 h**, nur privat | **hoch bei Produkt** |
| Kitco HTML | robots erlaubt, ToS verbietet Bots (U) | 1–2× täglich | mittel |
| Investing RSS | RSS öffentlich, Website blockiert | ≤ 1× pro 30 min | gering–mittel |
| Yahoo Chart API | inoffiziell, ToS (U) | vermeiden bzw. nur Backup | hoch (429) |
| **Reuters, MarketWatch-Web, CME-Web, Reddit, Stooq, Investing-Web, Myfxbook-Web, FF-Web** | robots/ToS verbieten oder technisch blockiert | **nicht verwenden** | hoch |

### 5.3 Fachliche Risiken

- **Overfitting auf 13-Wochen-Fenster:** Die Schwelle wandert mit, deshalb Kalibrierung regelmäßig neu schätzen.
- **Regimewechsel:** Das Goldpreisniveau hat sich seit 2022 mehr als verdoppelt. Deshalb **relative TR (TR/Close)** für lange Historien nutzen, die absolute TR nur im 13-Wochen-Fenster.
- **Futures vs. Spot:** GC=F enthält Roll-Sprünge, deshalb für Statistik MT5-XAUUSD (Spot/CFD) nehmen.
- **Broker-Abhängigkeit:** Die TR hängt vom Broker-Feed und vom Tagesschnitt (Server-Zeit) ab. Eine Definition festlegen, z. B. NY-Close 17:00 ET = MT5-Server 00:00 bei UTC+2/+3.
- **LLM-Extraktion aus News:** Halluzinationsrisiko. Nur Strukturdaten (Levels, Bias) mit Quellen-Link speichern und stichprobenartig prüfen.

---

## 6. Explizit unverifizierte Punkte (U)

Nicht selbst getestet oder nur aus Sekundärquellen, **vor Implementierung prüfen:**

1. ForexFactory-Feed-Rate-Limit „~2 Requests/5 min“ (nur Community-Aussage).
2. Myfxbook-ToS-Details sowie Community-Outlook-API-Antwortformat nach Login.
3. Finnhub-Kalender: nur Premium?
4. EZB-Sitzungskalender: Tabellenstruktur nicht geparst.
5. CME-Regeln für FND/LTD/OG-Verfall (aus Rulebook-Zusammenfassung, gegen https://www.cmegroup.com/rulebook/COMEX/ prüfen).
6. CNBC-RSS-ID für Gold/Commodities.
7. gold.org: Registrierungspflicht für ETF-Flow-Downloads, Existenz eines RSS.
8. iShares-IAU-Download-Link.
9. Cboe-Nutzungsbedingungen für verzögerte CDN-Daten; LBMA/IBA-Lizenzbedingungen.
10. FXStreet-ToS-Klausel zu KI/Training; Kitco-ToS-Bot-Verbot.
11. Atlanta-Fed-Market-Probability-Tracker: Downloadformat.
12. Preise und Freikontingente aller Such-APIs (Brave, Serper, Tavily, SerpAPI, Exa, Jina, Firecrawl, Mojeek, Linkup, Parallel, Perplexity, You.com, Kagi), laut Recherche Stand 2026, kann sich schnell ändern.
13. „Grounding with Bing“: Preis ~$14/1000.
14. Studien: Christie-David et al. (2000) Details; Hysa (2026) Peer-Review-Status; Qiao et al. (2026); Ball/Torous/Tschoegl (1982) Seitenzahlen; Kohli (2012) nicht verifiziert und deshalb nicht zitiert.
15. tastytrade-Expected-Move-Gewichtung (0,6/0,3/0,1).
16. Dukascopy SWFX, IG Client Sentiment: Datenzugang ohne Browser/Login.
17. FXStreet Forecast Poll: Seitenstruktur nicht getestet.
18. Die Klimatologie-Zahlen (43 %) basieren auf Yahoo GC=F, nicht auf MT5-XAUUSD. **Mit Broker-Daten wiederholen.**

---

## Anhang: Testlauf

- Skript: `testlauf/probe.py` (Python 3, `requests`; Aufruf `python probe.py urls.txt out.json`, unter Windows `PYTHONIOENCODING=utf-8` setzen)
- URL-Listen und Rohergebnisse: `testlauf/urls*.txt`, `testlauf/probe*.txt|json`, `testlauf/details.txt`
- Testzeitpunkt: 23.09.2026, ca. 09:35–10:30 MESZ, von einem Windows-Rechner mit deutscher IP (Ergebnisse können sich mit IP, Frequenz und Zeitpunkt ändern)

