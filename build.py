#!/usr/bin/env python3
"""Build an 800x480 e-paper dashboard page (docs/index.html).

Weather: Open-Meteo (free, no API key) for zip 10016 / Murray Hill, Manhattan.
Headlines: any RSS feeds listed in FEEDS.
Runs on a schedule in GitHub Actions; the reTerminal shows the published page.
Standard library only.
"""
import html
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---- Settings you might want to change ------------------------------------
LAT, LON = 40.7466, -73.9786          # zip 10016
PLACE = "Murray Hill, NYC"
TZ = ZoneInfo("America/New_York")
HOURS_SHOWN = 8                        # hourly forecast columns
DAYS_SHOWN = 4                         # daily forecast rows (bottom-left kept free for SenseCraft sensor gauges)
HEADLINES_SHOWN = 6
# (short label, headlines per source, [feed URLs to try in order])
FEEDS = [
    ("NYT", 2, ["https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"]),
    ("WSJ", 2, ["https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
                "https://feeds.a.dj.com/rss/RSSWorldNews.xml"]),
    ("FT",  2, ["https://www.ft.com/rss/home",
                "https://www.ft.com/news-feed?format=rss"]),
]
# ---------------------------------------------------------------------------

OUT = Path(__file__).parent / "docs" / "index.html"
UA = {"User-Agent": "eink-dashboard/1.0"}

WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy",
    45: "Fog", 48: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain",
    65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow",
    73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Showers", 81: "Showers",
    82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorms", 96: "Thunderstorms", 99: "Thunderstorms",
}


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m"
        "&hourly=temperature_2m,precipitation_probability,weather_code"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FNew_York&forecast_days=7"
    )
    return json.loads(get(url))


def read_feed(url, n):
    root = ET.fromstring(get(url))
    items = []
    for it in root.iter("item"):
        t = " ".join((it.findtext("title") or "").split())
        if t:
            items.append(t)
        if len(items) >= n:
            break
    return items


def fetch_headlines():
    out = []
    for label, n, urls in FEEDS:
        for url in urls:
            try:
                items = read_feed(url, n)
                if items:
                    out += [(label, t) for t in items]
                    break
            except Exception as e:  # try the next URL; one bad feed never breaks the page
                print(f"feed failed {label} {url}: {e}", file=sys.stderr)
        else:
            print(f"no working feed for {label}", file=sys.stderr)
    return "Headlines", out or [("", "Headlines unavailable right now.")]


def hour_label(dt):
    h = dt.hour % 12 or 12
    return f"{h}{'a' if dt.hour < 12 else 'p'}"


def render(w, feed_label, headlines, now):
    e = html.escape
    cur = w["current"]
    d = w["daily"]
    hr = w["hourly"]

    # hourly: next N hours starting at the coming hour
    times = [datetime.fromisoformat(t).replace(tzinfo=TZ) for t in hr["time"]]
    start = next(i for i, t in enumerate(times) if t >= now.replace(minute=0, second=0, microsecond=0))
    hours = range(start + 1, start + 1 + HOURS_SHOWN)
    hourly_html = "".join(
        f"<td><div class=h>{hour_label(times[i])}</div>"
        f"<div class=ht>{round(hr['temperature_2m'][i])}°</div>"
        f"<div class=hp>{hr['precipitation_probability'][i] or 0}%</div></td>"
        for i in hours
    )

    daily_rows = ""
    for i in range(DAYS_SHOWN):
        day = datetime.fromisoformat(d["time"][i])
        name = "Today" if i == 0 else day.strftime("%a")
        daily_rows += (
            f"<tr><td class=dn>{name}</td>"
            f"<td class=dc>{e(WMO.get(d['weather_code'][i], ''))}</td>"
            f"<td class=dp>{d['precipitation_probability_max'][i] or 0}%</td>"
            f"<td class=dt><b>{round(d['temperature_2m_max'][i])}°</b> / {round(d['temperature_2m_min'][i])}°</td></tr>"
        )

    sunset = datetime.fromisoformat(d["sunset"][0]).strftime("%-I:%M")
    heads = "".join(
        f"<li><span class=tag>{e(src)}</span> {e(h)}</li>" for src, h in headlines[:HEADLINES_SHOWN]
    )
    updated = now.strftime("%-I:%M %p").lower()

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=800, height=480">
<meta http-equiv="refresh" content="900">
<title>Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:800px;height:480px;overflow:hidden;background:#fff;color:#000;
  font-family:Georgia,"Times New Roman",Times,serif;-webkit-font-smoothing:none}}
.wrap{{display:flex;flex-direction:column;height:480px;padding:18px 22px 14px}}
header{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:3px solid #000;padding-bottom:6px}}
.date{{font-size:30px;font-weight:bold}}
.meta{{font-size:15px}}
main{{display:flex;flex:1;gap:22px;padding-top:12px;min-height:0}}
.wx{{width:372px;display:flex;flex-direction:column}}
.now{{display:flex;align-items:center;gap:16px}}
.temp{{font-size:84px;font-weight:bold;line-height:.9;letter-spacing:-2px}}
.cond{{font-size:22px;font-weight:bold}}
.sub{{font-size:15px;line-height:1.35}}
table{{border-collapse:collapse;width:100%}}
.hourly{{margin-top:12px;border-top:2px solid #000;border-bottom:2px solid #000}}
.hourly td{{text-align:center;padding:5px 0}}
.h{{font-size:14px}} .ht{{font-size:20px;font-weight:bold}} .hp{{font-size:13px}}
.daily{{margin-top:6px}}
.daily td{{font-size:17px;padding:4px 0;border-bottom:1px solid #000}}
.daily tr:last-child td{{border-bottom:none}}
.dn{{font-weight:bold;width:62px}} .dp{{text-align:right;width:48px;font-size:14px}} .dt{{text-align:right;width:92px}}
.news{{flex:1;border-left:2px solid #000;padding-left:20px;min-width:0}}
.src{{font-size:15px;text-transform:uppercase;letter-spacing:2px;font-weight:bold;margin-bottom:6px}}
ul{{list-style:none}}
li{{font-size:18px;line-height:1.22;margin-top:7px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
li+li{{border-top:1px solid #000;padding-top:7px}}
.tag{{font-size:13px;font-weight:bold;letter-spacing:1px;border:1.5px solid #000;padding:0 4px;margin-right:4px;vertical-align:2px}}
</style></head>
<body><div class=wrap>
<header><div class=date>{now.strftime("%A, %B %-d")}</div>
<div class=meta>{e(PLACE)} &middot; updated {updated}</div></header>
<main>
<section class=wx>
  <div class=now>
    <div class=temp>{round(cur['temperature_2m'])}°</div>
    <div><div class=cond>{e(WMO.get(cur['weather_code'], ''))}</div>
    <div class=sub>Feels {round(cur['apparent_temperature'])}° &middot; Wind {round(cur['wind_speed_10m'])} mph<br>
    Humidity {cur['relative_humidity_2m']}% &middot; Sunset {sunset}</div></div>
  </div>
  <table class=hourly><tr>{hourly_html}</tr></table>
  <table class=daily>{daily_rows}</table>
</section>
<section class=news>
  <div class=src>{e(feed_label)}</div>
  <ul>{heads}</ul>
</section>
</main></div></body></html>"""


def main():
    now = datetime.now(TZ)
    if len(sys.argv) > 1:  # local preview with saved sample data
        sample = json.loads(Path(sys.argv[1]).read_text())
        w, (label, heads) = sample["weather"], (sample["label"], sample["headlines"])
        now = datetime.fromisoformat(sample["now"]).replace(tzinfo=TZ)
    else:
        w = fetch_weather()
        label, heads = fetch_headlines()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(w, label, heads, now), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
