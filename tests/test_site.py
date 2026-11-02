from html.parser import HTMLParser
from pathlib import Path
import json
import unittest


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.scripts = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.scripts += 1
        for key in ('href', 'src'):
            if key in attrs:
                self.targets.append(attrs[key])


class SiteTests(unittest.TestCase):
    def test_local_assets_and_navigation_resolve(self):
        for page in ('index.html', 'privacy.html', '404.html'):
            parser = Links()
            parser.feed((Path('public') / page).read_text())
            self.assertEqual(parser.scripts, 0)
            for target in parser.targets:
                if target.startswith('/'):
                    file = 'index.html' if target == '/' else target.lstrip('/')
                    if '.' not in file:
                        file += '.html'
                    self.assertTrue((Path('public') / file).is_file(), target)

    def test_hosting_excludes_worker_and_retains_security(self):
        hosting = json.loads(Path('firebase.json').read_text())['hosting']
        self.assertEqual(hosting['public'], 'public')
        self.assertEqual(hosting['site'], 'xbox-twitch-recorder')
        self.assertTrue(hosting['cleanUrls'])
        self.assertNotIn('rewrites', hosting)
        headers = {h['key']: h['value'] for h in hosting['headers'][0]['headers']}
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        self.assertIn('not active', Path('public/privacy.html').read_text())
        self.assertNotIn('1X9VfSes_', Path('public/privacy.html').read_text())
