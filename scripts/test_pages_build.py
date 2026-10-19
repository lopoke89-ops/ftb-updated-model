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
    def test_stale_readiness_model_or_evaluator_blocks_publication(self):
        original = pages.digest
        for changed in ('parlay.js', 'scouting_history.js', 'evaluate_readiness.cjs'):
            with self.subTest(changed=changed), patch.object(pages, 'digest', side_effect=lambda path: 'changed' if path.name == changed else original(path)):
                with self.assertRaisesRegex(ValueError, 'Readiness evaluat'):
                    pages.validate(pages.SOURCE)

    def test_stale_research_fit_or_browser_configuration_blocks_publication(self):
        original = pages.digest
        with patch.object(pages, 'digest', side_effect=lambda path: 'changed' if path.name=='fit_parlay_transition.cjs' else original(path)):
            with self.assertRaisesRegex(ValueError, 'Research'):
                pages.validate(pages.SOURCE)

    def test_export_is_allowlisted_and_preserves_design(self):
        with temporary_output() as folder:
            output = Path(folder) / 'site'
            manifest = pages.build(output=output)
            self.assertEqual(manifest['archiveGames'], 1322)
            self.assertEqual(manifest['firstFreeThrows'], 249)
            self.assertEqual(pages.digest(output / 'scout-theme.css'), pages.digest(pages.SOURCE / 'scout-theme.css'))
            self.assertEqual((output / 'index.html').read_bytes(), (output / 'ftb-scout.html').read_bytes())
            html = (output / 'index.html').read_text(encoding='utf-8')
            for name in pages.ASSETS:
                self.assertIn(name + '?v=' + pages.digest(output / name)[:16] + '"', html)
                self.assertNotIn('="' + name + '"', html)
            history = pages.read(output / 'data/history.json')
            self.assertEqual(len(history['analysis']['games']), 1322)
            self.assertEqual(pages.read(output / 'data/seasons/2026-27.json')['meta']['season'], '2026-27')
            from parlay_journal import release_hashes
            self.assertEqual(pages.read(output / 'data/seasons/2026-27.json')['publication']['parlayCodeHashes'],release_hashes())
            self.assertFalse(any(p.suffix in ('.xlsx', '.py', '.exe', '.gz') for p in output.rglob('*')))
            self.assertFalse((output / 'cache').exists())
            for relative, expected in manifest['files'].items():
                self.assertEqual(pages.digest(output / relative), expected['sha256'])

    def test_changed_assets_get_new_urls_while_unchanged_assets_keep_their_urls(self):
        with temporary_output() as folder:
            for name in pages.ASSETS:
                (folder / name).write_text(name, encoding='utf-8')
            html = '<script src="analyst_ui.js"></script><link href="scout-theme.css"/>'
            first = pages.version_asset_references(html, folder)
            self.assertEqual(first, pages.version_asset_references(html, folder))
            (folder / 'analyst_ui.js').write_text('updated interface', encoding='utf-8')
            second = pages.version_asset_references(html, folder)
            self.assertNotEqual(first.split('</script>')[0], second.split('</script>')[0])
            self.assertEqual(first.split('</script>')[1], second.split('</script>')[1])
            self.assertIn('src="analyst_ui.js?v=', second)
            self.assertIn('href="scout-theme.css?v=', second)

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

    def test_opening_content_changes_block_export(self):
        original = pages.read
        original_script = pages.javascript_payload
        def alter(data):
            opening = data['openingEvidence']
            next(iter(opening['games'].values()))['firstScores'].clear()
            return data
        def changed(path):
            data = original(path)
            return alter(data) if path.name == 'parlay_data.json' else data
        def changed_script(path, variable):
            data = original_script(path, variable)
            return alter(data) if variable == '__FTB_PARLAY_DATA__' else data
        with patch.object(pages, 'read', side_effect=changed), patch.object(pages, 'javascript_payload', side_effect=changed_script):
            with self.assertRaisesRegex(ValueError, 'Opening content hash mismatch'):
                pages.validate(pages.SOURCE)


if __name__ == '__main__':
    unittest.main()
