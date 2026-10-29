import datetime
import os
from pathlib import Path

from dateutil import parser
from webscraper import scrape_slides
from zoneinfo import ZoneInfo
from ffmpeg.asyncio import FFmpeg
import asyncio

LONDON = ZoneInfo("Europe/London")

def parse_time(time_str: str, tz):

    split = time_str.split("-")

    start =     split[0].strip()
    end =       split[1].strip()

    start = parser.parse(start, fuzzy=True)
    end = parser.parse(end, fuzzy=True)

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
                      tz: ZoneInfo, retry_delay: datetime.timedelta):

    await _sleep_until(start - start_padding, tz)
 
    attempt = 0
    now = datetime.datetime.now(tz)

    while True:
        remaining = ((end + end_padding) - now)
        if remaining < datetime.timedelta(seconds=5):
            break
 
        attempt += 1
        file_name = f"{title}.mp3" if attempt == 1 else f"{title}_part{attempt}.mp3"

        print(f"Recording {title} -> {out_dir} ({remaining.total_seconds():.0f} s)")
        try:
            await record_show(out_dir, title, stream_url, remaining, file_name)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print("ffmpeg failed for '%s': %s", title, e)

        path = Path(f'{out_dir}/{file_name}')
 
        if path.exists() and path.stat().st_size == 0:
            path.unlink()  # don't leave empty files from failed attempts

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
                            tz: ZoneInfo = LONDON,
                            retry_delay: datetime.timedelta = datetime.timedelta(seconds=60),
                            poll_interval: datetime.timedelta = datetime.timedelta(minutes=5)):

    tasks: dict[tuple, tuple[asyncio.Task, dict]] = {}
 
    try:
        while True:
            try:
                shows = get_next_shows(url, tz)
                now = datetime.datetime.now(tz)
 
                for show in shows:
                    key = (show["title"], show["start"])
 
                    if key in tasks:
                        continue

                    if show["end"] + end_padding <= now:
                        continue  # already over
 
                    print(f'Scheduling {show["title"]} {show["start"]:%H:%M}-{show["end"]:%H:%M}')

                    out_folder = f'{out}/{show['start'].strftime("%Y/%m/%d")}'

                    os.makedirs(out_folder, exist_ok=True)

                    
                    task = asyncio.create_task(
                        create_record_show_continuous_task(show['title'], show['start'], show['end'], stream_url, out_folder, start_padding, end_padding, tz, retry_delay),
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
            upcoming = [s["end"] - start_padding for _, s in tasks.values()
                        if s["end"] - start_padding > now]
            if upcoming:
                wake = min(wake, max(upcoming))
            await asyncio.sleep(max(5, (wake - now).total_seconds()))
    finally:
        for task, _ in tasks.values():
            task.cancel()
        await asyncio.gather(*(t for t, _ in tasks.values()), return_exceptions=True)
 
