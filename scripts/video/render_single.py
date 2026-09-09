"""Prepare speech before recording, then render the owner-specified revision.

python -m scripts.video.render_single prepare
python manage.py test scripts.video.capture_single --noinput
python -m scripts.video.render_single render
"""
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import wave
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

import edge_tts
from PIL import Image, ImageDraw
from scripts.video.render import FFMPEG, run, font, wrap, seconds_in_video, ROOT
from scripts.video.single_voyage import OUT, VOICE, SHOTS

FPS, RATE = 30, 48000


async def prepare():
    for folder in ("speech", "raw", "clips", "graphics", "qa"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    shots = []
    for key, caption, text, preferred in SHOTS:
        digest = hashlib.sha256((VOICE+text).encode()).hexdigest()[:16]
        mp3 = OUT / "speech" / f"{digest}.mp3"
        if not mp3.exists():
            await edge_tts.Communicate(text, VOICE, rate="-4%").save(str(mp3))
        wav = OUT / "speech" / f"{key}.wav"
        trim = "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"
        run(["-i", mp3, "-af", trim, "-ar", RATE, "-ac", "1", "-c:a", "pcm_s16le", wav])
        with wave.open(str(wav), "rb") as audio:
            speech = audio.getnframes()/RATE
        lead = 1.35 if key in ("calculate", "best", "ledger") else .55
        minimum = speech + lead + .4
        frames = round(max(preferred, minimum)*FPS + .5)
        shots.append(dict(key=key, caption=caption, text=text, speech_seconds=speech,
                          lead=lead, frames=frames, minimum_frames=round(minimum*FPS+.5)))
        print(f"SPEECH {key}: {speech:.2f}s; shot {frames/FPS:.2f}s", flush=True)
    target = 80*FPS
    total = sum(s["frames"] for s in shots)
    if total > target:
        for s in shots:
            take = min(total-target, s["frames"]-s["minimum_frames"])
            s["frames"] -= take
            total -= take
    assert total <= target, f"Shorten the script to preserve natural speech: {total/FPS:.2f}s required"
    # Spend remaining seconds on the three requested output sections.
    index = 0
    while total < target:
        shots[-3+(index%3)]["frames"] += 1
        total += 1
        index += 1
    for s in shots:
        s["duration"] = s["frames"]/FPS
        assert s["lead"]+s["speech_seconds"]+.35 <= s["duration"]
    (OUT / "shot-plan.json").write_text(json.dumps(shots, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Prepared exactly 80 seconds; speech at natural -4% rate, no acceleration.", flush=True)


def caption_image(shot):
    path = OUT / "graphics" / (shot["key"]+".png")
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 960, 1920, 1080), fill="#102e32")
    d.rectangle((0, 960, 1920, 963), fill="#c8eea0")
    d.text((40, 976), "MARITIME CARBON  /  ILLUSTRATIVE 2026 CASE", font=font(17, True), fill="#c8eea0")
    lines = wrap(d, shot["caption"], font(30), 1830)
    assert len(lines) <= 1, shot["caption"]
    d.text((40, 1008), lines[0], font=font(30), fill="white")
    im.save(path)
    return path


def render():
    shots = json.loads((OUT / "capture.json").read_text(encoding="utf-8"))
    source = OUT / "raw" / "walkthrough.webm"
    # The final recording hold provides a clock anchor after every shot.
    offset = shots["recording_wall_seconds"]-seconds_in_video(source)
    assert abs(offset) < 2
    track = bytearray(80*RATE*2)
    clips, timeline = [], []
    elapsed = 0.0
    for i, s in enumerate(shots["scenes"]):
        n = s["frames"]
        # Finish the zoom before the narration starts. Keep the frame and pointer
        # stable throughout the explanation; there is no zoom-out during speech.
        ramp = 12
        p = f"min(1,on/{ramp})"
        zoom = f"1+{s['zoom']-1}*({p})*({p})*(3-2*({p}))"
        fx, fy = s["focus"]
        filters = (f"[0:v]fps=30,scale=3200:1600,zoompan=z='{zoom}':"
                   f"x='max(0,min(iw-iw/zoom,{fx*2}-iw/zoom/2))':"
                   f"y='max(0,min(ih-ih/zoom,{fy*2}-ih/zoom/2))':d=1:s=1920x960:fps=30,"
                   "pad=1920:1080:0:0:color=0x102e32[screen];[screen][1:v]overlay=0:0:format=auto,format=yuv420p[v]")
        target = OUT / "clips" / f"{i:02}-{s['key']}.mp4"
        run(["-ss", max(0, s["start"]-offset), "-i", source, "-loop", "1", "-framerate", "30",
             "-i", caption_image(s), "-filter_complex", filters, "-map", "[v]", "-frames:v", n,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "4", "-an", target])
        clips.append(target)
        with wave.open(str(OUT / "speech" / f"{s['key']}.wav"), "rb") as audio:
            pcm = audio.readframes(audio.getnframes())
        begin = round((elapsed+s["lead"])*RATE)*2
        assert begin+len(pcm) < round((elapsed+s["duration"])*RATE)*2
        track[begin:begin+len(pcm)] = pcm
        timeline.append(s | {"output_start": elapsed, "output_end": elapsed+s["duration"]})
        elapsed += s["duration"]
        print(f"ENCODE {s['key']}: {s['duration']:.2f}s", flush=True)
    assert abs(elapsed-80) < .01
    playlist = OUT / "concat.txt"
    playlist.write_text("".join(f"file 'clips/{p.name}'\n" for p in clips), encoding="utf-8")
    silent = OUT / "picture.mp4"
    run(["-f", "concat", "-safe", "0", "-i", playlist, "-c", "copy", silent])
    wav = OUT / "speech" / "narration.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(track)
    final = OUT / "Maritime_Carbon_One_Voyage_2026.mp4"
    run(["-i", silent, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-t", "80", "-sn", "-movflags", "+faststart", final])
    run(["-i", final, "-f", "null", "-"])
    assert abs(seconds_in_video(final)-80) < .05
    metadata = subprocess.run([FFMPEG, "-hide_banner", "-i", str(final)], capture_output=True, text=True).stderr
    assert re.findall(r"Stream #0:\d+.*?: (Video|Audio|Subtitle):", metadata) == ["Video", "Audio"]
    assert "1920x1080" in metadata and "30 fps" in metadata
    assert not list(OUT.glob("*.srt")), "Keep only one visible caption layer"
    (OUT / "edit-timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "Narration.txt").write_text("Synthetic British English voice; one visible caption layer.\n\n" + "\n\n".join(s["text"] for s in timeline), encoding="utf-8")
    for i, s in enumerate(timeline):
        run(["-ss", (s["output_start"]+s["output_end"])/2, "-i", final, "-frames:v", "1", OUT / "qa" / f"{i:02}-{s['key']}.png"])
    package = OUT / "Maritime_Carbon_One_Voyage_2026_Review.zip"
    with ZipFile(package, "w") as archive:
        for p in (final, OUT / "Narration.txt", OUT / "demo-audit.json", OUT / "demo-inputs.json", ROOT / "docs" / "VIDEO_SINGLE_VOYAGE_REVIEW.md"):
            archive.write(p, p.name, compress_type=ZIP_STORED if p.suffix == ".mp4" else ZIP_DEFLATED)
    print(f"READY: {final}; 80 seconds; 1920x1080; one caption layer; voiced.", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        asyncio.run(prepare())
    elif sys.argv[1] == "render":
        render()
