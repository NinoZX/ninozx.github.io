#!/usr/bin/env python3
"""Read-only HTTPS checks of the published site against the local price release."""

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path, PurePosixPath
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 10
MAX_BYTES = 5 * 1024 * 1024


class VerificationError(ValueError):
    pass


class HTTPSRedirectsOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme.lower() != "https":
            raise VerificationError("Poslužitelj preusmjerava HTTPS zahtjev na nesiguran URL.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def normalized(text):
    return " ".join(text.split())


class Page(HTMLParser):
    def __init__(self, body, url):
        super().__init__(convert_charrefs=True)
        self.url, self.links, self.text, self.rows = url, set(), [], []
        self.row = None
        self.feed(body.decode("utf-8-sig"))
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.add(urljoin(self.url, attrs["href"]).split("#", 1)[0])
        if tag == "tr":
            self.row = []

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            self.rows.append(normalized(" ".join(self.row)))
            self.row = None

    def handle_data(self, data):
        self.text.append(data)
        if self.row is not None:
            self.row.append(data)

    def require_text(self, *markers):
        text = normalized(" ".join(self.text))
        for marker in markers:
            if marker not in text:
                raise VerificationError(f"{self.url}: nedostaje tekst {marker!r}.")

    def require_link(self, target):
        variants = {target, target.rstrip("/"), target.rstrip("/") + "/index.html"}
        if not self.links.intersection(variants):
            raise VerificationError(f"{self.url}: nedostaje poveznica na {target}.")


def digest(body):
    return hashlib.sha256(body).hexdigest()


def fetch(opener, url):
    try:
        request = Request(url, headers={"User-Agent": "SalonNina-PublicationVerifier/1.0"})
        # Default urllib HTTPS handler validates certificates and hostnames.
        with opener.open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise VerificationError(f"{url}: HTTP {response.status}, očekivan je 200.")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise VerificationError(f"{url}: odgovor je neočekivano velik.")
            return body, response.geturl()
    except HTTPError as error:
        raise VerificationError(f"{url}: HTTP {error.code} ({error.reason}).") from None
    except (URLError, ssl.SSLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise VerificationError(f"{url}: HTTPS dohvat nije uspio: {reason}") from None


def amount(text):
    value = Decimal(text)
    if not value.is_finite():
        raise VerificationError("Lokalni CSV sadrži neispravan iznos.")
    return f"{value:.2f}".replace(".", ",") + " €"


def verify(base_url):
    parsed = urlsplit(base_url)
    if (parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise VerificationError("--base-url mora biti HTTPS URL bez prijave, upita i fragmenta.")
    base_url = urlunsplit(("https", parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))
    manifest = json.loads((ROOT / "cjenik" / "manifest.json").read_text(encoding="utf-8"))
    local_csv = (ROOT / "cjenik" / "cjenik.csv").read_bytes()
    expected = digest(local_csv)
    if manifest.get("sha256") != expected:
        raise VerificationError("Lokalni cjenik.csv ne odgovara SHA-256 iz manifesta; prvo ponovno pripremite izdanje.")
    filename, archive = manifest["filename"], manifest["archive_path"]
    if not isinstance(filename, str) or PurePosixPath(filename).name != filename or not filename.endswith(".csv"):
        raise VerificationError("Manifest sadrži neispravan naziv CSV datoteke.")
    if (not isinstance(archive, str) or not archive.startswith("arhiva/")
            or not archive.endswith("/") or ".." in PurePosixPath(archive).parts
            or any(char in filename + archive for char in "?#\\")):
        raise VerificationError("Manifest sadrži neispravnu putanju arhive.")
    rows = list(csv.DictReader(io.StringIO(local_csv.decode("utf-8-sig")), delimiter=";"))
    if not rows:
        raise VerificationError("Lokalni CSV ne sadrži usluge.")
    price_url = urljoin(base_url, "cjenik/")
    archive_url = urljoin(price_url, "arhiva/")
    opener = build_opener(HTTPSRedirectsOnly())
    # First live request fails fast on a TLS or publication error.
    for path in ("cjenik.csv", filename, archive + filename):
        url = urljoin(price_url, path)
        body, _ = fetch(opener, url)
        actual = digest(body)
        if actual != expected:
            raise VerificationError(f"{url}: CSV se razlikuje od lokalnog izdanja (SHA-256 {actual}; očekivano {expected}).")
        print(f"OK CSV: {url}")
    body, final_url = fetch(opener, price_url)
    page = Page(body, final_url)
    page.require_text("Cjenik usluga", "Aktualna cijena", "Cijena na 10.09.2026.")
    for row in rows:
        name = normalized(row["naziv_usluge"])
        prices = amount(row["maloprodajna_cijena"]) + " " + amount(row["bazna_cijena"])
        if not any(text.startswith(name + " ") and text.endswith(prices) for text in page.rows):
            raise VerificationError(f"{price_url}: HTML ne prikazuje očekivani par cijena za {name!r}.")
    for target in (urljoin(price_url, "cjenik.csv"), urljoin(price_url, filename), archive_url):
        page.require_link(target)
    print(f"OK HTML: {price_url} ({len(rows)} usluga)")
    body, final_url = fetch(opener, archive_url)
    page = Page(body, final_url)
    page.require_text("Arhiva cjenika")
    page.require_link(urljoin(price_url, archive))
    page.require_link(urljoin(price_url, archive + filename))
    print(f"OK arhiva: {archive_url}")
    body, final_url = fetch(opener, base_url)
    Page(body, final_url).require_link(price_url)
    print(f"OK naslovnica: {base_url}")
    print("Mrežna provjera je prošla. Datoteke i manifest nisu mijenjani.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://salon-nina.hr/", help="HTTPS korijen objavljenog weba")
    args = parser.parse_args()
    try:
        verify(args.base_url)
    except (VerificationError, OSError, UnicodeError, KeyError, TypeError, ValueError, InvalidOperation) as error:
        print(f"Provjera nije prošla: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
