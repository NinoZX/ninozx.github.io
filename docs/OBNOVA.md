# Obnova weba — ažurirano 24. 11. 2026.

## Sadržaj i izgled

- Pregledna naslovnica te zaseban pretraživ cjenik i arhiva. Poveznice `#home`, `#about`, `#reservations`, `#price-list`, `#gallery` i `#contact` ostaju podržane.
- Uvod „Kosa koja govori o vama”, telefonski poziv za termin, priča od 2002., četiri djelatnice, individualni pristup i stručne edukacije.
- Zasebna sekcija Eugène Perma Paris i Carmen Rituel: tri koraka rituala, dodatni podaci otvaraju se po želji.
- Topla svijetla podloga, tamni tekst, serifni naslovi i prigušeni brončani detalji. Postojeći logo i fotografije prostora dopunjeni su stvarnim fotografijama rada, tima i edukacija iz javnih Facebook objava salona. Porijeklo i način uporabe opisani su u [VIZUALI.md](VIZUALI.md); nisu dodane izmišljene fotografije tima ni recenzije.
- Broj telefona, adresa, vlasnica i Facebook sačuvani su iz postojećeg weba. Radno vrijeme usklađeno je s dostavljenim porukama, uključujući zatvoreno nedjeljom i blagdanima.
- Uklonjeni su slider, ovisnost o jQueryju i učitavanje starih dodataka. Stare datoteke ostaju u repozitoriju radi povratka/usporedbe, ali ih novi HTML ne učitava.
- Ispravljeni su jezik dokumenta, opisi slika, dimenzije, navigacija tipkovnicom i meta podaci. Dodani su HairSalon strukturirani podaci bez izmišljenih ocjena i cijena.

## Sadržajne korekcije

„24 godine iskustva” zamijenjeno je izrazom koji ne zastarijeva: „Od 2002.”. Uklonjena su ponavljanja i ispravljeni nepotpuni naslovi „UGÈNE”/„ALON”.

Aktualna [službena povijest brenda](https://eugene-perma-pro.myshopify.com/pages/fabrication-francaise) navodi 1919. godinu. Tvrdnja o 95 % prirodnog podrijetla označena je kao prosjek cjelokupnog [Carmen Rituel rituala](https://eugene-perma-pro.myshopify.com/collections/carmen-rituel). Sacha inchi i kokos povezani su s kremom, jojoba sa završnom njegom. Sačuvani su izrazi „do tri tona” i „do 100 %”, uz ograničenja, te napomena proizvođača da formula bez PPD-a ne isključuje alergijske reakcije.

## Podaci iz Neosalona

Uvezen je puni PDF cjenik iz Neosalona sa 108 stavki, prema odabiru vlasnika repozitorija. Svih 105 zajedničkih stavki CSV-a ima jednake aktualne i bazne iznose. Tri dodatne PDF stavke uključene su u objavu. Datum važenja potvrđen je kao 10.09.2026.; stvarno vrijeme pripreme/objave vodi se zasebno.

Stari desktop i mobilni cjenik nisu jednaki: četiri varijante bojanja imaju različite iznose. Oba izvora sačuvana su u strukturiranom povijesnom prijepisu. Nijedan stari iznos nije označen kao aktualan niti kao cijena na 10. 9. 2026.

Naslovnica vodi na `/cjenik/`, preuzimanje CSV-a i arhivu. Svaka usluga ima aktualnu i baznu cijenu, uz pretragu bez ovisnosti o dijakritici, kategorije i ispis. HTML, CSV i nepromjenjive arhivske kopije nastaju iz istog izvora u centima. Nema automatske veze s Neosalon API-jem: promjene se uvoze iz novih izvoza i objavljuju zajedno s webom. Detalji su u [CJENIK.md](CJENIK.md).

## Provjera prve verzije lokalnog prijedloga

- Pregled na širinama 320, 390, 768, 1024 i 1440 px: nema vodoravnog prelijevanja.
- Mobilni izbornik otvara se i zatvara; odabir stavke zatvara izbornik i vodi na odgovarajuću sekciju.
- Carmen Rituel dodatni tekst otvara se nativnim `details` elementom.
- Galerija otvara dijalog, Escape ga zatvara i vraća fokus na fotografiju.
- Nema neispravnih učitanih lokalnih slika ni prijavljenih JavaScript grešaka u pregledniku.
- Sitni naglašeni tekst potamnjen je radi kontrasta; podržano je smanjeno kretanje i vidljiv fokus.
- Bez JavaScripta izbornik je vidljiv, detalji rade, a fotografije se otvaraju izvornim poveznicama. Mobilno zaglavlje tada nije ljepljivo.

## Objava i daljnje provjere

Obnovljeni web i cjenik objavljeni su 24.11.2026. na GitHub Pagesu iz grane `master`. Cloudflare DNS je aktivan, delegacija spremljena, certifikat za glavnu domenu i `www` izdan te Enforce HTTPS uključen. Završna mrežna provjera preko uobičajenog sistemskog resolvera prošla je za tri CSV kopije, 108 parova cijena, arhivu i naslovnicu uz normalnu TLS provjeru, bez DNS zamjena. Sve kombinacije HTTP/HTTPS i glavne domene/`www` završavaju na HTTPS glavne domene uz HTTP 200.

Naslovnica se uspješno otvorila u pregledniku bez zaobilaženja upozorenja. Nema preostalih blokera za objavu; detalji provjere su u [DNS.md](DNS.md) i [PROVJERA.json](PROVJERA.json).

Pri budućoj izmjeni cijena uvesti novi izvoz, potvrditi promjene i objaviti ih do roka iz [CJENIK.md](CJENIK.md); stara izdanja ne brisati.
