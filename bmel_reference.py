# -*- coding: utf-8 -*-
"""Referenz-"Normalpreise" fuer ein paar Alltagsprodukte, offiziell vom BMEL
veroeffentlicht (AMI-Verbraucherpreispanel/GfK), aufgeschluesselt nach
Geschaeftstyp. Neueste verfuegbare Zahlen: Jahresdurchschnitt 2024.

Quelle: https://www.bmel-statistik.de/fileadmin/daten/5051000-0000.xlsx
        (Tabelle "229. Verbraucherpreise fuer wichtige Nahrungsmittel
        nach einzelnen Geschaeftstypen")

Nur 15 Grundprodukte, jaehrlicher bundesweiter Durchschnitt - kein Ersatz
fuer echte Filialpreise, aber eine grobe "was kostet das normalerweise"-
Referenz für Produkte, bei denen marktguru keinen oldPrice mitliefert.

Preise sind hier bereits auf dieselbe Einheit normalisiert, die auch
fetch_angebote.py fuer referencePrice/unit verwendet (kg/l/Stk), damit sie
direkt mit offer['referencePrice'] vergleichbar sind.
"""

BMEL_YEAR = 2024

# Jedes Item: keywords (mind. eines muss im Produktnamen vorkommen),
# exclude (falls eines davon vorkommt, KEIN Match), unit (Zieleinheit,
# muss zu offer['unit'] passen), und die drei fuer uns relevanten
# Geschaeftstyp-Durchschnittspreise (bereits auf `unit` umgerechnet).
BMEL_REFERENCE_ITEMS = [
    {
        "label": "Rinderbraten",
        "keywords": ["rinderbraten"],
        "exclude": [],
        "unit": "kg",
        "discount": 10.12,
        "leh_ohne_discount": 12.90,
        "sb_warenhaus": 11.02,
    },
    {
        "label": "Schweinekotelett",
        "keywords": ["schweinekotelett", "kotelett"],
        "exclude": ["kalb", "lamm", "hirsch", "reh"],
        "unit": "kg",
        "discount": 6.53,
        "leh_ohne_discount": 7.79,
        "sb_warenhaus": 6.63,
    },
    {
        "label": "Brathähnchen, gefroren",
        "keywords": ["brathähnchen"],
        "exclude": [],
        "unit": "kg",
        "discount": 4.05,
        "leh_ohne_discount": 4.13,
        "sb_warenhaus": 4.13,
    },
    {
        "label": "Eier (Bodenhaltung, Kl. M)",
        "keywords": ["eier"],
        "exclude": [],
        "unit": "Stk",
        "discount": 0.1983,
        "leh_ohne_discount": 0.2036,
        "sb_warenhaus": 0.1988,
    },
    {
        "label": "Äpfel, alle Sorten",
        "keywords": ["äpfel", "apfel"],
        "exclude": ["apfelsaft", "apfelmus", "apfelschorle", "apfelringe",
                     "berliner", "krapfen", "kuchen", "strudel", "tasche",
                     "wein", "essig", "chips", "kompott"],
        "unit": "kg",
        "discount": 1.935,
        "leh_ohne_discount": 2.552,
        "sb_warenhaus": 2.20,
    },
    {
        "label": "Speisekartoffeln",
        "keywords": ["kartoffel"],
        "exclude": ["kartoffelchips", "kartoffelsalat", "kartoffelpüree", "kartoffelklöße",
                     "süßkartoffel"],
        "unit": "kg",
        "discount": 1.08,
        "leh_ohne_discount": 1.23,
        "sb_warenhaus": 1.22,
    },
    {
        "label": "Frischmilch, ab 3,5% Fett",
        "keywords": ["milch"],
        "exclude": ["buttermilch", "kakao", "schoko", "mandel", "hafer", "soja",
                     "kokos", "reismilch", "milchreis", "kondensmilch"],
        "unit": "l",
        "discount": 1.032,
        "leh_ohne_discount": 1.066,
        "sb_warenhaus": 1.05,
    },
    {
        "label": "Deutsche Markenbutter",
        "keywords": ["butter"],
        "exclude": ["buttermilch", "erdnussbutter", "kräuterbutter", "buttergebäck",
                     "butterkeks", "buttermischung", "butternut", "butterkäse",
                     "cookie", "keks"],
        "unit": "kg",
        "discount": 1.919 * 4,
        "leh_ohne_discount": 1.894 * 4,
        "sb_warenhaus": 1.814 * 4,
    },
    {
        "label": "Fruchtjoghurt, mind. 3,5% Fett",
        "keywords": ["joghurt"],
        "exclude": ["riegel", "alternative", "schokolade", "eis"],
        "unit": "kg",
        "discount": 0.347 * (1000 / 150),
        "leh_ohne_discount": 0.384 * (1000 / 150),
        "sb_warenhaus": 0.359 * (1000 / 150),
    },
    {
        "label": "Emmentaler",
        "keywords": ["emmentaler"],
        "exclude": [],
        "unit": "kg",
        "discount": None,  # keine Daten fuer 2024
        "leh_ohne_discount": 9.38,
        "sb_warenhaus": 9.43,
    },
    {
        "label": "Gouda, jung",
        "keywords": ["gouda"],
        "exclude": [],
        "unit": "kg",
        "discount": 13.63,
        "leh_ohne_discount": 8.80,
        "sb_warenhaus": 7.92,
    },
    {
        "label": "Weizenmischbrot",
        "keywords": ["mischbrot", "weizenbrot"],
        "exclude": [],
        "unit": "kg",
        "discount": 1.611,
        "leh_ohne_discount": 1.95,
        "sb_warenhaus": 1.602,
    },
    {
        "label": "Mehrkornbrot",
        "keywords": ["mehrkornbrot"],
        "exclude": [],
        "unit": "kg",
        "discount": 1.881 * (1000 / 750),
        "leh_ohne_discount": 2.001 * (1000 / 750),
        "sb_warenhaus": 1.803 * (1000 / 750),
    },
    {
        "label": "Haushaltszucker",
        "keywords": ["zucker"],
        "exclude": ["puderzucker", "traubenzucker", "vanillezucker", "zuckerguss",
                     "zuckerwatte", "konfitüre", "marmelade", "konfekt"],
        "unit": "kg",
        "discount": 1.255,
        "leh_ohne_discount": 1.282,
        "sb_warenhaus": 1.218,
    },
]

# Grobe Zuordnung Kette -> BMEL-Geschaeftstyp-Spalte.
STORE_TO_BMEL_COLUMN = {
    "ALDI SÜD": "discount",
    "Lidl": "discount",
    "EDEKA": "leh_ohne_discount",
    "REWE": "leh_ohne_discount",
    "Kaufland": "sb_warenhaus",
}


def match_bmel_reference(offer: dict) -> dict | None:
    """Versucht, ein Angebot einem der 15 BMEL-Referenzprodukte zuzuordnen.
    Gibt None zurueck, wenn kein Match, keine passende Einheit, oder fuer
    diese Kette/dieses Produkt kein Referenzwert vorliegt."""
    product = (offer.get("product") or "").lower()
    if not product:
        return None

    column = STORE_TO_BMEL_COLUMN.get(offer.get("store"))
    if not column:
        return None

    for item in BMEL_REFERENCE_ITEMS:
        if item["unit"] != offer.get("unit"):
            continue
        if not any(kw in product for kw in item["keywords"]):
            continue
        if any(ex in product for ex in item["exclude"]):
            continue
        value = item.get(column)
        if value is None:
            continue
        return {
            "normalPrice": round(value, 2),
            "normalPriceLabel": item["label"],
            "normalPriceYear": BMEL_YEAR,
        }
    return None
