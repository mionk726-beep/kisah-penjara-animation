# Kisah Hidup di Penjara — Code-Based 2D Animation

A 30-second vertical (720x1280) 2D animation drawn entirely by **code**
(Python + PIL), in the round-headed flat-cartoon style. No AI video
generator, no screen recording. This is a test of the "Muse + GitHub"
workflow: an AI agent writes the animation code, the code renders the video.

Story (Indonesian, emotional): Rian sits in a prison cell holding a photo
of his family — "Dulu... aku punya segalanya." Flashback to a warm dinner
at home with his wife and child — "Sampai satu kesalahan menghancurkan
semuanya." Back in the cell, he stands at the barred window, determined —
"Tapi aku tidak menyerah. Demi mereka, aku akan berubah."

## The point of this test: real mouth sync

Videos from AI generators are silent; the voice is dubbed afterwards, so
the mouth never truly matches. Here the animation is drawn from the audio:

1. The narration is synthesized first (TTS).
2. `render.py` decodes the TTS to PCM and computes an RMS amplitude
   envelope per video frame (24 fps), smoothed over 5 frames.
3. The mouth is drawn as an ellipse whose height follows that envelope —
   open while the character speaks, closed (smile/frown) while silent.

It is amplitude-based, not phoneme-based: the mouth opens and closes with
the voice energy, which reads as talking, but it does not shape individual
words. Eyes blink every ~4.5 s.

## Requirements

- Python 3 + Pillow (`pip install Pillow`)
- ffmpeg (for audio decoding, final encode, WhatsApp version)
- DejaVu Sans Bold (for captions; any bold sans works — see `FONT_CAPTION`)
- The narration MP3s in `tts/` (regenerate with the `tts` tool, Helio
  `avocado_v2:MAI_03`, Indonesian, speed 95), and the piano bed
  `music.wav` (Mixkit "Classical 2", low volume)

## Run

```bash
python3 render.py
# renders 720 frames to frames/ (720x1280 PNGs) + check_*.png stills

# mix narration + music bed (already done — see final_audio.wav)
ffmpeg -y -i narration.wav -i music.wav \
  -filter_complex "[0][1]amix=inputs=2:duration=first:normalize=0[a]" \
  -map "[a]" final_audio.wav

# encode the full video
ffmpeg -y -framerate 24 -i frames/frame_%04d.png -i final_audio.wav \
  -c:v libx264 -pix_fmt yuv420p -r 24 -c:a aac -b:a 160k \
  -shortest penjara-test-full.mp4

# WhatsApp-sized version
ffmpeg -y -i penjara-test-full.mp4 -vf scale=540:960 \
  -c:v libx264 -crf 28 -pix_fmt yuv420p -c:a aac -b:a 128k \
  penjara-test-whatsapp.mp4
```

## Files

- `render.py` — the whole animation: scenes, characters, mouth envelope
- `tts/line1.mp3`, `line2.mp3`, `line3.mp3` — narration lines
- `narration.wav` — lines placed at 1.0s / 11.0s / 21.0s
- `music.wav` — piano bed, 30s, faded out at the end
- `final_audio.wav` — narration + music mix
- `frames/` — rendered PNGs + `check_t*.png` verification stills
- `notes.md` — what worked, what the mouth sync looks like, known flaws
