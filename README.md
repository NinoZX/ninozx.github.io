# Salon Nina

Statična stranica Frizerskog salona Nina u Svetom Ivanu Zelini. Repozitorij `NinoZX/ninozx.github.io` koristi GitHub Pages, granu **master**, korijen repozitorija i domenu `salon-nina.hr`.

## Obnova i cjenik

Obnovljena verzija, objavljena 24.11.2026., sadrži novu naslovnicu, prilagođen mobilni prikaz, postojeći logo, fotografije salona, tekstove o timu i njezi, galeriju te kontakt za dogovor termina. Vlastiti CSS i mali JavaScript zamjenjuju staru temu i dodatke. Izvorne datoteke ostaju sačuvane.

Cjenik je preuzet iz dostavljenih **NeoSalon PDF/CSV izvoza**. Odabran je puni PDF sa **108 stavki**; svih 105 zajedničkih CSV stavki ima jednake aktualne i bazne iznose. Datum primjene **10. 9. 2026.** potvrđen je u razgovoru. Jedan JSON izvor služi za HTML, strojno čitljiv CSV i arhivu. Izvoz se preuzima i provjerava lokalno; nema automatskog spajanja na NeoSalon ni periodičkog preuzimanja podataka.

Objava se izvršava slanjem provjerenog izdanja u `master`. Prvo izdanje novog cjenika objavljeno je 24.11.2026.; prethodni neobjavljeni radni primjerak sačuvan je izvan repozitorija i nije dio javne arhive. Cloudflare DNS je aktivan, GitHubov certifikat je izdan i Enforce HTTPS uključen. Završna mrežna provjera prošla je preko uobičajenog sistemskog resolvera, bez DNS zamjena ili zaobilaženja TLS provjere; detalji su u [DNS uputama](docs/DNS.md).

## Lokalni pregled

Za prikaz weba nisu potrebni paketi ni build. Iz korijena repozitorija pokrenuti:

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Otvoriti `http://127.0.0.1:4173/` i `/cjenik/`. Poslužitelj se zaustavlja s Ctrl+C. Python **3.9+** potreban je za lokalne skripte cjenika, koje koriste standardnu biblioteku.

## Važne datoteke

- `index.html`, `css/salon.css`, `js/salon.js` — naslovnica, izgled i interakcije.
- `data/prices.json` — potvrđen izvor aktualnih i baznih cijena, nazivi, kategorije i podaci objave.
- `data/source-audit.json` — SHA-256 izvora, usporedba PDF-a i CSV-a, korekcije naziva i podrijetlo poslovnih podataka.
- `scripts/import_neosalon.py` — strogo ograničen uvoz poznatog NeoSalon izvoza.
- `scripts/build_prices.py`, `templates/price-page.html` — generiranje cjenika i nepromjenjive arhive.
- `cjenik/` — objavljeni HTML, stabilni CSV, imenovane CSV kopije i arhiva.
- [Cjenik](docs/CJENIK.md) — izvori, uvoz, priprema objave i održavanje.
- [Vizuali](docs/VIZUALI.md) i [pregled obnove](docs/OBNOVA.md) — podrijetlo fotografija i sadržajne odluke.

`data/prices-legacy.json` i `data/prices-draft.json` čuvaju prethodnu pripremu; ne koriste se za aktualni cjenik.

## Provjere i objava

```sh
node --check js/salon.js
node --check js/cjenik.js
python3 -m unittest discover -s tests -v
```

Testovi obuhvaćaju uvoz, preciznost centi, podudaranje izvora, HTML/CSV escaping i zaštitu arhive. Ručni pregled uključuje mobilni prikaz, navigaciju, galeriju, kategorije i pretraživanje cjenika te preuzimanje CSV-a.

Skripte ne rade commit, push ni deployment. Push/merge u `master` pokreće GitHub Pages; nakon njega treba zasebno provjeriti javne stranice, HTTPS i CSV. Lokalni manifest s oznakom `prepared` nije dokaz mrežne objave. `CNAME` ostaje `salon-nina.hr`.

Nakon objave pokrenuti `python3 scripts/verify_live.py`. Skripta provjerava TLS certifikat, javni HTML i sve tri CSV putanje prema lokalnom SHA-256, bez promjene podataka. Završna provjera 24.11.2026. prošla je i preko uobičajenog sistemskog resolvera uz normalnu TLS provjeru: tri CSV kopije, 108 parova cijena, arhiva i naslovnica. Sva četiri početna URL-a (`http`/`https`, s `www` i bez njega) završavaju na HTTPS glavne domene uz HTTP 200. Rezultati su zabilježeni u [DNS.md](docs/DNS.md) i [PROVJERA.json](docs/PROVJERA.json).

Izvorna licenca nalazi se u `LICENSE`; prethodne verzije weba ostaju u Git povijesti.
