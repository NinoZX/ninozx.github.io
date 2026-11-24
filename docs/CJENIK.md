# Cjenik iz NeoSalona

## Izvor i provjera

`data/prices.json` sadrži **108 stavki iz punog PDF-a** `neo962007_izlistaj_cjenik.pdf`. Svih **105 stavki** iz `cjenik-usluge-20261117-1404.csv` podudara se s PDF-om po aktualnoj i baznoj cijeni. Samo PDF sadrži pletenicu (3,00 €), rezanje šiški (3,00 €) i poklon bon (14,00 €); korisnik je potvrdio uključivanje svih stavki.

Za svaku stavku aktualni i bazni iznos trenutačno su jednaki. Referentni datum je **10. 9. 2026.**, a korisnik je isti datum potvrdio kao početak primjene cjenika. To nije datum mrežne objave. PDF je izrađen 16. 11. 2026.; datum u nazivu CSV-a nije korišten kao dokaz datuma primjene.

`data/source-audit.json` čuva nazive i SHA-256 izvornih datoteka, rezultat usporedbe, tri dodatne PDF stavke, razlike naziva i promjene prikaznog teksta. Ispravljeni su očiti tipfeleri, dijakritika i oblikovanje naziva; iznosi nisu promijenjeni. `source_name` ostaje izvorni naziv, a ID-evi `service001`–`service108` očuvaju se pri ponovnom uvozu postojećeg izvora.

MBO **97550876** preuzet je iz [CompanyWalla](https://www.companywall.hr/tvrtka/frizerski-salon-nina--vl-nikolina-brlecic-bukal--sv-ivan-zelina--trg-ante-starcevica-5/MMCbleiY), uz podudaranje naziva, vlasnice, adrese i telefona. To je sekundarni izvor: primarni registar vratio je `Request Rejected`, pa službeni izvadak nije preuzet. Trag provjere je u auditu. Osobni OIB nije potreban ovom izvoru cjenika.

## Uvoz

Importer je prilagođen poznatom izvozu: zaglavlje je dodatno omotano navodnicima, a deset naziva sadrži neograđene zareze. Razdvaja zadnja četiri zareza, strogo provjerava zaglavlje i iznose te odbija neprazna promotivna polja koja zahtijevaju zaseban pregled. Nije opći popravljač proizvoljnog CSV-a.

Provjereni PDF retci nalaze se u radnoj datoteci `../../work/neosalon/pdf-rows.json`, izvan repozitorija. Ponovljiv uvoz dostavljenih izvora u **zaseban radni nacrt**:

```sh
python3 scripts/import_neosalon.py \
  ~/Downloads/cjenik-usluge-20261117-1404.csv \
  --pdf ~/Downloads/neo962007_izlistaj_cjenik.pdf \
  --pdf-rows ../../work/neosalon/pdf-rows.json \
  --output ../../work/neosalon/prices-import.json \
  --audit ../../work/neosalon/source-audit.json
```

PDF je u ovom pozivu puni izvor. Importer odbija razlike iznosa i CSV stavke kojih nema u PDF-u. Bez `--pdf-rows` uvozi samo CSV. Izrada provjerenog JSON-a iz PDF-a prethodi uvozu; importer sam ne čita PDF tablice. Ne prepisuje postojeći izvor sa statusom `confirmed`.

Za novi izvoz ponovno pregledati podatke, datum primjene i audit prije zamjene `data/prices.json`; postojeće potvrde i datume ne prenositi automatski. Nema NeoSalon API integracije, rasporeda preuzimanja ni automatske objave.

## Format podataka

Izvor koristi `schema_version: 2`, valutu `EUR` i cijene kao **cijele brojeve centi**. Prikazni nazivi uključuju duljinu kose, a stavke su raspoređene u sedam kategorija.

| Polje | Namjena |
| --- | --- |
| `status` | `confirmed` za pripremu objave; `draft`/`preview` samo za radni pregled |
| `effective_date`, `reference_date` | Datum primjene i referentni datum; trenutačno oba `2026-09-10` |
| `confirmed_by`, `confirmed_on` | Trag potvrde sadržaja |
| `trader` | Naziv obrta, `identifier_type: mbo` i matični broj kao tekst |
| `outlet` | Tip, grad, adresa i opseg cjenika |
| `publication_sequence` | Rastući broj; novi broj za svaki promijenjeni skup podataka |
| `published_at` | Planirano vrijeme stvarne mrežne objave s vremenskom zonom; nije datum primjene |
| `items[].current_price_cents` | Redovna aktualna cijena u centima |
| `items[].reference_price_cents` | Potvrđena bazna cijena u centima |
| `items[].promotion` | `null` ili objekt `{"name": "…", "price_cents": 1234}`; posebna cijena ne smije biti viša od redovne |

Za jedan javno poznat salon koristi se `outlet.scope: "all"`, odnosno isti cjenik za sva prodajna mjesta. Time se u nazivu datoteke koristi `ZA_SVA_PRODAJNA_MJESTA`; oznaka pojedinog objekta nije izmišljena i `outlet.code` ostaje `null`. Ako se opseg poslovanja promijeni, treba ponovno odabrati opseg cjenika. Za `scope: "single"` generator zahtijeva oznaku objekta.

## Radni pregled i priprema objave

Svi pozivi izvode se iz korijena repozitorija. Za označen radni HTML/CSV, bez izrade arhive:

```sh
python3 scripts/build_prices.py data/prices.json \
  --preview --output ../../work/cjenik-preview
```

Pregled mora biti u mapi `work/` izvan javnog repozitorija. Njegov manifest ima `production_ready: false`.

Za lokalnu pripremu potvrđene objave:

```sh
python3 scripts/build_prices.py data/prices.json --output cjenik
```

Prije prve pripreme postaviti `published_at` na planirano vrijeme stvarne objave toga dana. Nova arhiva smije imati samo današnji datum u `Europe/Zagreb`; skripta ne izmišlja ranije mrežne objave. Za sljedeću izmjenu povećati `publication_sequence` i navesti kasnije vrijeme. Ako prva objava kasni na drugi dan, neobjavljeni radni primjerak sačuvati izvan javnog repozitorija i pripremiti prvo stvarno izdanje s novim datumom. Već objavljene arhive ne prepisivati. Tako je neobjavljeni primjerak od 23.11. zamijenjen pripremom prve objave 24.11.2026.

Generator odbija nepotvrđene izvore, nedostajuće ili nevaljane cijene, ponovljene stavke, ponovno korištenje broja za drugi sadržaj i povratak na stariji broj. Prije nove pripreme provjerava sažetke svih arhiva i imenovanih CSV kopija. Ponovno generiranje istog izvora zadržava postojeću arhivu nepromijenjenom.

## Generirane datoteke

- `cjenik/index.html` — pregled po kategorijama, pretraživanje i preuzimanje; cijene su dostupne i bez JavaScripta.
- `cjenik/cjenik.csv` — stalni URL aktualnog strojno čitljivog cjenika.
- `cjenik/<puni-naziv>.csv` — dodatna fizička kopija s punim nazivom, sačuvana nakon sljedećih izmjena.
- `cjenik/cjenik-fragment.html` — generirani HTML tablica; naslovnica povezuje samostalni `/cjenik/`.
- `cjenik/arhiva/index.html` — popis sačuvanih verzija.
- `cjenik/arhiva/<broj>-<sažetak>/` — nepromjenjivi HTML, CSV, JSON, fragment i manifest te verzije.
- `cjenik/manifest.json` — lokalni zapis pripreme, naziva datoteke i SHA-256; `status: prepared`, `deployment_verified: false`.

Za odabrani opseg puni CSV naziv ima oblik `97550876_ZA_SVA_PRODAJNA_MJESTA_usluge_<broj06>_<GGGGMMDD_SSMM>.csv`. Vrijeme u nazivu preračunava se u `Europe/Zagreb`, uključujući ljetno računanje vremena.

CSV koristi UTF-8, **točku-zarez**, navodnike oko svih polja te decimalnu točku s dvije decimale. Stupci su `naziv_usluge`, `maloprodajna_cijena`, `posebni_oblik_prodaje`, `naziv_posebnog_oblika_prodaje`, `bazna_cijena`, `redovna_maloprodajna_cijena`, `datum_bazne_cijene`. Prikazana maloprodajna cijena uzima posebnu cijenu kada postoji; redovna i bazna ostaju zasebno dostupne. Stupci za robu poput količine, marke i barkoda nisu dio ovog cjenika usluga.

Glavno preuzimanje koristi stalni `cjenik.csv` i HTML atribut `download` s punim nazivom. Dodatna poveznica vodi izravno na imenovanu kopiju. GitHub Pages ne omogućuje podešavanje odgovarajućeg `Content-Disposition` zaglavlja za stalni alias; ponašanje naziva preuzimanja zato ovisi i o pregledniku. Ovo je tehnička izvedba, bez tvrdnje da predstavlja službeno tumačenje kombinacije stalnog URL-a i propisanog naziva datoteke.

## Održavanje i pravila objave

Od **17. 11. 2026.** vrijede završni pravilnici. Za usluge je referentni datum 10. 9. 2026., a bazna cijena prikazuje se uz aktualnu cijenu iste usluge. [NN 132/2026-1583, čl. 3. i 6.](https://narodne-novine.nn.hr/clanci/sluzbeni/2026_11_132_1583.html)

Izmijenjeni cjenik objavljuje se do **11:00 na dan izmjene**. Prethodni mora ostati dostupan najmanje **15 dana od zamjene novim cjenikom**, a ne od prvotne objave. Propis navodi CSV/XML, stalni URL zamijenjene datoteke, UTF-8 i točku-zarez te sadržaj i naziv datoteke. [NN 132/2026-1584, čl. 3. i 6.](https://narodne-novine.nn.hr/clanci/sluzbeni/2026_11_132_1584.html)

Skripta arhive i imenovane kopije **ne briše automatski** i ne upravlja vremenom objave. Lokalni build ne dokazuje da je datoteka bila javno dostupna. Nakon odobrene GitHub Pages objave treba provjeriti HTTPS, `/cjenik/`, stalni CSV, imenovanu kopiju i arhivu. Ne mijenjati povijesne manifeste da bi se lokalna priprema prikazala kao ranija javna objava.

```sh
python3 -m unittest discover -s tests -v
```

Testovi pokrivaju uvoz i iznose, neispravan CSV, razlike izvora, stabilne ID-eve, promocije, datume, escaping, oblik izlaza i zaštitu arhive. Stari `prices-legacy.json` i `prices-draft.json` nisu izvor novih cijena.

Nakon objave: `python3 scripts/verify_live.py`. Provjerava TLS, javne CSV sažetke, HTML cijene i arhivske poveznice prema pripremljenom izdanju. Ako provjera ne prođe, ne proglašavati izdanje uspješno objavljenim.

Pri dodavanju usluga koje prvi put ulaze u ponudu nakon 10.09.2026. treba proširiti validaciju i prikaz referentnog datuma po stavci. Trenutačni generator namjerno prihvaća samo potvrđeni referentni datum ovih 108 stavki, kako datum nove usluge ne bi prešutno zamijenio povijesnim datumom.
