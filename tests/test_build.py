import sys
import unittest
import json
import re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,parse_qs
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build import vcard, fold_line, validate


class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.tags=[];self.feed(text)
    def handle_starttag(self,tag,attrs): self.tags.append((tag,dict(attrs)))


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads((ROOT/'site.config.json').read_text())
        cls.html=(ROOT/'dist/index.html').read_text()
        cls.page=Page(cls.html)

    def test_social_metadata_exists_in_initial_html(self):
        metas={a.get('property') or a.get('name'):a.get('content') for t,a in self.page.tags if t=='meta'}
        self.assertEqual(metas['og:url'],self.c['cardUrl'])
        self.assertEqual(metas['twitter:card'],'summary_large_image')
        self.assertEqual(metas['twitter:image'],metas['og:image'])
        self.assertTrue(metas['og:image:alt'])
        path=ROOT/'dist'/urlparse(metas['og:image']).path.lstrip('/')
        with Image.open(path) as image:
            self.assertEqual(image.size,(1200,630))
        self.assertLess(path.stat().st_size,300_000)
        self.assertLess(len(self.html.encode()),100_000)

    def test_static_links_and_assets_exist(self):
        for tag,attrs in self.page.tags:
            for key in ['src','href']:
                value=attrs.get(key,'')
                if value.startswith('/'):
                    self.assertTrue((ROOT/'dist'/value.lstrip('/')).is_file(),value)
        self.assertNotIn('{{',self.html)
        self.assertNotIn('data-preview',self.html)
        self.assertNotIn('Certified Organic',self.html)
        self.assertNotIn('1170',self.html)

    def test_all_share_channels_match_the_canonical(self):
        for tag,attrs in self.page.tags:
            if attrs.get('data-channel'):
                params=parse_qs(urlparse(attrs['href']).query)
                self.assertTrue((params.get('text') or params.get('body'))[0].endswith(self.c['cardUrl']))
        self.assertIn('URL:'+self.c['cardUrl'],(ROOT/'dist/romeo-health-heaven.vcf').read_text())

    def test_vcard_structure_escaping_and_utf8_folding(self):
        raw=vcard(self.c)
        self.assertTrue(raw.startswith(b'BEGIN:VCARD\r\nVERSION:3.0\r\n'))
        self.assertTrue(raw.endswith(b'END:VCARD\r\n'))
        for line in raw.split(b'\r\n'):
            self.assertLessEqual(len(line),75)
            line.decode('utf-8')
        text='NOTE:'+('é,;\\\n'*35)
        folded=fold_line(text)
        self.assertEqual(folded.replace('\r\n ',''),text)
        special={**self.c,'founder':'Romeo;Test, Person\\One\nTwo'}
        self.assertIn(b'N:;Romeo\\;Test\\, Person\\\\One\\nTwo;;;',vcard(special))

    def test_configuration_rejects_preview_tracking_or_credentials(self):
        for value in ['http://hello.example.com/','https://hello.example.com/?utm_source=x','https://user:secret@example.com/','https://example.com/card/']:
            with self.assertRaises(ValueError):validate({**self.c,'cardUrl':value})

    def test_self_hosted_runtime_and_intentional_motion(self):
        resources=[a.get('src') or a.get('href') for t,a in self.page.tags if t in ['script','img','link'] and (t!='link' or a.get('rel')!='canonical')]
        self.assertTrue(all(not url or url.startswith('/') for url in resources))
        script=(ROOT/'src/app.mjs').read_text()
        self.assertNotIn('pointermove',script)
        self.assertNotIn('requestAnimationFrame',script)
        css=(ROOT/'src/styles.css').read_text()
        self.assertIn('rotateX(0deg) rotateY(0deg) rotateZ(0deg)',css)
        self.assertIn('prefers-reduced-motion:reduce',css)

    def test_preview_indexing_does_not_block_social_crawlers(self):
        self.assertIn('User-agent: *\nAllow: /',(ROOT/'dist/robots.txt').read_text())
        if not self.c['indexable']:
            self.assertIn('content="noindex, follow"',self.html)


if __name__=='__main__':unittest.main()
