#!/usr/bin/env python3
"""Import the reviewed NeoSalon export into a draft; never publish or infer missing prices.

The CSV recovery is intentionally limited to the known five-column export with
unquoted commas in names and empty promotion columns. Reviewed PDF extraction can
be the canonical source; all overlapping CSV prices must then agree exactly.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


REFERENCE_DATE = "2026-09-10"
HEADERS = ["NAZIV USLUGE", "MALOPRODAJNA CIJENA",
           "MPC ZA VRIJEME POSEBNOG OBLIKA PRODAJE",
           "NAZIV POSEBNOG OBLIKA PRODAJE", "SIDRENA CIJENA NA 10.9.2026"]
CATEGORIES = {
    "sisanje-brada": "Šišanje i brada",
    "pranje-njega": "Pranje i njega",
    "frizure-oblikovanje": "Frizure i oblikovanje",
    "bojanje-preljev": "Bojanje i preljev",
    "pramenovi-balayage-ombre": "Pramenovi, balayage i ombre",
    "paketi": "Paketi usluga",
    "poklon-bon": "Poklon bon",
}


class ImportError(ValueError):
    pass


def match_key(name):
    value = " ".join(name.upper().split())
    value = re.sub(r",\s*", ",", value)
    return value.replace("BOJANJE KOSE + PRAMENOVI", "BOJANJE KOSE PRAMENOVI")


def checked_name(value):
    if (not isinstance(value, str) or not value.strip() or
            any(ord(character) < 32 for character in value) or '"' in value):
        raise ImportError("Neispravan naziv usluge u očekivanom izvozu.")
    return value


def money(value):
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", value):
        raise ImportError(f"Iznos mora imati decimalnu točku i dvije decimale: {value!r}.")
    whole, cents = value.split(".")
    return int(whole) * 100 + int(cents)


def unique_rows(rows):
    seen = set()
    for row in rows:
        key = match_key(row["name"])
        if key in seen:
            raise ImportError(f"Dupliciran naziv: {row['name']}.")
        seen.add(key)
    return rows


def parse_csv(text):
    lines = text.removeprefix("\ufeff").splitlines()
    if len(lines) < 2:
        raise ImportError("CSV nema zaglavlje i stavke.")
    try:
        header = next(csv.reader([lines[0]], strict=True))
        if len(header) == 1:
            header = next(csv.reader(header, strict=True))
    except csv.Error as error:
        raise ImportError("Neispravno CSV zaglavlje.") from error
    if header != HEADERS:
        raise ImportError("CSV zaglavlje nije podržani NeoSalon izvoz s datumom 10.9.2026.")
    rows = []
    for line_number, line in enumerate(lines[1:], 2):
        cells = line.rsplit(",", 4)
        if len(cells) != 5:
            raise ImportError(f"Redak {line_number}: očekuje se pet polja.")
        name, current, sale, promotion, reference = cells
        checked_name(name)
        if sale or promotion:
            raise ImportError(f"Redak {line_number}: promociju treba zasebno pregledati; automatski uvoz nije dopušten.")
        rows.append({"name": name, "current_cents": money(current),
                     "reference_cents": money(reference), "line": line_number})
    return unique_rows(rows)


def parse_pdf_rows(value):
    if not isinstance(value, list) or not value:
        raise ImportError("Nedostaju provjereni retci PDF-a.")
    for row in value:
        if not isinstance(row, dict) or set(row) != {"name", "current_cents", "reference_cents", "page"}:
            raise ImportError("Neočekivan zapis izdvojen iz PDF-a.")
        checked_name(row["name"])
        for field in ("current_cents", "reference_cents"):
            if type(row[field]) is not int or row[field] < 0:
                raise ImportError("PDF cijene moraju biti nenegativni cijeli brojevi centi.")
        if type(row["page"]) is not int or row["page"] < 1:
            raise ImportError("PDF stranica mora biti pozitivan cijeli broj.")
    return unique_rows(value)


def reconcile(pdf_rows, csv_rows):
    pdf = {match_key(row["name"]): row for row in pdf_rows}
    csv_map = {match_key(row["name"]): row for row in csv_rows}
    common = pdf.keys() & csv_map.keys()
    differences = []
    for key in common:
        if any(pdf[key][field] != csv_map[key][field] for field in ("current_cents", "reference_cents")):
            differences.append(pdf[key]["name"])
    if differences:
        raise ImportError("PDF i CSV imaju različite iznose: " + "; ".join(sorted(differences)))
    if csv_map.keys() - pdf.keys():
        raise ImportError("CSV sadrži stavke koje nedostaju u odabranom PDF-u.")
    return {
        "pdf_item_count": len(pdf_rows), "csv_item_count": len(csv_rows),
        "matched_item_count": len(common), "price_mismatches": [], "csv_only": [],
        "pdf_only": [row for row in pdf_rows if match_key(row["name"]) not in csv_map],
        "name_differences": [{"pdf": row["name"], "csv": csv_map[match_key(row["name"])]["name"]}
                             for row in pdf_rows if match_key(row["name"]) in csv_map and
                             row["name"] != csv_map[match_key(row["name"])]["name"]],
    }


def display_name(source):
    value = " ".join(source.lower().split())
    corrections = {"panje": "pranje", "eksta": "ekstra",
                   "susenje": "sušenje", "svecana": "svečana", "musko": "muško",
                   "sisanje": "šišanje", "masinicom": "mašinicom", "uredivanje": "uređivanje",
                   "siski": "šiški"}
    for original, corrected in corrections.items():
        value = re.sub(r"\b" + re.escape(original) + r"\b", corrected, value)
    value = re.sub(r",\s*", ", ", value)
    value = value.replace("bojanje kose pramenovi", "bojanje kose + pramenovi")
    value = value.replace("1kom", "1 kom").replace("pramen(folija)", "pramen (folija)")
    value = value[:1].upper() + value[1:]
    return value.replace("Loreal steampod", "L’Oréal SteamPod")


def category_id(name):
    name = match_key(name)
    if name == "POKLON BON":
        return "poklon-bon"
    if name.startswith(("BOJANJE,", "PRANJE,", "PANJE,")):
        return "paketi"
    if any(word in name for word in ("PRAMEN", "BALAYAGE", "OMBRE")):
        return "pramenovi-balayage-ombre"
    if name.startswith(("BOJANJE", "SKIDANJE BOJE", "PRELJEV")):
        return "bojanje-preljev"
    if name.startswith(("PRANJE", "MASKA", "KERATINSKI", "COCOCHOCO")):
        return "pranje-njega"
    if name.startswith(("ŠIŠANJE", "DJEČJE", "MUSKO", "MODERNO", "REZANJE", "BRIJANJE", "SKIDANJE BRADE", "UREDIVANJE")):
        return "sisanje-brada"
    if name.startswith(("FEN", "SVECANA", "VALOVI", "UPORABA", "LOREAL", "PLETENICA", "MINIVAL")):
        return "frizure-oblikovanje"
    raise ImportError(f"Usluzi treba dodijeliti kategoriju: {name}.")


def make_data(rows, existing_items=()):
    stable_ids = {}
    used_ids = set()
    for item in existing_items:
        identifier = item["id"]
        key = match_key(item["source_name"])
        if not re.fullmatch(r"service[0-9]{3,}", identifier) or identifier in used_ids or key in stable_ids:
            raise ImportError("Postojeći stabilni identifikatori nisu valjani.")
        stable_ids[key] = identifier
        used_ids.add(identifier)
    next_id = max([int(value[7:]) for value in used_ids] or [0]) + 1
    items = []
    for row in rows:
        key = match_key(row["name"])
        if key not in stable_ids:
            stable_ids[key] = f"service{next_id:03d}"
            next_id += 1
        category = category_id(row["name"])
        items.append({"id": stable_ids[key], "name": display_name(row["name"]),
                      "source_name": row["name"], "category": CATEGORIES[category], "category_id": category,
                      "current_price_cents": row["current_cents"],
                      "reference_price_cents": row["reference_cents"],
                      "reference_date": REFERENCE_DATE, "promotion": None})
    return {"schema_version": 2, "status": "draft", "currency": "EUR",
            "effective_date": None, "reference_date": REFERENCE_DATE,
            "confirmed_by": None, "confirmed_on": None,
            "trader": {"name": "FRIZERSKI SALON NINA, vl. Nikolina Brlečić Bukal",
                       "identifier_type": "mbo", "identifier": None},
            "outlet": {"type": "Frizerski salon", "city": "Sveti Ivan Zelina",
                       "address": "Trg Ante Starčevića 5", "code": None},
            "publication_sequence": 1, "published_at": None, "items": items}


def source_record(path):
    return {"filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def import_sources(csv_path, pdf_rows_path=None, pdf_path=None, existing_items=()):
    csv_rows = parse_csv(csv_path.read_text(encoding="utf-8-sig"))
    sources = {"csv": source_record(csv_path)}
    comparison = None
    rows = csv_rows
    if pdf_rows_path is not None:
        if pdf_path is None:
            raise ImportError("Za PDF izvor potrebna je i izvorna PDF datoteka radi SHA-256 traga.")
        rows = parse_pdf_rows(json.loads(pdf_rows_path.read_text(encoding="utf-8")))
        comparison = reconcile(rows, csv_rows)
        sources.update({"pdf": source_record(pdf_path), "reviewed_pdf_rows": source_record(pdf_rows_path)})
    data = make_data(rows, existing_items)
    audit = {"audit_version": 1, "sources": sources,
             "canonical_source": "pdf" if pdf_rows_path else "csv",
             "reference_date": REFERENCE_DATE, "effective_date": data["effective_date"],
             "confirmation_status": "needs_confirmation",
             "effective_date_source": "Datum primjene nije utvrđen uvozom; potrebna je zasebna potvrda.",
             "source_choice": ("PDF je odabran argumentom --pdf-rows; opseg i točnost izvora treba potvrditi prije objave."
                               if pdf_rows_path else "CSV je odabran kao ulaz; opseg i točnost izvora treba potvrditi prije objave."),
             "comparison": comparison,
             "csv_recovery": {"header": "Poznato zaglavlje bilo je zapisano kao jedno dodatno navodnicima omotano polje.",
                              "data": "Razdvajanje zadnja četiri zareza; stroga provjera iznosa i praznih promotivnih polja.",
                              "names_with_unquoted_commas": sum("," in row["name"] for row in csv_rows)},
             "display_name_changes": [{"id": item["id"], "source_name": item["source_name"], "display_name": item["name"]}
                                      for item in data["items"] if item["name"] != item["source_name"]],
             "amounts_changed": False,
             "pending": ["Potvrda datuma primjene, opsega izvora i točnosti novog uvoza.",
                         "Evidentiranje osobe i datuma stvarne potvrde prije objave.",
                         "Provjera poslovnog identifikatora i oznake objekta prije objave.",
                         "Stvarno vrijeme mrežne objave još nije određeno."]}
    return data, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--pdf-rows", type=Path, help="Ručno provjeren JSON iz PDF-a; odabire PDF kao puni izvor")
    parser.add_argument("--pdf", type=Path, help="Izvorni PDF za trag podrijetla")
    parser.add_argument("--output", type=Path, default=Path("data/prices.json"))
    parser.add_argument("--audit", type=Path, default=Path("data/source-audit.json"))
    args = parser.parse_args()
    try:
        existing = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else {}
        if existing.get("status") == "confirmed":
            raise ImportError("Potvrđeni cjenik ne smije se zamijeniti nacrtom; odaberite drugu izlaznu datoteku.")
        data, audit = import_sources(args.csv, args.pdf_rows, args.pdf, existing.get("items", []))
        for path, value in ((args.output, data), (args.audit, audit)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Uvoz zaustavljen: {error}\n")
    print(f"Pripremljen nacrt: {len(data['items'])} stavki. Nema mrežne objave.")


if __name__ == "__main__":
    main()
