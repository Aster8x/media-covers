"""Builds real-image collage covers for the Nuvio Test profile.

Runs on GitHub Actions every week. Folders in REFRESH get fresh stills from
TMDB each run (current trending / new streaming releases). Every other folder
uses the stills saved in xp/plan.json. No generated art: only TMDB backdrops.
"""
import datetime as dt, io, json, os, sys, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN = os.environ.get("TMDB_TOKEN", "").strip()
PLAN = "xp/plan.json"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
today = dt.date.today()
since = (today - dt.timedelta(days=120)).isoformat()
SUBS = "8|9|337|1899|15|350|2303|386|283|43"   # Netflix, Prime, Disney+, Max, Hulu, Apple, Paramount+, Peacock, Crunchyroll, Starz

def streaming_new(kind):
    date = "primary_release_date" if kind == "movie" else "first_air_date"
    q = {"watch_region": "US", "with_watch_monetization_types": "flatrate", "with_watch_providers": SUBS,
         "sort_by": f"{date}.desc", f"{date}.lte": today.isoformat(), f"{date}.gte": since,
         "vote_count.gte": "15", "include_adult": "false"}
    return f"discover/{kind}?" + urllib.parse.urlencode(q)

REFRESH = {
    "trending/for-you-top-100-today": ["trending/all/day"],
    "trending/trending": ["trending/all/week"],
    "trending/popular": ["movie/popular"],
    "trending/most-popular-top-20": ["tv/popular"],
    "new-latest/digital-releases": [streaming_new("movie")],
    "new-latest/latest-releases": [streaming_new("movie"), streaming_new("tv")],
    "new-latest/on-the-air": ["tv/on_the_air"],
    "new-latest/airing-today": ["tv/airing_today"],
    "new-latest/airing-shows": ["tv/on_the_air?page=2"],
}

def get(url, binary=False):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "accept": "application/json", "User-Agent": "media-covers"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else json.loads(data)

def tmdb_backdrops(paths):
    out = []
    for p in paths:
        sep = "&" if "?" in p else "?"
        res = get(f"https://api.themoviedb.org/3/{p}{sep}language=en-US").get("results", [])
        for r in res:
            if r.get("adult") or not r.get("backdrop_path") or r.get("media_type") == "person":
                continue
            if r["backdrop_path"] not in out:
                out.append(r["backdrop_path"])
    return out[:4]

def fill(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))

def cover(title, paths):
    W, H, g = 960, 540, 4
    canvas = Image.new("RGB", (W, H), (8, 8, 12))
    cw, ch = (W - g) // 2, (H - g) // 2
    for i, p in enumerate(paths[:4]):
        try:
            im = Image.open(io.BytesIO(get(f"https://image.tmdb.org/t/p/w780{p}", binary=True))).convert("RGB")
        except Exception:
            continue
        canvas.paste(fill(im, cw, ch), ((i % 2) * (cw + g), (i // 2) * (ch + g)))
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(255 * (0.35 + 0.45 * y / (H - 1))))
    canvas = Image.composite(Image.new("RGB", (W, H), (8, 8, 12)), canvas, grad.resize((W, H)))
    d = ImageDraw.Draw(canvas)
    size = 86
    while size > 20:
        f = ImageFont.truetype(FONT, size)
        if d.textlength(title, font=f) <= W * 0.86:
            break
        size -= 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((W / 2, H / 2 + 3), title, font=f, anchor="mm", fill=(0, 0, 0, 210))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas.paste(shadow, (0, 0), shadow)
    ImageDraw.Draw(canvas).text((W / 2, H / 2), title, font=f, anchor="mm", fill=(255, 255, 255))
    return canvas

def main():
    plan = json.load(open(PLAN, encoding="utf-8"))
    only = set(sys.argv[1:])
    for key, item in plan.items():
        if only and key not in only and "all" not in only:
            continue
        paths = item["b"]
        if key in REFRESH and TOKEN:
            try:
                fresh = tmdb_backdrops(REFRESH[key])
                if len(fresh) >= 4:
                    paths = item["b"] = fresh
            except Exception as e:
                print("refresh failed", key, e)
        out = f"xp/{key}.webp"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cover(item["t"], paths).save(out, quality=82)
        print("built", out)
    json.dump(plan, open(PLAN, "w", encoding="utf-8"), indent=1)

if __name__ == "__main__":
    main()
