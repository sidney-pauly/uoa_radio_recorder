#!/usr/bin/env python3
"""
Scrape the main slide reel on https://aberdeenstudentradio.com/

Install:  pip install requests beautifulsoup4

Example:
    from asr_slides import scrape_slides
    data = scrape_slides(full_size=True)
    for s in data["slides"]:
        print(s["title"], s["time"], s["image"])
"""
import re

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://aberdeenstudentradio.com/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; asr-slide-scraper/1.0)"}

# Markup used by the ProRadio theme's Owl Carousel slider
SLIDE_SELECTOR = "article.proradio-slider__item"
TITLE_SELECTOR = ".proradio-post__title"
TIME_SELECTOR = ".proradio-itemmetas"
IMAGE_SELECTOR = ".proradio-slider__img img"

TIME_RE = re.compile(r"\d{1,2}:\d{2}\s*[ap]m\s*[-–]\s*\d{1,2}:\d{2}\s*[ap]m", re.I)


def _is_clone(tag):
    """Owl Carousel duplicates slides (class 'cloned') for infinite looping."""
    for node in [tag, *tag.parents]:
        if "cloned" in (node.get("class") or []):
            return True
    return False


def _text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else None


def _extract_image(slide, full_size):
    img = slide.select_one(IMAGE_SELECTOR)
    if img is None:
        return None
    if full_size:
        # data-orig-file is the original upload; drop any resize params
        url = img.get("data-orig-file") or img.get("src")
        return url.split("?")[0] if url else None
    return img.get("src") or img.get("data-src") or img.get("data-orig-file")


def _extract_time(slide):
    el = slide.select_one(TIME_SELECTOR)
    if el is None:
        return None
    # The element also contains the "access_time" icon text, so regex the range out
    m = TIME_RE.search(_text(el) or "")
    return m.group(0) if m else None


def scrape_slides(url=DEFAULT_URL, full_size=False, debug=False, timeout=20,
                  slide_selector=SLIDE_SELECTOR):
    """
    Scrape the slide reel from the Aberdeen Student Radio homepage.

    Parameters
    ----------
    url : str
        Page to scrape.
    full_size : bool
        Return the original image (data-orig-file) with resize params
        like ?fit=770%2C357&ssl=1 removed, instead of the 770px version.
    debug : bool
        Include the first slide's raw HTML in the result under "debug_html".
    timeout : int | float
        Request timeout in seconds.
    slide_selector : str
        CSS selector for one slide; change it if the theme markup changes.

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

    found = soup.select(slide_selector)

    slides, seen = [], set()
    for slide in found:
        if _is_clone(slide):
            continue
        item = {
            "title": _text(slide.select_one(TITLE_SELECTOR)),
            "time": _extract_time(slide),
            "image": _extract_image(slide, full_size),
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