"""The known broken CSV must not shift prices, discard PDF rows, or change IDs."""

import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from import_neosalon import (HEADERS, ImportError, display_name, import_sources, make_data,
                            parse_csv, parse_pdf_rows, reconcile)


def broken_header():
    stream = io.StringIO()
    csv.writer(stream, lineterminator="").writerow([','.join([HEADERS[0]] + ['"' + value + '"' for value in HEADERS[1:]])])
    return stream.getvalue()


class NeoSalonImportTests(unittest.TestCase):
    def test_known_broken_header_and_unquoted_name_commas_preserve_money(self):
        rows = parse_csv(broken_header() + '\nBOJANJE, ŠIŠANJE FRIZURA DUGA,50.00,,,49.99\n')
        self.assertEqual(rows[0]['name'], 'BOJANJE, ŠIŠANJE FRIZURA DUGA')
        self.assertEqual(rows[0]['current_cents'], 5000)
        self.assertEqual(rows[0]['reference_cents'], 4999)

    def test_unexpected_headers_amounts_and_promotions_are_rejected(self):
        header = broken_header()
        with self.assertRaises(ImportError):
            parse_csv(header.replace('10.9.2026', '10.9.2025') + '\nMaska,6.00,,,6.00\n')
        for current in ('6', '6.0', '6,00', '-6.00', 'NaN', '1e3', ' 6.00', '6.001'):
            with self.subTest(current=current), self.assertRaises(ImportError):
                parse_csv(header + f'\nMaska,{current},,,6.00\n')
        for tail in ('6.00,5.00,Akcija,6.00', '6.00,,Akcija,6.00', '6.00,5.00,,6.00'):
            with self.subTest(tail=tail), self.assertRaises(ImportError):
                parse_csv(header + '\nMaska,' + tail + '\n')

    def test_duplicate_and_blank_rows_are_not_silently_dropped(self):
        for content in ('Maska,6.00,,,6.00\nMASKA,6.00,,,6.00', 'Maska,6.00,,,6.00\n\n'):
            with self.subTest(content=content), self.assertRaises(ImportError):
                parse_csv(broken_header() + '\n' + content)

    def test_pdf_is_canonical_but_overlap_must_match_both_amounts(self):
        csv_rows = parse_csv(broken_header() + '\nBOJANJE KOSE + PRAMENOVI DUGA,60.00,,,60.00\n')
        pdf = parse_pdf_rows([
            {'name': 'BOJANJE KOSE PRAMENOVI DUGA', 'current_cents': 6000, 'reference_cents': 6000, 'page': 3},
            {'name': 'PLETENICA 1KOM', 'current_cents': 300, 'reference_cents': 300, 'page': 4}])
        result = reconcile(pdf, csv_rows)
        self.assertEqual(result['matched_item_count'], 1)
        self.assertEqual(result['pdf_only'], [pdf[1]])
        self.assertEqual(len(make_data(pdf)['items']), 2)
        for field in ('current_cents', 'reference_cents'):
            changed = copy.deepcopy(pdf)
            changed[0][field] += 1
            with self.subTest(field=field), self.assertRaises(ImportError):
                reconcile(changed, csv_rows)
        with self.assertRaises(ImportError):
            reconcile(pdf[1:], csv_rows)

    def test_pdf_float_prices_and_duplicate_services_are_rejected(self):
        row = {'name': 'Maska', 'current_cents': 600, 'reference_cents': 600, 'page': 5}
        with self.assertRaises(ImportError):
            parse_pdf_rows([row, row])
        for invalid in (True, 600.0, '600', -1):
            with self.subTest(invalid=invalid), self.assertRaises(ImportError):
                parse_pdf_rows([{**row, 'reference_cents': invalid}])

    def test_ids_survive_reordering_and_display_fixes_keep_source_names(self):
        rows = [{'name': 'PANJE,ŠIŠANJE FRIZURA EKSTRA KRATKA', 'current_cents': 1900, 'reference_cents': 1900},
                {'name': 'BOJANJE, ŠIŠANJE FRIZURA EKSTA DUGA', 'current_cents': 6000, 'reference_cents': 6000}]
        original = make_data(rows)
        repeated = make_data(list(reversed(rows)), original['items'])
        self.assertEqual([item['id'] for item in repeated['items']], ['service002', 'service001'])
        self.assertEqual(original['items'][0]['source_name'], rows[0]['name'])
        self.assertEqual(original['items'][0]['name'], 'Pranje, šišanje frizura ekstra kratka')
        self.assertEqual(original['items'][1]['name'], 'Bojanje, šišanje frizura ekstra duga')
        self.assertEqual(display_name('Loreal steampod pegla'), 'L’Oréal SteamPod pegla')

    def test_reimport_preserves_ids_but_never_reuses_a_previous_confirmation(self):
        rows = [{'name': 'Maska', 'current_cents': 600, 'reference_cents': 500}]
        previous = make_data(rows)
        previous.update(status='confirmed', effective_date='2026-09-10',
                        confirmed_by='Potvrđivač prethodnog cjenika', confirmed_on='2026-11-23')
        before = copy.deepcopy(previous)
        rows[0]['current_cents'] = 700
        imported = make_data(rows, previous['items'])
        self.assertEqual(imported['status'], 'draft')
        self.assertEqual(imported['items'][0]['id'], previous['items'][0]['id'])
        self.assertEqual(imported['items'][0]['current_price_cents'], 700)
        for field in ('effective_date', 'confirmed_by', 'confirmed_on'):
            self.assertIsNone(imported[field])
        self.assertEqual(previous, before)

    def test_csv_and_pdf_import_audits_require_new_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            csv_path = directory / 'izvoz.csv'
            csv_path.write_text(broken_header() + '\nMaska,6.00,,,5.00\n', encoding='utf-8')
            pdf_path = directory / 'izvor.pdf'
            pdf_path.write_bytes(b'test source for provenance hash')
            pdf_rows_path = directory / 'reviewed-rows.json'
            pdf_rows_path.write_text(json.dumps([
                {'name': 'Maska', 'current_cents': 600, 'reference_cents': 500, 'page': 1},
                {'name': 'Pletenica 1kom', 'current_cents': 300, 'reference_cents': 300, 'page': 1}
            ]), encoding='utf-8')
            for include_pdf in (False, True):
                with self.subTest(include_pdf=include_pdf):
                    data, audit = import_sources(csv_path, pdf_rows_path if include_pdf else None,
                                                 pdf_path if include_pdf else None)
                    self.assertEqual(data['status'], 'draft')
                    for field in ('effective_date', 'confirmed_by', 'confirmed_on'):
                        self.assertIsNone(data[field])
                    self.assertIsNone(audit['effective_date'])
                    self.assertEqual(audit['confirmation_status'], 'needs_confirmation')
                    self.assertEqual(audit['canonical_source'], 'pdf' if include_pdf else 'csv')
                    self.assertEqual(len(data['items']), 2 if include_pdf else 1)
                    self.assertEqual(data['items'][0]['current_price_cents'], 600)
                    self.assertEqual(data['items'][0]['reference_price_cents'], 500)
                    self.assertNotIn('Korisnik je', audit['source_choice'])
                    self.assertNotIn('2026-11-23', json.dumps(audit, ensure_ascii=False))

    def test_repository_import_keeps_all_108_confirmed_source_prices(self):
        data = json.loads((ROOT / 'data/prices.json').read_text(encoding='utf-8'))
        audit = json.loads((ROOT / 'data/source-audit.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['items']), 108)
        self.assertEqual(len({item['id'] for item in data['items']}), 108)
        self.assertEqual(audit['comparison']['matched_item_count'], 105)
        self.assertEqual({row['name']: row['current_cents'] for row in audit['comparison']['pdf_only']},
                         {'PLETENICA 1KOM': 300, 'REZANJE SISKI': 300, 'POKLON BON': 1400})
        self.assertEqual(audit['comparison']['price_mismatches'], [])
        self.assertFalse(audit['amounts_changed'])
        self.assertTrue(all(item['reference_date'] == '2026-09-10' and
                            item['current_price_cents'] == item['reference_price_cents'] for item in data['items']))


if __name__ == '__main__':
    unittest.main()
