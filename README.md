# Salon Nina

Statična stranica Frizerskog salona Nina u Svetom Ivanu Zelini. Repozitorij `NinoZX/ninozx.github.io` koristi GitHub Pages, granu **master**, korijen repozitorija i domenu `salon-nina.hr`.

## Obnova i cjenik

Grana `codex/salon-nina-refresh` sadrži obnovljenu naslovnicu, prilagođen mobilni prikaz, postojeći logo, fotografije salona, tekstove o timu i njezi, galeriju te kontakt za dogovor termina. Vlastiti CSS i mali JavaScript zamjenjuju staru temu i dodatke. Izvorne datoteke ostaju sačuvane.

Cjenik je preuzet iz dostavljenih **NeoSalon PDF/CSV izvoza**. Odabran je puni PDF sa **108 stavki**; svih 105 zajedničkih CSV stavki ima jednake aktualne i bazne iznose. Datum primjene **10. 9. 2026.** potvrđen je u razgovoru. Jedan JSON izvor služi za HTML, strojno čitljiv CSV i arhivu. Izvoz se preuzima i provjerava lokalno; nema automatskog spajanja na NeoSalon ni periodičkog preuzimanja podataka.

Objava se izvršava slanjem provjerenog izdanja u `master`. Prvo izdanje novog cjenika pripremljeno je za 24.11.2026.; jučerašnji neobjavljeni radni primjerak sačuvan je izvan repozitorija i nije dio javne arhive. DNS i HTTPS domene dovršavaju se zasebno prema [DNS uputama](docs/DNS.md).

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
- `cjenik/` — pripremljeni HTML, stabilni CSV, imenovane CSV kopije i arhiva.
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

Nakon objave pokrenuti `python3 scripts/verify_live.py`. Skripta provjerava TLS certifikat, javni HTML i sve tri CSV putanje prema lokalnom SHA-256, bez promjene podataka. Provjera 23.11.2026. nije prošla: certifikat domene ne odgovara nazivu `salon-nina.hr`.

Izvorna licenca nalazi se u `LICENSE`; prethodne verzije weba ostaju u Git povijesti.
