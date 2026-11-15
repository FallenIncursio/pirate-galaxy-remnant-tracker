"""Deterministic PNG status board inspired by the game's Remnant panel."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont

from .card import LABELS
from .intel import clock, departure_detail, duration, reveal_detail
from .model import Snapshot

WIDTH = 1200
ROW_HEIGHT = 168
ROW_STEP = 180
MAX_ROWS = 15
GOLD, PURPLE, WHITE, MUTED = '#e9c653', '#d979fa', '#ecf1f4', '#9babb6'
GREEN, BLUE, LINE = '#74ff9f', '#a6d9ef', '#314145'


@lru_cache(maxsize=40)
def font(size: int, bold: bool = False):
    windows = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    names = ('seguisb.ttf', 'segoeuib.ttf', 'arialbd.ttf') if bold else ('segoeui.ttf', 'arial.ttf')
    candidates = [windows / name for name in names]
    candidates += [Path('/usr/share/fonts/truetype/dejavu') / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                   Path('/usr/share/fonts/truetype/liberation2') / ('LiberationSans-Bold.ttf' if bold else 'LiberationSans-Regular.ttf')]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def fit(draw, value: str, width: int, size: int, bold=False):
    face = font(size, bold)
    value = ''.join(c if ord(c) >= 32 else ' ' for c in value)
    if draw.textlength(value, font=face) <= width:
        return value
    while value and draw.textlength(value + '…', font=face) > width:
        value = value[:-1]
    return value + '…'


def text(draw, xy, value, size=20, color=WHITE, bold=False, width=None, right=False):
    value = str(value)
    if width is not None:
        value = fit(draw, value, width, size, bold)
    x, y = xy
    if right:
        x -= draw.textlength(value, font=font(size, bold))
    draw.text((x, y), value, font=font(size, bold), fill=color)


def name(value):
    return LABELS.get(value, value) if value else None


def glyph(draw, x, y, boss):
    accent = PURPLE if boss else GOLD
    draw.rounded_rectangle((x, y, x+76, y+82), radius=9, fill='#101a1d', outline='#354549', width=1)
    draw.ellipse((x+10, y+9, x+66, y+65), outline='#344a4b', width=1)
    draw.line((x+38,y+7,x+38,y+68), fill='#293b3c')
    draw.line((x+8,y+37,x+68,y+37), fill='#293b3c')
    # Own vector emblem; no extracted game artwork or invented ship portrait.
    draw.polygon([(x+38,y+16),(x+57,y+30),(x+52,y+53),(x+38,y+63),(x+24,y+53),(x+19,y+30)],
                 fill='#2b2332' if boss else '#2c2b1e', outline=accent)
    label = 'XC' if boss else 'SC'
    text(draw,(x+38-draw.textlength(label,font=font(20,True))/2,y+27),label,20,accent,True)
    text(draw,(x+38-draw.textlength('TRÄGER',font=font(10,True))/2,y+67),'TRÄGER',10,MUTED,True)


def render(snapshot: Snapshot | None, *, server: str, poll_seconds: int, now_ms: int,
           problem: str | None = None, history: dict | None = None) -> bytes:
    carriers = sorted(snapshot.carriers, key=lambda c: (c.spawn_ms,c.name)) if snapshot else ()
    visible = carriers[:MAX_ROWS]
    rows = max(1, len(visible))
    footer_y = 168 + rows * ROW_STEP
    height = footer_y + 120
    image = Image.new('RGB', (WIDTH,height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1,height-1)
        draw.line((0,y,WIDTH,y), fill=tuple(round(a+(b-a)*t) for a,b in zip((21,32,34),(7,12,16))))
    draw.rounded_rectangle((20,18,1180,height-18),radius=15,fill='#10191c',outline='#415155',width=2)
    draw.rectangle((21,42,25,height-42),fill='#b98e47' if problem else GOLD)
    text(draw,(50,35),'PIRATE GALAXY',14,GOLD,True)
    text(draw,(214,35),'/  REMNANTEN',14,MUTED,True)
    draw.line((50,61,1150,61),fill=LINE)
    text(draw,(50,72),'REMNANT-TRÄGER',40,WHITE,True)
    observed = snapshot.observed_ms if snapshot else None
    observed_text = clock(observed,date=True) + ' Uhr' if observed else 'noch kein Datenstand'
    text(draw,(52,125),f'{server.upper()}  ·  {len(carriers):02d} SIGNALE  ·  {sum(c.kind=="boss" for c in carriers):02d} XC  ·  {poll_seconds//60}-MIN-TAKT',16,MUTED,True)
    badge = 'LETZTER STAND' if problem else 'VERBUNDEN'
    accent = '#e8b26b' if problem else GREEN
    draw.rounded_rectangle((946,78,1150,114),radius=6,fill='#30271d' if problem else '#1b302b',outline=accent)
    draw.ellipse((962,92,970,100),fill=accent)
    text(draw,(981,85),badge,15,accent,True)
    text(draw,(1150,128),observed_text,16,WHITE,right=True)
    if not visible:
        text(draw,(60,218),'Keine Träger gelistet' if snapshot else 'Verbindung wird aufgebaut',28,WHITE,True)
        text(draw,(60,264),'Warte auf den nächsten bestätigten Datenstand.' if not snapshot else 'Bestätigter leerer Stand vom Spielserver.',19,MUTED)
    for index, carrier in enumerate(visible):
        top = 170 + index*ROW_STEP
        boss = carrier.kind == 'boss'
        accent = PURPLE if boss else GOLD
        draw.rounded_rectangle((44,top,1156,top+ROW_HEIGHT),radius=8,
                               fill='#1d1b24' if boss else ('#172225' if index%2==0 else '#141f22'),
                               outline='#58405e' if boss else LINE,width=1)
        draw.rounded_rectangle((45,top+10,49,top+ROW_HEIGHT-10),radius=2,fill=accent)
        glyph(draw,62,top+37,boss)
        text(draw,(158,top+12),carrier.name,29,accent,True,width=590)
        age = duration(max(0,(observed or now_ms)-carrier.spawn_ms))
        spawn_label = f'SPAWN {clock(carrier.spawn_ms,date=True)}  ·  {age}'
        if carrier.spawn_ms > (observed or now_ms):
            spawn_label = f'SPAWN {clock(carrier.spawn_ms,date=True)}  ·  in {duration(carrier.spawn_ms-(observed or now_ms))}'
        text(draw,(1134,top+22),spawn_label,15,MUTED,right=True)
        draw.line((158,top+52,1134,top+52),fill=LINE)
        columns = [('system','SYSTEMTECHNOLOGIE',158,280,GREEN,'System noch unbekannt'),
                   ('category','BEUTE',458,330,BLUE,'Beute nach Anschuss'),
                   ('planet','PLANET',812,322,GREEN,'Planet noch unbekannt')]
        for field, title, x, width, color, unknown in columns:
            value = name(getattr(carrier,field))
            text(draw,(x,top+61),title,11,MUTED,True)
            text(draw,(x,top+78),value or unknown,22,color if value else MUTED, bool(value),width=width)
            detail = reveal_detail(carrier,field,observed or now_ms,(history or {}).get(carrier.key))
            text(draw,(x,top+109),detail,13,MUTED,width=width)
        bar_x, bar_y, bar_w = 158, top+145, 290
        draw.rounded_rectangle((bar_x,bar_y,bar_x+bar_w,bar_y+8),radius=3,fill='#263538')
        if carrier.hp is None:
            for offset in range(0,bar_w,17):
                draw.line((bar_x+offset,bar_y+7,bar_x+min(offset+7,bar_w),bar_y),fill='#425054')
        elif carrier.hp:
            fill = '#da6659' if carrier.hp<30 else '#e9b856' if carrier.hp<60 else '#78c9a3'
            draw.rectangle((bar_x,bar_y,bar_x+round(bar_w*carrier.hp/100),bar_y+8),fill=fill)
        text(draw,(465,top+136),'HP unbekannt' if carrier.hp is None else f'HP {carrier.hp} %',16,MUTED if carrier.hp is None else WHITE,True)
        text(draw,(1134,top+136),departure_detail(carrier,observed or now_ms,stale=bool(problem)),16,BLUE if carrier.departure_ms else MUTED,right=True)
    draw.line((50,footer_y+3,1150,footer_y+3),fill=LINE)
    footer = problem or ('Alle gelisteten Träger' if len(carriers)<=MAX_ROWS else f'Anzeige {MAX_ROWS} von {len(carriers)} Trägern · vollständiger Verlauf lokal')
    text(draw,(52,footer_y+13),footer,16,'#e8b26b' if problem else WHITE,True,width=1095)
    text(draw,(52,footer_y+39),'Reveal-Zeit offen: Der Server meldet keinen Termin. Anschuss legt alle Informationen sofort offen.',15,MUTED,width=1095)
    text(draw,(52,footer_y+65),'Erfasst / Reveal = Beobachtung des Trackers  ·  Zeiten: Europe/Berlin  ·  Countdown gilt zum Datenstand',13,MUTED,width=1095)
    output = BytesIO()
    image.save(output,format='PNG',optimize=True)
    return output.getvalue()
