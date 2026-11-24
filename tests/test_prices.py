"""Publication safeguards for the schema-2 HTML/CSV generator; synthetic data stays in temp."""

import copy
import csv
from datetime import datetime
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_prices as prices  # noqa: E402


def confirmed_data():
    return {
        "schema_version": 2, "status": "confirmed", "currency": "EUR",
        "effective_date": "2026-09-10", "reference_date": "2026-09-10",
        "confirmed_by": "Testni salon", "confirmed_on": "2026-11-23",
        "trader": {"name": "Testni salon", "identifier_type": "mbo", "identifier": "12345678"},
        "outlet": {"type": "Frizerski salon", "city": "Sveti Ivan Zelina", "address": "Testna ulica 1", "code": "test"},
        "publication_sequence": 1, "published_at": "2026-11-23T10:30:00+01:00",
        "items": [{"id": "test-1", "name": "Šišanje, kratka kosa", "source_name": "ŠIŠANJE, KRATKA KOSA",
                   "category": "Šišanje", "category_id": "sisanje", "reference_date": "2026-09-10",
                   "current_price_cents": 1234, "reference_price_cents": 1001, "promotion": None}],
    }


def directory_bytes(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def csv_rows(content):
    return list(csv.DictReader(io.StringIO(content.decode("utf-8")), delimiter=";"))


class PricePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "cjenik"
        self.now = datetime.fromisoformat("2026-11-23T11:00:00+01:00")

    def build(self, data):
        return prices.build(data, self.output, now=self.now)

    def test_draft_legacy_and_unconfirmed_input_cannot_release(self):
        for status in ("draft", "legacy", "preview", None):
            data = confirmed_data()
            data["status"] = status
            with self.subTest(status=status), self.assertRaises(prices.PriceError):
                self.build(data)
            self.assertFalse(self.output.exists())
        for key in ("confirmed_by", "confirmed_on", "effective_date", "reference_date", "published_at"):
            data = confirmed_data()
            data[key] = None
            with self.subTest(key=key), self.assertRaises(prices.PriceError):
                self.build(data)
            self.assertFalse(self.output.exists())

    def test_malformed_money_identifiers_and_categories_are_rejected(self):
        for key in ("current_price_cents", "reference_price_cents"):
            for value in (None, 12.34, "1234", True, -1):
                data = confirmed_data()
                data["items"][0][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(prices.PriceError):
                    self.build(data)
        for field, value in (("identifier", "1234x"), ("identifier", 12345678), ("identifier_type", "vat")):
            data = confirmed_data()
            data["trader"][field] = value
            with self.subTest(field=field), self.assertRaises(prices.PriceError):
                self.build(data)
        data = confirmed_data()
        data["items"][0]["category_id"] = 'x" onclick="alert(1)'
        with self.assertRaises(prices.PriceError):
            self.build(data)
        self.assertFalse(self.output.exists())

    def test_dates_offsets_and_date_relationships_are_validated(self):
        mutations = [{"effective_date": "2026-02-30"}, {"effective_date": "2026-11-24"},
                     {"effective_date": "2025-09-10"}, {"confirmed_on": "2026-11-24"},
                     {"reference_date": "2026-09-11"}, {"published_at": "2026-11-23T10:30:00"},
                     {"published_at": "2026-11-23T10:30:00.50+01:00"}]
        for mutation in mutations:
            data = confirmed_data()
            data.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(prices.PriceError):
                self.build(data)
        data = confirmed_data()
        data["items"][0]["reference_date"] = "2026-09-11"
        with self.assertRaises(prices.PriceError):
            self.build(data)
        self.assertFalse(self.output.exists())

    def test_csv_column_order_semicolon_quoting_utf8_and_exact_cents(self):
        data = confirmed_data()
        data["items"][0]["name"] = 'Šišanje; "posebno", duga kosa'
        data["items"][0]["current_price_cents"] = 9007199254740993
        data["items"][0]["reference_price_cents"] = 1
        output = prices.csv_bytes(data)
        header = output.decode("utf-8").splitlines()[0]
        self.assertEqual(header, '"naziv_usluge";"maloprodajna_cijena";"posebni_oblik_prodaje";"naziv_posebnog_oblika_prodaje";"bazna_cijena";"redovna_maloprodajna_cijena";"datum_bazne_cijene"')
        row = csv_rows(output)[0]
        self.assertEqual(row["naziv_usluge"], data["items"][0]["name"])
        self.assertEqual(row["maloprodajna_cijena"], "90071992547409.93")
        self.assertEqual(row["bazna_cijena"], "0.01")
        self.assertEqual(row["posebni_oblik_prodaje"], "ne")
        self.assertEqual(row["naziv_posebnog_oblika_prodaje"], "")
        self.assertIn("90071992547409,93 €", prices.html_fragment(data))

    def test_active_promotion_replaces_active_price_but_preserves_regular_and_base(self):
        data = confirmed_data()
        data["items"][0]["promotion"] = {"name": "Akcijska prodaja", "price_cents": 999}
        row = csv_rows(prices.csv_bytes(data))[0]
        self.assertEqual(row["maloprodajna_cijena"], "9.99")
        self.assertEqual(row["redovna_maloprodajna_cijena"], "12.34")
        self.assertEqual(row["bazna_cijena"], "10.01")
        self.assertEqual(row["posebni_oblik_prodaje"], "da")
        html = prices.html_fragment(data)
        self.assertIn('class="price-current"><strong>9,99 €</strong>', html)
        self.assertIn('class="price-reference"><strong>10,01 €</strong>', html)
        self.assertIn("redovna cijena 12,34 €", html)
        self.assertNotIn("<del", html)
        for promotion in ("Akcija", {}, {"name": "", "price_cents": 900},
                          {"name": "Akcija", "price_cents": 999.0},
                          {"name": "Akcija", "price_cents": 1235}):
            data["items"][0]["promotion"] = promotion
            with self.subTest(promotion=promotion), self.assertRaises(prices.PriceError):
                prices.validate(data)

    def test_html_escapes_all_labels_groups_categories_and_preserves_source(self):
        data = confirmed_data()
        data["items"][0]["name"] = '<script>alert("x")</script> Šišanje & njega'
        data["items"][0]["category"] = 'Njega & "stil"'
        second = copy.deepcopy(data["items"][0])
        second.update(id="test-2", name="Valovi", category="Oblikovanje", category_id="oblikovanje")
        data["items"].append(second)
        before = copy.deepcopy(data)
        html = prices.html_fragment(data)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Njega &amp; &quot;stil&quot;", html)
        self.assertEqual(html.count('class="price-category"'), 2)
        self.assertIn('id="category-oblikovanje"', html)
        self.assertIn('<th scope="row">', html)
        self.assertIn('data-name="valovi"', html)
        self.assertEqual(data, before)

    def test_duplicate_names_and_inconsistent_categories_are_rejected(self):
        first = confirmed_data()
        for update in ({"id": "test-2"}, {"id": "test-2", "name": "Drugo", "category": "Druga kategorija"}):
            data = copy.deepcopy(first)
            duplicate = copy.deepcopy(data["items"][0])
            duplicate.update(update)
            data["items"].append(duplicate)
            with self.assertRaises(prices.PriceError):
                prices.validate(data)

    def test_new_release_preserves_all_archives_named_copy_and_stable_alias(self):
        first = confirmed_data()
        first_archive = self.build(first)
        original = directory_bytes(first_archive)
        filename = next(first_archive.glob("*.csv")).name
        self.assertEqual(filename, "12345678_frizerski-salon_sveti-ivan-zelina-testna-ulica-1_test_usluge_000001_20261123_1030.csv")
        second = copy.deepcopy(first)
        second.update(publication_sequence=2, published_at="2026-11-23T10:45:00+01:00")
        second["items"][0]["current_price_cents"] = 1500
        second_archive = self.build(second)
        self.assertEqual(directory_bytes(first_archive), original)
        self.assertEqual((self.output / filename).read_bytes(), original[filename])
        self.assertEqual(csv_rows((self.output / "cjenik.csv").read_bytes())[0]["maloprodajna_cijena"], "15.00")
        archive_index = (self.output / "arhiva" / "index.html").read_text(encoding="utf-8")
        self.assertIn(first_archive.name, archive_index)
        self.assertIn(second_archive.name, archive_index)
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["deployment_verified"])
        self.assertEqual(manifest["sha256"], prices.sha256((self.output / "cjenik.csv").read_bytes()))
        before = directory_bytes(self.output)
        self.build(second)
        self.assertEqual(directory_bytes(self.output), before)
        with self.assertRaisesRegex(prices.PriceError, "Stariji broj"):
            self.build(first)
        self.assertEqual(directory_bytes(self.output), before)

    def test_history_rejects_reused_numbers_and_backdated_new_publication(self):
        data = confirmed_data()
        self.build(data)
        before = directory_bytes(self.output)
        changed = copy.deepcopy(data)
        changed["items"][0]["current_price_cents"] += 1
        with self.assertRaisesRegex(prices.PriceError, "Broj pohrane"):
            self.build(changed)
        changed["publication_sequence"] = 2
        changed["published_at"] = "2026-11-23T10:29:00+01:00"
        with self.assertRaisesRegex(prices.PriceError, "Vrijeme nove"):
            self.build(changed)
        self.assertEqual(directory_bytes(self.output), before)

    def test_first_release_cannot_fabricate_a_past_publication(self):
        data = confirmed_data()
        data.update(published_at="2026-11-22T10:30:00+01:00", confirmed_on="2026-11-22")
        with self.assertRaisesRegex(prices.PriceError, "povijesne objave"):
            self.build(data)
        self.assertFalse(self.output.exists())

    def test_modified_old_archive_blocks_new_release_without_any_writes(self):
        data = confirmed_data()
        archived = self.build(data)
        next(archived.glob("*.csv")).write_text("promijenjeno\n", encoding="utf-8")
        before = directory_bytes(self.output)
        data.update(publication_sequence=2, published_at="2026-11-23T10:45:00+01:00")
        with self.assertRaisesRegex(prices.PriceError, "promijenjena arhiva"):
            self.build(data)
        self.assertEqual(directory_bytes(self.output), before)

    def test_modified_named_copy_blocks_release_without_partial_current_updates(self):
        data = confirmed_data()
        self.build(data)
        (self.output / prices.csv_filename(data)).write_text("promijenjeno\n", encoding="utf-8")
        before = directory_bytes(self.output)
        data.update(publication_sequence=2, published_at="2026-11-23T10:45:00+01:00")
        with self.assertRaisesRegex(prices.PriceError, "Imenovani CSV"):
            self.build(data)
        self.assertEqual(directory_bytes(self.output), before)

    def test_zagreb_filename_converts_utc_using_summer_time(self):
        data = confirmed_data()
        data.update(effective_date="2027-07-01", confirmed_on="2027-07-01", published_at="2027-07-01T08:30:00Z")
        self.assertTrue(prices.csv_filename(data).endswith("_20270701_1030.csv"))

    def test_all_outlets_scope_uses_named_convention_without_an_invented_code(self):
        data = confirmed_data()
        data["outlet"].update(scope="all", code=None)
        expected = "12345678_ZA_SVA_PRODAJNA_MJESTA_usluge_000001_20261123_1030.csv"
        self.assertEqual(prices.csv_filename(data), expected)
        self.build(data)
        self.assertTrue((self.output / expected).is_file())
        html = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'href="{expected}" download>CSV s punim nazivom</a>', html)
        self.assertIn(f'href="cjenik.csv" download="{expected}"', html)
        for scope in ("single", "unexpected"):
            data["outlet"]["scope"] = scope
            with self.subTest(scope=scope), self.assertRaises(prices.PriceError):
                prices.validate(data)

    def test_visible_dates_use_croatian_order_and_metadata_stays_iso(self):
        self.build(confirmed_data())
        html = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn('<time datetime="2026-09-10">10.09.2026</time>', html)
        archive = (self.output / "arhiva" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Od 10.09.2026 · 23.11.2026 u 10:30", archive)
        self.assertEqual(csv_rows((self.output / "cjenik.csv").read_bytes())[0]["datum_bazne_cijene"], "2026-09-10")

    def test_preview_is_labelled_outside_repo_without_release_artifacts(self):
        data = confirmed_data()
        data.update(status="draft", effective_date=None, confirmed_by=None, confirmed_on=None,
                    published_at=None, publication_sequence=None)
        data["trader"]["identifier"] = None
        data["outlet"]["code"] = None
        output = Path(self.temporary.name) / "work" / "preview"
        prices.build_preview(data, output)
        self.assertFalse((output / "arhiva").exists())
        self.assertFalse((output / "cjenik.csv").exists())
        for name in ("index.html", "cjenik-fragment.html"):
            self.assertIn("nije objavljeni cjenik", (output / name).read_text(encoding="utf-8"))
        manifest = json.loads((output / "preview-manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["production_ready"])
        for bad_output in (self.output, ROOT / "work" / "preview"):
            with self.assertRaises(prices.PriceError):
                prices.build_preview(data, bad_output)
        with self.assertRaises(prices.PriceError):
            self.build(data)

    def test_template_tokens_and_root_paths_are_applied(self):
        template_root = Path(self.temporary.name) / "template-project"
        (template_root / "templates").mkdir(parents=True)
        template = template_root / "templates" / "price-page.html"
        template.write_text('<title>{{TITLE}}</title><a href="{{ROOT}}">Salon</a><main>{{CONTENT}}</main>', encoding="utf-8")
        with patch.object(prices, "PROJECT_ROOT", template_root):
            archive = self.build(confirmed_data())
        self.assertIn('href="../"', (self.output / "index.html").read_text(encoding="utf-8"))
        self.assertIn('href="../../"', (self.output / "arhiva" / "index.html").read_text(encoding="utf-8"))
        self.assertIn('href="../../../"', (archive / "index.html").read_text(encoding="utf-8"))
        self.assertNotIn("{{", (self.output / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
