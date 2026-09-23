Evaluierung von Marktdatenquellen und Systemarchitekturen für ein automatisiertes Gold-Volatilitätsprognose-System (MqlGoldscanner)

Der vorliegende Forschungsbericht liefert eine erschöpfende Analyse von Marktdatenquellen, Web-APIs und methodischen Ansätzen zur Konstruktion eines LLM-gestützten Multi-Agenten-Systems in Java 21. Ziel dieses "MqlGoldscanner"-Systems ist die präzise Prognose von Volatilitätsereignissen im Goldmarkt (XAUUSD), spezifisch definiert als Handelstage, an denen die True Range das 1,0-fache der durchschnittlichen True Range (ATR) des jeweiligen Wochentags der vorangegangenen 13 Wochen überschreitet.



Um dieses Ziel unter den strengen Vorgaben eines minimalen Budgets (Fokus auf Freemium, Open Data und maschinenlesbare Formate wie JSON und RSS) zu erreichen, erfordert das System eine hochgradig resiliente Datenpipeline. Die Architektur kombiniert unstrukturierte Textdaten (News, Chartanalysen) mit harten quantitativen Metriken (Wirtschaftskalender, Positionierungsdaten, Optionsvolatilitäten), die anschließend durch spezialisierte LLM-Agenten fusioniert und kalibriert werden. Die nachfolgenden Abschnitte dekonstruieren die verfügbare Datenlandschaft, bewerten Zugangshürden und präsentieren fortgeschrittene statistische Methoden zur Kalibrierung der Wahrscheinlichkeitsprognosen.



Block 1: Wirtschaftskalender und Makroökonomische Termine

Die Erfassung makroökonomischer Ereignisse bildet das Fundament für die Antizipation von Liquiditätsschocks. Gold reagiert als nicht-verzinsliches, in US-Dollar denominiertes Asset extrem sensibel auf Überraschungen bei Inflationsdaten (CPI, PCE), Arbeitsmarktdaten (NFP, Initial Jobless Claims) und geldpolitischen Entscheidungen (FOMC, EZB). Die zentrale technologische Herausforderung besteht darin, diese Daten verlässlich, maschinenlesbar und mit sauberen Historien (Actual vs. Forecast) abzurufen, ohne in Bot-Fallen der Anbieter zu geraten.



Die Untersuchung der von Ihnen vorgeschlagenen Startliste liefert klare Ergebnisse hinsichtlich der Nutzbarkeit für automatisierte Java-Pipelines. Der oft genutzte Kalender von ForexFactory (Fair Economy) hat seine Zugriffsrichtlinien drastisch verschärft. Seit August 2024 limitiert die Plattform den Download von wöchentlichen Kalenderdateien (unabhängig ob JSON, XML, ICS oder CSV) auf maximal zwei Anfragen pro fünf Minuten. Ein Überschreiten dieses Limits führt nicht zu einer Standard-API-Fehlermeldung, sondern liefert eine HTML-Seite mit dem Inhalt "Request Denied" zurück, was unvorbereitete JSON-Parser in Java sofort zum Absturz bringen kann. Eine Zwischenspeicherung (Caching) in der lokalen SQLite-Datenbank ist daher zwingend erforderlich; der Kalender-Agent darf diese Quelle keinesfalls bei jedem Schleifendurchlauf abfragen.   



Der Kalender von Myfxbook bietet eine robustere Alternative über eine offizielle JSON-API. Um den Endpunkt get-daily-events zu nutzen, muss das System zunächst einen Login-Request durchführen, um ein Session-Token zu erhalten. Diese Sessions sind strikt an die anfragende IP-Adresse gebunden und haben eine Laufzeit (Time-to-Live) von einem Monat. Im kostenlosen Modus ist die API auf 100 Anfragen pro 24 Stunden limitiert, was für ein Desktop-Tool, das Volatilitätsmatrizen für die laufende Woche berechnet, absolut ausreichend ist.   



Zusätzlich zu den klassischen Forex-Kalendern müssen hochrelevante Spezialkalender in die Pipeline integriert werden. Die US-Treasury-Auktionen (insbesondere 10- und 30-jährige Staatsanleihen) generieren häufig signifikante Ausschläge in den Renditen, die sich invers auf den Goldpreis auswirken. Das US-Finanzministerium stellt hierfür die "FiscalData API" zur Verfügung, einen hervorragenden, quelloffenen Endpunkt (upcoming\_auctions), der ohne API-Key genutzt werden kann und detaillierte JSON-Strukturen zu bevorstehenden Auktionen liefert. Ebenso relevant sind die Verfallstermine von COMEX-Goldoptionen, da das sogenannte "Options Pinning" an großen Strike-Preisen am Verfallstag erhebliche Preisbewegungen erzwingt. Diese Termine lassen sich über die CME Group abrufen, erfordern jedoch sauberes HTML-Parsing, da direkte öffentliche JSON-Feeds hierfür oft hinter Enterprise-Paywalls liegen.   



Quellenkatalog: Wirtschaftskalender

Name	exakte URL	Zugangsweg (offizielle API / inoffizieller JSON-Endpunkt / RSS / HTML)	Formatbeispiel (1 Zeile)	Kosten	Update-Frequenz	Rate-Limit/Bot-Schutz	Gold-Relevanz (1–5)	Anmerkung

ForexFactory JSON	https://nfs.faireconomy.media/ff\_calendar\_thisweek.json	inoffizieller JSON-Endpunkt	{"title":"Core CPI m/m","country":"USD","date":"2026-09-11","time":"08:30am","impact":"High","forecast":"0.2%","previous":"0.2%"}	Kostenlos	Wöchentlich / Bei Release	Max. 2 Abrufe pro 5 Min.	5	

PREFERRED. Strenges Rate-Limit seit 2024. Bei Verstoß Rückgabe von HTML "Request Denied" statt JSON.



Myfxbook API	https://www.myfxbook.com/api	offizielle API (JSON)	{"id":"1234","name":"NFP","currency":"USD","impact":"High","actual":"150K","forecast":"160K"}	Kostenlos (Account)	Täglich	

100 Req/24h (Free), IP-gebunden



5	

PREFERRED. Erfordert Login-Request. Sehr strukturierte Daten, ideal für SQL-Mapping.



FXMacroData API	https://api.fxmacrodata.com/v1/calendar/usd	offizielle API (JSON)	{"announcement\_datetime\_utc":"2026-09-11T12:30:00Z","indicator":"CPI","consensus":"0.2"}	Freemium	Täglich	Key für volle Historie nötig	5	

PREFERRED. Liefert exakte UTC-Timestamps und Konsensschätzungen, extrem entwicklerfreundlich.



US Treasury Auctions	https://api.fiscaldata.treasury.gov/services/api/fiscal\_service/v1/accounting/od/upcoming\_auctions	offizielle API (JSON)	{"record\_date":"2026-09-18","security\_type":"Bill","security\_term":"4-Week","auction\_date":"2026-09-24"}	Kostenlos	Nach Bedarf	Sehr moderat (Open Data)	4	

PREFERRED. Auktionsdaten für US-Treasuries. Essenziell für Zinsmarkt-Volatilität, die Gold treibt.



Finnhub Econ Calendar	https://finnhub.io/api/v1/economic-calendar	offizielle API (JSON)	{"actual":150,"country":"US","estimate":160,"event":"Nonfarm Payrolls","impact":"high"}	Freemium	Täglich	

30 Calls/Sekunde (Free Tier)



4	

PREFERRED. Solide Ausweichmöglichkeit. Sehr hohe Rate-Limits im kostenlosen Bereich.



CME Gold Options Expiry	https://www.cmegroup.com/markets/metals/precious/gold.calendar.options.html	HTML (JSoup)	<td class="table-cell">24 Sep 2026</td>	Kostenlos	Monatlich	Hoch (Cloudflare/Akamai)	4	

Enthält Expiry-Dates für Gold-Optionen (Kürzel: OG). Wichtig für Intraday-Reversals.



Investing.com Calendar	https://www.investing.com/economic-calendar/	HTML	<tr id="eventRowId\_12345" data-event-datetime="...">	Kostenlos	Live	Extrem aggressiv (Cloudflare)	4	

Dauerhaftes Scraping per Java-HttpClient führt fast unweigerlich zu IP-Sperren. Vermeiden.



DailyFX Calendar	https://www.dailyfx.com/economic-calendar	HTML / inoffizieller JSON-Endpunkt	Oft via XHR-Netzwerk-Requests findbar	Kostenlos	Täglich	Moderat	4	

Endpunkte ändern sich sporadisch, was den Parser fragil macht. Als Fallback geeignet.



&#x20; 

Block 2: Gold-News- und Analyse-Quellen

Der News-Recherche-Agent fungiert als qualitativer Sensor des Systems. Ein LLM ist nur so gut wie der Kontext, der ihm zugeführt wird. Um bullische oder bärische Treiber präzise zu destillieren, benötigt der Agent unstrukturierte, aber hochrelevante Textdaten. Hier erweisen sich RSS-Feeds als das Format der Wahl, da sie ressourcenschonend aggregiert werden können, eine saubere XML-Struktur aufweisen und von den meisten Publishern explizit für den maschinellen Abruf bereitgestellt werden, was ToS-Konflikte minimiert.



Die Überprüfung Ihrer initialen Startliste offenbart ein gemischtes Bild für die automatisierte Verarbeitung. Kitco ist die unbestrittene Referenz im Bereich Edelmetalle und bietet hervorragende, stabile RSS-Feeds an, die stündlich aktualisiert werden (z.B. für Mining-News unter https://www.kitco.com/news/category/mining/rss). FXStreet stellt ebenfalls saubere RSS-Feeds für Marktanalysen zur Verfügung, die durch hohe Gold-Spezifität glänzen.   



Quellen wie Reuters, Bloomberg und MarketWatch sind hingegen für ein budgetlimitiertes System hochproblematisch. Diese Anbieter operieren mit harten Paywalls und aggressiver Bot-Erkennung (insbesondere Datadome oder Cloudflare), die den automatisierten Abruf ohne extrem teure Enterprise-APIs blockieren. CNBC und Invezz bieten zwar offene Artikel, limitieren RSS-Feeds jedoch oft auf kurze Text-Snippets, was dem LLM zu wenig Kontext für eine tiefgreifende Kausalanalyse liefert. Das World Gold Council (gold.org) liefert exzellente Fundamentaldaten, agiert aber auf einer sehr geringen Frequenz (Quartalsberichte, monatliche ETF-Flows), wodurch es für tagesaktuelle Volatilitätsprognosen zu träge ist.



Um das Spektrum zu erweitern, wurden 15 neue, hochkarätige Quellen identifiziert, die den News-Agenten mit tieferer Expertise versorgen. Der "TF Metals Report" bietet tiefgreifende Makroanalysen speziell für Gold und Silber. "Marc to Market", geführt von Veteran Marc Chandler, liefert institutionelle Perspektiven auf den US-Dollar (DXY) und globale Kapitalströme, was für die Kontextualisierung von Goldbewegungen unerlässlich ist. Der "BullionStar Blog" liefert wöchentliche Detailanalysen zu physischen Goldströmen und Zentralbankkäufen, Themen, die von Mainstream-Finanzmedien oft übersehen werden. Für den deutschsprachigen Raum bietet "Gold.de" exzellente Analysen zu physischer Nachfrage und lokalen Aufgeldern. Eine besonders wertvolle Ergänzung ist der wöchentliche Marktbericht von Heraeus Precious Metals, der tiefe industrielle Einblicke gewährt, jedoch als PDF oder HTML-Text extrahiert werden muss.   



Quellenkatalog: Gold-News- und Analyse-Quellen

Name	exakte URL	Zugangsweg (offizielle API / inoffizieller JSON-Endpunkt / RSS / HTML)	Formatbeispiel (1 Zeile)	Kosten	Update-Frequenz	Rate-Limit/Bot-Schutz	Gold-Relevanz (1–5)	Anmerkung

TF Metals Report	https://www.tfmetalsreport.com/rss.xml	RSS	<title>TF Metals Report...</title>	Kostenlos	1-2x Täglich	Gering	5	

PREFERRED. Tiefe Makro- und Edelmetallanalysen. Exzellent für das LLM-Sentiment.



Marc to Market	https://feeds.feedburner.com/MarcToMarket	RSS	<item><title>Dollar Consolidates...</title></item>	Kostenlos	Täglich	Gering	4	

PREFERRED. Institutioneller Blick auf Währungen (DXY). Starker Korrelationsbezug zu Gold.



BullionStar Blog	https://www.bullionstar.com/rss	RSS	<title>Central Bank Gold Buying...</title>	Kostenlos	Wöchentlich	Gering	5	

PREFERRED. Analysen zu physischen Goldströmen und Zentralbanken.



InvestMacro	https://investmacro.com/feed	RSS	<title>Gold Technical Analysis...</title>	Kostenlos	Täglich	Gering	4	

PREFERRED. Fokus auf technische Analyse und Makroökonomie.



Blanchard Gold News	https://feeds.feedburner.com/BlanchardGold	RSS	<description>Market updates...</description>	Kostenlos	Wöchentlich	Gering	4	

PREFERRED. Fundamentale Marktanalyse eines großen Bullion-Dealers.



Heraeus Precious Metals	https://www.heraeus-precious-metals.com/en/precious-metal-trading/	HTML / PDF	Text-Extraction aus wöchentlichem Report	Kostenlos	Wöchentlich	Moderat	5	

Industrielle und institutionelle Analysen. Benötigt PDF-Parsing (z.B. Apache PDFBox).



FinancialJuice API	https://www.financialjuice.com	inoffizieller JSON-Endpunkt	{"headline":"Gold spikes on Fed...","impact":"high"}	Freemium	Echtzeit	

API-Key nötig für Strukturdaten



4	

PREFERRED. Liefert Live-Schlagzeilen und Imbalances am Markt.



ForexLive	https://www.forexlive.com/feed	RSS	<item><category>Gold</category>...	Kostenlos	Sehr Hoch	Gering	5	PREFERRED. Sehr schnell bei Makro-Gerüchten und Orderflow-Informationen.

Action Forex	https://www.actionforex.com/feed/	RSS	<title>XAU/USD Mid-Day Outlook</title>	Kostenlos	Mehrmals täglich	Gering	4	PREFERRED. Regelmäßige technische Updates, gut für Chart-Community-Agent.

Gold.de News (DE)	https://www.gold.de/rss/news.xml	RSS	<title>Goldpreis Analyse...</title>	Kostenlos	Täglich	Gering	4	PREFERRED. Beste deutsche Quelle für physische Nachfragetrends.

Miningscout (DE)	https://www.miningscout.de/feed/	RSS	<category>Gold</category>	Kostenlos	2-3x Wöchentlich	Gering	3	PREFERRED. Indirekte Gold-Relevanz durch Fokus auf Minenwerte.

ZeroHedge	https://www.zerohedge.com/rss.xml	RSS / HTML	<title>Fed Pivots, Gold Soars</title>	Kostenlos	Stündlich	Hoch (Cloudflare)	3	Aggressive Bot-Abwehr oft selbst beim RSS-Feed. Sehr contrarian, spiegelt extremes Sentiment wider.

Econoday	https://www.econoday.com	HTML (JSoup)	<div class="article-content">...</div>	Kostenlos	Täglich	Moderat	4	Liefert gute Erklärungen zu Wirtschaftskalender-Events und deren Metalle-Impact.

Goldco News	https://goldco.com/feed	RSS	<description>Precious metals IRA...</description>	Kostenlos	Wöchentlich	Gering	3	

PREFERRED. Fokus auf langfristiges Investment/Retirement, gutes Makro-Sentiment.



FinanzNachrichten	https://www.finanznachrichten.de/rss/	RSS	<title>Gold, silver ease as stocks rally</title>	Kostenlos	Hoch	Moderat	4	

PREFERRED. Aggregiert oft englische Quellen wie Kitco lokalisiert.



&#x20; 

Block 3: Chartanalyse und Community-Konsens

Der "Chart-Community-Agent" ist essenziell, um die Schwarmintelligenz technischer Händler abzubilden. Ausbrüche in der Volatilität ereignen sich häufig genau dann, wenn breite Konsens-Levels (z.B. eine vielbeachtete gleitende Durchschnittslinie oder psychologische runde Marken wie 2.500 USD) gebrochen werden. Das LLM liest Fremdanalysen und destilliert daraus Cluster von Support- und Resistance-Marken.



Die Validierung Ihrer Startliste bestätigt die Eignung vieler Quellen, deckt jedoch auch technische Hürden auf. TradingView Ideas (https://www.tradingview.com/symbols/XAUUSD/ideas/) ist eine Goldmine für technisches Sentiment. Die Seite ist statisch auslesbar, und per Jsoup können die spezifischen HTML-Tags der Ideen-Kacheln (inklusive Meta-Tags für "Long" oder "Short" Bias) sehr einfach extrahiert werden. Eine Anmeldung ist für den reinen Lesezugriff der öffentlichen Ideen nicht erforderlich. FXStreet und DailyFX bieten ebenfalls frei zugängliche textbasierte technische Forecasts, die ein LLM problemlos auf Preiszonen parsen kann. Investing.com hingegen ist durch restriktive WAF-Systeme (Web Application Firewalls) geschützt; automatisierte Abrufe der "Technical Analysis" Sektion enden meist in CAPTCHA-Loops.



Um die Diversität des Sentiments zu erhöhen, muss der Agent auch unkonventionelle Quellen abgreifen. Ein direkter Abruf des XAUUSD-Streams der StockTwits API bietet ungefiltertes Retail-Sentiment und kann zur Konstruktion eines Fear/Greed-Index herangezogen werden. Auch Reddit (spezifisch Subreddits wie r/Forex oder r/Gold) bietet einen JSON-Endpunkt, wenn man .json an die Such-URL anhängt (z.B. https://www.reddit.com/r/Forex/search.json?q=XAUUSD\&sort=new). Reddit blockiert jedoch generische Anfragen; der Java HttpClient muss zwingend einen eindeutigen, deskriptiven User-Agent Header senden. Die MQL5-Blogs bieten zudem stark algorithmisch und quantitativ geprägte Marktanalysen über leicht abrufbare RSS-Feeds. Eine weitere hochkarätige Quelle ist der Community-Outlook von Myfxbook, der über die offizielle API das Verhältnis von Long- zu Short-Positionen der Retail-Trader ausgibt und somit als exzellenter Kontra-Indikator fungiert.   



Quellenkatalog: Chartanalyse- und Community-Quellen

Name	exakte URL	Zugangsweg (offizielle API / inoffizieller JSON-Endpunkt / RSS / HTML)	Formatbeispiel (1 Zeile)	Kosten	Update-Frequenz	Rate-Limit/Bot-Schutz	Gold-Relevanz (1–5)	Anmerkung

StockTwits API	https://api.stocktwits.com/api/2/streams/symbol/XAUUSD.json	offizielle API (JSON)	{"message":{"body":"Gold breaking out...","entities":...}}	Kostenlos	Live	200 Req/Stunde (ohne Auth)	4	PREFERRED. Perfekt für Retail-Sentiment (Bullish/Bearish) am aktuellen Rand.

Myfxbook Outlook	https://www.myfxbook.com/api (Endpunkt get-community-outlook)	offizielle API (JSON)	{"symbol":"XAUUSD","shortVolume":45,"longVolume":55}	Kostenlos	Echtzeit	

100/24h (Free Tier)



5	

PREFERRED. Exzellentes Retail-Positionierungs-Sentiment für Contrarian-Modelle.



Reddit (r/Forex)	https://www.reddit.com/r/Forex/search.json?q=XAUUSD\&sort=new	inoffizieller JSON-Endpunkt	{"data":{"children":\[{"data":{"title":"Gold levels..."}}]}}	Kostenlos	Intraday	

Streng, User-Agent zwingend



3	PREFERRED. Liefert Diskussionen zu Leveln. Deskriptiver User-Agent verhindert sofortigen IP-Bann.

MQL5 Blogs	https://www.mql5.com/en/blogs/rss	RSS	<title>XAUUSD Technical Outlook...</title>	Kostenlos	Täglich	Gering	3	

PREFERRED. Stark quantitativ geprägte Analysen von algorithmischen Tradern.



TradingView Ideas	https://www.tradingview.com/symbols/XAUUSD/ideas/	HTML (JSoup)	<div class="tv-widget-idea\_\_description-text">...</div>	Kostenlos	Live	Moderat	5	Extrahierbar ohne Login. Optimales Futter für das LLM zur Levelfindung.

Barchart Technicals	https://www.barchart.com/forex/quotes/%5EXAUUSD/technical-analysis	HTML (JSoup)	<div class="block-content">100% Buy</div>	Kostenlos	Täglich	Hoch (Cloudflare)	4	Aggregierte Kauf/Verkauf-Signale basierend auf klassischen Indikatoren.

&#x20; 

Block 4: Sentiment-, Positionierungs- und Marktdaten (Quantitativer Kontext)

Dieser Block ist das Herzstück für jedes Vorhersagemodell, das über einfache News-Analyse hinausgeht. Wahrscheinlichkeiten für Ausbrüche lassen sich signifikant besser kalibrieren, wenn fundamentale Spannungen im Markt durch harte quantitative Daten abgebildet werden.



Die Commitment of Traders (COT) Daten der CFTC sind unerlässlich, um das Extrem-Sentiment der Commercials (Hedger) und Large Speculators (Funds) zu messen. Die "Disaggregated"-Berichte stehen wöchentlich freitags kostenlos als CSV/TXT-Archive auf der CFTC-Website bereit; der relevante Identifikationscode für COMEX Gold lautet 088691. Extreme Positionierungen der Spekulanten kündigen oft mittelfristige Reversals und damit einhergehende Volatilitätsschocks an.   



Physische Zu- und Abflüsse lassen sich optimal über den größten Gold-ETF, den SPDR Gold Shares (GLD), verfolgen. Die offizielle Website (spdrgoldshares.com) bietet tägliche CSV-Downloads der gehaltenen Tonnen an Gold, was einen direkten Rückschluss auf die institutionelle Investmentnachfrage erlaubt.   



Die mit Abstand wichtigste Quelle für das Volatilitätsregime ist der Cboe Gold ETF Volatility Index (GVZ). Analog zum VIX für den S\&P 500 misst der GVZ die vom Optionsmarkt erwartete 30-Tage-Volatilität (implizite Volatilität) für den GLD ETF. Da Optionshändler echtes Geld riskieren, sind diese Erwartungen historisch betrachtet weitaus präzisere Prognostiker künftiger Volatilität als rein rückwärtsgewandte statistische Modelle. Die historischen und tagesaktuellen Schlusskurse der Serie GVZCLS lassen sich komfortabel und kostenlos über die offizielle FRED-API der St. Louis Fed abrufen.   



Das makroökonomische Umfeld wird über zwei weitere Serien der FRED-API kontrolliert: Der 10-Year Treasury Inflation-Indexed Security (TIPS) Yield bildet den realen Zinssatz ab, der als primärer Opportunitätskostenfaktor negativ mit Gold korreliert ist. Der nominale US-Dollar wird über den Trade Weighted U.S. Dollar Index (DXY) gemessen. Die Zinspfaderwartung des Marktes (CME FedWatch Tool) ist zwar nicht über eine offizielle API verfügbar, lässt sich aber über XHR-Endpunkte der CME-Website als JSON extrahieren.



Quellenkatalog: Quantitative Marktdaten

Name (Metrik)	exakte URL	Zugangsweg (offizielle API / inoffizieller JSON-Endpunkt / RSS / HTML)	Formatbeispiel (1 Zeile)	Kosten	Update-Frequenz	Rate-Limit/Bot-Schutz	Gold-Relevanz (1–5)	Anmerkung

CFTC COT Report	https://www.cftc.gov/files/dea/history/fut\_disagg\_txt\_2026.zip	Offizieller CSV-Download	088691, GOLD - COMMODITY EXCHANGE INC., 2026-09-15, ...	Kostenlos	Wöchentlich (Fr)	Gering	5	

PREFERRED. COMEX Gold-Code: 088691. Fundamentale Marktpositionierung.



SPDR GLD Inventory	https://www.spdrgoldshares.com/usa/gld/	Offizieller CSV-Export	Historische Bestandslisten als .csv	Kostenlos	Täglich	Gering	5	

PREFERRED. Liefert physische Tonnage-Zahlen institutioneller Investoren.



Cboe Gold Vol (GVZ)	https://api.stlouisfed.org/fred/series/observations?series\_id=GVZCLS...	offizielle API (JSON)	{"date":"2026-09-18","value":"23.31"}	Kostenlos (Key nötig)	Täglich	

120 Req/Min



5	

PREFERRED. Basis für Expected-Move-Kalkulation (Optionsmarkt).



US 10Y TIPS (Realzins)	https://api.stlouisfed.org/fred/series/observations?series\_id=DFII10...	offizielle API (JSON)	{"date":"2026-09-18","value":"1.85"}	Kostenlos (Key nötig)	Täglich	120 Req/Min	5	PREFERRED. Wichtigster Makro-Treiber für den Goldpreis.

US Dollar Index (DXY)	https://api.stlouisfed.org/fred/series/observations?series\_id=DTWEXBGS...	offizielle API (JSON)	{"date":"2026-09-18","value":"104.50"}	Kostenlos (Key nötig)	Täglich	120 Req/Min	5	PREFERRED. Zeigt USD-Stärke, inverse Korrelation zu XAUUSD.

CME FedWatch Tool	https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/30DayFederalFunds/...	inoffizieller JSON-Endpunkt	{"targetRate":"5.00-5.25","probability":0.85}	Kostenlos	Live	Moderat	5	Wahrscheinlichkeit für Zinsänderungen. Essenziell vor FOMC-Meetings.

Google Trends	https://trends.google.com/trends/api/explore?q=gold+price	inoffizieller JSON-Endpunkt	{"time":"1694217600","value":\[45]}	Kostenlos	Täglich / Live	Sehr hoch	3	Nur über spezielle Java-Libraries (Simulation von Handshakes) dauerhaft nutzbar.

Saisonalität Gold	https://www.seasonalcharts.com/classics\_gold.html	HTML (JSoup)	Bilder oder tabellarische Werte	Kostenlos	Jährlich	Gering	3	Liefert Wochentags/Monats-Muster. Als statische SQLite-Tabelle effizienter abbildbar.

&#x20; 

Block 5: Web-Such-APIs für den URL-Scout-Agent

Der URL-Scout-Agent hat die Aufgabe, dynamisch nach neu entstehenden Informationsquellen, hochrelevanten Blog-Artikeln oder aktuellen Analysen zu suchen, die den Startlisten entgangen sind. Im Jahr 2026 ist das direkte massenhafte Scrapen von Google- oder Bing-Ergebnisseiten (SERPs) durch Captchas und IP-Banns extrem ineffizient und fehleranfällig geworden. Eine dedizierte Such-API ist daher unverzichtbar.



Die Landschaft der Such-APIs teilt sich in drei Kategorien: Traditionelle Legacy-Anbieter, datenschutzfokussierte Nischen-Indizes und KI-zentrierte Aggregatoren. Die Preise für die offizielle Bing Web Search API sind drastisch gestiegen, was sie für unbudgetierte Projekte unattraktiv macht (oft ab $15 pro 1.000 Abfragen). Gleiches gilt für die Google Custom Search API, die zudem starken Restriktionen unterliegt.   



Die Tavily Search API stellt momentan die Speerspitze für KI-Agenten dar. Sie wurde explizit entwickelt, um LLMs mit bereinigtem Web-Content zu versorgen. Ein einziger API-Aufruf bündelt bis zu 20 Webseiten und liefert nicht nur Links, sondern direkt maschinenlesbaren, relevanten Text zurück. Dies entlastet das Java-Tool enorm, da der Jsoup-Overhead entfällt. Der kostenlose "Development Tier" gewährt 1.000 Suchanfragen pro Monat, was für einen wöchentlich laufenden URL-Scout-Agenten mehr als ausreichend ist.   



Als Alternative im datenschutzfreundlichen Spektrum bietet sich Mojeek an. Mojeek ist ein unabhängiger Suchindex aus Großbritannien (ca. 9 Mrd. Seiten), der explizit KI-Anwendungen und LLM-Nutzung erlaubt, ohne in restriktive Nutzungsbedingungen bezüglich der Kombination von Daten zu verfallen. Die Ergebnisse können jedoch qualitativ in Nischen-Finanzthemen leicht hinter den Branchenriesen zurückbleiben. Brave Search API positioniert sich als Freemium-Option mit einem starken, eigenen Index und hoher Relevanz für Finanzabfragen (ca. 2.000 Suchen kostenlos im Monat).   



Populäre Open-Source Python/Java-Bibliotheken für DuckDuckGo sind hingegen keine Empfehlung für Produktionssysteme. Da DuckDuckGo automatisierten Traffic aggressiv drosselt, laufen diese Bibliotheken reihenweise in 202 Ratelimit Exceptions und blockieren die Agenten-Pipelines.   



Quellenkatalog: Web-Such-APIs

Name	exakte URL	Zugangsweg	Formatbeispiel (1 Zeile)	Kosten	Update-Frequenz	Rate-Limit/Bot-Schutz	Gold-Relevanz (1–5)	Anmerkung

Tavily Search API	https://api.tavily.com/search	offizielle API (JSON)	{"query":"gold forecast","results":\[{"title":"...","url":"...","content":"..."}]}	Freemium	Live	

100/min (Dev), 1.000/Monat (Free)



5	

Die Top-Empfehlung für LLMs. Liefert direkt bereinigten Content, spart JSoup-Parsing.



Serper.dev	https://google.serper.dev/search	offizielle API (JSON)	{"organic":\[{"title":"Gold Price Prediction","link":"..."}]}	Freemium	Live	300 Req/Sekunde. 2.500 Free Credits	5	

Liefert saubere Google-SERPs. Extrem kosteneffizient (\~$0.30 pro 1k Suchen).



Brave Search API	https://api.search.brave.com/res/v1/web/search	offizielle API (JSON)	{"web":{"results":\[{"title":"...","url":"..."}]}}	Freemium	Live	

2.000 Free/Monat



4	Hervorragender unabhängiger Index, sehr gute Datenqualität für Finanzthemen.

Mojeek Search	https://www.mojeek.com/services/search/web-search-api/	offizielle API (JSON/XML)	<results><result><title>...</title></result></results>	Freemium	Live	Variabel (Custom Plans)	3	

UK-Index. KI/LLM-Nutzung explizit ohne Copyright-Restriktionen erlaubt.



DuckDuckGo Libs	Python/Java Wrapper Libraries	inoffizieller JSON-Endpunkt / HTML	N/A	Kostenlos	Live	Extrem restriktiv (202 Ratelimit)	1	

Nicht empfohlen. Ständige Abstürze durch Bot-Abwehr.



SearXNG	Lokale Docker-Instanz	offizielle API (JSON) via Self-Host	{"results":\[{"url":"...","title":"..."}]}	Kostenlos (Self-Hosted)	Live	Hardware/Network abhängig	4	

Empfehlung als Fallback. Bündelt Suchen ohne API-Keys, erfordert aber Wartung (IP-Sperren).



&#x20; 

Top-15-Kurzliste: Die wertvollsten NEUEN Quellen für den MqlGoldscanner

Unter der Prämisse einer Java-Client-Architektur (ohne Headless-Browser) und bewertet nach der Matrix "Nutzen für Volatilitätsprognose vs. Integrationsaufwand", stellen diese 15 Quellen den größten Mehrwert für Ihr System dar:



Cboe GVZ Index via FRED API (JSON): Der absolute Gamechanger für Volatilitätsprognosen. Liefert direkt die Options-implizite Volatilität, womit sich die Expected Daily Move berechnen lässt. Minimaler Programmieraufwand (offizielle API).   



FXMacroData API (JSON): Löst das ForexFactory-Rate-Limit-Problem. Liefert exakte UTC-Kalenderdaten und entscheidende Konsens-Werte für USD-Events ohne Paywall-Hürden.   



Tavily Search API (JSON): Ersetzt fehleranfälliges Google-Scraping. Liefert dem LLM-Scout direkt den bereinigten Text von Ziel-URLs mit (spart hunderte Zeilen Jsoup-Code).   



US 10-Year TIPS Yield via FRED API (JSON): Fundamental-Kontext. Der Realzins korreliert massiv mit Goldausbrüchen. Offizielle API, stabil, kein Scraping.



Myfxbook Community Outlook API (JSON): Liefert präzises Retail-Sentiment (Short/Long-Ratios) zur Bildung von Kontra-Indikatoren, bevor Volatilität ausbricht.   



US Treasury Upcoming Auctions API (JSON): Staatliche Open-Data-Schnittstelle. Treasury-Auktionen sind unterschätzte Treiber für Zins- und Gold-Vola.   



TF Metals Report (RSS): Einer der besten Nischen-Blogs für Makro- und Edelmetallanalysen. Über RSS extrem leicht vom News-Agenten abzugreifen.   



CFTC Disaggregated COT Report (CSV): Historisch bewährte Fundamentaldaten zur Positionierung von Hedgern vs. Spekulanten. Wöchentlicher CSV-Download ist leicht in SQLite zu importieren.   



SPDR Gold Shares (GLD) Inventory (CSV): Die physischen Tonnage-Daten zeigen die harte, institutionelle Investmentnachfrage. Leicht als CSV abzurufen.   



Marc to Market (RSS): Institutioneller Blick auf den DXY und Kapitalströme. Liefert den makroökonomischen Kontext, den reine Chartanalysten oft übersehen.   



US Dollar Index (DXY) via FRED API (JSON): Die Stärke der Weltleitwährung diktiert oft die Gold-Trends. Unkompliziert über FRED abrufbar.



BullionStar Blog (RSS): Deckt blinde Flecken der Mainstream-Medien ab (Zentralbankkäufe im Osten, physischer Abfluss). Ideal für langfristigen Kontext.   



Reddit r/Forex / r/Gold (JSON Endpunkte): Durch Anhängen von .json an URLs erhält das LLM Zugang zur unzensierten Retail-Diskussion über Support/Resistance-Zonen. Erfordert nur einen sauberen User-Agent.   



Finnhub Economic Calendar (JSON): Hervorragende, redundante Quelle für Wirtschaftsdaten, falls andere APIs ausfallen. Hohes Freikontingent.   



Heraeus Precious Metals Weekly (PDF/HTML): Physischer Markteinblick aus der Industrie. Zwar ist PDF-Parsing (via Apache PDFBox) komplexer, der analytische Wert für fundamentale Ausbrüche ist jedoch enorm hoch.   



Block 6: Methoden, Modelle und Produkt-Ideen

Um aus der Masse an gesammelten Daten eine präzise Wahrscheinlichkeit für einen Volatilitätsausbruch (Tages-Range > 1,0x ATR) zu berechnen, muss das System deterministische Mathematik mit probabilistischen LLM-Ausgaben verschmelzen.



Methodik der Volatilitätsschätzung

GARCH(1,1)-Volatilitätsprognose: Das Modell "Generalized Autoregressive Conditional Heteroskedasticity" (GARCH) ist der akademische Goldstandard zur Modellierung von Finanzzeitreihen, da es das Phänomen der "Volatilitäts-Cluster" (hohe Schwankungen folgen auf hohe Schwankungen) abbildet. In Gold- und Devisenmärkten liefert GARCH(1,1) signifikante Kalibrierungsgewinne, indem es die Varianz des heutigen Tages aus der langfristigen Durchschnittsvarianz, dem Schock des Vortages (ARCH) und der Rest-Volatilität des Vortages (GARCH) berechnet. Die Umsetzung in Java erfordert eine Bibliothek für nicht-lineare Optimierung (Maximum-Likelihood-Schätzung), wie beispielsweise Apache Commons Math. Der Programmieraufwand ist hoch, jedoch durch bestehende Open-Source-Implementierungen abbildbar.   



Ereignisstudien (Event Studies): Diese Methode analysiert systematisch das abnormale Rendite- und Volatilitätsverhalten rund um vorab bekannte Zeitpunkte, wie NFP, CPI oder FOMC. Das Tool speichert historisch, wie weit der Goldpreis an den letzten 20 NFP-Freitagen im Vergleich zu "Normaltagen" ausgeschlagen ist. Der Java-Aufwand ist minimal (SQL-Aggregation GROUP BY event\_type), der Kalibrierungsbeitrag ist an Makro-Tagen jedoch massiv, da Algorithmen der Großbanken zu diesen Zeitpunkten vorhersehbar Liquidität abziehen oder hinzufügen.   



Options-IV-basierte erwartete Bewegung (Expected Move): Die implizite Volatilität (IV) aus dem Optionsmarkt (abgebildet über den GVZ-Index) stellt die reale Erwartungshaltung der Marktteilnehmer dar, für die sie Risikoprämien bezahlt haben. Die tägliche erwartete Bewegung in Prozent lässt sich simpel durch die Formel GVZ / sqrt(252) (bei 252 Handelstagen) approximieren. Kombiniert man dies mit dem aktuellen Goldpreis, erhält das LLM einen harten mathematischen Korridor in USD. Der Integrationsaufwand ist trivial, der Nutzen unübertroffen.   



Kalibrierung von Wahrscheinlichkeiten: Wenn der Analytiker-Agent behauptet, "es gibt heute eine 70% Wahrscheinlichkeit für einen Ausbruch", muss überprüft werden, ob in 7 von 10 identischen Prognosefällen tatsächlich ein Ausbruch stattfand. Der Brier Score misst diesen quadratischen Vorhersagefehler (0 ist perfekt, 1 ist völliges Versagen). Ein Reliability-Diagramm plottet grafisch die vom LLM ausgegebene Konfidenz gegen die tatsächlich beobachtete Frequenz. In der Praxis nutzt der Verifikations-Agent diese Metriken, um die System-Prompting-Gewichtung am Wochenende dynamisch anzupassen: Ist das LLM "overconfident" (Brier Score steigt), wird künftig dem GARCH-Modell mehr Gewicht eingeräumt.   



Ideenliste für neue Agenten und UI-Konzepte

Idee / Konzept	Funktion \& Nutzen	Datenbasis	Aufwand / Nutzen

Macro-Correlation-Agent	Vergleicht die rollierende 30-Tage-Korrelation zwischen Gold, 10Y-TIPS und DXY. Bricht die historische inverse Korrelation, signalisiert dies Stress im System (Regime Shift) und drohende Volatilität.	FRED API (DXY, TIPS) und MT5 Goldkurse.	Moderater Aufwand, Hoher Nutzen.

Options-Flow-Agent	

Identifiziert Streik-Preise mit massiven Open-Interest-Blöcken (z.B. große Puts bei 2.400). Erlaubt Prognosen zu Gamma-Squeezes und "Pinning" am Verfallstag.



CME Group Options Expiry.



Hoher Aufwand, Hoher Nutzen.

Asian-Session-Breakout-Agent	Analysiert die Handelsspanne der asiatischen Session (00:00 - 08:00 MEZ). Extrem enge Ranges ("Spring Coil") erhöhen statistisch die Chance für starke Ausbrüche in London/New York.	MT5 M15/H1 Intraday-Daten.	Geringer Aufwand, Moderater Nutzen.

Meteorologische Wochenmatrix (UI)	Darstellung der Volatilitätswahrscheinlichkeiten (Mo-Fr) adaptiert von Niederschlagsradaren. Hitze-Farbskalen (Rot = >80% Bewegung). Tornado-Symbole für NFP/FOMC-Tage.	Intern (JavaFX).	Moderater Aufwand, Hoher Nutzen (UX).

Gauge-Overlay-Diagramm (UI)	Kombiniert die harte Mathematik (Nadel zeigt erwartete Range via Options-IV) mit dem LLM-Sentiment (Hintergrundfarbe signalisiert bullischen/bärischen News-Konsens).	Intern (JavaFX).	Geringer Aufwand, Hoher Nutzen (UX).

&#x20; 

Wettbewerbsanalyse: Traditionelle Gold-Forecast-Seiten (wie DailyFX oder FXStreet Outlooks) publizieren meist diskretionäre, textbasierte Wochenausblicke. Was diesen Angeboten fast immer fehlt, ist eine harte Quantifizierung der Wahrscheinlichkeit sowie eine strikte, nachvollziehbare Kalibrierung (Brier Score) ihrer Prognosen. Ihr Ansatz eines Multi-Agenten-Systems, das maschinelles Lernen (LLMs) für Narrative mit stochastischen Modellen (GARCH) kreuzt und sich über eine Feedback-Loop selbst kalibriert, übertrifft den Standard im Retail-Sektor signifikant.



Risiken, Nutzungsbedingungen (ToS) und Abruf-Strategien

Die dauerhafte Stabilität des "MqlGoldscanner" hängt davon ab, nicht in automatisierte IP-Sperren oder rechtliche Grauzonen zu geraten.



Die massenhafte, ungebremste Abfrage (Echtzeit-Scraping im Sekundentakt) ist von fast allen Anbietern (ForexFactory, Investing.com) in den Nutzungsbedingungen strikt untersagt, um Serverüberlastungen und den Weiterverkauf von Daten zu unterbinden. Das ForexFactory-Limit von zwei Downloads pro fünf Minuten ist ein klares Indiz für diese Praxis.

Myfxbook bindet die API-Nutzung an Richtlinien für kostenlose Software (Free Software Guidelines) und ein Tageslimit (100 Anfragen), an das man sich zwingend halten muss.   



Der Einsatz von reinem HTML-Scraping über Java-HttpClients auf Plattformen wie Investing.com führt fast immer in Cloudflare-CAPTCHA-Schleifen. Es ist weitaus nachhaltiger, stattdessen offene JSON-APIs (wie FXMacroData, Finnhub) oder etablierte Web-Search-APIs (Tavily) zu verwenden, die explizit für den maschinellen Konsum konzipiert sind.   



RSS-Feeds (Kitco, ActionForex, etc.) sind von Natur aus für Syndikation und maschinelles Einlesen vorgesehen. Eine Abfragefrequenz von einmal pro Stunde ist hierbei absolut höflich, schont die Serverressourcen des Anbieters und löst keine ToS-Verletzungen aus. Offizielle APIs staatlicher Einrichtungen (FRED, US Treasury) tolerieren großzügige Limits von bis zu 120 Anfragen pro Minute und sind prädestiniert für den vollautomatisierten Abruf.



Fazit zur Architektur: Um höchste Resilienz zu gewährleisten, muss die Java-Anwendung streng entkoppelt arbeiten. Die Datenbeschaffungs-Agenten laufen als isolierte Cronjobs, die im Hintergrund (z.B. RSS stündlich, Kalender 2x täglich, COT freitagsabends) Daten sammeln und in die lokale SQLite-Datenbank persistieren. Der Analytiker-Agent fragt das Internet zu keinem Zeitpunkt direkt ab. Er generiert die Wochenmatrix ausschließlich auf Basis der bereits gesammelten, lokalen Datenbankeinträge. Dieses asynchrone Design schützt das System vor temporären Netzwerkausfällen, umgeht Rate-Limits und respektiert die Infrastruktur der Datenlieferanten.





forexfactory.com

MQL4/5 programmers: This weekly news download code solves limit!

Wird in einem neuen Fenster geöffnet



myfxbook.com

API - Myfxbook.com

Wird in einem neuen Fenster geöffnet



api-community.fiscal.treasury.gov

Enterprise APIs:Treasury-Securities-Upcoming-Auctions-Data

Wird in einem neuen Fenster geöffnet



fiscaldata.treasury.gov

Treasury Securities Upcoming Auctions Data

Wird in einem neuen Fenster geöffnet



fiscaldata.treasury.gov

Treasury Securities Auctions Data

Wird in einem neuen Fenster geöffnet



cmegroup.com

Gold Futures Contract Specs - CME Group

Wird in einem neuen Fenster geöffnet



cmegroup.com

Gold Option Calendar - CME Group

Wird in einem neuen Fenster geöffnet



fxmacrodata.com

Economic Calendar API for Forex Traders - FXMacroData

Wird in einem neuen Fenster geöffnet



finnhub.io

Economic Calendar API - Finnhub

Wird in einem neuen Fenster geöffnet



parse.bot

Investing Economic Calendar API - Parse.bot

Wird in einem neuen Fenster geöffnet



github.com

GitHub - MatthiasEckhart/Forex-Calendar-API: API used for getting

Wird in einem neuen Fenster geöffnet



kitco.com

RSS News - KITCO

Wird in einem neuen Fenster geöffnet



kitco.com

RSS News - KITCO

Wird in einem neuen Fenster geöffnet



forexfactory.com

recommendations rss news feeds | Forex Factory

Wird in einem neuen Fenster geöffnet



rss.feedspot.com

Top 80 Gold RSS Feeds

Wird in einem neuen Fenster geöffnet



rss.feedspot.com

Best Forex RSS Feeds by Category (2026)

Wird in einem neuen Fenster geöffnet



heraeus-precious-metals.com

Precious Metal Trading

Wird in einem neuen Fenster geöffnet



heraeus-precious-metals.com

Wöchentlicher Marktbericht - Heraeus Precious Metals

Wird in einem neuen Fenster geöffnet



parse.bot

ForexFactory API – Calendar, Quotes \& News - Parse.bot

Wird in einem neuen Fenster geöffnet



finanznachrichten.de

Kitco | Nachrichten - Finanznachrichten

Wird in einem neuen Fenster geöffnet



reddit.com

RSS For High Impact Economic Events? : r/Forex - Reddit

Wird in einem neuen Fenster geöffnet



cotdata.net

Gold Futures (COMEX) — Commitments of Traders Report - COT Data

Wird in einem neuen Fenster geöffnet



metalcharts.org

Gold COT Report Today | Weekly CFTC Positioning Chart

Wird in einem neuen Fenster geöffnet



en.macromicro.me

SPDR Gold Trust ETF \[GLD] (Total Gold, Tonnes) | Series | MacroMicro

Wird in einem neuen Fenster geöffnet



spdrgoldshares.com

GLD, New York Stock Exchange) | Charts, data and downloads

Wird in einem neuen Fenster geöffnet



cboe.com

Cboe Global Indices: GVZ Index Dashboard

Wird in einem neuen Fenster geöffnet



princeton.edu

Structural GARCH: The Volatility- Leverage Connection

Wird in einem neuen Fenster geöffnet



fred.stlouisfed.org

CBOE Gold ETF Volatility Index (GVZCLS) | FRED | St. Louis Fed

Wird in einem neuen Fenster geöffnet



blog.mojeek.com

Reasons to Use the Mojeek Search API

Wird in einem neuen Fenster geöffnet



docs.tavily.com

About - Tavily Docs

Wird in einem neuen Fenster geöffnet



docs.tavily.com

Web Search Essentials - Tavily Docs

Wird in einem neuen Fenster geöffnet



medium.com

Cheapest Web Search APIs for Production Use (2026): Real Costs

Wird in einem neuen Fenster geöffnet



docs.tavily.com

Rate Limits - Tavily Docs

Wird in einem neuen Fenster geöffnet



european-alternatives.eu

Mojeek | European Alternatives

Wird in einem neuen Fenster geöffnet



mojeek.com

Mojeek Web Search API

Wird in einem neuen Fenster geöffnet



serp.fast

Mojeek Review: Pricing \& Alternatives - serp.fast

Wird in einem neuen Fenster geöffnet



purchasewithpurpose.io

Mojeek - Purchase with Purpose

Wird in einem neuen Fenster geöffnet



github.com

duckduckgo\_search.exceptions.RatelimitException: 202 Ratelimit

Wird in einem neuen Fenster geöffnet



tessl.io

pypi-duckduckgo-search@8.1.0 • tessl • Registry

Wird in einem neuen Fenster geöffnet



link.sc

DuckDuckGo Search API: The Official Option, the Unofficial Ones

Wird in einem neuen Fenster geöffnet



scispace.com

Modelling exchange rate volatility using GARCH models - SciSpace

Wird in einem neuen Fenster geöffnet



publikationen.bibliothek.kit.edu

Evaluation of Selected Models for Value at Risk Calculation - KIT

Wird in einem neuen Fenster geöffnet



github.com

VolatilityEstimatorV2/INTERVIEW\_GUIDE.md at main - GitHub

Wird in einem neuen Fenster geöffnet



escholarship.org

Three Essays in Macroeconomics - UC Irvine

Wird in einem neuen Fenster geöffnet



researchgate.net

Out-of-sample predictability of gold market volatility: The role of US

Wird in einem neuen Fenster geöffnet



arxiv.org

A New Benchmark for Evaluating Epistemic Calibration via Pr - arXiv

Wird in einem neuen Fenster geöffnet



sites.insead.edu

Fair Skill Brier Score: Evaluating Probabilistic Forecasts of One-Off

Wird in einem neuen Fenster geöffnet



github.com

drapala/drapala - GitHub

Wird in einem neuen Fenster geöffnet



preprints.org

Monotone Probability Recalibration for Turnover-Constrained ETF

Wird in einem neuen Fenster geöffnet



github.com

Java SDK for the FlashAlpha options analytics API — live ... - GitHub

