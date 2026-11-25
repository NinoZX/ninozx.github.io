#!/usr/bin/env python3
"""Prepare schema-2 price-list artifacts locally; never deploy or fabricate history."""

import argparse
from collections import OrderedDict
import csv
from datetime import date, datetime
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://salon-nina.hr"
SERVICE_PATH = "/usluge/balayage-i-pramenovi/"
ZAGREB = ZoneInfo("Europe/Zagreb")
REFERENCE_DATE = "2026-09-10"
ARCHIVE_PATTERN = re.compile(r"\d{6,}-[a-f0-9]{16}")
CSV_COLUMNS = ("naziv_usluge", "maloprodajna_cijena", "posebni_oblik_prodaje",
               "naziv_posebnog_oblika_prodaje", "bazna_cijena",
               "redovna_maloprodajna_cijena", "datum_bazne_cijene")


class PriceError(ValueError):
    pass


def required_text(value, field):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise PriceError(f"{field}: potreban je neprazan tekst bez kontrolnih znakova.")
    return value


def valid_date(value, field):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise PriceError(f"{field} mora biti datum YYYY-MM-DD.") from None


def publication_time(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})", value):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise PriceError("published_at mora biti ISO datum i vrijeme s vremenskom zonom, bez djelića sekunde.") from None


def cents(value, field):
    if type(value) is not int or value < 0:
        raise PriceError(f"{field} mora biti nenegativan cijeli broj centi.")
    return value


def normalize(value):
    value = value.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", normalize(value)).strip("-")


def _validate(data, preview=False):
    if not isinstance(data, dict):
        raise PriceError("Cjenik mora biti JSON objekt.")
    allowed = {"draft", "preview", "confirmed"} if preview else {"confirmed"}
    if data.get("status") not in allowed:
        raise PriceError("Objava zahtijeva status 'confirmed'; draft i legacy nisu objava.")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 2 or data.get("currency") != "EUR":
        raise PriceError("Podržani su schema_version 2 i valuta EUR.")
    if data.get("reference_date") != REFERENCE_DATE:
        raise PriceError(f"reference_date mora biti {REFERENCE_DATE}.")
    effective = None
    for key in ("effective_date", "confirmed_on"):
        if not (preview and data.get(key) is None):
            parsed = valid_date(data.get(key), key)
            if key == "effective_date":
                effective = parsed
    if effective is not None and effective < valid_date(REFERENCE_DATE, "reference_date"):
        raise PriceError("Datum primjene ne može prethoditi referentnom datumu.")
    if not (preview and data.get("confirmed_by") is None):
        required_text(data.get("confirmed_by"), "confirmed_by")
    trader = data.get("trader")
    if not isinstance(trader, dict):
        raise PriceError("Nedostaju podaci trader.")
    required_text(trader.get("name"), "trader.name")
    if trader.get("identifier_type") not in {"mbo", "oib"}:
        raise PriceError("trader.identifier_type mora biti mbo ili oib.")
    if not (preview and trader.get("identifier") is None):
        if not isinstance(trader.get("identifier"), str) or not re.fullmatch(r"[0-9]+", trader["identifier"]):
            raise PriceError("trader.identifier mora biti tekst sastavljen samo od znamenki.")
    outlet = data.get("outlet")
    if not isinstance(outlet, dict):
        raise PriceError("Nedostaju podaci outlet.")
    if outlet.get("scope", "single") not in {"single", "all"}:
        raise PriceError("outlet.scope mora biti single ili all.")
    for key in ("type", "city", "address", "code"):
        if key == "code" and (outlet.get("scope") == "all" or (preview and outlet.get(key) is None)):
            continue
        required_text(outlet.get(key), f"outlet.{key}")
        if not slug(outlet[key]):
            raise PriceError(f"outlet.{key} nije moguće pretvoriti u naziv datoteke.")
    sequence = data.get("publication_sequence")
    if not (preview and sequence is None):
        if type(sequence) is not int or sequence < 1:
            raise PriceError("publication_sequence mora biti pozitivan cijeli broj.")
    published = None
    if not (preview and data.get("published_at") is None):
        published = publication_time(data.get("published_at"))
        publication_day = published.astimezone(ZAGREB).date()
        if effective is not None and effective > publication_day:
            raise PriceError("Datum primjene ne može biti nakon planirane objave aktualnog cjenika.")
        if data.get("confirmed_on") is not None and valid_date(data["confirmed_on"], "confirmed_on") > publication_day:
            raise PriceError("Datum potvrde ne može biti nakon planirane objave.")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise PriceError("Cjenik mora sadržavati barem jednu uslugu.")
    ids, names, categories, category_labels = set(), set(), {}, {}
    for item in items:
        if not isinstance(item, dict):
            raise PriceError("Svaka stavka mora biti JSON objekt.")
        for key in ("id", "name", "source_name", "category", "category_id"):
            required_text(item.get(key), key)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", item["id"]):
            raise PriceError("ID stavke sadrži nedopuštene znakove.")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item["category_id"]):
            raise PriceError("category_id mora biti slug od malih slova, znamenki i crtica.")
        name = item["name"].strip().casefold()
        if item["id"] in ids or name in names:
            raise PriceError(f"Duplicirana stavka: {item['id']}.")
        ids.add(item["id"])
        names.add(name)
        category_id, category = item["category_id"], item["category"]
        if categories.get(category_id, category) != category or category_labels.get(category, category_id) != category_id:
            raise PriceError("Identifikator i naziv kategorije moraju biti jednoznačni.")
        categories[category_id], category_labels[category] = category, category_id
        cents(item.get("current_price_cents"), "current_price_cents")
        cents(item.get("reference_price_cents"), "reference_price_cents")
        if item.get("reference_date") != data["reference_date"]:
            raise PriceError("Referentni datum svake stavke mora odgovarati datumu cjenika.")
        if "promotion" not in item:
            raise PriceError("promotion mora biti null ili objekt s nazivom i cijenom.")
        promotion = item["promotion"]
        if promotion is not None:
            if not isinstance(promotion, dict) or set(promotion) != {"name", "price_cents"}:
                raise PriceError("promotion mora sadržavati samo name i price_cents.")
            required_text(promotion["name"], "promotion.name")
            cents(promotion["price_cents"], "promotion.price_cents")
            if promotion["price_cents"] > item["current_price_cents"]:
                raise PriceError("Posebna cijena ne može biti viša od redovne cijene.")
    return published


def validate(data):
    """Validate release input; return its timezone-aware declared publication time."""
    return _validate(data)


def amount(value, separator="."):
    euros, remainder = divmod(cents(value, "iznos"), 100)
    return f"{euros}{separator}{remainder:02d}"


def human_date(value):
    return valid_date(value, "datum").strftime("%d.%m.%Y")


def active_price(item):
    return item["promotion"]["price_cents"] if item["promotion"] is not None else item["current_price_cents"]


def csv_bytes(data):
    _validate(data, preview=True)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for item in data["items"]:
        promo = item["promotion"]
        writer.writerow((item["name"], amount(active_price(item)), "da" if promo else "ne",
                         promo["name"] if promo else "", amount(item["reference_price_cents"]),
                         amount(item["current_price_cents"]), item["reference_date"]))
    return stream.getvalue().encode("utf-8")


def html_fragment(data, *, heading_level=2):
    _validate(data, preview=True)
    if heading_level not in {2, 3}:
        raise PriceError("Tablice podržavaju razinu naslova 2 ili 3.")
    categories = OrderedDict()
    for item in data["items"]:
        categories.setdefault(item["category_id"], []).append(item)
    lines = []
    for category_id, items in categories.items():
        label = escape(items[0]["category"])
        lines.extend([f'<section class="price-category" id="category-{category_id}" aria-labelledby="heading-{category_id}">',
                      f'<h{heading_level} id="heading-{category_id}">{label}</h{heading_level}>',
                      f'<div class="price-table-scroll" role="region" aria-label="{label}" tabindex="0">',
                      '<table class="price-table">',
                      f'<caption>{label} — cijene u eurima</caption>',
                      '<thead><tr><th scope="col">Usluga</th><th scope="col">Aktualna cijena</th>',
                      '<th scope="col">Cijena na 10.09.2026.</th></tr></thead><tbody>'])
        for item in items:
            search = " ".join(normalize(item["name"]).split())
            promotion = item["promotion"]
            promo_text = (f'<span class="price-promotion">{escape(promotion["name"])} · redovna cijena '
                          f'{amount(item["current_price_cents"], ",")} €</span>') if promotion else ""
            lines.append(f'<tr data-name="{escape(search, quote=True)}" data-category="{category_id}">'
                         f'<th scope="row">{escape(item["name"])}{promo_text}</th>'
                         f'<td class="price-current"><strong>{amount(active_price(item), ",")} €</strong></td>'
                         f'<td class="price-reference"><strong>{amount(item["reference_price_cents"], ",")} €</strong></td></tr>')
        lines.append("</tbody></table></div></section>")
    return "\n".join(lines) + "\n"


def price_content(data, csv_href, archive_href, *, preview=False, archived=False):
    heading = "Arhivski cjenik usluga" if archived else "Cjenik usluga"
    intro = f'<div class="price-intro"><p class="eyebrow">Salon Nina</p><h1>{heading}</h1>'
    if archived:
        intro += '<p class="price-meta">Arhivska verzija. <a href="../../">Pogledajte aktualni cjenik.</a></p>'
    if preview:
        intro += '<p class="price-preview" role="status"><strong>Radni pregled — nije objavljeni cjenik.</strong> Podaci čekaju završnu potvrdu.</p>'
    if data.get("effective_date"):
        intro += f'<p class="price-meta">Cjenik vrijedi od <time datetime="{data["effective_date"]}">{human_date(data["effective_date"])}</time>.</p>'
    elif preview:
        intro += '<p class="price-meta">Datum početka primjene još nije potvrđen.</p>'
    intro += '<p>Sve cijene su u eurima. Uz aktualnu je prikazana bazna cijena na dan 10.09.2026.</p></div>'
    if not archived and not preview:
        intro += '<p>Planirate posvjetljivanje? <a href="../usluge/balayage-i-pramenovi/">Usporedite balayage i pramenove</a> prije dogovora termina.</p>'
    download_name = "cjenik-preview.csv" if preview else csv_filename(data)
    intro += f'<nav class="price-downloads" aria-label="Preuzimanje cjenika"><a href="{escape(csv_href, quote=True)}" download="{download_name}">Preuzmite {"radni " if preview else ""}CSV</a>'
    if not preview and csv_href == "cjenik.csv":
        intro += f'<a href="{download_name}" download>CSV s punim nazivom</a>'
    if archive_href:
        intro += f'<a href="{escape(archive_href, quote=True)}">Arhiva cjenika</a>'
    intro += '</nav><nav class="price-category-nav" aria-label="Kategorije usluga">'
    categories = OrderedDict((item["category_id"], item["category"]) for item in data["items"])
    intro += "".join(f'<a href="#category-{key}">{escape(label)}</a>' for key, label in categories.items())
    intro += '</nav><div class="price-search" hidden><label for="price-search">Pretražite usluge</label>'
    intro += '<input id="price-search" type="search" placeholder="Naziv usluge" autocomplete="off">'
    intro += '</div>'
    return intro + html_fragment(data)


def html_page(title, content, root_prefix, *, canonical_path="/cjenik/", description=None):
    description = description or "Cjenik Salona Nina u Svetom Ivanu Zelini: šišanje, bojanje, balayage i pramenovi. Aktualne i bazne cijene te CSV za preuzimanje."
    canonical = SITE_URL + canonical_path
    template = PROJECT_ROOT / "templates" / "price-page.html"
    if template.exists():
        source = template.read_text(encoding="utf-8")
        for token in ("{{TITLE}}", "{{ROOT}}", "{{CONTENT}}"):
            if token not in source:
                raise PriceError(f"Predlošku nedostaje {token}.")
        return (source.replace("{{TITLE}}", escape(title)).replace("{{ROOT}}", escape(root_prefix, quote=True))
                .replace("{{DESCRIPTION}}", escape(description, quote=True)).replace("{{CANONICAL}}", escape(canonical, quote=True))
                .replace("{{CONTENT}}", content)).encode("utf-8")
    return (f'<!doctype html><html lang="hr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(title)}</title><meta name="description" content="{escape(description, quote=True)}">'
            f'<link rel="canonical" href="{escape(canonical, quote=True)}"></head><body><main>{content}</main></body></html>\n').encode("utf-8")


def service_price_data(data):
    """Select current service variants by their names; never keep a second set of prices."""
    groups = (
        ("balayage", "Balayage", lambda name: name.startswith("balayage ")),
        ("pramenovi", "Pramenovi", lambda name: name.startswith("pramenovi ") and not name.startswith("pramenovi izrast ")),
        ("pramenovi-izrast", "Obnova pramenova na izrastu", lambda name: name.startswith("pramenovi izrast ")),
        ("boja-i-pramenovi", "Bojanje kose + pramenovi", lambda name: name.startswith("bojanje kose + pramenovi ")),
    )
    selected = []
    for category_id, category, matches in groups:
        selected.extend({**item, "category_id": category_id, "category": category}
                        for item in data["items"] if matches(normalize(item["name"])))
    return {**data, "items": selected}


def service_price_answer(data):
    """A visible answer from the exact long-hair row, including active sale semantics."""
    matching = [item for item in data["items"]
                if " ".join(normalize(item["name"]).split()) in {"balayage duga", "balayage duga kosa"}]
    if len(matching) != 1:
        return ""
    item = matching[0]
    promotion = item["promotion"]
    detail = (f'<p class="service-quick-promotion">{escape(promotion["name"])}. '
              f'Redovna cijena: {amount(item["current_price_cents"], ",")} €.</p>') if promotion else ""
    return ('<aside class="service-quick-price" aria-labelledby="long-hair-price">'
            '<h2 id="long-hair-price">Koliko košta balayage za dugu kosu?</h2>'
            '<dl><div><dt>Aktualna cijena</dt>'
            f'<dd><strong>{amount(active_price(item), ",")} €</strong></dd></div>'
            f'<div><dt>Cijena na {human_date(item["reference_date"])}.</dt>'
            f'<dd><strong>{amount(item["reference_price_cents"], ",")} €</strong></dd></div></dl>'
            + detail + '</aside>')


def service_page(data):
    """Render the service page from the same confirmed dataset as HTML and CSV prices."""
    validate(data)
    template = PROJECT_ROOT / "templates" / "service-page.html"
    if not template.exists():
        raise PriceError("Nedostaje obvezni predložak templates/service-page.html; izgradnja je zaustavljena.")
    service_data = service_price_data(data)
    prices = (html_fragment(service_data, heading_level=3) if service_data["items"] else
              '<p>Ove usluge trenutačno nisu navedene u objavljenom cjeniku. Za aktualnu ponudu nazovite salon.</p>')
    title = "Balayage i pramenovi u Svetom Ivanu Zelini"
    description = "Balayage i pramenovi u Salonu Nina u Svetom Ivanu Zelini. Usporedite tehnike, pogledajte aktualne i bazne cijene te nazovite za termin."
    url = SITE_URL + SERVICE_PATH
    provider = {"@type": "HairSalon", "@id": SITE_URL + "/#salon", "name": "Frizerski salon Nina", "url": SITE_URL + "/",
                "telephone": "+385915798154", "address": {"@type": "PostalAddress",
                "streetAddress": data["outlet"]["address"], "addressLocality": data["outlet"]["city"], "addressCountry": "HR"}}
    structured = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": url, "url": url, "name": title + " · Salon Nina",
         "description": description, "inLanguage": "hr-HR", "about": {"@id": url + "#usluga"},
         "breadcrumb": {"@id": url + "#putanja"}},
        {"@type": "Service", "@id": url + "#usluga", "name": "Balayage i pramenovi",
         "serviceType": "Bojanje i posvjetljivanje kose", "url": url, "provider": provider,
         "areaServed": {"@type": "City", "name": data["outlet"]["city"]},
         "image": SITE_URL + "/img/social/kosa-posvjetljivanje.jpg"},
        {"@type": "BreadcrumbList", "@id": url + "#putanja", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Salon Nina", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Balayage i pramenovi", "item": url}]}]}
    replacements = {"TITLE": escape(title), "DESCRIPTION": escape(description, quote=True),
                    "CANONICAL": url, "EFFECTIVE_DATE": human_date(data["effective_date"]),
                    "EFFECTIVE_DATE_ISO": data["effective_date"], "PRICES": prices,
                    "PRICE_ANSWER": service_price_answer(data),
                    "STRUCTURED_DATA": json.dumps(structured, ensure_ascii=False, indent=2).replace("<", "\\u003c")}
    source = template.read_text(encoding="utf-8")
    for key in replacements:
        if "{{" + key + "}}" not in source:
            raise PriceError(f"Predlošku usluge nedostaje {{{{{key}}}}}.")
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: replacements[match[1]], source).encode("utf-8")


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def csv_filename(data):
    published = validate(data).astimezone(ZAGREB)
    outlet = data["outlet"]
    if outlet.get("scope") == "all":
        return "_".join((data["trader"]["identifier"], "ZA_SVA_PRODAJNA_MJESTA", "usluge",
                         f"{data['publication_sequence']:06d}", published.strftime("%Y%m%d_%H%M"))) + ".csv"
    return "_".join((data["trader"]["identifier"], slug(outlet["type"]),
                     slug(outlet["city"] + " " + outlet["address"]), slug(outlet["code"]),
                     "usluge", f"{data['publication_sequence']:06d}", published.strftime("%Y%m%d_%H%M"))) + ".csv"


def atomic_write(path, content):
    if path.exists() and path.read_bytes() == content:
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
            handle.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def read_archives(archive):
    """Check every retained snapshot before allowing any release mutation."""
    records = []
    if not archive.exists():
        return records
    for directory in sorted(archive.iterdir()):
        if not directory.is_dir() or not ARCHIVE_PATTERN.fullmatch(directory.name):
            continue
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            hashes = manifest["files_sha256"]
            if not isinstance(hashes, dict) or set(p.name for p in directory.iterdir()) != set(hashes) | {"manifest.json"}:
                raise ValueError
            for name, digest in hashes.items():
                if Path(name).name != name or not (directory / name).is_file() or sha256((directory / name).read_bytes()) != digest:
                    raise ValueError
            source = json.loads((directory / "cjenik.json").read_text(encoding="utf-8"))
            validate(source)
            expected_files = {"cjenik.json", "index.html", "cjenik-fragment.html", csv_filename(source)}
            if (set(hashes) != expected_files or manifest["status"] != "prepared" or
                    manifest["deployment_verified"] is not False or
                    manifest["effective_date"] != source["effective_date"] or
                    manifest["archive_path"] != f"arhiva/{directory.name}/" or
                    manifest["publication_sequence"] != source["publication_sequence"] or
                    manifest["published_at"] != source["published_at"] or
                    manifest["filename"] != csv_filename(source) or
                    manifest["sha256"] != sha256(csv_bytes(source)) or
                    directory.name != f"{source['publication_sequence']:06d}-{sha256(json_bytes(source))[:16]}" or
                    (directory / manifest["filename"]).read_bytes() != csv_bytes(source)):
                raise ValueError
            records.append((directory, manifest))
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise PriceError(f"Neispravna ili promijenjena arhiva: {directory.name}. Arhiva se neće prepisati.") from error
    records.sort(key=lambda record: record[1]["publication_sequence"])
    sequences = [record[1]["publication_sequence"] for record in records]
    times = [publication_time(record[1]["published_at"]) for record in records]
    if len(sequences) != len(set(sequences)) or any(b <= a for a, b in zip(times, times[1:])):
        raise PriceError("Arhiva sadrži ponovljene brojeve ili nevaljan slijed vremena.")
    return records


def build(data, output, *, now=None):
    """Prepare a release, not a deployment. All earlier archive snapshots remain unchanged."""
    published = validate(data)
    output = Path(output)
    archive = output / "arhiva"
    canonical = json_bytes(data)
    version = f"{data['publication_sequence']:06d}-{sha256(canonical)[:16]}"
    destination = archive / version
    records = read_archives(archive)
    for _, record in records:
        named_copy = output / record["filename"]
        if named_copy.exists() and sha256(named_copy.read_bytes()) != record["sha256"]:
            raise PriceError("Imenovani CSV razlikuje se od sačuvane arhive.")
    latest = records[-1][1] if records else None
    if latest and data["publication_sequence"] < latest["publication_sequence"]:
        raise PriceError("Stariji broj pohrane ne smije zamijeniti aktualni cjenik.")
    if latest and data["publication_sequence"] == latest["publication_sequence"] and records[-1][0] != destination:
        raise PriceError("Broj pohrane već postoji za drugi sadržaj.")
    is_new = not destination.exists()
    if is_new:
        clock = now if now is not None else datetime.now(ZAGREB)
        if clock.utcoffset() is None:
            raise PriceError("now mora sadržavati vremensku zonu.")
        if published.astimezone(ZAGREB).date() != clock.astimezone(ZAGREB).date():
            raise PriceError("Nova objava mora imati današnji datum u Europe/Zagreb; povijesne objave se ne izmišljaju.")
        if latest and published <= publication_time(latest["published_at"]):
            raise PriceError("Vrijeme nove objave mora biti nakon prethodne objave.")
    filename = csv_filename(data)
    csv_content = csv_bytes(data)
    named_path = output / filename
    if named_path.exists() and named_path.read_bytes() != csv_content:
        raise PriceError("Imenovani CSV već postoji s drukčijim sadržajem.")
    fragment = html_fragment(data).encode("utf-8")
    # Prepare templates before any mutation; a broken template cannot leave a partial release.
    current_page = html_page("Cjenik frizerskih usluga u Svetom Ivanu Zelini", price_content(data, "cjenik.csv", "arhiva/"), "../")
    current_service_page = service_page(data)
    archive_date = human_date(data["effective_date"])
    publication_label = published.astimezone(ZAGREB).strftime("%d.%m.%Y u %H:%M")
    archived_description = (f"Arhivski cjenik Salona Nina u Svetom Ivanu Zelini, izdanje {data['publication_sequence']}. "
                            f"Primjena od {archive_date}; objava {publication_label}. Povijesne cijene usluga i CSV.")
    snapshot = {filename: csv_content, "cjenik.json": canonical, "cjenik-fragment.html": fragment,
                "index.html": html_page(f"Cjenik od {archive_date}, izdanje {data['publication_sequence']} · Sveti Ivan Zelina",
                                        price_content(data, filename, "../", archived=True), "../../../",
                                        canonical_path=f"/cjenik/arhiva/{version}/", description=archived_description)}
    manifest = {"schema_version": 2, "status": "prepared", "deployment_verified": False,
                "filename": filename, "sha256": sha256(csv_content), "publication_sequence": data["publication_sequence"],
                "published_at": data["published_at"], "effective_date": data["effective_date"],
                "archive_path": f"arhiva/{version}/", "files_sha256": {name: sha256(body) for name, body in snapshot.items()}}
    if not is_new:
        # HTML/CSS may evolve, but an existing snapshot must stay byte-for-byte unchanged.
        manifest = next(record[1] for record in records if record[0] == destination)
    else:
        snapshot["manifest.json"] = json_bytes(manifest)
        records.append((destination, manifest))
    list_items = []
    for directory, record in reversed(records):
        shown_time = publication_time(record["published_at"]).astimezone(ZAGREB).strftime("%d.%m.%Y u %H:%M")
        label = f"Od {human_date(record['effective_date'])} · {shown_time}"
        list_items.append(f'<li><a href="{directory.name}/">{escape(label)}</a> '
                          f'(<a href="{directory.name}/{record["filename"]}" download>CSV</a>)</li>')
    archive_page = html_page("Arhiva cjenika · Sveti Ivan Zelina", '<h1>Arhiva cjenika</h1><p><a href="../">Aktualni cjenik</a></p><ul>' + "".join(list_items) + "</ul>", "../../",
                             canonical_path="/cjenik/arhiva/", description="Arhiva cjenika Salona Nina u Svetom Ivanu Zelini. Prethodna izdanja, datumi primjene i izvorni CSV zapisi cijena usluga.")
    if is_new:
        archive.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=archive))
        try:
            for name, body in snapshot.items():
                (staging / name).write_bytes(body)
            staging.rename(destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    atomic_write(archive / "index.html", archive_page)
    atomic_write(output / "cjenik.csv", csv_content)
    # Named copies also remain available; stable alias is the machine-readable current endpoint.
    if not named_path.exists():
        atomic_write(named_path, csv_content)
    atomic_write(output / "cjenik-fragment.html", fragment)
    atomic_write(output / "index.html", current_page)
    atomic_write(output / "manifest.json", json_bytes(manifest))
    service_output = output.parent / SERVICE_PATH.strip("/") / "index.html"
    service_output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(service_output, current_service_page)
    return destination


def build_preview(data, output):
    """Write a visibly labelled review into work/ outside the public repository only."""
    _validate(data, preview=True)
    output = Path(output).resolve()
    if "work" not in output.parts or output == PROJECT_ROOT or PROJECT_ROOT in output.parents:
        raise PriceError("Pregled smije nastati samo u work/ izvan javnog repozitorija.")
    banner = '<p class="price-preview" role="status"><strong>Radni pregled — nije objavljeni cjenik.</strong></p>\n'
    page = html_page("Radni pregled cjenika", price_content(data, "cjenik-preview.csv", None, preview=True), "../")
    output.mkdir(parents=True, exist_ok=True)
    atomic_write(output / "cjenik-fragment.html", (banner + html_fragment(data)).encode("utf-8"))
    atomic_write(output / "cjenik-preview.csv", csv_bytes(data))
    atomic_write(output / "index.html", page)
    atomic_write(output / "preview-manifest.json", json_bytes({"status": "preview", "deployment_verified": False,
                                                               "production_ready": False, "item_count": len(data["items"])}))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="JSON cjenik schema_version 2")
    parser.add_argument("--output", type=Path, default=Path("cjenik"))
    parser.add_argument("--preview", action="store_true", help="Samo radni pregled, zahtijeva --output izvan repoa u work/")
    args = parser.parse_args()
    try:
        data = json.loads(args.source.read_text(encoding="utf-8"))
        result = build_preview(data, args.output) if args.preview else build(data, args.output)
    except (PriceError, OSError, ValueError) as error:
        parser.exit(1, f"Cjenik nije generiran: {error}\n")
    print(f"{'Radni pregled' if args.preview else 'Lokalno pripremljen cjenik'}: {result}. Mrežna objava nije izvršena.")


if __name__ == "__main__":
    main()
