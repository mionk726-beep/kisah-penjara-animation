#!/usr/bin/env python3
"""
Kisah Hidup di Penjara — code-based 2D animation test (Muse + GitHub workflow).

Draws every frame programmatically with PIL (circles, rounded rectangles,
lines) — NO AI video generator, NO screen recording. 720x1280, 24fps, 30s.

Key feature: the mouth follows the real voice. The TTS lines are decoded to
PCM first, an RMS amplitude envelope is computed per video frame, and the
mouth ellipse height is drawn from that envelope, so the mouth opens when
the character speaks and closes when silent.

Run:
    python3 render.py            # renders frames/ + narration.wav
    # then encode with ffmpeg (see encode.sh or README.md)

Files expected (relative to this script):
    tts/line1.mp3  tts/line2.mp3  tts/line3.mp3   (Indonesian TTS, Helio)
"""
import math
import os
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
W, H = 720, 1280
FPS = 24
DUR = 30.0
NFRAMES = int(DUR * FPS)

FONT_CAPTION = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SMALL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# --- narration timing (seconds) -------------------------------------------
# line i starts at LINE_START[i]; captions show a little longer than audio.
LINE_START = {1: 1.0, 2: 11.0, 3: 21.0}
CAPTIONS = [
    (0.8, 4.8, "Dulu... aku punya segalanya."),
    (10.8, 15.8, "Sampai satu kesalahan menghancurkan semuanya."),
    (20.8, 26.0, "Tapi aku tidak menyerah. Demi mereka, aku akan berubah."),
]

# --- palette ----------------------------------------------------------------
SKIN = (244, 196, 144)
SKIN_SHADOW = (232, 178, 122)
OUTLINE = (32, 28, 26)
HAIR = (28, 24, 22)
ORANGE_UNIFORM = (232, 118, 32)
BLUE_SHIRT = (64, 122, 196)
PINK_DRESS = (232, 120, 160)
YELLOW_SHIRT = (244, 200, 48)
PANTS_DARK = (70, 74, 88)
CELL_WALL = (104, 110, 124)
CELL_WALL_DARK = (82, 88, 102)
CELL_FLOOR = (64, 68, 80)
BAR = (40, 42, 50)
HOME_WALL = (245, 201, 138)
HOME_WALL_DARK = (232, 182, 112)


# --- audio envelope ----------------------------------------------------------
def decode_to_wav(mp3_path, wav_path, sr=16000):
    """Decode mp3 to mono wav with ffmpeg (for envelope analysis)."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", mp3_path,
         "-ac", "1", "-ar", str(sr), wav_path],
        check=True,
    )


def compute_envelope(sr=16000):
    """RMS amplitude per video frame, 0..1, smoothed. One value per frame."""
    spf = sr // FPS  # samples per frame
    total = int(DUR * sr)
    pcm = [0.0] * total
    for i in (1, 2, 3):
        mp3 = os.path.join(BASE, "tts", f"line{i}.mp3")
        wav = os.path.join(BASE, "tts", f"line{i}.wav")
        decode_to_wav(mp3, wav, sr)
        with wave.open(wav, "rb") as w:
            raw = w.readframes(w.getnframes())
        import struct
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        start = int(LINE_START[i] * sr)
        for j, s in enumerate(samples):
            if start + j < total:
                pcm[start + j] = s / 32768.0
    # RMS per frame
    env = []
    for f in range(NFRAMES):
        seg = pcm[f * spf:(f + 1) * spf]
        rms = math.sqrt(sum(x * x for x in seg) / max(1, len(seg)))
        env.append(rms)
    # smooth with a 5-frame moving average
    sm = []
    for f in range(NFRAMES):
        lo, hi = max(0, f - 2), min(NFRAMES, f + 3)
        sm.append(sum(env[lo:hi]) / (hi - lo))
    peak = max(sm) or 1.0
    # noise floor + normalise; mouth fully open at ~55% of peak
    out = []
    for v in sm:
        o = (v - 0.02) / (0.55 * peak)
        out.append(max(0.0, min(1.0, o)))
    return out


# --- drawing helpers ---------------------------------------------------------
def rrect(d, box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill,
                        outline=outline, width=width)


def text_wrapped(d, text, font, cx, y, max_w, fill, outline_w=3):
    """Centred wrapped caption with black outline. Returns bottom y."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = font.size + 10
    total_h = lh * len(lines)
    y0 = y - total_h
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=font)
        x = cx - tw / 2
        yy = y0 + i * lh
        for dx in (-outline_w, 0, outline_w):
            for dy in (-outline_w, 0, outline_w):
                d.text((x + dx, yy + dy), ln, font=font, fill=(0, 0, 0))
        d.text((x, yy), ln, font=font, fill=fill)
    return y0 + total_h


def draw_bars(d, x0, y0, x1, y1, n_v=4, n_h=2):
    """Iron bars inside a window rect."""
    for i in range(n_v):
        x = x0 + (i + 0.5) * (x1 - x0) / n_v
        d.rectangle([x - 7, y0, x + 7, y1], fill=BAR)
    for j in range(n_h):
        y = y0 + (j + 0.5) * (y1 - y0) / n_h
        d.rectangle([x0, y - 7, x1, y + 7], fill=BAR)
    d.rectangle([x0, y0, x1, y1], outline=BAR, width=10)


def draw_light_rays(img, window, color, alpha, n=4):
    """Translucent light rays from a window rect, slanting down-left."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    x0, y0, x1, y1 = window
    for i in range(n):
        fx = x0 + (i + 0.5) * (x1 - x0) / n
        od.polygon([(fx - 26, y1), (fx + 26, y1),
                    (fx - 130, H), (fx + 30, H)],
                   fill=color + (alpha,))
    img.alpha_composite(ov)


def draw_head(d, cx, cy, r, mouth_open, mood="sad", blink=False,
              hair="short", skin=SKIN):
    """Big round head: hair, dot eyes, mouth driven by `mouth_open` (0..1)."""
    # ears
    d.ellipse([cx - r - 14, cy - 10, cx - r + 16, cy + 26], fill=skin,
              outline=OUTLINE, width=4)
    d.ellipse([cx + r - 16, cy - 10, cx + r + 14, cy + 26], fill=skin,
              outline=OUTLINE, width=4)
    # face
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=skin,
              outline=OUTLINE, width=6)
    # hair
    if hair == "short":
        d.pieslice([cx - r - 4, cy - r - 6, cx + r + 4, cy + 10],
                   start=180, end=360, fill=HAIR)
        d.arc([cx - r - 4, cy - r - 6, cx + r + 4, cy + 10],
              start=180, end=360, fill=OUTLINE, width=5)
    elif hair == "long":  # wife: hair falls past the shoulders
        d.rounded_rectangle([cx - r - 10, cy - r - 4, cx - r + 34, cy + r + 150],
                            radius=20, fill=HAIR)
        d.rounded_rectangle([cx + r - 34, cy - r - 4, cx + r + 10, cy + r + 150],
                            radius=20, fill=HAIR)
        d.pieslice([cx - r - 4, cy - r - 6, cx + r + 4, cy + 10],
                   start=180, end=360, fill=HAIR)
    # eyes
    ex, ey = r * 0.38, -r * 0.12
    if blink:
        d.line([cx - ex - 13, cy + ey, cx - ex + 13, cy + ey],
               fill=OUTLINE, width=5)
        d.line([cx + ex - 13, cy + ey, cx + ex + 13, cy + ey],
               fill=OUTLINE, width=5)
    else:
        d.ellipse([cx - ex - 9, cy + ey - 11, cx - ex + 9, cy + ey + 11],
                  fill=OUTLINE)
        d.ellipse([cx + ex - 9, cy + ey - 11, cx + ex + 9, cy + ey + 11],
                  fill=OUTLINE)
    # eyebrows (sad = inner ends up)
    d.line([cx - ex - 14, cy + ey - 30, cx - ex + 12, cy + ey - 22],
           fill=OUTLINE, width=5)
    d.line([cx + ex + 14, cy + ey - 30, cx + ex - 12, cy + ey - 22],
           fill=OUTLINE, width=5)
    # mouth — the sync feature: ellipse height follows the voice
    my = cy + r * 0.48
    if mouth_open > 0.06:
        mh = 4 + mouth_open * 30
        d.ellipse([cx - 20, my - mh / 2, cx + 20, my + mh / 2],
                  fill=(92, 32, 28), outline=OUTLINE, width=3)
    else:
        if mood == "sad":  # frown
            d.arc([cx - 22, my - 16, cx + 22, my + 16], start=200, end=340,
                  fill=OUTLINE, width=5)
        else:  # smile
            d.arc([cx - 22, my - 16, cx + 22, my + 16], start=20, end=160,
                  fill=OUTLINE, width=5)


def draw_body(d, cx, top, w, h, shirt, pants=None, arms="down"):
    """Torso + arms (+ legs when pants given)."""
    rrect(d, [cx - w / 2, top, cx + w / 2, top + h], radius=28,
          fill=shirt, outline=OUTLINE, width=5)
    # collar
    d.ellipse([cx - 26, top - 6, cx + 26, top + 22], fill=(255, 255, 255),
              outline=OUTLINE, width=3)
    # arms
    ay0, ay1 = top + 20, top + h - 10
    if arms == "down":
        rrect(d, [cx - w / 2 - 34, ay0, cx - w / 2 + 2, ay1], radius=16,
              fill=shirt, outline=OUTLINE, width=4)
        rrect(d, [cx + w / 2 - 2, ay0, cx + w / 2 + 34, ay1], radius=16,
              fill=shirt, outline=OUTLINE, width=4)
        d.ellipse([cx - w / 2 - 32, ay1 - 8, cx - w / 2 + 0, ay1 + 24],
                  fill=SKIN, outline=OUTLINE, width=4)
        d.ellipse([cx + w / 2 + 0, ay1 - 8, cx + w / 2 + 32, ay1 + 24],
                  fill=SKIN, outline=OUTLINE, width=4)
    if pants is not None:
        leg_top = top + h - 6
        rrect(d, [cx - w / 2 + 8, leg_top, cx - 6, leg_top + 150], radius=14,
              fill=pants, outline=OUTLINE, width=4)
        rrect(d, [cx + 6, leg_top, cx + w / 2 - 8, leg_top + 150], radius=14,
              fill=pants, outline=OUTLINE, width=4)


# --- scenes ------------------------------------------------------------------
def scene_cell(img, d, t, mo, blink, evening=True):
    """Scenes 1 & 3: prison cell. Rian sits (1) / stands at window (3)."""
    d.rectangle([0, 0, W, H], fill=CELL_WALL)
    d.rectangle([0, 0, W, 90], fill=CELL_WALL_DARK)
    d.rectangle([0, 940, W, H], fill=CELL_FLOOR)
    d.line([0, 940, W, 940], fill=OUTLINE, width=5)
    # brick lines
    for y in range(180, 940, 110):
        d.line([0, y, W, y], fill=(92, 98, 112), width=3)
    # barred window, upper right
    win = (430, 150, 660, 420)
    sky = (250, 196, 110) if evening else (140, 200, 250)
    d.rectangle(win, fill=sky, outline=OUTLINE, width=6)
    d.ellipse([470, 190, 540, 260], fill=(255, 236, 170))  # sun / moon glow
    draw_bars(d, *win)
    draw_light_rays(img, win,
                    (255, 214, 130) if evening else (255, 240, 190),
                    46 if evening else 70)
    # bed (scene 1) — simple frame + mattress + pillow
    if evening:
        rrect(d, [60, 830, 430, 950], radius=12, fill=(122, 84, 52),
              outline=OUTLINE, width=5)
        rrect(d, [70, 800, 420, 850], radius=12, fill=(226, 222, 210),
              outline=OUTLINE, width=4)
        rrect(d, [80, 780, 180, 812], radius=10, fill=(255, 255, 255),
              outline=OUTLINE, width=4)
    if evening:
        # Rian SITTING on the bed, holding a photo, sad
        cx, base = 250, 800
        # legs stretched forward on the bed
        rrect(d, [cx - 40, base - 30, cx + 130, base + 6], radius=14,
              fill=PANTS_DARK, outline=OUTLINE, width=4)
        draw_body(d, cx, base - 210, 190, 210, ORANGE_UNIFORM)
        draw_head(d, cx, base - 300, 92, mo, mood="sad", blink=blink)
        # small photo in his hand (white card, tiny figures)
        d.rectangle([cx + 96, base - 60, cx + 152, base - 6], fill="white",
                    outline=OUTLINE, width=3)
        d.ellipse([cx + 108, base - 50, cx + 126, base - 32], fill=SKIN,
                  outline=OUTLINE, width=2)
        d.ellipse([cx + 128, base - 50, cx + 146, base - 32], fill=SKIN,
                  outline=OUTLINE, width=2)
        d.rectangle([cx + 104, base - 28, cx + 148, base - 12],
                    fill=PINK_DRESS)
    else:
        # Rian STANDING at the window, sunlight on his face, determined
        cx, base = 470, 940
        draw_body(d, cx, 520, 210, 250, ORANGE_UNIFORM, pants=PANTS_DARK)
        draw_head(d, cx, 420, 95, mo, mood="happy", blink=blink)
        # hand near pocket (photo tucked away)
        d.rectangle([cx + 40, 740, cx + 92, 786], fill="white",
                    outline=OUTLINE, width=3)


def scene_home(img, d, t, mo, blink):
    """Scene 2: flashback — warm dinner at home, Rian + wife + child."""
    d.rectangle([0, 0, W, H], fill=HOME_WALL)
    d.rectangle([0, 0, W, 90], fill=HOME_WALL_DARK)
    d.rectangle([0, 940, W, H], fill=(196, 148, 96))
    # window with curtains + lamp glow
    win = (70, 150, 280, 380)
    d.rectangle(win, fill=(150, 205, 245), outline=OUTLINE, width=6)
    d.ellipse([120, 200, 190, 270], fill=(255, 240, 180))
    d.rectangle([40, 140, 80, 400], fill=(220, 90, 90), outline=OUTLINE,
                width=4)
    d.rectangle([270, 140, 310, 400], fill=(220, 90, 90), outline=OUTLINE,
                width=4)
    # hanging lamp
    d.line([360, 90, 360, 210], fill=OUTLINE, width=6)
    d.ellipse([300, 210, 420, 300], fill=(255, 224, 130), outline=OUTLINE,
              width=5)
    # warm glow overlay
    ov = Image.new("RGBA", (W, H), (255, 190, 90, 18))
    img.alpha_composite(ov)
    # family behind the table (upper bodies)
    # wife (left), Rian (centre), child (right, smaller)
    draw_body(d, 185, 560, 170, 220, PINK_DRESS)
    draw_head(d, 185, 470, 88, 0.0, mood="happy", blink=blink, hair="long")
    draw_body(d, 390, 540, 190, 240, BLUE_SHIRT)
    draw_head(d, 390, 440, 92, mo, mood="happy", blink=blink)
    draw_body(d, 570, 600, 130, 180, YELLOW_SHIRT)
    draw_head(d, 570, 520, 66, 0.0, mood="happy", blink=blink)
    # table + food
    rrect(d, [40, 780, 680, 940], radius=14, fill=(150, 100, 58),
          outline=OUTLINE, width=5)
    for px in (150, 360, 560):
        d.ellipse([px - 42, 748, px + 42, 786], fill="white",
                  outline=OUTLINE, width=4)
        d.ellipse([px - 18, 756, px + 18, 778], fill=(240, 170, 80))
    # steam curls above the food
    for sx in (150, 360, 560):
        d.arc([sx - 14, 700, sx + 14, 736], start=200, end=340,
              fill=(255, 255, 255), width=4)


def render_frame(idx, envelope):
    """Render one frame; returns PIL Image (RGB)."""
    t = idx / FPS
    mo = envelope[idx]
    # blink: 4 frames every ~4.5s
    blink = (idx % 108) in (104, 105, 106, 107)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img, "RGBA")
    if t < 10:
        scene_cell(img, d, t, mo, blink, evening=True)
    elif t < 20:
        scene_home(img, d, t, mo, blink)
    else:
        scene_cell(img, d, t - 20, mo, blink, evening=False)
    # caption for this moment
    for (a, b, text) in CAPTIONS:
        if a <= t <= b:
            font = ImageFont.truetype(FONT_CAPTION, 46)
            text_wrapped(d, text, font, W // 2, 1180, 640, (255, 255, 255))
            break
    return img.convert("RGB")


def main():
    os.makedirs(os.path.join(BASE, "frames"), exist_ok=True)
    print("Computing mouth envelope from TTS...")
    envelope = compute_envelope()
    print(f"Envelope peak frames speaking: "
          f"{sum(1 for v in envelope if v > 0.1)} / {NFRAMES}")
    checks = {1, 2, 5, 9, 12, 15, 22, 25}
    for i in range(NFRAMES):
        img = render_frame(i, envelope)
        img.save(os.path.join(BASE, "frames", f"frame_{i:04d}.png"))
        if int(i / FPS) in checks and i % FPS == 0:
            t = int(i / FPS)
            img.save(os.path.join(BASE, "frames", f"check_t{t}.png"))
        if i % 120 == 0:
            print(f"  frame {i}/{NFRAMES}")
    print("Done rendering frames.")


if __name__ == "__main__":
    main()
