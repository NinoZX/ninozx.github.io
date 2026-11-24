# Domena i HTTPS

## Stanje provjereno 24. 11. 2026.

Obnovljeni web i cjenik objavljeni su na GitHub Pagesu. DNS je premješten na Cloudflare, zona je **Active**, a u registru domene spremljeni su poslužitelji `chris.ns.cloudflare.com` i `hera.ns.cloudflare.com`. Delegacija je potvrđena na `.hr` poslužiteljima i putem Googleova javnog DNS-a. Domena je produžena do **24. 11. 2027.**

GitHub Pages API za `NinoZX/ninozx.github.io` potvrđuje:

- `status`: `built`; izvor `master`, korijen `/`
- `cname`: `salon-nina.hr`; `html_url`: `https://salon-nina.hr/`
- `https_enforced`: `true`
- certifikat `approved` za `salon-nina.hr` i `www.salon-nina.hr`, vrijedi do **22. 2. 2027.**

Ponovno povezivanje iste custom domene radi izdavanja certifikata stvorilo je GitHubove commitove za uklanjanje i vraćanje `CNAME`; domena je ostala `salon-nina.hr`. Pregledani HEAD nakon tih promjena je `2519ea7e2b5e60e77dc6b3a4deda62fbbd9adffc`.

## DNS zona

Svih **11 zapisa** ima TTL **300** i postavku **DNS only**, bez Cloudflare proxyja. Četiri A zapisa usmjeravaju glavnu domenu na GitHub Pages:

```text
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

| Naziv | Vrsta | Vrijednost |
| --- | --- | --- |
| `www` | CNAME | `ninozx.github.io.` |
| `@` | MX, prioritet 10 | `sm3.mojsite.com.` |
| `@` | TXT | `v=spf1 a mx include:mojsite.com ~all` |
| `_dmarc` | TXT | `v=DMARC1; p=none; adkim=r; aspf=r;` |
| `autoconfig` | CNAME | `adr.plus.hr.` |
| `autodiscover` | CNAME | `adr.plus.hr.` |
| `mail` | CNAME | `sm3.mojsite.com.` |

Postojeći zapisi povezani s poštom sačuvani su. DNS zapisima sada se upravlja u Cloudflareu; delegacijom i produženjem domene na `domene.hr`. Custom domain u [GitHub Pages postavkama](https://github.com/NinoZX/ninozx.github.io/settings/pages) i datoteka `CNAME` ostaju `salon-nina.hr`.

## Završna mrežna provjera

TLS provjera na sve četiri nove GitHubove IP adrese vratila je HTTP 200 uz normalnu provjeru certifikata i naziva domene. `verify_live.py`, uz razrješavanje adrese preko aktualnog javnog DNS-a `1.1.1.1`, potvrdio je SHA-256 stabilnog, imenovanog i arhivskog CSV-a, svih **108 parova cijena**, arhivske poveznice i poveznicu s naslovnice. TLS provjera nije isključena; hostname je ostao `salon-nina.hr`.

Sva četiri početna URL-a (`http`/`https`, s `www` i bez njega) završila su na `https://salon-nina.hr/` uz HTTP 200. `http://www.salon-nina.hr/` prvo prelazi na HTTP glavne domene, zatim na HTTPS. Nijedno HTTPS preusmjeravanje ne vraća se na HTTP.

**Završna provjera prošla je i putem uobičajenog sistemskog resolvera**, bez zamjene DNS adresa i bez isključivanja TLS provjere. Običan poziv `verify_live.py` potvrdio je tri CSV kopije, 108 parova cijena, arhivu i naslovnicu. Sva četiri početna URL-a i preko normalnog DNS-a završila su na HTTPS glavne domene uz HTTP 200 i uspješnu provjeru certifikata. Naslovnica se otvorila u pregledniku bez zaobilaženja upozorenja. Nema preostalog blokera zbog lokalne DNS predmemorije.

Tijekom ranije faze migracije lokalni je resolver privremeno vraćao stare adrese `192.30.252.153` i `192.30.252.154`, pa je početna provjera tada pala. To je povijesni rezultat; kasnija završna provjera prošla je.

Za ponovnu provjeru nakon budućih objava pokrenuti:

```sh
python3 scripts/verify_live.py
```

Skripta ne mijenja manifest ni datoteke. Lokalni zapis mrežne provjere je `salon-nina-https-provjera-2026-11-24.json`, sačuvan izvan repozitorija; sažetak je u [PROVJERA.json](PROVJERA.json). Povijesni manifesti cjenika ostaju nepromijenjeni.

Prije migracije, 23. 11. 2026., domena je koristila `dns1.idoneus.hr` i `dns2.idoneus.hr`, stare A adrese te nije imala ispravan HTTPS. To je prethodno stanje, a ne aktualna konfiguracija. Za buduće poteškoće koristiti [GitHubove upute za custom domene](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site) i [otklanjanje problema](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages).
