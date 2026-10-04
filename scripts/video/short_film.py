"""Produce a narrated, under-one-minute film from verified app evidence.

prepare -> manage.py test scripts.video.capture_short -> render
Production dependencies belong in .tmp/video-short-deps, outside the app env.
"""
import asyncio
import hashlib
import json
import math
import re
import subprocess
import sys
import wave

import edge_tts
from PIL import Image, ImageDraw

from scripts.video.render import FFMPEG, font, run, seconds_in_video
from scripts.video.render import srt_timestamp
from scripts.video.short_case import ROOT, OUT

FPS, RATE = 30, 48000
VOICE = "en-GB-RyanNeural"
FINAL = ROOT / "Maritime_Carbon_One_Minute.mp4"
INK, GREEN, MUTED = '#102e32', '#c8eea0', '#adcbc5'


def scenes():
    return [
        ('intro', "Maritime Carbon. Compare your next carbon-cost decision.", 4.3),
        ('options', "Explore conventional fuels, pooling, alternative fuels and shore power. Compare the options together, under the same assumptions.", 8.5),
        ('case', "Take this fictional cargo ship in twenty twenty-six: conventional fuel at sea, and marine gas oil at berth.", 8.5),
        ('setup', "Now allow eligible fame, plus shore power that's already installed. Set prices, technical limits, and replaceable berth consumption.", 8.8),
        ('results', "The lowest evaluated option costs about one point one nine million euros: roughly sixty-four thousand less than the reference.", 9.4),
        ('actions', "It selects eighteen tonnes of fame and one hundred and fifty megawatt-hours of shore power. No external pooling is needed.", 9.7),
        ('close', "From assumptions to a clear, traceable decision. Maritime Carbon.", 4.8),
    ]


async def prepare():
    for folder in ('speech', 'raw', 'frames', 'qa', 'clips'):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    plan = []
    for key, text, preferred in scenes():
        digest = hashlib.sha256((VOICE + '+3%' + text).encode()).hexdigest()[:16]
        mp3 = OUT / 'speech' / f'{digest}.mp3'
        if not mp3.exists():
            await edge_tts.Communicate(text, VOICE, rate='+3%').save(str(mp3))
        wav = OUT / 'speech' / f'{key}.wav'
        trim = 'silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.03,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse'
        run(['-i', mp3, '-af', trim, '-ar', RATE, '-ac', 1, '-c:a', 'pcm_s16le', wav])
        with wave.open(str(wav), 'rb') as source:
            length = source.getnframes() / RATE
        duration = math.ceil(max(preferred, length + .55) * FPS) / FPS
        plan.append(dict(key=key, text=text, speech_seconds=length, duration=duration, lead=.2, wav=str(wav)))
        print(f'{key}: {length:.2f}s speech / {duration:.2f}s picture', flush=True)
    duration = sum(s['duration'] for s in plan)
    assert duration <= 59.5, f'Shorten the script; measured duration {duration:.2f}s'
    (OUT / 'shot-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    (OUT / 'Narration.txt').write_text('\n\n'.join(f"{s['key'].upper()}\n{s['text'].replace('fame', 'FAME')}" for s in plan), encoding='utf-8')
    print(f'TOTAL: {duration:.2f}s', flush=True)


W, H = 1920, 1080
WHITE, SURFACE, LINE = '#f6fbf5', '#1c3c40', '#365b5c'
FONTS = {}


def face(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = font(size, bold)
    return FONTS[key]


def label(draw, xy, text, size=30, color=WHITE, bold=False, spacing=1.2):
    x, y = xy
    for line in text.split('\n'):
        draw.text((x, y), line, font=face(size, bold), fill=color, anchor='lt')
        y += round(size * spacing)


def layer(width, height, color=None, radius=24):
    im = Image.new('RGBA', (width, height))
    if color:
        ImageDraw.Draw(im).rounded_rectangle((0, 0, width-1, height-1), radius, fill=color)
    return im


def writing(text, size, width, height, color=WHITE, bold=False):
    im = layer(width, height)
    label(ImageDraw.Draw(im), (0, 0), text, size, color, bold)
    return im


def screenshot(name, width, box=None):
    im = Image.open(OUT / 'raw' / f'{name}.png').convert('RGBA')
    if box:
        im = im.crop(box)
    return im.resize((width, round(im.height * width / im.width)), Image.Resampling.LANCZOS)


def ship(width=740, height=380):
    im = layer(width, height)
    d = ImageDraw.Draw(im)
    # A restrained line illustration, drawn at the native size.
    d.polygon([(36,225),(706,225),(636,298),(98,298)], fill='#2c5455')
    d.line([(36,225),(706,225),(636,298),(98,298),(36,225)], fill=GREEN, width=4)
    for row in range(2):
        for column in range(5):
            x, y = 173+column*80, 119+row*51
            d.rounded_rectangle((x,y,x+72,y+43), 5, fill='#41675f', outline='#759388', width=2)
    d.rectangle((83,157,149,223), fill='#a3c6b4')
    d.rectangle((98,126,140,157), fill=GREEN)
    d.line((117,91,117,126), fill=GREEN, width=4)
    for i in range(3):
        y=319+i*17
        points=[(x,y+4*math.sin(x/70+i)) for x in range(20,727,6)]
        d.line(points, fill=('#789b91' if i==0 else '#365b5c'), width=2)
    return im


def icon(kind, color=GREEN):
    im = layer(112, 96)
    d = ImageDraw.Draw(im)
    if kind == 'ship':
        d.line([(8,54),(102,54),(84,79),(28,79),(8,54)], fill=color, width=4)
        d.rectangle((28,30,67,52), outline=color, width=3)
        d.rectangle((73,39,89,52), outline=color, width=3)
    elif kind == 'pool':
        for x,y in [(10,33),(70,33),(40,1)]:
            d.ellipse((x,y,x+32,y+32), outline=color, width=4)
        d.line([(27,71),(27,84),(87,84),(87,71)], fill=color, width=4)
    elif kind == 'fuel':
        d.polygon([(35,5),(11,43),(15,65),(35,77),(55,65),(59,43)], outline=color, width=4)
        d.line([(82,11),(72,43),(94,43),(78,79)], fill=color, width=5)
    else:
        for x,y in [(10,8),(61,8),(10,57),(61,57)]:
            d.rounded_rectangle((x,y,x+31,y+28), 5, outline=color, width=3)
    return im


def background():
    im = Image.new('RGB', (W,H), INK)
    d = ImageDraw.Draw(im)
    for radius in (220,380,560,750,980):
        d.ellipse((1820-radius,870-radius,1820+radius,870+radius), outline='#1b3b3f', width=2)
    for i,length in enumerate((51,40,29)):
        d.rounded_rectangle((82,59+i*12,82+length,64+i*12), 2, fill=GREEN)
    label(d, (153,57), 'MARITIME CARBON', 29, WHITE, True)
    label(d, (1438,60), 'FuelEU Maritime  +  EU ETS', 25, MUTED)
    return im


def build_scene(key, prepared):
    """Return staged, readable graphic layers; numbers come from the frozen run."""
    items = []
    def add(im, x, y, start=0, slide=22):
        assert x >= 0 and y >= 0 and x+im.width <= W and y+im.height <= 990, (key,x,y,im.size)
        items.append((im,x,y,start,slide))
    def text(text, x, y, size=30, width=1750, height=85, color=WHITE, bold=False, start=0):
        add(writing(text,size,width,height,color,bold),x,y,start)
    def heading(kicker, title):
        text(kicker,82,175,23,height=32,color=GREEN,bold=True)
        text(title,78,224,65,height=95,bold=True,start=.10)
    strategies={s['key']:s for s in prepared['results']['strategies']}
    best=strategies['fuel']
    baseline=strategies['baseline']
    saving=baseline['npv']-best['npv']
    fuels={f['code']:f for f in prepared['inputs']['fuels']}
    vessel=prepared['inputs']['vessels'][0]
    if key == 'intro':
        text('A DECISION FOR YOUR FLEET',83,222,24,color=GREEN,bold=True,height=40)
        text('A clearer route\nto carbon costs.',78,306,104,width=1100,height=268,bold=True,start=.14)
        text('Compare fuels, pooling and shore power.',84,611,34,width=1100,height=70,color=MUTED,start=.35)
        add(ship(),1090,366,.4,12)
        for i,(a,b) in enumerate([('01','Set assumptions'),('02','Compare options'),('03','See the decision')]):
            card=layer(555,102,SURFACE,16)
            d=ImageDraw.Draw(card)
            label(d,(25,34),a,25,GREEN,True)
            label(d,(81,33),b,29,WHITE,True)
            add(card,82+i*581,805,.65+i*.22)
    elif key == 'options':
        heading('THE STRATEGIES', 'Four ways to compare.')
        text('One set of vessel, price and eligibility assumptions.',82,327,32,color=MUTED,height=60,start=.25)
        specs=[('ship','Current fuels','Keep the starting mix.','Settle residual deficits.'),
               ('pool','Pooling','Keep current fuels.','Buy eligible surplus.'),
               ('fuel','Fuel + shore power','Allow alternative fuels.','Electrify eligible berth use.'),
               ('combine','Combined','Allow fuel, shore power','and pooling together.')]
        for i,(glyph,title,line1,line2) in enumerate(specs):
            card=layer(422,418,SURFACE,22)
            card.alpha_composite(icon(glyph),(28,34))
            d=ImageDraw.Draw(card)
            label(d,(28,160),f'0{i+1}',23,GREEN,True)
            label(d,(28,216),title,32,WHITE,True)
            label(d,(28,285),line1+'\n'+line2,24,MUTED,spacing=1.6)
            add(card,82+i*445,433,.3+i*.45)
        text('Compare the total modelled cost of each approach.',84,896,30,color=MUTED,height=55,start=2.1)
    elif key == 'case':
        heading('THE EXAMPLE', 'One ship. A conventional starting point.')
        text('DEMO AURORA  ·  CARGO  ·  30,000 GT  ·  2026',83,326,28,color=MUTED,height=50,start=.22)
        card=layer(560,481,SURFACE)
        d=ImageDraw.Draw(card)
        label(d,(32,31),'ANNUAL FUEL AT SEA',23,GREEN,True)
        label(d,(29,85),'1,400 t  VLSFO',51,WHITE,True)
        label(d,(30,162),'+ 100 t  MGO',43,WHITE,True)
        d.line((32,249,528,249),fill=LINE,width=2)
        label(d,(32,282),'AT EU BERTH',23,GREEN,True)
        label(d,(29,337),'40 t  MGO',52,WHITE,True)
        add(card,82,420,.38)
        table=layer(1168,481,'#eef5ee')
        d=ImageDraw.Draw(table)
        label(d,(26,24),'THE APP  /  ENTER CONSUMPTION BY VOYAGE LEG',22,INK,True)
        table.alpha_composite(screenshot('consumption',1080),(44,57))
        add(table,670,420,.6)
        text('Fictional annual plan · Sea consumption split across intra-EU and extra-EU legs.',84,934,24,color=MUTED,height=38,start=.75)
    elif key == 'setup':
        heading('THE CHOICES', 'Add FAME. Enable shore power.')
        specs=[('fame','FAME', 'Eligible pathway assumed', 'Up to 20% alternative sea energy'),
               ('shore','Shore power','Connection already installed','75% of EU-berth MGO is replaceable')]
        for i,(name,title,line1,line2) in enumerate(specs):
            card=layer(866,537,'#eef5ee')
            d=ImageDraw.Draw(card)
            label(d,(27,24),title,38,INK,True)
            label(d,(28,83),line1,25,'#3c6156')
            label(d,(28,128),line2,26,INK,True)
            # Exact app controls, enlarged and selectively cropped for legibility.
            if name=='fame':
                crop=screenshot(name,806,(0,182,1040,335))
                card.alpha_composite(crop,(30,195))
                label(d,(29,373),f"€{fuels['FAME']['price']:,.0f}/t  ·  25 gCO₂e/MJ",30,INK,True)
                label(d,(30,439),'Non-food/feed pathway; FuelEU eligibility\nand ETS zero-rating assumed.',23,'#3c6156',spacing=1.4)
            else:
                crop=screenshot(name,806,(0,105,1040,273))
                card.alpha_composite(crop,(30,195))
                label(d,(29,373),f"€{prepared['inputs']['electricity_price']:,.0f}/MWh  ·  No new capex",30,INK,True)
                label(d,(30,439),'€2,000/year additional operating cost.\nCompatibility assumed checked.',23,'#3c6156',spacing=1.4)
            add(card,82+i*891,374,.28+i*.7)
        text('Illustrative prices and eligibility · Use your own evidence and technical limits.',84,940,24,color=MUTED,height=38,start=1.2)
    elif key == 'results':
        heading('THE COMPARISON', 'Same ship. Lower modelled cost.')
        add(screenshot('strategies',453),82,349,.28,12)
        text('2026 TOTAL MODELLED COST',595,355,24,width=1200,height=42,color=MUTED,bold=True,start=.38)
        entries=[('baseline','Current fuels'),('pool','Current fuels + pooling'),
                 ('fuel','FAME + shore power'),('combined','FAME + shore power + pooling allowed')]
        for i,(strategy,title) in enumerate(entries):
            card=layer(1238,109,SURFACE,14)
            d=ImageDraw.Draw(card)
            tint=GREEN if strategy in ('fuel','combined') else '#9ab3b0'
            label(d,(22,20),title,26,WHITE,strategy=='fuel')
            price=f"€{strategies[strategy]['npv']:,.0f}"
            d.text((1216,17),price,font=face(34,True),fill=tint,anchor='rt')
            d.rounded_rectangle((23,73,1214,81),4,fill='#315154')
            length=round(1191*strategies[strategy]['npv']/baseline['npv'])
            d.rounded_rectangle((23,73,23+length,81),4,fill=tint)
            add(card,596,409+i*125,.4+i*.38,14)
        text(f"€{saving/1000:.1f}k lower  ·  {saving/baseline['npv']*100:.1f}%",596,923,39,width=1238,height=57,color=GREEN,bold=True,start=2.1)
    elif key == 'actions':
        heading('THE SELECTED PLAN', 'A specific action. A traceable result.')
        fame=best['rows'][0]['alternative_t']
        electricity=best['actions']['electricity_mwh']
        for i,(value,title,detail) in enumerate([
            (f'{fame:.1f} t','FAME at sea','Replaces 15.57 t MGO on the intra-EU leg'),
            (f'{electricity:.1f} MWh','Shore electricity','Replaces 30 t MGO at EU berth')]):
            card=layer(866,316,GREEN if i==0 else SURFACE)
            d=ImageDraw.Draw(card)
            color=INK if i==0 else WHITE
            label(d,(32,30),title.upper(),25,color,True)
            label(d,(27,85),value,100,color,True)
            label(d,(33,239),detail,25,color)
            add(card,82+i*891,376,.25+i*.35)
        text('No external pooling required  ·  €0 modelled FuelEU penalty',83,727,35,height=57,color=GREEN,bold=True,start=1.2)
        add(screenshot('actions',1756,(0,60,1294,185)),82,810,1.5,12)
    elif key == 'close':
        text('FROM ASSUMPTIONS TO ACTION',84,233,24,height=42,color=GREEN,bold=True)
        text('Your assumptions.\nA traceable decision.',77,321,102,width=1600,height=275,bold=True,start=.15)
        text('See what changes. Understand what it costs.',84,635,36,width=1600,height=66,color=MUTED,start=.38)
        end=layer(1150,112,GREEN,19)
        d=ImageDraw.Draw(end)
        label(d,(32,33),'MARITIME CARBON',39,INK,True)
        label(d,(468,42),'FuelEU Maritime + EU ETS planning',27,INK)
        add(end,83,800,.55)
    return items


def ease(value):
    value=max(0,min(1,value))
    return 1-(1-value)**3


def render_frame(base, layers, t, duration, elapsed, total, key):
    im=base.copy().convert('RGBA')
    for item,x,y,start,slide in layers:
        alpha=ease((t-start)/.52)
        # Quiet exit into the persistent brand background.
        alpha*=min(1,max(0,(duration-t)/.14))
        if not alpha:
            continue
        yy=y+round(slide*(1-ease((t-start)/.65)))
        if alpha < .999:
            item=item.copy()
            item.putalpha(item.getchannel('A').point(lambda a: round(a*alpha)))
        im.alpha_composite(item,(x,yy))
    d=ImageDraw.Draw(im)
    d.line((82,1003,1837,1003),fill=LINE,width=2)
    d.line((82,1003,82+round(1755*(elapsed+t)/total),1003),fill=GREEN,width=3)
    label(d,(83,1025),'Illustrative case · Planning assumptions',23,MUTED)
    qualifier=('Lowest evaluated option · Results depend on inputs' if key in ('results','actions','close')
               else 'From options to a decision')
    d.text((1837,1025),qualifier,font=face(23),fill=MUTED,anchor='rt')
    return im.convert('RGB')


def render(preview=False):
    plan=json.loads((OUT/'shot-plan.json').read_text(encoding='utf-8'))
    prepared=json.loads((OUT/'prepared-case.json').read_text(encoding='utf-8'))
    audit=json.loads((OUT/'demo-audit.json').read_text(encoding='utf-8'))
    capture=json.loads((OUT/'capture.json').read_text(encoding='utf-8'))
    assert audit['results']==prepared['results']
    assert 'saved inputs' in capture['checked']
    total=sum(s['duration'] for s in plan)
    assert total<=60
    base=background()
    elapsed=0
    clips=[]
    timeline=[]
    pcm=bytearray(round(total*RATE)*2)
    for i,scene in enumerate(plan):
        key,duration=scene['key'],scene['duration']
        layers=build_scene(key,prepared)
        mid=render_frame(base,layers,min(duration-.5,3.5),duration,elapsed,total,key)
        mid.save(OUT/'qa'/f'{i+1:02}-{key}-layout.png')
        if not preview:
            path=OUT/'clips'/f'{i:02}-{key}.mp4'
            with (OUT/'qa'/f'encode-{key}.log').open('w',encoding='utf-8') as err:
                process=subprocess.Popen([FFMPEG,'-hide_banner','-loglevel','error','-y',
                    '-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r',str(FPS),
                    '-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18',
                    '-pix_fmt','yuv420p','-threads','4',str(path)],stdin=subprocess.PIPE,stderr=err)
                try:
                    for frame in range(round(duration*FPS)):
                        process.stdin.write(render_frame(base,layers,frame/FPS,duration,elapsed,total,key).tobytes())
                finally:
                    process.stdin.close()
                assert process.wait()==0, f'Encoding {key} failed; inspect its log.'
            clips.append(path)
            with wave.open(scene['wav'],'rb') as source:
                assert source.getnchannels()==1 and source.getsampwidth()==2 and source.getframerate()==RATE
                voice=source.readframes(source.getnframes())
            start=round((elapsed+scene['lead'])*RATE)*2
            assert scene['lead']+len(voice)/(RATE*2)<duration
            pcm[start:start+len(voice)]=voice
        timeline.append(dict(key=key,start=elapsed,end=elapsed+duration,
                             speech_start=elapsed+scene['lead'],
                             speech_end=elapsed+scene['lead']+scene['speech_seconds'],
                             narration=scene['text'].replace('fame','FAME')))
        elapsed+=duration
        print(f"{'Previewed' if preview else 'Encoded'} {key}: {duration:.2f}s",flush=True)
    sheet=Image.new('RGB',(1280,1440),INK)
    d=ImageDraw.Draw(sheet)
    for i,scene in enumerate(plan):
        thumb=Image.open(OUT/'qa'/f"{i+1:02}-{scene['key']}-layout.png")
        thumb.thumbnail((620,349),Image.Resampling.LANCZOS)
        sheet.paste(thumb,(10+(i%2)*640,5+(i//2)*360))
    sheet.save(OUT/'qa'/'layout-contact-sheet.png')
    if preview:
        return
    (OUT/'edit-timeline.json').write_text(json.dumps(timeline,indent=2),encoding='utf-8')
    concat=OUT/'clips'/'concat.txt'
    concat.write_text(''.join(f"file '{p.name}'\n" for p in clips),encoding='utf-8')
    silent=OUT/'picture-master.mp4'
    run(['-f','concat','-safe','0','-i',concat,'-c','copy',silent])
    narration=OUT/'speech'/'narration.wav'
    with wave.open(str(narration),'wb') as target:
        target.setnchannels(1); target.setsampwidth(2); target.setframerate(RATE)
        target.writeframes(pcm)
    run(['-i',silent,'-i',narration,'-map','0:v:0','-map','1:a:0',
         '-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=7','-ar',RATE,
         '-ac','2','-c:a','aac','-b:a','192k','-movflags','+faststart',
         '-metadata','title=Maritime Carbon | From options to a decision',
         '-metadata','comment=Fictional 2026 case. Synthetic English narration. Planning assumptions.',FINAL])
    (OUT/'optional-captions').mkdir(exist_ok=True)
    captions=[]
    for scene in timeline:
        # Sentence-sized captions remain selectable, never cover app evidence.
        phrases=re.split(r'(?<=[.!?])\s+',scene['narration'])
        counts=[len(p.split()) for p in phrases]
        position=scene['speech_start']
        for phrase,count in zip(phrases,counts):
            end=position+(scene['speech_end']-scene['speech_start'])*count/sum(counts)
            captions.append(f"{len(captions)+1}\n{srt_timestamp(position)} --> {srt_timestamp(end)}\n{phrase}\n")
            position=end
    (OUT/'optional-captions'/'Maritime_Carbon_One_Minute.en.srt').write_text('\n'.join(captions),encoding='utf-8')
    verify(plan,total)


def verify(plan,total):
    # Full decode, stream inspection, encoded stills, loudness and timing checks.
    run(['-i',FINAL,'-map','0:v','-map','0:a','-f','null','-'])
    probe=subprocess.run([FFMPEG,'-hide_banner','-i',str(FINAL)],capture_output=True,text=True).stderr
    assert len(re.findall(r'Stream #\d+:\d+(?:\[.*?\])?.*Video:',probe))==1,probe
    assert len(re.findall(r'Stream #\d+:\d+(?:\[.*?\])?.*Audio:',probe))==1,probe
    assert '1920x1080' in probe and '30 fps' in probe and '48000 Hz' in probe,probe
    duration=seconds_in_video(FINAL)
    assert duration <= 60 and abs(duration-total)<.1
    loudness=subprocess.run([FFMPEG,'-hide_banner','-i',str(FINAL),'-af',
        'loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
    measured=json.JSONDecoder().raw_decode(loudness[loudness.rfind('{'):])[0]
    assert -17<float(measured['input_i'])<-15,measured
    assert float(measured['input_tp'])<-.8,measured
    elapsed=0
    for i,scene in enumerate(plan):
        run(['-ss',elapsed+min(3.5,scene['duration']-.5),'-i',FINAL,'-frames:v','1',OUT/'qa'/f"{i+1:02}-{scene['key']}-encoded.png"])
        elapsed+=scene['duration']
    result=dict(file=str(FINAL),duration_seconds=duration,width=W,height=H,fps=FPS,
        speech_fits_all_scenes=True,full_decode='passed',audio=measured,
        sha256=hashlib.sha256(FINAL.read_bytes()).hexdigest(),bytes=FINAL.stat().st_size)
    (OUT/'qa'/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__ == '__main__':
    command=sys.argv[1]
    if command=='prepare':
        asyncio.run(prepare())
    elif command in ('preview','render'):
        render(preview=command=='preview')
    elif command=='verify':
        plan=json.loads((OUT/'shot-plan.json').read_text(encoding='utf-8'))
        verify(plan,sum(s['duration'] for s in plan))
    else:
        raise SystemExit('Use prepare, preview, render, or verify.')
