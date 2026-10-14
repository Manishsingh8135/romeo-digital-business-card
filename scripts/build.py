"""Build a portable, crawler-readable card. Runtime: static files only."""
from pathlib import Path
from html import escape
from urllib.parse import urlparse, quote
from hashlib import sha256
import base64
import io
import json
import re
import shutil
import uuid

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageFilter
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


KEEP_DIR = 'assets/keep'
KEEP_FILES = {
    'front': 'romeos-health-heaven-card-front.png',
    'back': 'romeos-health-heaven-card-back.png',
    'pdf': 'romeos-health-heaven-card.pdf',
    'frontThumb': 'card-front-thumb.jpg',
    'backThumb': 'card-back-thumb.jpg',
}
FACE = (1050, 600)  # 3.5 × 2 in; rendered at 2× = 600 dpi.
FACE_SCALE = 2


class Painter:
    """Draws in card points (1050 × 600) on a 2× canvas, matching the live card's type."""
    fonts = {
        'serif': ROOT/'src/design-fonts/CormorantGaramond-500.ttf',
        'italic': ROOT/'src/design-fonts/CormorantGaramond-400i.ttf',
        'sans': ROOT/'assets/fonts/dm-sans-0.ttf',
        'sans-medium': ROOT/'assets/fonts/dm-sans-1.ttf',
    }

    def __init__(self, image):
        self.image = image
        self.draw = ImageDraw.Draw(image, 'RGBA')
        self.cache = {}

    def s(self, value):
        return round(value * FACE_SCALE)

    def font(self, name, size):
        key = (name, size)
        if key not in self.cache:
            self.cache[key] = ImageFont.truetype(str(self.fonts[name]), self.s(size))
        return self.cache[key]

    def width(self, value, name, size, tracking=0):
        font = self.font(name, size)
        if not tracking: return font.getlength(value) / FACE_SCALE
        return sum(font.getlength(char) for char in value) / FACE_SCALE + tracking * (len(value) - 1)

    def text(self, x, baseline, value, name, size, fill, tracking=0, align='left'):
        """Left/right/centre aligned on a baseline; tracking in card points like CSS letter-spacing."""
        if align == 'right': x -= self.width(value, name, size, tracking)
        elif align == 'center': x -= self.width(value, name, size, tracking) / 2
        font = self.font(name, size)
        if not tracking:
            self.draw.text((self.s(x), self.s(baseline)), value, font=font, fill=fill, anchor='ls')
            return
        cursor = x
        for char in value:
            self.draw.text((self.s(cursor), self.s(baseline)), char, font=font, fill=fill, anchor='ls')
            cursor += font.getlength(char) / FACE_SCALE + tracking


def paper(size):
    """Ivory stock: warm base, a soft top-left light, and the live card's fine paper grain."""
    width, height = size
    image = Image.new('RGBA', size, '#fffcf2')
    light = Image.radial_gradient('L').resize((round(width * 1.5), round(height * 1.9)), Image.Resampling.BICUBIC)
    light = light.point(lambda value: max(0, 235 - value * 1.6))
    glow = Image.new('RGBA', size, '#fffefa')
    glow.putalpha(light.crop((round(width * .36), round(height * .6), round(width * .36) + width, round(height * .6) + height)))
    image.alpha_composite(glow)
    grain = Image.new('RGBA', size)
    gd = ImageDraw.Draw(grain)
    for y in range(0, height, 6): gd.line((0, y, width, y), fill='#9585640b', width=1)
    for x in range(0, width, 8): gd.line((x, 0, x, height), fill='#ffffff38', width=1)
    image.alpha_composite(grain)
    return image


def blind_frame(p):
    p.draw.rounded_rectangle([p.s(24), p.s(24), p.s(FACE[0]-24), p.s(FACE[1]-24)], radius=p.s(24), outline='#e6e0d0', width=p.s(1))
    p.draw.rounded_rectangle([p.s(24), p.s(25), p.s(FACE[0]-24), p.s(FACE[1]-23)], radius=p.s(24), outline='#ffffffa0', width=1)


def embossed_seal(image, center, radius):
    """The front seal: brushed gold ring, recessed core, and the untouched brand logo."""
    s = lambda value: round(value * FACE_SCALE)
    cx, cy, r = s(center[0]), s(center[1]), s(radius)
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).ellipse((cx-r+s(4), cy-r+s(8), cx+r+s(4), cy+r+s(8)), fill='#7468453a')
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s(9))))
    ring = Image.new('RGBA', (2*r, 2*r))
    rd = ImageDraw.Draw(ring)
    stops = ['#eee6cd', '#fffced', '#dfd2ad', '#f9f3de', '#e8dcbc', '#fffce8', '#eee6cd']
    def mix(a, b, t): return tuple(round(int(a[i:i+2], 16) * (1-t) + int(b[i:i+2], 16) * t) for i in (1, 3, 5))
    for degree in range(360):
        position = degree / 360 * (len(stops) - 1)
        index = min(int(position), len(stops) - 2)
        rd.pieslice((0, 0, 2*r-1, 2*r-1), degree - 75, degree - 74 + 1, fill=mix(stops[index], stops[index+1], position - index))
    mask = Image.new('L', ring.size)
    ImageDraw.Draw(mask).ellipse((0, 0, 2*r-1, 2*r-1), fill=255)
    ring.putalpha(mask)
    image.alpha_composite(ring, (cx-r, cy-r))
    d = ImageDraw.Draw(image, 'RGBA')
    d.ellipse((cx-r, cy-r, cx+r, cy+r), outline='#d7cda7', width=s(1))
    d.ellipse((cx-r+s(2), cy-r+s(2), cx+r-s(2), cy+r-s(2)), outline='#ffffffaa', width=s(1))
    inner = r - s(14)
    d.ellipse((cx-inner, cy-inner, cx+inner, cy+inner), outline='#ad9b6650', width=s(1))
    core = r - s(40)
    # Light falls from the upper left, as in the CSS radial-gradient(circle at 30% 20%).
    well = Image.radial_gradient('L').resize((4*core, 4*core), Image.Resampling.BICUBIC).crop((round(1.4*core), round(1.6*core), round(3.4*core), round(3.6*core)))
    core_image = Image.composite(Image.new('RGBA', well.size, '#ebe4cf'), Image.new('RGBA', well.size, '#fffff7'), well)
    core_mask = Image.new('L', well.size)
    ImageDraw.Draw(core_mask).ellipse((0, 0, 2*core-1, 2*core-1), fill=255)
    core_image.putalpha(core_mask)
    image.alpha_composite(core_image, (cx-core, cy-core))
    d.ellipse((cx-core, cy-core, cx+core, cy+core), outline='#e3dac1', width=s(1))
    # Recessed core: a soft inner shadow under the upper rim.
    rim = Image.new('L', image.size)
    ImageDraw.Draw(rim).ellipse((cx-core, cy-core-s(3), cx+core, cy+core-s(3)), outline=60, width=s(5))
    inside = Image.new('L', image.size)
    ImageDraw.Draw(inside).ellipse((cx-core, cy-core, cx+core, cy+core), fill=255)
    shade = Image.new('RGBA', image.size, '#786945')
    shade.putalpha(ImageChops.multiply(rim.filter(ImageFilter.GaussianBlur(s(4))), inside))
    image.alpha_composite(shade)
    logo = Image.open(ROOT/'assets/images/logo.webp').convert('RGBA')
    logo = ImageEnhance.Color(logo).enhance(.6)
    logo.thumbnail((round(core*1.42), round(core*1.2)), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (cx - logo.width//2, cy - logo.height//2))
    dot = s(2)
    d.ellipse((cx-dot, cy-r+s(11)-dot, cx+dot, cy-r+s(11)+dot), fill='#af9a6680')


def card_face(config, side, qr):
    """Flat face at 2100 × 1200 (3.5 × 2 in, 600 dpi), drawn from the same type and palette as the live card."""
    image = paper((FACE[0]*FACE_SCALE, FACE[1]*FACE_SCALE))
    p = Painter(image)
    blind_frame(p)
    if side == 'front':
        p.text(62, 84, 'A LITTLE CLOSER', 'sans', 21, '#71806b', tracking=4.2)
        p.text(62, 120, 'TO NATURE.', 'sans', 21, '#71806b', tracking=4.2)
        p.text(58, 262, 'Romeo’s', 'serif', 116, '#294237', tracking=-3.6)
        p.text(60, 352, 'Health Heaven', 'italic', 96, '#66774e', tracking=-2.4)
        p.text(62, 420, 'Cold-pressed juices.', 'sans', 24, '#67725f')
        p.text(62, 458, 'Plant-based living, with purpose.', 'sans', 24, '#67725f')
        p.text(62, 540, config['founder'], 'serif', 52, '#294237')
        p.text(62 + p.width(config['founder'], 'serif', 52) + 14, 540, '·  ' + config['role'], 'sans', 22, '#7c816f')
        p.text(988, 540, f'{config["city"].upper()}, {config["region"]}', 'sans', 17, '#7c816f', tracking=3, align='right')
        embossed_seal(image, (866, 214), 124)
    else:
        p.text(60, 132, f'Meet {config["founder"]}.', 'serif', 86, '#294237', tracking=-1.2)
        p.text(63, 176, f'{config["role"]} · {config["brand"]}', 'sans', 22, '#7b826d')
        for index, line in enumerate(['Plant-based living.', 'A love of nature.', 'A community that', 'grows together.']):
            p.text(62, 276 + index * 44, line, 'serif', 40, '#62705a')
        rows = [('PHONE', config['phoneDisplay']), ('EMAIL', config['email']), ('WEBSITE', urlparse(config['websiteUrl']).hostname)]
        for index, (label, value) in enumerate(rows):
            top = 270 + index * 74
            p.text(540, top, label, 'sans', 15, '#95977e', tracking=2.2)
            p.text(540, top + 33, value, 'sans', 23, '#294237')
        well = (826, 54, 988, 216)
        p.draw.rounded_rectangle([p.s(v) for v in well], radius=p.s(14), fill='#ffffff', outline='#e4dfd1', width=p.s(1))
        code = qr.resize((p.s(140), p.s(140)), Image.Resampling.NEAREST)
        image.alpha_composite(code, (p.s(837), p.s(65)))
        p.text(907, 242, 'SCAN TO OPEN', 'sans', 13, '#818571', tracking=2.4, align='center')
        p.draw.line((p.s(62), p.s(500), p.s(988), p.s(500)), fill='#e3ddcc', width=p.s(1))
        p.text(62, 542, f'{config["city"]}, New York' if config['region'] == 'NY' else f'{config["city"]}, {config["region"]}', 'sans', 18, '#7b826d')
        p.text(988, 542, urlparse(config['cardUrl']).hostname, 'sans', 18, '#7b826d', align='right')
    return image.convert('RGB')


def keepsake_photo(face):
    """The face resting on the stage, the way it sits on screen: rounded, layered stock, soft shadow."""
    width, height = 2400, 1600
    left, top = (width - face.width) // 2, 170
    radius = 72
    stage = Image.new('RGBA', (width, height), '#eeece4')
    light = Image.radial_gradient('L').resize((width * 2, height * 2))
    glow = Image.new('RGBA', stage.size, '#fffefa')
    glow.putalpha(light.crop((width - 300, height - 200, width * 2 - 300, height * 2 - 200)).point(lambda value: max(0, 200 - value)))
    stage.alpha_composite(glow)
    shadow = Image.new('RGBA', stage.size)
    ImageDraw.Draw(shadow).rounded_rectangle((left + 40, top + 70, left + face.width - 40, top + face.height + 50), radius=radius, fill='#5b604440')
    stage.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(46)))
    d = ImageDraw.Draw(stage)
    for offset, color in [(14, '#cbc2aa'), (9, '#e0d8c4'), (4, '#beb59d')]:
        d.rounded_rectangle((left, top + offset, left + face.width, top + face.height + offset), radius=radius, fill=color)
    mask = Image.new('L', face.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, face.width - 1, face.height - 1), radius=radius, fill=255)
    stage.paste(face, (left, top), mask)
    d.rounded_rectangle((left, top, left + face.width, top + face.height), radius=radius, outline='#d8d0be', width=2)
    return stage.convert('RGB')


def keepsakes(config):
    """Front and back to keep: photo-ready PNGs, a two-page card-size PDF, and drawer thumbnails."""
    folder = OUT/KEEP_DIR
    folder.mkdir(parents=True, exist_ok=True)
    qr = segno.make(config['cardUrl'], error='m', micro=False)
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=10, border=2, dark='#203b2c', light='#ffffff')
    qr_image = Image.open(io.BytesIO(buffer.getvalue())).convert('RGBA')
    faces = {side: card_face(config, side, qr_image) for side in ['front', 'back']}
    for side, face in faces.items():
        keepsake_photo(face).save(folder/KEEP_FILES[side], optimize=True)
        thumb = face.resize((560, 320), Image.Resampling.LANCZOS)
        thumb.save(folder/KEEP_FILES[side + 'Thumb'], quality=88, optimize=True, progressive=True)
    faces['front'].save(folder/KEEP_FILES['pdf'], save_all=True, append_images=[faces['back']], resolution=600.0,
        title=f'{config["brand"]} · Business card', author=config['brand'], subject='Front and back of the card',
        creationDate=None, modDate=None)


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
    keepsakes(config)

    share_text = f'Meet {config["founder"]} · {config["brand"]}\n{config["cardUrl"]}'
    values = {**config,
        'cardHost':urlparse(config['cardUrl']).hostname,
        'socialImagePath':social_name,
        'keepFront':f'/{KEEP_DIR}/{KEEP_FILES["front"]}','keepBack':f'/{KEEP_DIR}/{KEEP_FILES["back"]}','keepPdf':f'/{KEEP_DIR}/{KEEP_FILES["pdf"]}',
        'keepFrontThumb':f'/{KEEP_DIR}/{KEEP_FILES["frontThumb"]}','keepBackThumb':f'/{KEEP_DIR}/{KEEP_FILES["backThumb"]}',
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
    nojs = f'''<noscript><link rel="stylesheet" href="/no-script.css"><section class="no-script"><h2>Keep in touch with Romeo</h2><p><a href="tel:{e(config['phone'])}">{e(config['phoneDisplay'])}</a> · <a href="mailto:{e(config['email'])}">{e(config['email'])}</a></p><p><a href="/romeo-health-heaven.vcf">Open contact file</a> · <a href="{e(config['shopUrl'])}">Visit the shop</a></p><p>Keep the card: <a href="/{KEEP_DIR}/{KEEP_FILES['pdf']}" download>front &amp; back (PDF)</a></p><p>Share this address: <a href="{e(config['cardUrl'])}">{e(config['cardUrl'])}</a></p><img src="/assets/qr-card.svg" alt="QR code for Romeo’s card" width="200" height="200"></section></noscript>'''
    (OUT/'index.html').write_text(head+body+nojs+'</body></html>\n')
    for filename in ['styles.css','app.mjs','sharing.mjs','no-script.css']:
        shutil.copyfile(ROOT/'src'/filename,OUT/filename)
    public_config = {key:config[key] for key in ['brand','founder','cardUrl']}
    public_config['keep'] = {side:f'/{KEEP_DIR}/{KEEP_FILES[side]}' for side in ['front','back','pdf']}
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
    netlify_headers = '/*\n'+''.join(f'  {key}: {value}\n' for key,value in headers.items())+'\n/romeo-health-heaven.vcf\n  Content-Type: text/vcard; charset=utf-8\n  Content-Disposition: inline; filename="romeo-health-heaven.vcf"\n\n/site.webmanifest\n  Content-Type: application/manifest+json\n\n/'+KEEP_DIR+'/*\n  Content-Disposition: attachment\n\n/sw.js\n  Cache-Control: no-cache\n'
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
            {'source':f'/{KEEP_DIR}/(.*)','headers':[{'key':'Content-Disposition','value':'attachment'}]},
        ],
    }
    (ROOT/'vercel.json').write_text(json.dumps(vercel,indent=2)+'\n')

    # Contents determine the cache version, so a changed contact / image cannot reuse an old cache.
    cache_files = ['/'] + ['/'+str(path.relative_to(OUT)) for path in sorted(OUT.rglob('*')) if path.is_file() and path.suffix in ['.css','.mjs','.png','.webp','.ttf','.vcf','.webmanifest'] and not path.relative_to(OUT).as_posix().startswith(KEEP_DIR+'/')]
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
