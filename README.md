# Angebote Einkaufen — Poing

Lokale HTML-Seite, die aktuelle Supermarkt-Angebote in Poing (PLZ 85586) von
**EDEKA, REWE, ALDI SÜD, Lidl und Kaufland** an einem Ort zusammenfasst, damit
man Preise leichter vergleichen kann. Kaufland (Burgerfeld 8, 85570 Markt
Schwaben) läuft über denselben Poing-Suchradius mit, da marktguru dafür keinen
separaten Zip-Code braucht.

## Nutzung

### Mit Docker (empfohlen — kein lokales Python nötig)

```
docker compose up -d           # Seite + automatischer Auto-Refresh starten
# -> http://localhost:8000/Angebote%20Poing.dc.html
docker compose down             # alles stoppen
```

Das startet zwei Container:
- **`web`** — serviert die Seite auf Port 8000.
- **`scheduler`** — holt automatisch neue Angebote, standardmäßig alle 24h
  (`FETCH_INTERVAL_SECONDS`, siehe unten), läuft dauerhaft im Hintergrund.
  Kein Cron/System-Scheduler nötig, das übernimmt eine simple Schleife im
  Container.

Alle Container teilen sich per Bind-Mount denselben Ordner — Daten landen
ganz normal in `data.js`/`data/`, kein Docker-Volume-Umweg.

Intervall anpassen (z.B. alle 6h statt taeglich):
```
FETCH_INTERVAL_SECONDS=21600 docker compose up -d
```
oder dauerhaft in einer `.env`-Datei im selben Ordner:
```
FETCH_INTERVAL_SECONDS=21600
```

Manueller Sofort-Abruf, ohne auf den Scheduler zu warten:
```
docker compose --profile fetch run --rm fetch
```

### Ohne Docker

1. Angebote aktualisieren (holt aktuelle Daten, dauert ca. 30–60s):
   ```
   python3 fetch_angebote.py
   ```
2. `Angebote Poing.dc.html` öffnen. Die Seite lädt `data.js` per `fetch()`,
   das braucht einen lokalen Server statt Doppelklick (`file://` blockiert
   `fetch` im Browser):
   ```
   python3 -m http.server
   ```
   dann `http://localhost:8000/Angebote%20Poing.dc.html` aufrufen.

### Beide Varianten

Zwei Ansichten oben in der Seite:
   - **Alle Angebote**: durchsuchbare/filterbare Liste, gruppiert nach
     Kalenderwoche (ein Angebot erscheint in jeder Woche, in der es
     tatsächlich gültig ist) oder nach Abteilung (Obst & Gemüse, Fleisch &
     Wurst, Konserven & Fertiggerichte, …).
   - **Preisvergleich**: Produkte, die bei ≥2 Ketten im Angebot sind,
     nebeneinander. Verglichen wird nach **Grundpreis** (€ pro kg/l/Stück),
     nicht nach Packungspreis, damit unterschiedliche Packungsgrößen fair
     vergleichbar bleiben (z.B. 250g- vs. 400g-Packung Butter). Angebote mit
     unterschiedlicher Einheit (z.B. €/kg vs. €/Stück) werden dafür nicht
     gemischt.

Die Seite matcht Produkte über den von marktguru vergebenen generischen
Produktnamen (z.B. "H-Milch" bei EDEKA und REWE) — keine eigene
Fuzzy-Text-Erkennung, daher können vereinzelt sehr unterschiedlich
benannte, eigentlich identische Produkte nicht zusammengeführt werden.

## Datenquelle

`fetch_angebote.py` nutzt die inoffizielle Such-API von marktguru.de
(`api.marktguru.de/api/v1/offers/search`), die keinen "alle Angebote einer
PLZ"-Endpunkt hat, sondern zwingend einen Suchbegriff verlangt. Das Script
fragt deshalb eine Liste typischer Supermarkt-Kategorien ab (Obst, Milch,
Fleisch, Getränke, Drogerie, …) und dedupliziert die Treffer.

**Hinweis:** Diese API ist nicht offiziell dokumentiert/unterstützt und kann
sich jederzeit ändern (Endpoint, Keys, Struktur). Falls `fetch_angebote.py`
irgendwann Fehler wirft oder leere Ergebnisse liefert, ist das der
wahrscheinlichste Grund.

## Dateien

- `fetch_angebote.py` — holt & normalisiert Angebote, schreibt
  `data/angebote.json` (Rohdaten) und `data.js` (von der Seite geladen).
- `bmel_reference.py` — amtliche Referenzpreise für 15 Grundprodukte (siehe
  unten), wird von `fetch_angebote.py` importiert.
- `data/history/` — datierte Snapshots für die Normalpreis-Berechnung aus
  eigener Historie (siehe unten), wird von `fetch_angebote.py` geschrieben.
- `data/known_products.json` — Registry mit dem letzten bekannten Grundpreis
  pro Kette+Produkt, unbegrenzt aufbewahrt (siehe "Grundpreis nach
  Angebotsende" unten), wird von `fetch_angebote.py` geschrieben.
- `Angebote Poing.dc.html` + `support.js` — die eigentliche Vergleichsseite
  (Design-Canvas-Komponente, ersetzt die alte `index.html`/`app.js`/
  `style.css`-Version). `support.js` ist die Laufzeit-Bibliothek dafür, nicht
  von Hand bearbeiten.
- `data.js` — generiert, nicht von Hand bearbeiten (wird bei jedem Lauf von
  `fetch_angebote.py` überschrieben), wird von `Angebote Poing.dc.html` per
  `fetch("./data.js")` geladen (siehe Hinweis zum lokalen Server oben).
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` — Docker-Setup (siehe
  oben), baut nur die Python-Umgebung (`requests`); der Code kommt per
  Bind-Mount aus diesem Ordner, kein Rebuild bei Code-Änderungen nötig.
  `docker-compose.yml` enthält 3 Services: `web` (Seite), `scheduler`
  (automatischer Auto-Refresh, dauerhaft), `fetch` (einmaliger manueller
  Abruf, eigenes Profil). Optionale `.env`-Datei fuer `FETCH_INTERVAL_SECONDS`.

## Automatisierung

Mit Docker läuft die Aktualisierung automatisch über den `scheduler`-Service
(siehe oben). Ohne Docker muss `fetch_angebote.py` weiterhin manuell oder per
eigenem Cronjob/Claude Codes `/loop`-Skill erneut ausgeführt werden.

## Normale Preise (kein Wochenangebot)

Zwei direkte Ansätze sind gescheitert (siehe Verlauf): REWE-Regalpreise per
Playwright scrapen (Cloudflare-Bot-Schutz erkennt die Automatisierung selbst,
unabhängig von Browser/Maschine) und preisrunter.de (führt für Deutschland
praktisch nur Drogerien wie dm/Müller, keine der 5 Ketten hier). Stattdessen
gibt es jetzt zwei "Normalpreis"-Hinweise direkt in den Angebotskarten, wo
verfügbar:

1. **`oldPrice`** (marktguru liefert das bei ca. 7% der Angebote mit) — der
   tatsächliche durchgestrichene Ursprungspreis, exakt.
2. **BMEL-Referenz** (`bmel_reference.py`) — für 15 Alltagsprodukte (Milch,
   Butter, Brot, Eier, Käse, Fleisch, Kartoffeln, Äpfel, Zucker) amtlicher
   Jahresdurchschnittspreis 2024 nach Geschäftstyp (AMI-Verbraucherpreispanel/
   GfK, via bmel-statistik.de), passend zur Kette zugeordnet (Discounter für
   ALDI SÜD/Lidl, LEH ohne Discount für EDEKA/REWE, SB-Warenhaus für
   Kaufland). Nur ein grober bundesweiter Richtwert, kein Filialpreis.
3. **Eigene Preishistorie** (`data/history/`) — `fetch_angebote.py` schreibt
   bei jedem Lauf einen datierten Snapshot. Sobald für ein Produkt+Kette
   mindestens `MIN_HISTORY_SNAPSHOTS` (Standard: 3) Tages-Snapshots vorliegen,
   wird der Median-Grundpreis als "üblicher Preis" angezeigt — deckt
   perspektivisch alle Produkte ab, braucht aber ein paar Wochen/Monate
   gesammelte Läufe, um aussagekräftig zu werden. Geht vor der BMEL-Referenz,
   wenn beides vorliegt.

`data/history/` wächst mit jedem Lauf (ein kleines JSON pro Tag) - bei
Bedarf irgendwann alte Snapshots aufräumen.

## Grundpreis nach Angebotsende

Wenn ein Angebot bei marktguru nicht mehr auftaucht (Aktion beendet), fällt
der Grundpreis dafür nicht mehr einfach weg: `fetch_angebote.py` merkt sich
in `data/known_products.json` pro Kette+Produkt den letzten bekannten
Grundpreis dauerhaft. Ist ein Produkt in einem Lauf nicht mehr unter den
aktiven Angeboten, wird stattdessen ein schlanker Eintrag ohne Angebotspreis
in `data.js` ausgegeben (nur `referencePrice`/`unit`), den die Seite als
eigene Karte mit Badge "nur Grundpreis" und reduzierter Deckkraft zwischen
den aktuellen Angeboten anzeigt (auch wenn "Nur aktuell gültige" aktiv ist –
das betrifft nur echte Angebote, nicht diese Grundpreis-Referenzen). Fließt
nicht in den Preisvergleich (Compare-Ansicht) ein, um nicht alte mit
aktuellen Preisen zu vermischen. Wird unbegrenzt aufbewahrt, bis wieder ein
echtes Angebot für dasselbe Produkt+Kette kommt (dann wird der Eintrag
automatisch wieder normal).

## Rabatt-% gegenüber dem Grundpreis

Marktguru liefert nur bei ca. 7% der Angebote einen `oldPrice` (den echten,
bestätigten Rabatt). Für den Rest berechnet `fetch_angebote.py` einen
geschätzten Rabatt, indem der aktuelle Grundpreis mit der besten verfügbaren
Referenz verglichen wird (eigene Preishistorie vor BMEL-Referenz, je
nachdem was vorliegt) — nur wenn kein echter `oldPrice` da ist, und nur bei
mindestens 1% Unterschied. Erscheint als eigenes, anders eingefärbtes Badge
("−12% ggü. hist. Ø" / "−12% ggü. BMEL-Ø"), um es klar von echten,
marktguru-bestätigten Rabatten zu unterscheiden — das ist eine Schätzung
gegen unsere eigene Referenz, keine offizielle Angabe.

## Angebote sind klickbar

Jede Karte verlinkt auf `https://www.marktguru.de/offers/{id}` (marktguru
selbst mitgeliefert), öffnet in neuem Tab. Gilt nur für echte, aktuell
laufende Angebote — die "nur Grundpreis"-Einträge (siehe oben) haben keine
gültige Angebots-ID mehr und sind daher nicht klickbar.
