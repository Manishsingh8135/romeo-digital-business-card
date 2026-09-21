"""Build a portable, crawler-readable card. Runtime: static files only."""
from pathlib import Path
from html import escape
from urllib.parse import urlparse, quote
from hashlib import sha256
import base64
import json
import re
import shutil
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import segno

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'


def vcard_escape(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold_line(line):
    """RFC 2425: 75 UTF-8 octets, no split codepoints; continuation includes space."""
    lines, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            lines.append(current)
            current = ' '
        current += char
    return '\r\n'.join(lines + [current])


def vcard(config):
    e = vcard_escape
    lines = [
        'BEGIN:VCARD', 'VERSION:3.0',
        f'N:;{e(config["founder"])};;;',
        f'FN:{e(config["founder"] + " · " + config["brand"])}',
        f'ORG:{e(config["brand"])}', f'TITLE:{e(config["role"])}',
        f'TEL;TYPE=WORK,VOICE:{config["phone"]}',
        f'EMAIL;TYPE=INTERNET,WORK:{config["email"]}',
        f'ADR;TYPE=WORK:;;;{e(config["city"])};{e(config["region"])};;{e(config["country"])}',
        f'URL:{config["cardUrl"]}',
        f'NOTE:{e("Cold-pressed juices. Plant-based living, with purpose. Website: " + config["websiteUrl"])}',
        'UID:urn:uuid:' + str(uuid.uuid5(uuid.NAMESPACE_URL, config['websiteUrl'] + '#romeo')),
        'END:VCARD',
    ]
    return ('\r\n'.join(map(fold_line, lines)) + '\r\n').encode('utf-8')


def validate(config):
    for key in ['cardUrl', 'websiteUrl', 'shopUrl']:
        url = urlparse(config[key])
        if url.scheme != 'https' or not url.hostname or url.query or url.fragment or url.username or url.password:
            raise ValueError(f'{key} must be a clean, absolute HTTPS URL')
    if urlparse(config['cardUrl']).path != '/':
        raise ValueError('This build expects its own subdomain root ending in /')
    if not isinstance(config['indexable'], bool):
        raise ValueError('indexable must be true or false')
    if not re.fullmatch(r'\+[1-9][0-9]{7,14}', config['phone']):
        raise ValueError('phone must use E.164 format')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', config['email']):
        raise ValueError('Invalid public email')


def social_image(config, destination):
    # A new code-rendered composition, using the approved brand's existing logo.
    scale = 2
    def xy(box): return tuple(round(x * scale) for x in box)
    image = Image.new('RGB', (1200 * scale, 630 * scale), '#eeece4')
    shadow = Image.new('RGBA', image.size)
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(xy((102, 114, 1098, 544)), radius=34*scale, fill='#5b604434')
    image = Image.alpha_composite(image.convert('RGBA'), shadow.filter(ImageFilter.GaussianBlur(22*scale)))
    d = ImageDraw.Draw(image)
    for offset, color in [(8,'#d0c7af'), (5,'#e5dcc7'), (2,'#f4ecd9'), (0,'#fffdf3')]:
        d.rounded_rectangle(xy((95, 89+offset, 1105, 521+offset)), radius=26*scale, fill=color, outline='#d8d0bc', width=scale)
    d.rounded_rectangle(xy((111, 105, 1089, 505)), radius=17*scale, outline='#e5decb', width=scale)
    serif = ROOT/'src/design-fonts/CormorantGaramond-500.ttf'
    italic = ROOT/'src/design-fonts/CormorantGaramond-400i.ttf'
    sans = ROOT/'src/design-fonts/Montserrat-400.ttf'
    def text(pos, value, font, size, color):
        d.text(xy(pos), value, font=ImageFont.truetype(str(font), size*scale), fill=color)
    text((154,135), 'A LITTLE CLOSER TO NATURE.', sans, 17, '#657359')
    text((151,181), 'Romeo’s', serif, 89, '#294237')
    text((153,271), 'Health Heaven', italic, 76, '#65754f')
    text((157,382), 'Cold-pressed juices.', sans, 21, '#5b6d52')
    text((157,416), 'Plant-based living, with purpose.', sans, 21, '#5b6d52')
    text((156,468), 'ROMEO  ·  FOUNDER', sans, 13, '#6c735f')
    # Stationary embossed seal. The original logo is placed without retouching.
    d.ellipse(xy((840,188,1030,378)),fill='#b9ae8b')
    d.ellipse(xy((838,181,1028,371)),fill='#eee5ca',outline='#cbbd94',width=scale)
    d.ellipse(xy((846,187,1020,361)),outline='#fffdf0',width=2*scale)
    d.ellipse(xy((856,199,1010,353)),outline='#d1c298',width=scale)
    d.ellipse(xy((873,216,993,336)),fill='#fbf7e8',outline='#e0d5b8',width=scale)
    logo = Image.open(ROOT/'assets/images/logo.webp').convert('RGBA')
    logo.thumbnail((101*scale,90*scale),Image.Resampling.LANCZOS)
    image.alpha_composite(logo,(int(933*scale-logo.width/2),int(276*scale-logo.height/2)))
    d = ImageDraw.Draw(image)
    text((741,463), 'Brooklyn, New York', sans, 18, '#6c735f')
    text((154,562), urlparse(config['cardUrl']).hostname, sans, 18, '#6c735f')
    image.convert('RGB').resize((1200,630),Image.Resampling.LANCZOS).save(destination,quality=92,optimize=True,progressive=True)


def icons():
    logo = Image.open(ROOT/'assets/images/logo.webp').convert('RGBA')
    for size,name in [(32,'favicon-32.png'),(180,'apple-touch-icon.png'),(192,'icon-192.png'),(512,'icon-512.png'),(512,'icon-maskable-512.png')]:
        image = Image.new('RGBA',(size,size),'#fffcf2')
        mark = logo.copy()
        # Entire original mark stays inside the maskable icon's safe zone.
        mark.thumbnail((round(size*.62),round(size*.62)),Image.Resampling.LANCZOS)
        image.alpha_composite(mark,((size-mark.width)//2,(size-mark.height)//2))
        image.save(OUT/'assets'/name)
        if name=='icon-192.png': image.save(OUT/'favicon.ico',sizes=[(16,16),(32,32),(48,48)])


def main():
    config = json.loads((ROOT/'site.config.json').read_text())
    validate(config)
    # Only remove our known generated directory; authoring files are never touched.
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT/'assets',OUT/'assets')
    qr = segno.make(config['cardUrl'],error='m',micro=False)
    qr.save(OUT/'assets/qr-card.svg',scale=7,border=4,dark='#203b2c',light='#ffffff',xmldecl=False)
    qr.save(OUT/'assets/qr-card.png',scale=20,border=4,dark='#203b2c',light='#ffffff')
    (OUT/'romeo-health-heaven.vcf').write_bytes(vcard(config))
    social = OUT/'assets/social-card.jpg'
    social_image(config,social)
    social_hash = sha256(social.read_bytes()).hexdigest()[:12]
    social_name = f'/assets/social-card-{social_hash}.jpg'
    social.rename(OUT/social_name.lstrip('/'))
    icons()

    share_text = f'Meet {config["founder"]} · {config["brand"]}\n{config["cardUrl"]}'
    values = {**config,
        'cardHost':urlparse(config['cardUrl']).hostname,
        'socialImagePath':social_name,
        'whatsappShare':'https://wa.me/?text='+quote(share_text,safe=''),
        'emailShare':'mailto:?subject='+quote(config['brand'],safe='')+'&body='+quote(share_text,safe=''),
    }
    body = (ROOT/'src/card.html').read_text()
    body = re.sub(r'\{\{(\w+)\}\}',lambda match:escape(str(values[match[1]]),quote=True),body)
    def insert_icon(match):
        raw = (ROOT/'assets/icons'/f'{match[1]}.svg').read_text()
        raw = re.sub(r'<\?xml[^>]*\?>|<!--[\s\S]*?-->','',raw).strip()
        return raw.replace('<svg ','<svg aria-hidden="true" focusable="false" ',1)
    body = re.sub(r'<i data-lucide="([^"]+)"[^>]*></i>',insert_icon,body)

    schema = {
        '@context':'https://schema.org','@graph':[
            {'@type':'Organization','@id':config['websiteUrl']+'#organization','name':config['brand'],
             'url':config['websiteUrl'],'logo':config['cardUrl']+'assets/images/logo.webp',
             'email':config['email'],'telephone':config['phone'],
             'address':{'@type':'PostalAddress','addressLocality':config['city'],'addressRegion':config['region'],'addressCountry':config['country']},
             'founder':{'@id':config['cardUrl']+'#romeo'}},
            {'@type':'Person','@id':config['cardUrl']+'#romeo','name':config['founder'],
             'jobTitle':config['role'],'worksFor':{'@id':config['websiteUrl']+'#organization'}},
            {'@type':'WebPage','@id':config['cardUrl']+'#card','url':config['cardUrl'],'name':config['title'],
             'description':config['description'],'about':{'@id':config['websiteUrl']+'#organization'},'inLanguage':'en-US'},
        ]
    }
    schema_text = json.dumps(schema,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    schema_hash = base64.b64encode(sha256(schema_text.encode()).digest()).decode()
    e = escape
    image_url = config['cardUrl'].rstrip('/')+social_name
    robots = 'index, follow, max-image-preview:large' if config['indexable'] else 'noindex, follow'
    head = f'''<!doctype html>
<html lang="en-US"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(config['title'])}</title>
<meta name="description" content="{e(config['description'],quote=True)}">
<meta name="robots" content="{robots}">
<meta name="theme-color" content="{config['themeColor']}">
<meta name="color-scheme" content="light">
<meta name="format-detection" content="telephone=no">
<link rel="canonical" href="{e(config['cardUrl'],quote=True)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="en_US">
<meta property="og:site_name" content="{e(config['brand'],quote=True)}">
<meta property="og:title" content="{e(config['title'],quote=True)}">
<meta property="og:description" content="{e(config['description'],quote=True)}">
<meta property="og:url" content="{e(config['cardUrl'],quote=True)}">
<meta property="og:image" content="{image_url}">
<meta property="og:image:secure_url" content="{image_url}">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(config['imageAlt'],quote=True)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(config['title'],quote=True)}">
<meta name="twitter:description" content="{e(config['description'],quote=True)}">
<meta name="twitter:image" content="{image_url}">
<meta name="twitter:image:alt" content="{e(config['imageAlt'],quote=True)}">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png" sizes="180x180">
<meta name="apple-mobile-web-app-title" content="Romeo’s">
<link rel="manifest" href="/site.webmanifest">
<link rel="preload" href="/assets/fonts/cormorant-roman.ttf" as="font" type="font/ttf" crossorigin>
<link rel="preload" href="/assets/fonts/dm-sans-0.ttf" as="font" type="font/ttf" crossorigin>
<link rel="stylesheet" href="/styles.css">
<script type="application/ld+json">{schema_text}</script>
<script type="module" src="/app.mjs"></script>
</head><body>
'''
    nojs = f'''<noscript><link rel="stylesheet" href="/no-script.css"><section class="no-script"><h2>Keep in touch with Romeo</h2><p><a href="tel:{e(config['phone'])}">{e(config['phoneDisplay'])}</a> · <a href="mailto:{e(config['email'])}">{e(config['email'])}</a></p><p><a href="/romeo-health-heaven.vcf">Open contact file</a> · <a href="{e(config['shopUrl'])}">Visit the shop</a></p><p>Share this address: <a href="{e(config['cardUrl'])}">{e(config['cardUrl'])}</a></p><img src="/assets/qr-card.svg" alt="QR code for Romeo’s card" width="200" height="200"></section></noscript>'''
    (OUT/'index.html').write_text(head+body+nojs+'</body></html>\n')
    for filename in ['styles.css','app.mjs','sharing.mjs','no-script.css']:
        shutil.copyfile(ROOT/'src'/filename,OUT/filename)
    public_config = {key:config[key] for key in ['brand','founder','cardUrl']}
    (OUT/'config.mjs').write_text('export default '+json.dumps(public_config,ensure_ascii=False)+';\n')
    manifest = {
        'id':'/','name':config['brand'],'short_name':'Romeo’s','description':config['description'],
        'lang':'en-US','start_url':'/','scope':'/','display':'standalone',
        'background_color':config['themeColor'],'theme_color':config['themeColor'],
        'icons':[
            {'src':'/assets/icon-192.png','sizes':'192x192','type':'image/png','purpose':'any'},
            {'src':'/assets/icon-512.png','sizes':'512x512','type':'image/png','purpose':'any'},
            {'src':'/assets/icon-maskable-512.png','sizes':'512x512','type':'image/png','purpose':'maskable'},
        ],
        'shortcuts':[{'name':'Share Romeo’s card','short_name':'Share card','url':'/?view=share','icons':[{'src':'/assets/icon-192.png','sizes':'192x192'}]}]
    }
    (OUT/'site.webmanifest').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (OUT/'robots.txt').write_text('User-agent: *\nAllow: /\n'+('Sitemap: '+config['cardUrl']+'sitemap.xml\n' if config['indexable'] else ''))
    if config['indexable']:
        (OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+e(config['cardUrl'])+'</loc></url></urlset>')
    (OUT/'404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Card not found · Romeo’s</title><link rel="stylesheet" href="/styles.css"><main><h1>This little path ends here.</h1><p><a href="/">Return to Romeo’s card</a></p></main></html>')

    # Shared header configuration is enforced by the dev server; deployment must map it to its host.
    csp = "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'; script-src 'self' 'sha256-"+schema_hash+"'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self'; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'"
    headers = {'Content-Security-Policy':csp,'X-Content-Type-Options':'nosniff','Referrer-Policy':'strict-origin-when-cross-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=(), web-share=(self), screen-wake-lock=(self)','Cache-Control':'no-cache'}
    (OUT/'headers.json').write_text(json.dumps(headers,indent=2)+'\n')
    netlify_headers = '/*\n'+''.join(f'  {key}: {value}\n' for key,value in headers.items())+'\n/romeo-health-heaven.vcf\n  Content-Type: text/vcard; charset=utf-8\n  Content-Disposition: inline; filename="romeo-health-heaven.vcf"\n\n/site.webmanifest\n  Content-Type: application/manifest+json\n\n/sw.js\n  Cache-Control: no-cache\n'
    (OUT/'_headers').write_text(netlify_headers)
    vercel = {
        '$schema':'https://openapi.vercel.sh/vercel.json',
        'framework':None,
        'installCommand':'',
        'buildCommand':'node scripts/verify-dist.mjs',
        'outputDirectory':'dist',
        'headers':[
            {'source':'/(.*)','headers':[{'key':key,'value':value} for key,value in headers.items()]},
            {'source':'/romeo-health-heaven.vcf','headers':[
                {'key':'Content-Type','value':'text/vcard; charset=utf-8'},
                {'key':'Content-Disposition','value':'inline; filename="romeo-health-heaven.vcf"'},
            ]},
            {'source':'/site.webmanifest','headers':[{'key':'Content-Type','value':'application/manifest+json'}]},
        ],
    }
    (ROOT/'vercel.json').write_text(json.dumps(vercel,indent=2)+'\n')

    # Contents determine the cache version, so a changed contact / image cannot reuse an old cache.
    cache_files = ['/'] + ['/'+str(path.relative_to(OUT)) for path in sorted(OUT.rglob('*')) if path.is_file() and path.suffix in ['.css','.mjs','.png','.webp','.ttf','.vcf','.webmanifest']]
    cache_files.append('/assets/qr-card.svg')
    digest = sha256(b''.join((OUT/'index.html' if file=='/' else OUT/file.lstrip('/')).read_bytes() for file in cache_files)).hexdigest()[:12]
    sw = (ROOT/'src/sw.js').read_text().replace('__CACHE_VERSION__',digest).replace('__PRECACHE__',json.dumps(cache_files))
    (OUT/'sw.js').write_text(sw)
    source_files = [ROOT/'site.config.json',ROOT/'requirements.txt',ROOT/'scripts/build.py']
    for folder in ['src','assets']:
        source_files.extend(path for path in (ROOT/folder).rglob('*') if path.is_file())
    source_hashes = {path.relative_to(ROOT).as_posix():sha256(path.read_bytes()).hexdigest() for path in sorted(source_files)}
    output_hashes = {path.relative_to(OUT).as_posix():sha256(path.read_bytes()).hexdigest() for path in sorted(OUT.rglob('*')) if path.is_file()}
    (OUT/'build-info.json').write_text(json.dumps({'cardUrl':config['cardUrl'],'indexable':config['indexable'],'socialImage':social_name,'cacheVersion':digest,'qrPayload':config['cardUrl'],'sourceHashes':source_hashes,'outputHashes':output_hashes},indent=2)+'\n')
    print(f'Built {OUT}\nCanonical: {config["cardUrl"]}\nIndexing: {config["indexable"]}\nSocial image: {social_name}\nOffline shell: {len(cache_files)} files')


if __name__=='__main__': main()
