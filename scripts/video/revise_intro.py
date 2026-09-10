"""Replace only the current film's first card and speech, retaining later footage."""
import asyncio
import hashlib
import json
import math
import re
import subprocess
import wave
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

import edge_tts

from scripts.video.refresh import OUT as PREVIOUS, FPS, RATE
from scripts.video.render import FFMPEG, ROOT, card, run, seconds_in_video
from scripts.video.single_voyage import VOICE

OUT = PREVIOUS / "revised-intro"
FINAL = OUT / "Maritime_Carbon_Revised.mp4"
TEXT = ("Helping Shipping Professionals Compare Fuel EU and EU ETS Planning Options - "
        "From Alternative Fuels and Pooling to Shore Power")
SPOKEN = ("Maritime Carbon. Helping shipping professionals compare Fuel E U and E U E T S planning options. "
          "From alternative fuels and pooling to shore power.")


def packet_hashes(path):
    result = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-map", "0:v:0",
                             "-c", "copy", "-f", "framehash", "-hash", "sha256", "-"],
                            capture_output=True, text=True, check=True)
    return [line.rsplit(",", 1)[-1].strip() for line in result.stdout.splitlines()
            if line and not line.startswith("#")]


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    previous = json.loads((PREVIOUS / "edit-timeline.json").read_text(encoding="utf-8"))
    assert previous[0]["key"] == "intro"
    old_intro = previous[0]
    source_video = PREVIOUS / "Maritime_Carbon_Updated.mp4"
    source_intro = old_intro
    if not source_video.exists():
        source_video = FINAL
        source_intro = json.loads((OUT / "edit-timeline.json").read_text(encoding="utf-8"))[0]
    old_hashes = packet_hashes(source_video)
    digest = hashlib.sha256((VOICE+"-4%"+SPOKEN).encode()).hexdigest()[:16]
    mp3 = OUT / f"{digest}.mp3"
    if not mp3.exists():
        await edge_tts.Communicate(SPOKEN, VOICE, rate="-4%").save(str(mp3))
    speech_wav = OUT / "intro-speech.wav"
    trim = "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.04,areverse"
    run(["-i", mp3, "-af", trim, "-ar", RATE, "-ac", 1, "-c:a", "pcm_s16le", speech_wav])
    with wave.open(str(speech_wav), "rb") as audio:
        speech_seconds = audio.getnframes()/RATE
    lead = .5
    frames = math.ceil((speech_seconds+lead+.75)*FPS)
    intro_seconds = frames/FPS
    image = card("planning_intro", destination=OUT / "intro.png")
    intro_clip = OUT / "intro.mp4"
    run(["-loop", 1, "-framerate", FPS, "-i", image, "-frames:v", frames,
         "-c:v", "libx264", "-preset", "fast", "-crf", 18, "-pix_fmt", "yuv420p", "-an", intro_clip])
    intro = dict(key="intro", caption=TEXT, text=SPOKEN, speech_seconds=speech_seconds,
                 lead=lead, frames=frames, duration=intro_seconds, clip=str(intro_clip), wav=str(speech_wav))
    pieces = [intro] + previous[1:]
    elapsed_frames = 0
    for s in pieces:
        s.update(output_start=elapsed_frames/FPS, output_end=(elapsed_frames+s["frames"])/FPS)
        elapsed_frames += s["frames"]
    duration = elapsed_frames/FPS
    playlist = OUT / "concat.txt"
    playlist.write_text("".join("file '"+s["clip"].replace("\\", "/")+"'\n" for s in pieces), encoding="utf-8")
    silent = OUT / "picture.mp4"
    run(["-f", "concat", "-safe", 0, "-i", playlist, "-c", "copy", silent])
    # Normalize the new spoken card; preserve the old film's decoded audio after
    # its first seven seconds, including every later pause and narration cue.
    intro_audio = OUT / "intro-audio.wav"
    run(["-i", speech_wav, "-af", f"loudnorm=I=-16:TP=-1.5:LRA=7,adelay={round(lead*1000)}:all=1,apad",
         "-t", intro_seconds, "-ar", RATE, "-ac", 2, "-c:a", "pcm_s16le", intro_audio])
    tail_audio = OUT / "tail-audio.wav"
    run(["-i", source_video, "-ss", source_intro["duration"],
         "-vn", "-ar", RATE, "-ac", 2, "-c:a", "pcm_s16le", tail_audio])
    narration = OUT / "narration.wav"
    with wave.open(str(narration), "wb") as target:
        target.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        for path in (intro_audio, tail_audio):
            with wave.open(str(path), "rb") as source:
                assert source.getparams()[:3] == (2, 2, RATE)
                target.writeframes(source.readframes(source.getnframes()))
    run(["-i", silent, "-i", narration, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", RATE, "-ac", 2, "-t", duration,
         "-sn", "-movflags", "+faststart", FINAL])
    run(["-i", FINAL, "-f", "null", "-"])
    new_hashes = packet_hashes(FINAL)
    assert new_hashes[frames:] == old_hashes[source_intro["frames"]:], "Later picture packets changed"
    assert abs(seconds_in_video(FINAL)-duration) < .05
    metadata = subprocess.run([FFMPEG, "-hide_banner", "-i", str(FINAL)], capture_output=True, text=True).stderr
    assert re.findall(r"Stream #0:\d+.*?: (Video|Audio|Subtitle):", metadata) == ["Video", "Audio"]
    assert "1920x1080" in metadata and "30 fps" in metadata
    for name, moment in (("intro", intro_seconds/2), ("transition", intro_seconds+.5),
                         ("allocation", next(s["output_start"]+3 for s in pieces if s["key"] == "allocation"))):
        run(["-ss", moment, "-i", FINAL, "-frames:v", 1, OUT / f"qa-{name}.png"])
    (OUT / "edit-timeline.json").write_text(json.dumps(pieces, indent=2, ensure_ascii=False), encoding="utf-8")
    transcript = OUT / "Narration.txt"
    transcript.write_text("Synthetic British English narration.\n\n" + "\n\n".join(
        f"{s['output_start']:.2f}s · {s['key']}\n{s['text']}" for s in pieces), encoding="utf-8")
    verification = dict(duration_seconds=duration, intro_seconds=intro_seconds,
                        intro_speech_seconds=speech_seconds, preserved_picture_packets=len(new_hashes)-frames,
                        remaining_picture_identical=True, first_page_text=TEXT,
                        source_video=source_video.name, source_intro_frames=source_intro["frames"])
    (OUT / "verification.json").write_text(json.dumps(verification, indent=2, ensure_ascii=False), encoding="utf-8")
    package = OUT / "Maritime_Carbon_Revised_Review.zip"
    with ZipFile(package, "w") as archive:
        for path in (FINAL, transcript, OUT / "edit-timeline.json", OUT / "verification.json",
                     PREVIOUS / "demo-inputs.json", PREVIOUS / "demo-audit.json",
                     ROOT / "docs" / "VIDEO_CURRENT_ENGINE_REVIEW.md"):
            archive.write(path, path.name, compress_type=ZIP_STORED if path.suffix == ".mp4" else ZIP_DEFLATED)
    print(json.dumps(verification, indent=2), flush=True)
    print(f"READY: {FINAL}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
