# -*- coding: utf-8 -*-
"""Hilfe-Texte für die i-Buttons (Port der KiScanner-Hilfe).
Jeder Eintrag: Schlüssel → (Titel, Erklärung als Markdown)."""
from __future__ import annotations

HELP: dict[str, tuple[str, str]] = {
    "wochenlauf": ("Wochenlauf — was passiert da?",
        "Der komplette Durchlauf: **Kurse** vom Broker holen → **Kalender** aus "
        "5 Quellen + Regeltermine → **Marktdaten** (GVZ, FRED, CFTC, GLD) → "
        "**Matrix** neu berechnen (Klimatologie + HAR-Modell + Richtung) → "
        "**News & Community** abrufen → **KI-Fusion** (erklärt und verschiebt "
        "im ±10-pp-Band) → **PDF-Bericht** und MT5-Export schreiben.\n\n"
        "Dauert typisch 3–8 Minuten (die KI-Aufrufe sind das Langsamste). "
        "Der Daemon macht das automatisch sonntags 18:00."),
    "matrix_neu": ("Matrix neu bauen — was ist das?",
        "Berechnet **nur die Statistik** neu (Klimatologie, HAR-Modell, "
        "Richtung) aus den **bereits gespeicherten** Kursen — ohne neue "
        "Abrufe, ohne KI, ohne PDF.\n\n"
        "**Wann sinnvoll?** Wenn sich z. B. der Schwellen-Parameter (k) oder "
        "das Fenster in den Einstellungen geändert hat, oder nach dem "
        "Import längerer Historie. Für aktuelle Daten lieber den vollen "
        "**Wochenlauf** starten.\n\n"
        "Die KI-Analyse (P_finale) der letzten Fusion bleibt dabei "
        "sichtbar, bis ein neuer Wochenlauf sie ersetzt."),
    "kpi_kennzahlen": ("Kennzahlen einordnen (Farbskala)",
        "Die Farbe zeigt die **Bewegungsintensität** — grün = ruhig, gelb = "
        "normal, rot = stark bewegt:\n\n"
        "- **ATR 14 / TR heute**: eingestuft gegen die eigenen Werte der "
        "letzten 12 Monate (Perzentil). Der Balken zeigt, wie viele Tage "
        "historisch RUHIGER waren.\n"
        "- **RSI 14**: Farbe nach Distanz zu 50 — je weiter von der Mitte, "
        "desto deutlicher die Kursbewegung.\n"
        "- **Kalender-Events**: hochrelevante Termine (★≥4) der laufenden "
        "Woche.\n\n"
        "Achtung: grün/rot ist KEIN Kauf-/Verkaufssignal, nur ein "
        "Bewegtheits-Maß."),
    "kpi_atr": ("ATR 14 (D1) — Average True Range",
        "Die durchschnittliche **Tagesbewegung** der letzten 14 Tage, in "
        "US-Dollar. Beispiel: ATR 40 heißt: in den letzten zwei Wochen "
        "schwankte Gold im Schnitt etwa 40 USD pro Tag.\n\n"
        "Die Farbe ordnet den Wert ein: **Perzentil gegen die eigenen "
        "Werte der letzten 12 Monate** — bei „Perzentil 84“ war Gold an "
        "84 % der Tage ruhiger als aktuell. Grün = unteres Drittel, "
        "rot = oberes."),
    "kpi_rsi": ("RSI 14 (D1) — Relative Strength Index",
        "Oszillator zwischen 0 und 100: Werte weit über 50 = letzte Tage "
        "deutlich aufwärts, weit unter 50 = deutlich abwärts, um 50 = "
        "ausgeglichen.\n\n"
        "Die Farbe zeigt hier die **Bewegtheit** (Distanz zu 50), keine "
        "Kauf-/Verkaufsempfehlung."),
    "richtung_marktlage": ("Richtung & Marktlage (Stufe 5)",
        "Links die P(hoch)-Prognosen der Richtungsmodelle (ehrlich: als "
        "„nicht verifiziert“ gekennzeichnet — sie schlagen die Basisrate "
        "nicht), rechts die aktuellen Quant-Signale: Δ Realzins und Δ "
        "Dollar (5 Tage), COT-Fondspositionen mit Perzentil, GLD-ETF-Flüsse "
        "sowie Crowding-Warnungen."),
    "ki_analyse": ("KI-Analyse (Stufe 4)",
        "Der Analytiker-Agent erhält die Modell-Matrix, Termine, die "
        "News-Treiber und den Community-Konsens. Er darf P_stat je Tag nur "
        "im ±10-pp-Band verschieben und muss jede Abweichung begründen — "
        "Verstöße verwirft das System automatisch. Der Treiber-Wasserfall "
        "zeigt, welche Einflüsse die Verschiebung tragen."),
    "wochen_summe": ("Wochen-Summenwert",
        "Wahrscheinlichkeit, dass **mindestens ein** Tag der Woche ein "
        "Bewegungstag wird — berechnet als 1 − ∏(1 − p) unter der "
        "vereinfachenden Annahme unabhängiger Tage. Weil Bewegungstage "
        "real clustern, liegt der wahre Wert eher etwas darunter."),
    "was_waere_wenn": ("Was-wäre-wenn — Simulation",
        "Schiebt die Modell-Verteilung (μ und σ der erwarteten Range) und "
        "rechnet P je Tag mit derselben Formel neu. Reine Sandbox: nichts "
        "davon wird gespeichert, exportiert oder verifiziert."),
}

# Ausführliche Informationen je Baum-Knoten (Titel, Markdown-Erklärung).
# Die Live-Daten (Metriken, Tabellen, PDFs) setzt das Dashboard dazu.
KNOTEN_INFO: dict[str, tuple[str, str]] = {
    "kurse": ("Kurse — die Rohdaten",
        "**Was passiert hier?** Der Scanner verbindet sich mit deinem "
        "MetaTrader-5-Terminal (Broker Tickmill) und kopiert — strikt nur "
        "lesend — Tages-, 4-Stunden- und Stundenkerzen von XAUUSD. Eine "
        "statisch geprüfte Whitelist erlaubt ausschließlich Lese-Aufrufe; "
        "Orders sind technisch unmöglich.\n\n"
        "**Warum 17 Jahre?** Die Klimatologie misst Wochentags-Muster, das "
        "HAR-Modell lernt aus rund 4.350 Tageskerzen inklusive Finanzkrise, "
        "Corona und Inflationsschub — Grundlage des ehrlichen Walk-Forward-"
        "Tests über 4.078 Tage.\n\n"
        "**Danach:** Alles landet in der lokalen Datenbank; jedes Modell "
        "rechnet nur aus der DB („Der Analytiker liest nie live“)."),
    "kalender": ("Kalender — die Termin-Datenbank",
        "**Was passiert hier?** Fünf offizielle Quellen werden abgerufen und "
        "per Hash archiviert: ForexFactory, US-Arbeitsamt BLS (NFP/CPI mit "
        "Uhrzeiten), BEA (GDP/PCE), Federal Reserve (FOMC/Reden), US-Schatzamt "
        "(Auktionen). Dazu regelberechnete Termine: Gold-Future-Fälligkeiten "
        "(FND/LTD), Optionsverfall, Feiertage, Zeitumstellung.\n\n"
        "**Deduplizierung:** Dieselbe Nachricht aus mehreren Quellen zählt "
        "einmal — die Qualität gewinnt. Jeder Termin bekommt eine "
        "Gold-Relevanz (★1–5).\n\n"
        "**Point-in-time:** Jeder Abruf wird versioniert — späteres "
        "Nachbessern der Quellen kann alte Prognosen nicht verfälschen."),
    "gvz": ("Marktdaten & Quant-Feeds",
        "**Was passiert hier?** Sechs quantitative Serien: GVZ (erwartete "
        "Gold-Volatilität aus Optionen), FRED-Realzins 10 J, "
        "Inflationserwartung, breiter Dollar-Index, VIX — dazu CFTC-"
        "Fondspositionen (wöchentlich) und GLD-ETF-Bestände in Tonnen.\n\n"
        "**Wozu?** Sie speisen die Marktlage (Δ Realzins, Δ Dollar, "
        "COT-Perzentil, ETF-Flüsse, Crowding-Warnungen) und sind Merkmale "
        "im Modell. CFTC erscheint bewusst erst 4 Tage nach Stichtag "
        "(Veröffentlichungsverzug) — kein Blick in die Zukunft.\n\n"
        "**Ehrlich:** Die Richtung konnten auch diese Feeds nicht vorhersagen "
        "(Tor T5) — sie liefern Kontext, keine Richtungs-Prognose."),
    "news": ("News — 8 RSS-Feeds mit Delta-Prinzip",
        "**Was passiert hier?** Acht RSS-Quellen (FXStreet news/analysis, "
        "Google News deutsch & englisch, Bing, FXEmpire, Investing) werden "
        "höflich abgefragt; ein Gold-Relevanz-Filter wirft Irrelevantes raus, "
        "ein 7-Tage-Fenster begrenzt.\n\n"
        "**Delta-Prinzip (spart Geld):** Jeder Artikel hat einen SHA-"
        "Fingerabdruck — unveränderte Artikel werden nie erneut an die KI "
        "geschickt (max. 80 pro Destillations-Aufruf).\n\n"
        "**Wo bleibt das?** In den Treibern der KI-Destillation — mit "
        "Quellenlink als Beleg."),
    "community": ("Community — Stimmung als Kontra-Indikator",
        "**Was passiert hier?** TradingView-Ideen für XAUUSD werden "
        "deterministisch ausgezählt (Long vs. Short, häufigste Kursmarken), "
        "dazu Analysten-Sentiment (FXStreet/FXEmpire) und die Kitco-Umfrage. "
        "Reines Zählen — keine KI.\n\n"
        "**Der Clou — Retail-Bias:** Ist die Community extrem einseitig "
        "(≥ 70 % eine Richtung), leuchtet ein Kontra-Flag: Extreme "
        "Einzelmeinung ist historisch oft ein Umkehrsignal — die KI bekommt "
        "diese Warnung ausdrücklich."),
    "statistik": ("Statistik-Engine — das Herzstück (KI-frei!)",
        "**Was passiert hier?** Reiner Code: Die Klimatologie legt die "
        "Basisrate je Wochentag fest (mit Shrinkage). Das HAR-Modell lernt "
        "aus Gestern-/Woche-/Monats-Gedächtnis plus Termin-Merkmalen und "
        "Options-Vola und schätzt P(Bewegungstag) samt Range-Band Q10–Q90. "
        "Das Richtungsmodell läuft mit — und ist ehrlich als „nicht "
        "verifiziert“ gekennzeichnet.\n\n"
        "**Qualitätskontrolle:** Vor jeder Veröffentlichung läuft der "
        "Walk-Forward-Test (4.078 Testtage). Nur bei BSS > 0 gegen die "
        "Klimatologie (Tor T3) kommt das Modell auf die Matrix.\n\n"
        "**Bewusste Trennung:** Diese Engine bekommt weder News noch "
        "Community — Prognose-Kern und Stimmung bleiben getrennt."),
    "news_destill": ("KI: News-Treiber destillieren",
        "**Was passiert hier?** Das schnelle Modell (glm-5.3-flash) bekommt "
        "bis zu 80 neue Artikel als JSON und liefert max. 8 Treiber mit "
        "Richtung, Zeithorizont, Konfidenz und Quellenlink.\n\n"
        "**Sicherheit:** Kaputte Antworten werden verworfen — nie "
        "gespeichert; nach 3 Fehlversuchen Fail-Fast. Jeder Aufruf landet "
        "vollständig im Audit-Journal (Prompt/Antwort/Token)."),
    "comm_destill": ("KI: Community-Stimmung einordnen",
        "**Was passiert hier?** Das schnelle Modell (glm-5.3-flash) "
        "interpretiert die ausgezählte Community: Konsens-Richtung, "
        "Einigkeit, wichtige Levels — und ob der Konsens diese Woche eher "
        "verstärkend oder dämpfend wirkt.\n\n"
        "**Kontra-Denke:** Der Prompt mahnt ausdrücklich, dass extreme "
        "Einseitigkeit historisch oft GEGEN die Menge funktioniert. Auch "
        "hier: ungültige Antworten fliegen raus, alles im Journal."),
    "fusion": ("KI-Fusion — der Analytiker im Korsett",
        "**Was passiert hier?** Das starke Modell (glm-5.3) erhält die "
        "Modell-Matrix, die News-Treiber und den Community-Konsens. Es darf "
        "P_stat je Tag anpassen — aber nur innerhalb ±10 Prozentpunkten, und "
        "jede Abweichung über 1 Punkt braucht eine konkrete Begründung "
        "(Treiber-Wasserfall).\n\n"
        "**Band-Disziplin:** Verstöße verwirft das System automatisch. Damit "
        "bleibt die KI messbar: Der Track-Record vergleicht, ob die KI-"
        "Version oder die reine Modellzahl näher an der Realität lag "
        "(Tor T4) — hilft das Delta nicht, dreht man das Band auf 0."),
    "matrix": ("Wochenmatrix — das Produkt",
        "**Was passiert hier?** Alles läuft zusammen: Pro Wochentag stehen "
        "P_finale (KI), P_stat (Modell) und Klimatologie nebeneinander, dazu "
        "Schwelle B, Range-Band, Warnstufe und Top-Termine. Jede Version "
        "wird mit Zeitstempel archiviert (as_of — Grundlage der ehrlichen "
        "Verifikation).\n\n"
        "**Konsumiert über:** Dashboard, REST (127.0.0.1:8606/matrix), "
        "MT5-Export. Samstags rechnet der Verifikations-Agent jede Prognose "
        "gegen die echte Kerze — das füllt den Track-Record."),
    "pdf": ("PDF-Bericht — die Wochenanalyse",
        "**Was passiert hier?** Nach jeder Fusion baut reiner Code "
        "(reportlab) den Wochenbericht: Matrix-Tabelle je Tag, "
        "KI-Zusammenfassung, Treiber, Risiken, Marktlage, Disclaimer — "
        "1–2 Seiten, landet in `data/reports/`.\n\n"
        "**Hier im Popup:** Die erzeugten PDFs sind unten direkt lesbar."),
    "export": ("MT5-Export — die EA-Schnittstelle",
        "**Was passiert hier?** Die Prognosen werden als CSV "
        "(`goldscanner_prognose.csv`; Semikolon, ISO-Datum, P in %) in den "
        "Common-Ordner aller MetaTrader-Terminals geschrieben — dein EA "
        "liest sie mit `FileOpen(..., FILE_COMMON|FILE_READ)`.\n\n"
        "**Typische Nutzung:** Handelsfilter an bewegungsarmen Tagen, "
        "Lot-Größe nach Range-Band. Zusätzlich lokale Kopie in "
        "`data/exports/` und REST `/prognose.csv`."),
}
