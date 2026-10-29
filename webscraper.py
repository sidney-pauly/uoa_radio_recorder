#!/usr/bin/env python3
"""
Scrape the main slide reel on https://aberdeenstudentradio.com/
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; asr-slide-scraper/1.0)"}

# e.g. "5:00 pm - 6:00 pm"
TIME_RE = re.compile(r"\d{1,2}:\d{2}\s*[ap]m\s*[-–]\s*\d{1,2}:\d{2}\s*[ap]m", re.I)
# background-image: url(...) in inline styles
BG_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.I)

# Class-name fragments used by common slider libraries (Swiper, Slick, Owl, Elementor...)
SLIDE_HINTS = ("slide", "owl-item", "carousel-item")
CLONE_HINTS = ("cloned", "duplicate")


def _class_str(tag):
    return " ".join(tag.get("class", [])).lower()


def _is_clone(tag):
    """Sliders duplicate slides for infinite looping; detect those copies."""
    node = tag
    while node is not None and getattr(node, "name", None):
        if any(h in _class_str(node) for h in CLONE_HINTS):
            return True
        node = node.parent
    return False


def _is_slide_like(tag):
    return any(h in _class_str(tag) for h in SLIDE_HINTS)


def _find_slide_for_time(time_node):
    """Walk up from a time string to the element that wraps the whole slide."""
    el = time_node.parent
    best = el
    while el.parent is not None and el.parent.name not in ("body", "html", "[document]"):
        parent = el.parent
        if len(TIME_RE.findall(parent.get_text(" ", strip=True))) > 1:
            break  # parent holds several slides, so stop here
        el = parent
        best = el
        if _is_slide_like(el):
            break
    return best


def _extract_image(slide, base_url):
    """Prefer a CSS/data background image; fall back to <img> tags."""
    candidates = []
    for el in [slide] + slide.find_all(True):
        m = BG_RE.search(el.get("style", "") or "")
        if m:
            candidates.append((0, m.group(1)))
        for attr in ("data-bg", "data-background", "data-bg-image"):
            if el.get(attr):
                candidates.append((0, el[attr]))
        if el.name == "img":
            for attr in ("data-src", "data-lazy-src", "src"):
                val = el.get(attr)
                if val and not val.startswith("data:"):
                    candidates.append((1, val))
                    break
            else:
                srcset = el.get("srcset") or el.get("data-srcset")
                if srcset:
                    candidates.append((1, srcset.split(",")[0].strip().split(" ")[0]))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])  # backgrounds first
    return urljoin(base_url, candidates[0][1])


def _extract_title(slide):
    heading = slide.find(["h1", "h2", "h3", "h4", "h5"])
    if heading and heading.get_text(strip=True):
        return re.sub(r"\s+", " ", heading.get_text(" ", strip=True))
    img = slide.find("img", alt=True)
    if img and img["alt"].strip():
        return img["alt"].strip()
    return None


def scrape_slides(url, selector=None, full_size=False,
                  debug=False, timeout=20):
    """
    Scrape the slide reel from the Aberdeen Student Radio homepage.

    Parameters
    ----------
    url : str
        Page to scrape.
    selector : str | None
        CSS selector matching one slide each. Overrides auto-detection.
    full_size : bool
        Strip resize query params (e.g. ?fit=770%2C770&ssl=1) from image URLs.
    debug : bool
        Include the first slide's raw HTML in the result under "debug_html".
    timeout : int | float
        Request timeout in seconds.

    Returns
    -------
    dict
        {
          "url": str,
          "count": int,
          "slides": [{"title": str, "time": str | None, "image": str | None}, ...],
          "debug_html": str   # only when debug=True
        }
    """
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    if selector:
        found = soup.select(selector)
    else:
        found = []
        for node in soup.find_all(string=TIME_RE):
            slide = _find_slide_for_time(node)
            if slide not in found:
                found.append(slide)
        # Prefer real slider slides so the weekly schedule isn't mixed in.
        slider_slides = [s for s in found if _is_slide_like(s)]
        if slider_slides:
            found = slider_slides

    slides, seen = [], set()
    for slide in found:
        if _is_clone(slide):
            continue
        t = TIME_RE.search(slide.get_text(" ", strip=True))
        image = _extract_image(slide, url)
        if image and full_size:
            image = image.split("?")[0]
        item = {
            "title": _extract_title(slide),
            "time": t.group(0) if t else None,
            "image": image,
        }
        key = (item["title"], item["time"], item["image"])
        if key in seen or not item["title"]:
            continue
        seen.add(key)
        slides.append(item)

    result = {"url": url, "count": len(slides), "slides": slides}
    if debug and found:
        result["debug_html"] = found[0].prettify()
    return result

