import shutil
import uuid
from contextlib import contextmanager
import unittest
from pathlib import Path
from unittest.mock import patch
import build_pages as pages


@contextmanager
def temporary_output():
    # Default mkdir permissions also work under the Windows workspace sandbox.
    root = (pages.ROOT / '.build-tests').resolve()
    folder = root / uuid.uuid4().hex
    folder.mkdir(parents=True)
    try:
        yield folder
    finally:
        resolved = folder.resolve()
        if resolved.parent != root or len(resolved.name) != 32:
            raise ValueError('Unexpected test cleanup path')
        shutil.rmtree(resolved)


class Publication(unittest.TestCase):
    def test_export_is_allowlisted_and_preserves_design(self):
        with temporary_output() as folder:
            output = Path(folder) / 'site'
            manifest = pages.build(output=output)
            self.assertEqual(manifest['archiveGames'], 1322)
            self.assertEqual(manifest['firstFreeThrows'], 249)
            self.assertEqual(pages.digest(output / 'scout-theme.css'), pages.digest(pages.SOURCE / 'scout-theme.css'))
            self.assertEqual((output / 'index.html').read_bytes(), (output / 'ftb-scout.html').read_bytes())
            history = pages.read(output / 'data/history.json')
            self.assertEqual(len(history['analysis']['games']), 1322)
            self.assertEqual(pages.read(output / 'data/seasons/2026-27.json')['meta']['season'], '2026-27')
            self.assertFalse(any(p.suffix in ('.xlsx', '.py', '.exe', '.gz') for p in output.rglob('*')))
            self.assertFalse((output / 'cache').exists())
            for relative, expected in manifest['files'].items():
                self.assertEqual(pages.digest(output / relative), expected['sha256'])

    def test_missing_archive_game_fails_before_any_export(self):
        original = pages.read
        def altered(path):
            data = original(path)
            if path.name == 'analyst_data.json':
                data['games'].pop()
            return data
        with temporary_output() as folder, patch.object(pages, 'read', side_effect=altered):
            output = Path(folder) / 'site'
            with self.assertRaisesRegex(ValueError, 'Missing archive games'):
                pages.build(output=output)
            self.assertFalse(output.exists())

    def test_mismatched_evaluation_cannot_be_published(self):
        original = pages.read
        def altered(path):
            data = original(path)
            if path.name == 'analyst_evaluation.json':
                data['evidenceHash'] = 'wrong'
            return data
        with patch.object(pages, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Evaluation evidence file mismatch'):
                pages.validate(pages.SOURCE)

    def test_season_version_cannot_escape_snapshot_folder(self):
        original = pages.read
        def altered(path):
            data = original(path)
            if path.name == 'manifest.json' and path.parent.name == '2026-27':
                data['activeVersion'] = '../private.json'
            return data
        with patch.object(pages, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Unsafe season version path'):
                pages.validate(pages.SOURCE)

    def test_shooting_evidence_mismatch_blocks_export(self):
        original = pages.read
        def altered(path):
            data = original(path)
            if path.name == 'parlay_data.json':
                data['meta']['parentEvidenceContentHash'] = 'wrong'
            return data
        with patch.object(pages, 'read', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Parlay evidence mismatch'):
                pages.validate(pages.SOURCE)

    def test_shooting_browser_payload_mismatch_blocks_export(self):
        original = pages.javascript_payload
        def altered(path, variable):
            data = original(path, variable)
            if variable == '__FTB_PARLAY_DATA__':
                data['games'].pop(next(iter(data['games'])))
            return data
        with patch.object(pages, 'javascript_payload', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Browser shooting evidence differs'):
                pages.validate(pages.SOURCE)


if __name__ == '__main__':
    unittest.main()
