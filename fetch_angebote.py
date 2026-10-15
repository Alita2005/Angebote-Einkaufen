#!/usr/bin/env python3
"""Holt aktuelle Supermarkt-Angebote fuer Poing (PLZ 85586) von der
marktguru.de-API und schreibt sie normalisiert nach data/angebote.json
und data.js (fuer die lokale HTML-Seite).

marktguru bietet keine "alle Angebote einer PLZ"-Route an - die Suche
verlangt zwingend einen Suchbegriff (q). Daher wird ueber eine Liste
typischer Supermarkt-Kategorien iteriert und dedupliziert.
"""

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from bmel_reference import match_bmel_reference

# Ab wie vielen unterschiedlichen Tages-Snapshots ein "ueblicher Preis" aus
# der eigenen Historie berechnet wird (weniger waere nicht aussagekraeftig -
# ein einzelner Tag ist kein "Normalpreis").
MIN_HISTORY_SNAPSHOTS = 3

# Registry-Datei: merkt sich pro (Kette, Produkt, Einheit) den letzten
# bekannten Grundpreis dauerhaft ueber Laeufe hinweg - auch nachdem das
# eigentliche Angebot bei marktguru nicht mehr auftaucht (siehe
# build_expired_entries()). Unbegrenzt aufbewahrt, kein automatisches
# Aufraeumen.
KNOWN_PRODUCTS_FILENAME = "known_products.json"

ZIP_CODE = "85586"  # Poing

RETAILER_IDS = {
    127093: "EDEKA",
    126802: "REWE",
    127153: "ALDI SÜD",
    126679: "Lidl",
    126654: "Kaufland",  # Burgerfeld 8, 85570 Markt Schwaben
}

API_URL = "https://api.marktguru.de/api/v1/offers/search"
HEADERS = {
    "x-clientkey": "WU/RH+PMGDi+gkZer3WbMelt6zcYHSTytNB7VpTia90=",
    "x-apikey": "8Kk+pmbf7TgJ9nVj2cXeA7P5zBGv8iuutVVMRfOfvNE=",
}

# Suchbegriffe, um moeglichst viele Angebotskategorien abzudecken.
# (q ist bei dieser API zwingend erforderlich - es gibt keinen
# "alle Angebote"-Endpunkt.)
SEARCH_TERMS = [
    "obst", "gemüse", "salat", "kartoffeln",
    "fleisch", "wurst", "geflügel", "fisch",
    "milch", "käse", "joghurt", "butter", "eier",
    "brot", "brötchen", "kuchen",
    "müsli", "nudeln", "reis", "konserven", "suppe", "sauce", "gewürze", "öl",
    "getränke", "wasser", "saft", "limonade", "bier", "wein", "kaffee", "tee",
    "süßigkeiten", "schokolade", "chips", "snacks",
    "tiefkühl", "eis", "pizza", "fertiggericht",
    "baby", "tiernahrung",
    "drogerie", "kosmetik", "pflege", "zahnpflege",
    "reiniger", "waschmittel", "toilettenpapier", "haushalt", "grillen",
]

PAGE_SIZE = 200
REQUEST_DELAY_SECONDS = 0.3

# Grobe Abteilungs-Zuordnung fuer die Kategorie-Gruppierung in der Seite.
# marktguru liefert pro Angebot nur eine sehr feine Leaf-Kategorie (z.B.
# "Wurzelgemüse", "Gemüsekonserven") - deren eigener /categories-Baum ist
# unvollstaendig (Elternkategorien fehlen teils in der API-Antwort). Daher
# hier eine explizite, von Hand gepflegte Zuordnung aller bisher
# beobachteten Leaf-Kategorien auf grobe Abteilungen. Neue, noch nicht
# gelistete Kategorien fallen auf CATEGORY_KEYWORD_FALLBACK zurueck.
CATEGORY_TO_DEPARTMENT: dict[str, str] = {
    # Fleisch & Wurst
    "Geflügel": "Fleisch & Wurst", "Hackfleisch": "Fleisch & Wurst",
    "Kalbfleisch": "Fleisch & Wurst", "Koch- und Streichwurst": "Fleisch & Wurst",
    "Lammfleisch": "Fleisch & Wurst", "Rindfleisch": "Fleisch & Wurst",
    "Salami": "Fleisch & Wurst", "Schinken": "Fleisch & Wurst",
    "Schweinefleisch": "Fleisch & Wurst", "Wurstaufschnitt": "Fleisch & Wurst",
    "Wurstsalate": "Fleisch & Wurst", "Würste": "Fleisch & Wurst",
    "gemischte Fleischwaren": "Fleisch & Wurst", "mariniertes Fleisch": "Fleisch & Wurst",
    # Fisch & Meeresfrüchte
    "Fischkonserven": "Fisch & Meeresfrüchte", "Fischsalate": "Fisch & Meeresfrüchte",
    "Frischfisch": "Fisch & Meeresfrüchte", "Meeresfrüchte": "Fisch & Meeresfrüchte",
    "Räucherfisch": "Fisch & Meeresfrüchte", "marinierter Fisch": "Fisch & Meeresfrüchte",
    # Milchprodukte & Eier
    "Butter": "Milchprodukte & Eier", "Eier": "Milchprodukte & Eier",
    "Joghurt": "Milchprodukte & Eier", "Käse": "Milchprodukte & Eier",
    "Milch": "Milchprodukte & Eier",
    "Sahne, Schmand und Crème fraîche": "Milchprodukte & Eier",
    # Obst & Gemüse
    "Beeren": "Obst & Gemüse", "Birnen": "Obst & Gemüse", "Bohnen": "Obst & Gemüse",
    "Brokkoli und Kohl": "Obst & Gemüse", "Exotische Früchte": "Obst & Gemüse",
    "Feinkostgemüse": "Obst & Gemüse", "Gurke": "Obst & Gemüse",
    "Kräuter": "Obst & Gemüse", "Melonen": "Obst & Gemüse", "Paprika": "Obst & Gemüse",
    "Pilze": "Obst & Gemüse", "Salate und Blattgemüse": "Obst & Gemüse",
    "Steinobst": "Obst & Gemüse", "Tomaten": "Obst & Gemüse",
    "Trockenobst": "Obst & Gemüse", "Weintrauben": "Obst & Gemüse",
    "Wurzelgemüse": "Obst & Gemüse", "Zitrusfrüchte": "Obst & Gemüse",
    "Zucchini & Kürbis": "Obst & Gemüse", "Zwiebeln und Knoblauch": "Obst & Gemüse",
    "Äpfel": "Obst & Gemüse",
    # Brot & Backwaren
    "Backzubehör": "Brot & Backwaren", "Backzutaten & -mischungen": "Brot & Backwaren",
    "Brot": "Brot & Backwaren", "Brötchen": "Brot & Backwaren",
    "Kuchen & Feinbackwaren": "Brot & Backwaren", "Salzgebäck": "Brot & Backwaren",
    # Wein, Bier & Spirituosen
    "Alkoholfreies Bier": "Wein, Bier & Spirituosen", "Bier": "Wein, Bier & Spirituosen",
    "Brauner Rum": "Wein, Bier & Spirituosen", "Brände": "Wein, Bier & Spirituosen",
    "Champagner": "Wein, Bier & Spirituosen", "Cocktails": "Wein, Bier & Spirituosen",
    "Gin": "Wein, Bier & Spirituosen", "Kornbrand": "Wein, Bier & Spirituosen",
    "Liköre": "Wein, Bier & Spirituosen", "Likörweine": "Wein, Bier & Spirituosen",
    "Roseweine": "Wein, Bier & Spirituosen", "Rotweine": "Wein, Bier & Spirituosen",
    "Sekt": "Wein, Bier & Spirituosen", "Wein": "Wein, Bier & Spirituosen",
    "Weinbrand": "Wein, Bier & Spirituosen", "Weinmischgetränke": "Wein, Bier & Spirituosen",
    "Weissweine": "Wein, Bier & Spirituosen", "Weißer Rum": "Wein, Bier & Spirituosen",
    "Whiskey": "Wein, Bier & Spirituosen", "Wodka": "Wein, Bier & Spirituosen",
    # Kaffee & Tee
    "Kaffee": "Kaffee & Tee", "Kakao": "Kaffee & Tee", "Tee": "Kaffee & Tee",
    # Getränke (alkoholfrei)
    "Softdrinks": "Getränke", "Wasser": "Getränke",
    # Süßes & Snacks
    "Chips": "Süßes & Snacks", "Desserts": "Süßes & Snacks",
    "Fruchtgummi": "Süßes & Snacks", "Honig": "Süßes & Snacks",
    "Kekse": "Süßes & Snacks", "Knabbereien": "Süßes & Snacks",
    "Marmeladen": "Süßes & Snacks", "Müslimischungen": "Süßes & Snacks",
    "Schokoaufstrich": "Süßes & Snacks", "Schokoladen": "Süßes & Snacks",
    "Snacks und Imbiss": "Süßes & Snacks", "herzhafte Aufstriche": "Süßes & Snacks",
    # Konserven & Fertiggerichte
    "Antipasti": "Konserven & Fertiggerichte", "Dips": "Konserven & Fertiggerichte",
    "Fingerfood": "Konserven & Fertiggerichte", "Gemüsekonserven": "Konserven & Fertiggerichte",
    "Instantgerichte": "Konserven & Fertiggerichte",
    "Internationale Spezialitäten": "Konserven & Fertiggerichte",
    "Kartoffelgerichte": "Konserven & Fertiggerichte", "Nudelsalate": "Konserven & Fertiggerichte",
    "Obstkonserven": "Konserven & Fertiggerichte", "Salatdressing": "Konserven & Fertiggerichte",
    "Soßen": "Konserven & Fertiggerichte", "Warme Speisen": "Konserven & Fertiggerichte",
    # Tiefkühl
    "Eis": "Tiefkühl", "Tiefkühlbackwaren & -feingebäck": "Tiefkühl",
    "Tiefkühlfisch und Meeresfrüchte": "Tiefkühl", "Tiefkühlfleisch": "Tiefkühl",
    "Tiefkühlgemüse": "Tiefkühl", "Tiefkühlgerichte": "Tiefkühl",
    "Tiefkühlkartoffeln": "Tiefkühl", "Tiefkühlpizza & -flammkuchen": "Tiefkühl",
    # Grundnahrungsmittel & Gewürze
    "Eier-Teigwaren": "Grundnahrungsmittel & Gewürze", "Getreide": "Grundnahrungsmittel & Gewürze",
    "Gewürzmischungen": "Grundnahrungsmittel & Gewürze", "Nudeln": "Grundnahrungsmittel & Gewürze",
    "Reis": "Grundnahrungsmittel & Gewürze", "Salz": "Grundnahrungsmittel & Gewürze",
    "Öle und Fette": "Grundnahrungsmittel & Gewürze",
    # Vegetarisch & Vegan
    "Veganes": "Vegetarisch & Vegan",
    # Baby
    "Baby-Spielzeug": "Baby", "Babymöbel": "Baby", "Babynahrung": "Baby",
    "Kinder- und Babybekleidung": "Baby", "Windeln": "Baby",
    # Tierbedarf
    "Hundefutter": "Tierbedarf", "Katzenfutter": "Tierbedarf",
    # Drogerie & Kosmetik
    "Damenhygiene ": "Drogerie & Kosmetik", "Deo": "Drogerie & Kosmetik",
    "Duschgel": "Drogerie & Kosmetik", "Elektrische Zahnpflege": "Drogerie & Kosmetik",
    "Gesichtspflege": "Drogerie & Kosmetik", "Haarpflege": "Drogerie & Kosmetik",
    "Makeup Zubehör": "Drogerie & Kosmetik", "Zahngesundheit": "Drogerie & Kosmetik",
    # Haushalt & Reinigung
    "Folienbeutel": "Haushalt & Reinigung", "Küchenrolle": "Haushalt & Reinigung",
    "Lufterfrischer": "Haushalt & Reinigung", "Müllbeutel": "Haushalt & Reinigung",
    "Reinigen": "Haushalt & Reinigung", "Reinigungsgeräte": "Haushalt & Reinigung",
    "Spülmittel": "Haushalt & Reinigung", "Taschentücher": "Haushalt & Reinigung",
    "Toilettenpapier": "Haushalt & Reinigung", "Waschmittel": "Haushalt & Reinigung",
    # Küche & Haushaltswaren
    "Aufbewahrungsbehälter": "Küche & Haushaltswaren", "Besteck": "Küche & Haushaltswaren",
    "Essgeschirr": "Küche & Haushaltswaren", "Glasartikel": "Küche & Haushaltswaren",
    "Kaffeemaschinen": "Küche & Haushaltswaren", "Kochgeschirr": "Küche & Haushaltswaren",
    "Küchengeräte": "Küche & Haushaltswaren", "Küchengroßgeräte": "Küche & Haushaltswaren",
    "Küchentextilien": "Küche & Haushaltswaren", "Küchenzubehör": "Küche & Haushaltswaren",
    "Töpfe": "Küche & Haushaltswaren", "Wäschenständer": "Küche & Haushaltswaren",
    # Sonstiges (Deko, Saisonales, Non-Food)
    "Auto": "Sonstiges", "Brennstoffe": "Sonstiges", "Deko": "Sonstiges",
    "Filtersysteme": "Sonstiges", "Gartenpflege": "Sonstiges", "Haustechnik": "Sonstiges",
    "Leuchten": "Sonstiges", "Muttertag": "Sonstiges", "Nähmaschinen": "Sonstiges",
    "Spiele": "Sonstiges", "Uhren": "Sonstiges", "Valentinstag": "Sonstiges",
    "Vatertag": "Sonstiges",
}

# Fallback per Stichwort fuer Kategorien, die noch nicht in
# CATEGORY_TO_DEPARTMENT gelistet sind (z.B. wenn marktguru neue
# Kategorien einfuehrt). Bewusst nur eindeutige, nicht zu kurze Stichworte,
# um Fehltreffer wie "eis" in "Reis" zu vermeiden.
CATEGORY_KEYWORD_FALLBACK: list[tuple[str, list[str]]] = [
    ("Fleisch & Wurst", ["wurst", "würst", "fleisch", "schinken"]),
    ("Fisch & Meeresfrüchte", ["fisch"]),
    ("Milchprodukte & Eier", ["käse", "milch", "joghurt", "butter"]),
    ("Obst & Gemüse", ["obst", "gemüse", "kartoffel", "frücht"]),
    ("Brot & Backwaren", ["brot", "brötchen", "kuchen", "gebäck"]),
    ("Wein, Bier & Spirituosen", ["wein", "bier", "likör", "spirituos"]),
    ("Kaffee & Tee", ["kaffee", "kakao"]),
    ("Süßes & Snacks", ["schokolade", "süßigkeit", "snack"]),
    ("Konserven & Fertiggerichte", ["konserve", "fertiggericht"]),
    ("Tiefkühl", ["tiefkühl"]),
    ("Drogerie & Kosmetik", ["drogerie", "kosmetik", "pflege"]),
    ("Haushalt & Reinigung", ["reinig", "wasch"]),
    ("Küche & Haushaltswaren", ["topf", "töpf", "küche"]),
    ("Baby", ["baby"]),
    ("Tierbedarf", ["tierfutter", "hundefutter", "katzenfutter"]),
]


def classify_department(category: str | None) -> str:
    if not category:
        return "Sonstiges"
    if category in CATEGORY_TO_DEPARTMENT:
        return CATEGORY_TO_DEPARTMENT[category]
    name = category.lower()
    for department, keywords in CATEGORY_KEYWORD_FALLBACK:
        if any(keyword in name for keyword in keywords):
            return department
    return "Sonstiges"


def fetch_term(session: requests.Session, term: str) -> list[dict]:
    results = []
    offset = 0
    retailer_ids = ",".join(str(rid) for rid in RETAILER_IDS)
    while True:
        params = {
            "as": "web",
            "limit": PAGE_SIZE,
            "offset": offset,
            "q": term,
            "zipCode": ZIP_CODE,
            "retailers": retailer_ids,
        }
        resp = session.get(API_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        page = data.get("results") or []
        results.extend(page)
        total = data.get("totalResults", 0)
        offset += len(page)
        if offset >= total or not page:
            break
    return results


def normalize(raw: dict) -> dict:
    advertiser = (raw.get("advertisers") or [{}])[0]
    brand = raw.get("brand") or {}
    product = raw.get("product") or {}
    unit = raw.get("unit") or {}
    categories = raw.get("categories") or []
    validity = (raw.get("validityDates") or [{}])[0]
    category_name = categories[0].get("name") if categories else None

    return {
        "id": raw.get("id"),
        "store": advertiser.get("name"),
        "product": product.get("name") or raw.get("description"),
        "brand": brand.get("name"),
        "description": raw.get("description"),
        "category": category_name,
        "department": classify_department(category_name),
        "price": raw.get("price"),
        "oldPrice": raw.get("oldPrice"),
        "referencePrice": raw.get("referencePrice"),
        "unit": unit.get("shortName"),
        "quantity": raw.get("quantity"),
        "volume": raw.get("volume"),
        "validFrom": validity.get("from"),
        "validUntil": validity.get("to"),
        "url": f"https://www.marktguru.de/offers/{raw['id']}" if raw.get("id") is not None else None,
        "image": (f"https://mg2de.b-cdn.net/api/v1/offers/{raw['id']}/images/default/0/medium.webp"
                  if raw.get("id") is not None and raw.get("images") else None),
    }


def write_history_snapshot(history_dir: Path, offers: list[dict]) -> Path:
    """Schreibt einen schlanken, datierten Snapshot (nur die fuer die
    Normalpreis-Berechnung noetigen Felder) - Grundlage fuer
    compute_usual_prices(), das erst nach ein paar Wochen/Monaten
    gesammelter Snapshots aussagekraeftig wird."""
    history_dir.mkdir(exist_ok=True)
    today = datetime.now().date().isoformat()
    snapshot = [
        {
            "store": o["store"],
            "product": o["product"],
            "unit": o["unit"],
            "referencePrice": o["referencePrice"],
            "price": o["price"],
        }
        for o in offers
        if o.get("product") and o.get("store")
    ]
    path = history_dir / f"{today}.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    return path


def compute_usual_prices(history_dir: Path) -> dict[tuple[str, str, str], dict]:
    """Median-Referenzpreis pro (Kette, Produkt, Einheit) ueber alle bisher
    gesammelten Tages-Snapshots - nur fuer Kombinationen mit genuegend
    Datenpunkten (siehe MIN_HISTORY_SNAPSHOTS)."""
    if not history_dir.exists():
        return {}

    samples: dict[tuple[str, str, str], list[float]] = {}
    for snapshot_file in history_dir.glob("*.json"):
        try:
            entries = json.loads(snapshot_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for entry in entries:
            price = entry.get("referencePrice") or entry.get("price")
            if price is None:
                continue
            key = (entry.get("store"), entry.get("product"), entry.get("unit"))
            samples.setdefault(key, []).append(price)

    usual_prices = {}
    for key, prices in samples.items():
        if len(prices) < MIN_HISTORY_SNAPSHOTS:
            continue
        usual_prices[key] = {
            "usualPrice": round(statistics.median(prices), 2),
            "usualPriceSamples": len(prices),
        }
    return usual_prices


def load_known_products(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def update_known_products(known: dict[str, dict], offers: list[dict], today: str) -> None:
    """Traegt fuer jedes aktuell aktive Angebot den Grundpreis in die
    Registry ein/aktualisiert ihn - lastSeen wird NUR fuer aktuell
    vorhandene Angebote aktualisiert, damit bereits abgelaufene Eintraege
    ihr letztes echtes Sichtungsdatum behalten."""
    for o in offers:
        if o.get("referencePrice") is None or o.get("unit") is None:
            continue
        key = f"{o.get('store')}|{o.get('product')}|{o.get('unit')}"
        known[key] = {
            "store": o.get("store"),
            "product": o.get("product"),
            "unit": o.get("unit"),
            "brand": o.get("brand"),
            "category": o.get("category"),
            "department": o.get("department"),
            "referencePrice": o.get("referencePrice"),
            "lastSeen": today,
        }


def build_expired_entries(known: dict[str, dict], current_keys: set[str]) -> list[dict]:
    """Baut fuer jeden Registry-Eintrag, der in diesem Lauf NICHT mehr unter
    den aktuellen Angeboten ist, einen schlanken "nur Grundpreis"-Eintrag
    (kein price/oldPrice/validFrom - validUntil = letztes Sichtungsdatum,
    damit die Seite ihn korrekt als abgelaufen/inaktiv erkennt)."""
    entries = []
    for key, info in known.items():
        if key in current_keys:
            continue
        entries.append({
            "id": f"expired-{key}",
            "store": info["store"],
            "product": info["product"],
            "brand": info.get("brand"),
            "description": None,
            "category": info.get("category"),
            "department": info.get("department"),
            "price": None,
            "oldPrice": None,
            "referencePrice": info["referencePrice"],
            "unit": info["unit"],
            "quantity": None,
            "volume": None,
            "validFrom": None,
            "validUntil": info["lastSeen"],
            "expired": True,
        })
    return entries


def main():
    project_dir = Path(__file__).resolve().parent
    session = requests.Session()

    by_id: dict[int, dict] = {}
    for term in SEARCH_TERMS:
        try:
            raw_offers = fetch_term(session, term)
        except requests.RequestException as exc:
            print(f"WARN: Suche nach '{term}' fehlgeschlagen: {exc}")
            continue
        for raw in raw_offers:
            offer = normalize(raw)
            if offer["id"] is not None:
                by_id[offer["id"]] = offer
        print(f"'{term}': {len(raw_offers)} Treffer (gesamt bisher {len(by_id)} eindeutige Angebote)")
        time.sleep(REQUEST_DELAY_SECONDS)

    offers = sorted(by_id.values(), key=lambda o: (o["product"] or "", o["store"] or ""))

    data_dir = project_dir / "data"
    history_dir = data_dir / "history"

    # 1) Normalpreis-Hinweis aus der amtlichen BMEL-Referenz (15 Grundprodukte,
    #    Jahresdurchschnitt nach Geschaeftstyp - siehe bmel_reference.py).
    for offer in offers:
        bmel_match = match_bmel_reference(offer)
        if bmel_match:
            offer.update(bmel_match)

    # 2) Heutigen Snapshot schreiben, dann ueblichen Preis aus der bisher
    #    gesammelten Historie berechnen (braucht mehrere Snapshots, siehe
    #    MIN_HISTORY_SNAPSHOTS - anfangs also noch leer, waechst mit der Zeit).
    write_history_snapshot(history_dir, offers)
    usual_prices = compute_usual_prices(history_dir)
    for offer in offers:
        key = (offer.get("store"), offer.get("product"), offer.get("unit"))
        usual = usual_prices.get(key)
        if usual:
            offer.update(usual)

        # Rabatt-% relativ zum Grundpreis-Referenzwert (eigene Historie vor
        # BMEL-Referenz) - nur wenn marktguru selbst keinen oldPrice liefert
        # (der ist exakt, das hier ist nur eine Schaetzung).
        ref_price = offer.get("referencePrice")
        if offer.get("oldPrice") is None and ref_price is not None:
            if offer.get("usualPrice") is not None:
                baseline, basis = offer["usualPrice"], "eigene Historie"
            elif offer.get("normalPrice") is not None:
                baseline, basis = offer["normalPrice"], "BMEL-Referenz"
            else:
                baseline, basis = None, None
            if baseline and baseline > ref_price:
                pct = round((1 - ref_price / baseline) * 100)
                if pct >= 1:
                    offer["referenceDiscountPct"] = pct
                    offer["referenceDiscountBasis"] = basis

    # 3) Grundpreis-Registry aktualisieren und fuer Produkte, deren Angebot
    #    diesmal nicht mehr dabei ist, einen "nur Grundpreis"-Eintrag
    #    ergaenzen, statt sie komplett verschwinden zu lassen.
    known_path = data_dir / KNOWN_PRODUCTS_FILENAME
    known_products = load_known_products(known_path)
    today = datetime.now().date().isoformat()
    current_keys = {
        f"{o.get('store')}|{o.get('product')}|{o.get('unit')}"
        for o in offers
        if o.get("referencePrice") is not None and o.get("unit") is not None
    }
    update_known_products(known_products, offers, today)
    expired_entries = build_expired_entries(known_products, current_keys)
    data_dir.mkdir(exist_ok=True)
    known_path.write_text(json.dumps(known_products, ensure_ascii=False, indent=2), encoding="utf-8")
    offers = offers + expired_entries
    print(f"Grundpreis-Registry: {len(known_products)} bekannte Produkte, "
          f"{len(expired_entries)} davon aktuell ohne laufendes Angebot")

    counts = {}
    for o in offers:
        counts[o["store"]] = counts.get(o["store"], 0) + 1
    print("\nAngebote pro Markt:")
    for store, count in sorted(counts.items()):
        print(f"  {store}: {count}")
    print(f"Gesamt: {len(offers)} eindeutige Angebote\n")

    data_dir.mkdir(exist_ok=True)
    json_path = data_dir / "angebote.json"
    json_path.write_text(
        json.dumps(offers, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data_js_path = project_dir / "data.js"
    data_js_path.write_text(
        "const ANGEBOTE_UPDATED = "
        + json.dumps(updated_at)
        + ";\nconst ANGEBOTE = "
        + json.dumps(offers, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )

    print(f"Geschrieben: {json_path}")
    print(f"Geschrieben: {data_js_path}")


if __name__ == "__main__":
    main()
