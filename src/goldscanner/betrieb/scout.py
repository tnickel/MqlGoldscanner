"""URL-Scout (S6): neue Gold-Quellen entdecken — deterministisch, ohne LLM.

Der Scout liest den Google-News-RSS (der deckt praktisch alle Publisher ab)
und zählt, welche Domänen in den letzten 7 Tagen wie oft gold-relevante
Artikel geliefert haben. Bekannte Domänen (bereits im Adapter oder bewusst
abgelehnt) fliegen raus — was übrig bleibt, sind bewertete Vorschläge
(Score = Anzahl Treffer, Beispiel-Titel als Beleg) für die Quellen-UI, wo
der Nutzer annehmen/ablehnen kann.

Tavily/andere Such-APIs bleiben optionaler Ausbau (S7): der Default-Lauf
kommt ohne Key aus (Konzept §7.5: Google/Bing-News-RSS decken ~90 % des
Scout-Bedarfs).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from .. import config
from ..adapter.news import gold_relevanz, _hole_feed

SUCHE_URL = ("https://news.google.com/rss/search?q=gold+price+OR+goldpreis"
             "&hl=en-US&gl=US&ceid=US:en")

# Bereits benutzt (Adapter) oder bewusst nicht (Konzept §7.2/§7.3 Negativliste)
BEKANNT = {
    "fxstreet.com", "fxempire.com", "investing.com", "nasdaq.com",
    "bing.com", "google.com", "news.google.com", "tradingview.com",
    "kitco.com", "reuters.com", "marketwatch.com", "myfxbook.com",
    "mining.com", "goldseiten.de", "dailyfx.com", "tradingeconomics.com",
    "babypips.com", "stooq.pl", "yahoo.com", "finance.yahoo.com",
    "msn.com", "youtube.com", "en.wikipedia.org", "g.co",
}
_DOMAIN_RE = re.compile(r"([a-z0-9-]+\.[a-z.]{2,6})$", re.I)


def domain_aus_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    host = host.lower().removeprefix("www.")
    m = _DOMAIN_RE.search(host)
    return m.group(1).rstrip(".") if m else host


def sammle_domains(inhalt: str, fenster_tage: int = 7
                   ) -> tuple[Counter, dict[str, str]]:
    """RSS → ({domain: n gold-relevanter Items im Fenster}, {domain: beispiel})."""
    grenze = datetime.now(timezone.utc) - timedelta(days=fenster_tage)
    zaehler: Counter = Counter()
    beispiele: dict[str, str] = {}
    root = ET.fromstring(inhalt)
    for it in root.findall(".//item"):
        titel = (it.findtext("title") or "").strip()
        quelle_url = ""
        source = it.find("source")
        if source is not None:
            quelle_url = source.get("url") or ""
        domain = domain_aus_url(quelle_url)
        if not domain and " - " in titel:
            domain = titel.rsplit(" - ", 1)[-1].strip().lower()
        if not domain or "." not in domain:
            continue
        beschreibung = it.findtext("description") or ""
        if gold_relevanz(titel, beschreibung) <= 0:
            continue
        roh = it.findtext("pubDate")
        try:
            dt = parsedate_to_datetime(roh)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < grenze:
                continue
        except (TypeError, ValueError):
            pass
        zaehler[domain] += 1
        beispiele.setdefault(domain, titel)
    return zaehler, beispiele


def suche(db, settings: dict) -> dict:
    """Feed holen, bewerten, neue Vorschläge in die DB legen."""
    inhalt = _hole_feed(SUCHE_URL, settings)
    zaehler, beispiele = sammle_domains(
        inhalt, int(settings.get("news_fenster_tage", 7)))
    neu = 0
    for domain, n in zaehler.most_common(30):
        if domain in BEKANNT or n < 3:
            continue
        if db.scout_vorschlag_speichern(domain, n, beispiele.get(domain, "")):
            neu += 1
    return {"ok": True, "domains": len(zaehler), "neu": neu}
