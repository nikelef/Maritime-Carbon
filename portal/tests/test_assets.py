from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from portal.templatetags.assets import versioned_static


class AssetVersionTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_changed_script_gets_a_new_url_and_unchanged_script_keeps_its_url(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "app.js"
            source.write_text("old script", encoding="utf-8")
            with patch("portal.templatetags.assets.finders.find", return_value=str(source)), patch("portal.templatetags.assets.static", return_value="/static/portal/app.js"):
                first = versioned_static("portal/app.js")
                self.assertEqual(first, versioned_static("portal/app.js"))
                source.write_text("new fuel row script", encoding="utf-8")
                self.assertNotEqual(first, versioned_static("portal/app.js"))
                self.assertTrue(first.startswith("/static/portal/app.js?v="))

    @override_settings(DEBUG=False)
    def test_production_retains_its_manifest_url(self):
        with patch("portal.templatetags.assets.static", return_value="/static/portal/app.abcd1234.js"), patch("portal.templatetags.assets.finders.find") as finder:
            self.assertEqual(versioned_static("portal/app.js"), "/static/portal/app.abcd1234.js")
            finder.assert_not_called()
