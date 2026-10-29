import datetime
import os
import re
from pathlib import Path

import requests
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TALB, TPE1, TDRC, TCON, APIC

from dateutil import parser
from webscraper import scrape_slides
from zoneinfo import ZoneInfo
from ffmpeg.asyncio import FFmpeg
import asyncio

LONDON = ZoneInfo("Europe/London")

def parse_time(time_str: str, tz):

    split = re.split(r"\s*[-–]\s*", time_str)

    start =     split[0].strip()
    end =       split[1].strip()

    # Default date = today in `tz` (dateutil would otherwise use the server's date)
    today = datetime.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start = parser.parse(start, fuzzy=True, default=today)
    end = parser.parse(end, fuzzy=True, default=today)

    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz)

    # Ends after midnight
    if end <= start:
        end += datetime.timedelta(days=1)

    return (start, end)

async def stream_and_save_current_show(url: str, stream_url: str, out: str, end_padding: datetime.timedelta, tz: ZoneInfo = LONDON):

    current_shows = scrape_slides(url)


    print(f'Found {current_shows['count']} shows scheduled:')

    for s in current_shows['slides']:
        print(f'{s["time"]} {s["title"]}')

    shows = list()

    for s in current_shows['slides']:
        start, end = parse_time(s['time'], tz)
        shows.append({"title": s['title'], "start": start, "end": end, "img": s['image']})

    now = datetime.datetime.now(tz)

    show = None

    for s in shows:

        if now >= s['start'] and now <= s['end']:
            show = s
            break;

    if show is None and (shows[0]["start"] - datetime.timedelta(minutes=20)) < now:
        show = shows[0]

    if show is None:
        print('Currently no show on')
        return

    record_end = show["end"] + end_padding
    
    print(f'\nRecording {show['title']} until {record_end.hour:02}:{record_end.minute:02}')

    out_folder = f'{out}/{show['start'].strftime("%Y/%m/%d")}'

    os.makedirs(out_folder, exist_ok=True)
    await record_show(out_folder, show['title'], stream_url, (record_end - show['start']))


async def record_show(out: str, title: str, url: str, record_length: datetime.timedelta, file_name: str | None = ''):

    file = file_name or f'{title}.mp3'

    ffmpeg = (
        FFmpeg()
        .option("y")  # overwrite output
        .input(url, {
            "reconnect": 1,
            "reconnect_streamed": 1,
            "reconnect_delay_max": 5,
        })
        .output(f'{out}/{file}', {"c:a": "copy", "t": record_length.total_seconds()})
    )

    try:
        await ffmpeg.execute()
    except asyncio.CancelledError:
        ffmpeg.terminate()
        raise

def tag_recording(path: Path, title: str, start: datetime.datetime, img_url: str | None, part: int = 1):
    """Write ID3 tags and cover art. Runs after ffmpeg has finished with the file."""
    art, mime = None, "image/jpeg"
    if img_url:
        try:
            r = requests.get(img_url, timeout=15)
            r.raise_for_status()
            art = r.content
            mime = r.headers.get("Content-Type", mime).split(";")[0]
        except Exception as e:
            print(f"Could not download cover for '{title}': {e}")

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    suffix = f" (part {part})" if part > 1 else ""
    tags.setall("TIT2", [TIT2(encoding=3, text=f"{title} - {start:%d %b %Y}{suffix}")])
    tags.setall("TALB", [TALB(encoding=3, text=title)])
    tags.setall("TPE1", [TPE1(encoding=3, text="Aberdeen Student Radio")])
    tags.setall("TDRC", [TDRC(encoding=3, text=start.strftime("%Y-%m-%dT%H:%M"))])
    tags.setall("TCON", [TCON(encoding=3, text="Radio")])
    if art:
        tags.setall("APIC", [APIC(encoding=3, mime=mime, type=3, desc="Cover", data=art)])
    tags.save(path, v2_version=3)  # v2.3 is the most widely supported


def get_next_shows(url: str,  tz: ZoneInfo):

    current_shows = scrape_slides(url)

    print(f'Found {current_shows['count']} shows scheduled:')

    for s in current_shows['slides']:
        print(f'{s["time"]} {s["title"]}')

    shows = list()

    for s in current_shows['slides']:
        start, end = parse_time(s['time'], tz)
        shows.append({"title": s['title'], "start": start, "end": end, "img": s['image']})

    return shows

 
async def _sleep_until(when: datetime.datetime, tz: ZoneInfo):
    now = datetime.datetime.now(tz)

    delay = (when - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)

async def create_record_show_continuous_task(title: str, start: datetime.datetime, end: datetime.datetime, stream_url: str, out_dir: str,
                      start_padding: datetime.timedelta,
                      end_padding: datetime.timedelta,
                      tz: ZoneInfo, retry_delay: datetime.timedelta,
                      img: str | None = None,
                      min_play_time: datetime.timedelta = datetime.timedelta(seconds=120)):

    await _sleep_until(start - start_padding, tz)
 
    attempt = 0
    now = datetime.datetime.now(tz)

    while True:
        remaining = ((end + end_padding) - now)
        if remaining < min_play_time:
            break
 
        attempt += 1
        # Start time keeps same-titled shows apart (e.g. two "After hours" slots a day);
        # sanitising avoids characters that are invalid in file names.
        safe_title = re.sub(r'[\\/:*?"<>|]+', "-", title).strip() or "show"
        base = f"{start:%H%M} {safe_title}"
        file_name = f"{base}.mp3" if attempt == 1 else f"{base}_part{attempt}.mp3"

        print(f"Recording {title} -> {out_dir} ({remaining.total_seconds():.0f} s)")
        try:
            await record_show(out_dir, title, stream_url, remaining, file_name)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"ffmpeg failed for '{title}': {e}")

        path = Path(f'{out_dir}/{file_name}')
 
        if path.exists() and path.stat().st_size == 0:
            path.unlink()  # don't leave empty files from failed attempts
        elif path.exists():
            try:
                await asyncio.to_thread(tag_recording, path, title, start, img, attempt)
            except Exception as e:  # tagging must never break the retry loop
                print(f"Tagging failed for '{title}': {e}")

        now = datetime.datetime.now(tz)
 
        remaining = ((end + end_padding) - now).total_seconds()
        if remaining >= 5:
            print(f"Recording of '{title}' stopped early; retrying in {int(retry_delay.total_seconds())}s")
            await asyncio.sleep(min(retry_delay.total_seconds(), remaining))
 
    print(f"Finished '{title}'")


async def record_continuous(url: str, 
                            stream_url: str, 
                            out: str,
                            start_padding: datetime.timedelta,
                            end_padding: datetime.timedelta,
                            blacklist: list[str],
                            re_blacklist: list[str],
                            tz: ZoneInfo = LONDON,
                            retry_delay: datetime.timedelta = datetime.timedelta(seconds=60),
                            poll_interval: datetime.timedelta = datetime.timedelta(minutes=5),
                            min_play_time: datetime.timedelta = datetime.timedelta(seconds=120)):

    tasks: dict[tuple, tuple[asyncio.Task, dict]] = {}
 
    try:
        while True:
            try:
                shows = await asyncio.to_thread(get_next_shows, url, tz)
                now = datetime.datetime.now(tz)
                scheduled_count = 0
 
                for show in shows:
                    key = (show["title"], show["start"])

                    if show['title'] in blacklist:
                        continue

                    re_match = False
                    for r in re_blacklist:
                        if re.match(r, show["title"]) is not None:
                            re_match = True
                    
                    if re_match:
                        continue
 
                    if key in tasks:
                        continue

                    if show["end"] + end_padding <= now:
                        continue  # already over

                    scheduled_count += 1
 
                    print(f'Scheduling {show["title"]} {show["start"]:%H:%M}-{show["end"]:%H:%M}')

                    out_folder = f'{out}/{show['start'].strftime("%Y/%m/%d")}'

                    os.makedirs(out_folder, exist_ok=True)

                    
                    task = asyncio.create_task(
                        create_record_show_continuous_task(show['title'], show['start'], show['end'], stream_url, out_folder, start_padding, end_padding, tz, retry_delay, show['img'], min_play_time),
                        name=f'record:{show["title"]}',
                    )
                    tasks[key] = (task, show)
 
                # Drop finished tasks and report any that crashed
                for key, (task, _) in list(tasks.items()):
                    if task.done():
                        if not task.cancelled() and task.exception():
                            print(f"Recording task {task.get_name()} crashed: {task.exception()}")
                        del tasks[key]
 
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Schedule update failed: {e}. Retrying in {int(retry_delay.total_seconds())}s")
                await asyncio.sleep(retry_delay.total_seconds())
                continue
 
            # Sleep until the next scrape: normally poll_interval, but wake in time
            # to catch the next schedule when the last known show is about to end.
            now = datetime.datetime.now(tz)
            wake = now + poll_interval
            # Using s["end"] here as we are interested in the end of the current show
            upcoming = [s["end"] - start_padding for _, s in tasks.values() if s["end"] - start_padding > now] 
            if upcoming:
                wake = min(wake, max(upcoming))

            wait_seconds = (wake - now).total_seconds()

            print(f'Nothing to schedule waiting for {int(wait_seconds)}s to re check')
            
            await asyncio.sleep(max(5, wait_seconds))
    finally:
        for task, _ in tasks.values():
            task.cancel()
        await asyncio.gather(*(t for t, _ in tasks.values()), return_exceptions=True)