# Domena i HTTPS

## Ponovno provjereno 23. 11. 2026.

GitHub Pages API za `NinoZX/ninozx.github.io` vraća:

- `source.branch`: `master`; `source.path`: `/`
- `cname`: `salon-nina.hr`
- `html_url`: `http://salon-nina.hr/`
- `https_enforced`: `false`; `https_certificate`: `null`

`salon-nina.hr` vraća A zapise `192.30.252.153` i `192.30.252.154`. Za `www.salon-nina.hr` nije pronađen DNS zapis. HTTP radi, a HTTPS za glavnu domenu vraća pogrešku nepodudaranja naziva certifikata. To nije popravljeno ovom lokalnom izmjenom koda.

Autoritativni DNS poslužitelji su `dns1.idoneus.hr` i `dns2.idoneus.hr`. Zapise treba urediti u DNS zoni kod pružatelja koji održava te poslužitelje. Promjena HTML-a ili datoteke `CNAME` ne popravlja DNS. GitHub prijava radi; udaljeni `master` još je na izvornom commitu `ebc1d44`.

## Koraci uz pristup DNS postavkama

Prema [službenim uputama GitHuba](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site), A zapise glavne domene treba zamijeniti aktualnim GitHub Pages adresama:

```text
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

Za `www` dodati CNAME koji pokazuje na `ninozx.github.io`. Postojeća Custom domain postavka i datoteka `CNAME` ostaju `salon-nina.hr`.

Ne mijenjati MX i TXT zapise pošte. Ako postoje AAAA zapisi za drugi hosting, treba ih ukloniti ili zamijeniti aktualnim GitHub Pages IPv6 zapisima iz službene dokumentacije. Postavke repozitorija: [Settings → Pages](https://github.com/NinoZX/ninozx.github.io/settings/pages).

Nakon propagacije zapisa u GitHub Settings → Pages provjeriti DNS i izdavanje certifikata, pa uključiti **Enforce HTTPS** kada opcija postane dostupna. Ako izdavanje ne krene, slijediti [GitHubove upute za otklanjanje problema](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages). Na kraju provjeriti HTTPS za domenu i preusmjeravanje `www`.

Nisu mijenjani DNS, Pages postavke ni javna stranica. Novi canonical/Open Graph/strukturirani URL-ovi već koriste HTTPS, pa je ispravak certifikata dio dovršetka prije objave.
