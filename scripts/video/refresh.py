"""Refresh the single-voyage film using current results and measured narration.

prepare -> manage.py test scripts.video.capture_refresh -> render
Earlier edits are preserved. Only the generic opening is reused.
"""
import asyncio
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

import edge_tts
from PIL import Image, ImageDraw

from portal.engine.calculator import compare
from portal.engine.rules import ENGINE_VERSION, RULESET_VERSION
from scripts.video.render import FFMPEG, ROOT, card, font, run, seconds_in_video, wrap
from scripts.video.single_voyage import OUT as PREVIOUS, SHOTS, VOICE, case_input

OUT = PREVIOUS / "current-engine"
OPENING = PREVIOUS / "opening"
FPS, RATE = 30, 48000
FINAL = OUT / "Maritime_Carbon_Updated.mp4"


def shot_script(result):
    strategies = result["strategies"]
    best = strategies[0]
    row, annual = best["rows"][0], best["annual"][0]
    legs = [l for l in row["leg_replacements"] if l["replaced_t"] > 1e-6]
    assert len(legs) == 1 and legs[0]["fuel"] == "MGO" and legs[0]["leg"] == "intra_t"
    leg = legs[0]
    assert [s["key"] for s in strategies] == ["combined", "fuel", "pool", "baseline"]
    assert abs(strategies[0]["npv"] - strategies[1]["npv"]) < .005
    assert not best["actions"]["pooling_used"]
    assert annual["pool_cost"] == annual["penalty_cost"] == annual["electricity_mwh"] == 0
    return SHOTS[:12] + [
        ("hvo", "HVO is selected as the replacement fuel for this case",
         "H V O is selected as the replacement fuel for this case.", 5),
        ("fuel_options", "More replacement-fuel options are available",
         "But more options exist.", 4.5),
        ("shore_power", "Shore power is not considered as an option for this case",
         "The shore power is not considered as an option for this case.", 5.5),
        ("calculate", "Compare the available strategies and identify the lowest evaluated cost",
         "Let's now compare the available strategies and identify which one gives the lower cost.", 7),
        ("rank_1", f"1 / TARGETED HVO · €{best['npv']:,.2f} · Pooling allowed, none used",
         "Best: targeted H V O. Pooling is allowed, but none is needed.", 5.5),
        ("rank_2", f"2 / HVO WITHOUT POOLING · Same annual cost: €{strategies[1]['npv']:,.2f}",
         "H V O without pooling reaches the same cost here.", 4.5),
        ("rank_3", f"3 / CURRENT FUELS + POOLING · €{strategies[2]['npv']:,.2f} · €{strategies[2]['npv']-best['npv']:,.2f} above best",
         "Current fuels plus pooling cost more in this case.", 4.5),
        ("rank_4", f"4 / CURRENT FUELS + PENALTIES · Highest cost: €{strategies[3]['npv']:,.2f}",
         "Current fuels plus penalties are the most expensive.", 5),
        ("best", f"Select the lowest evaluated cost: €{best['npv']:,.2f} for 2026",
         "Select the lowest evaluated cost strategy.", 4.5),
        ("operating", f"OPERATING CHOICE · Intra-EU: {leg['replaced_t']:.3f} t LSMGO → {leg['alternative_t']:.3f} t HVO",
         "The ship replaces gas oil with H V O on its intra E U leg.", 7),
        ("breakdown", f"ANNUAL COSTS · Fuel €{annual['fuel_cost']:,.2f} + ETS €{annual['ets_cost']:,.2f}",
         "Annual costs include fuel and allowances. No pooling or Fuel E U penalty remains.", 7),
        ("allocation", "FuelEU annual allocation · HVO first, then lower-intensity conventional fuels",
         "Annual Fuel E U allocation prioritizes H V O, then lower-intensity conventional fuels.", 8),
        ("ledger", "SHIP-BY-SHIP LEDGER · Intensity, compliance balance and settlement",
         "Finally, the ship-by-ship ledger shows the intensity, compliance balance, and settlement.", 7),
        ("thanks", "THANK YOU",
         "Thank you for watching. Maritime Carbon. Let's talk about your fleet.", 7),
    ]


async def prepare():
    for folder in ("speech", "raw", "clips", "graphics", "qa"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    data = case_input()
    result = compare(data)
    prepared = dict(engine_version=ENGINE_VERSION, ruleset_version=RULESET_VERSION,
                    inputs=data.to_dict(), results=result)
    (OUT / "prepared-case.json").write_text(json.dumps(prepared, indent=2), encoding="utf-8")
    shots = []
    for key, caption, text, preferred in shot_script(result):
        digest = hashlib.sha256((VOICE+"-4%"+text).encode()).hexdigest()[:16]
        mp3 = OUT / "speech" / f"{digest}.mp3"
        if not mp3.exists():
            # The oldest speech cache omitted rate from its hash; all was -4%.
            legacy = hashlib.sha256((VOICE+text).encode()).hexdigest()[:16]
            cached = [PREVIOUS / "speech" / f"{legacy}.mp3",
                      PREVIOUS / "closing-revision" / f"{digest}.mp3"]
            source = next((p for p in cached if p.exists()), None)
            if source:
                shutil.copyfile(source, mp3)
            else:
                await edge_tts.Communicate(text, VOICE, rate="-4%").save(str(mp3))
        wav = OUT / "speech" / f"{key}.wav"
        trim = "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"
        run(["-i", mp3, "-af", trim, "-ar", RATE, "-ac", 1, "-c:a", "pcm_s16le", wav])
        with wave.open(str(wav), "rb") as audio:
            speech = audio.getnframes()/RATE
        lead = 1.35 if key in ("calculate", "best", "allocation", "ledger") else .55
        duration = max(preferred, speech+lead+.5)
        if key == "calculate":
            duration += .6  # Preserve the button click after the sentence.
        frames = math.ceil(duration*FPS)
        shots.append(dict(key=key, caption=caption, text=text, speech_seconds=speech,
                          lead=lead, frames=frames, duration=frames/FPS))
        print(f"SPEECH {key}: {speech:.2f}s; hold {frames/FPS:.2f}s", flush=True)
    (OUT / "shot-plan.json").write_text(json.dumps(shots, indent=2, ensure_ascii=False), encoding="utf-8")


def caption_image(shot):
    path = OUT / "graphics" / f"{shot['key']}.png"
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 960, 1920, 1080), fill="#102e32")
    d.rectangle((0, 960, 1920, 963), fill="#c8eea0")
    d.text((40, 976), "MARITIME CARBON  /  ILLUSTRATIVE 2026 CASE", font=font(17, True), fill="#c8eea0")
    lines = wrap(d, shot["caption"], font(30), 1830)
    assert len(lines) == 1, shot["caption"]
    d.text((40, 1008), lines[0], font=font(30), fill="white")
    im.save(path)
    return path


def render():
    capture = json.loads((OUT / "capture.json").read_text(encoding="utf-8"))
    source = OUT / "raw" / "walkthrough.webm"
    offset = capture["recording_wall_seconds"] - seconds_in_video(source)
    assert abs(offset) < 2, offset
    pieces = []
    for s in json.loads((OPENING / "plan.json").read_text(encoding="utf-8")):
        pieces.append(s | dict(clip=str(OPENING / f"{s['key']}.mp4"),
                               wav=str(OPENING / f"{s['key']}.wav")))
    for s in capture["scenes"]:
        target = OUT / "clips" / f"{s['key']}.mp4"
        # Full-width result tables and dropdown; no cropped columns or options.
        run(["-ss", max(0, s["start"]-offset), "-i", source,
             "-loop", 1, "-framerate", FPS, "-i", caption_image(s),
             "-filter_complex", "[0:v]fps=30,scale=1920:960,pad=1920:1080:0:0:color=0x102e32[v];[v][1:v]overlay=0:0:format=auto,format=yuv420p[out]",
             "-map", "[out]", "-frames:v", s["frames"], "-c:v", "libx264", "-preset", "fast",
             "-crf", 18, "-threads", 4, "-an", target])
        pieces.append(s | dict(clip=str(target), wav=str(OUT / "speech" / f"{s['key']}.wav")))
        print(f"ENCODE {s['key']}", flush=True)
    thanks = next(s for s in json.loads((OUT / "shot-plan.json").read_text(encoding="utf-8")) if s["key"] == "thanks")
    target = OUT / "clips" / "thanks.mp4"
    run(["-loop", 1, "-framerate", FPS, "-i", card("thanks", destination=OUT / "graphics" / "thanks.png"),
         "-frames:v", thanks["frames"], "-c:v", "libx264", "-preset", "fast", "-crf", 18,
         "-pix_fmt", "yuv420p", "-an", target])
    pieces.append(thanks | dict(clip=str(target), wav=str(OUT / "speech" / "thanks.wav")))
    duration = sum(s["frames"] for s in pieces)/FPS
    track = bytearray(round(duration*RATE)*2)
    frames = 0
    for s in pieces:
        elapsed = frames/FPS
        with wave.open(s["wav"], "rb") as audio:
            assert audio.getparams()[:3] == (1, 2, RATE)
            pcm = audio.readframes(audio.getnframes())
        assert s["lead"]+len(pcm)/(RATE*2)+.35 <= s["duration"]
        begin = round((elapsed+s["lead"])*RATE)*2
        track[begin:begin+len(pcm)] = pcm
        s.update(output_start=elapsed, output_end=elapsed+s["duration"])
        frames += s["frames"]
    keys = [s["key"] for s in pieces]
    assert keys.index("hvo") < keys.index("fuel_options") < keys.index("shore_power") < keys.index("calculate")
    assert keys.index("breakdown") < keys.index("allocation") < keys.index("ledger")
    playlist = OUT / "concat.txt"
    playlist.write_text("".join("file '"+s["clip"].replace("\\", "/")+"'\n" for s in pieces), encoding="utf-8")
    silent = OUT / "picture.mp4"
    run(["-f", "concat", "-safe", 0, "-i", playlist, "-c", "copy", silent])
    wav = OUT / "speech" / "narration.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(track)
    run(["-i", silent, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", RATE, "-ac", 2, "-af", "loudnorm=I=-16:TP=-1.5:LRA=7",
         "-t", duration, "-sn", "-movflags", "+faststart", FINAL])
    run(["-i", FINAL, "-f", "null", "-"])
    assert abs(seconds_in_video(FINAL)-duration) < .05
    meta = subprocess.run([FFMPEG, "-hide_banner", "-i", str(FINAL)], capture_output=True, text=True).stderr
    assert re.findall(r"Stream #0:\d+.*?: (Video|Audio|Subtitle):", meta) == ["Video", "Audio"]
    assert "1920x1080" in meta and "30 fps" in meta
    (OUT / "edit-timeline.json").write_text(json.dumps(pieces, indent=2, ensure_ascii=False), encoding="utf-8")
    transcript = OUT / "Narration.txt"
    transcript.write_text("Synthetic British English narration. One visible caption layer.\n\n"+
                          "\n\n".join(f"{s['output_start']:.2f}s · {s['key']}\n{s['text']}" for s in pieces), encoding="utf-8")
    for s in pieces:
        run(["-ss", (s["output_start"]+s["output_end"])/2, "-i", FINAL, "-frames:v", 1, OUT / "qa" / f"{s['key']}.png"])
        if s["key"] in ("fuel_options", "allocation"):
            for fraction in (.2, .8):
                run(["-ss", s["output_start"]+s["duration"]*fraction, "-i", FINAL, "-frames:v", 1,
                     OUT / "qa" / f"{s['key']}-{fraction}.png"])
    package = OUT / "Maritime_Carbon_Updated_Review.zip"
    with ZipFile(package, "w") as archive:
        for p in (FINAL, transcript, OUT / "demo-inputs.json", OUT / "demo-audit.json",
                  OUT / "edit-timeline.json", ROOT / "docs" / "VIDEO_CURRENT_ENGINE_REVIEW.md"):
            archive.write(p, p.name, compress_type=ZIP_STORED if p.suffix == ".mp4" else ZIP_DEFLATED)
    print(f"READY {duration:.2f}s; {FINAL}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        asyncio.run(prepare())
    elif sys.argv[1] == "render":
        render()
