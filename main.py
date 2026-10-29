
import argparse
import asyncio
from datetime import timedelta
import json

from recorder import record_continuous, stream_and_save_current_show
from webscraper import scrape_slides

DEFAULT_URL = 'https://aberdeenstudentradio.com/'
DEFAULT_STREAM_URL = 'https://streaming.broadcast.radio/aberdeenstudentradio'


async def main():
    ap = argparse.ArgumentParser(description="Scrape ASR homepage slide reel")
    ap.add_argument('-u', "--url", metavar='url', default=DEFAULT_URL, help='Url of the website to scrape the metadata and scheduled shows')
    ap.add_argument('-s', "--stream-url", metavar='stream_url', default=DEFAULT_STREAM_URL, help='Url of the mp3 stream')
    ap.add_argument("-c", "--config", metavar="config", help='Config file path')
    ap.add_argument("-o", "--output", metavar="output", default='./out', help='Output folder')
    ap.add_argument("-p", "--padding", default=10, help='Time in minutes added to recording before and after show is scheduled to start/end (if --padding-end is set only applies to start padding)')
    ap.add_argument("-e", "--padding-end", metavar='padding_end', help='Time in minutes added to recording after show is scheduled end')
    ap.add_argument("-m", "--mode", metavar="mode", default='CONTINUOUS', help='Mode options are "SINGLE" or "CONTINUOUS"')
    ap.add_argument("-i", "--poll-interval", metavar="poll_interval", default=5, help='Poll interval to query for new shows and schedule them (in minutes)')
    ap.add_argument("-d", "--retry-delay", metavar="retry_delay", default=60, help='Retry delay if an error occurs (in seconds)')
    ap.add_argument("-t", "--min-play-time", metavar="min_play_time", default=240, help='Min remaining play time plus padding for a recording to be made of a show (in seconds)')

    args = ap.parse_args()

    config = None
    url: str = args.url
    out: str = args.output
    stream_url: str = args.stream_url
    padding: int = args.padding
    padding_end: int = args.padding_end if 'padding_end' in args and args.padding_end is not None else padding
    blacklist: list[str] = list()
    re_blacklist: list[str] = list()
    poll_interval: int = args.poll_interval
    retry_delay: int = args.retry_delay
    min_play_time: int = args.min_play_time

    if 'config' in args and args.config is not None:
        with open(args.config) as f:
            config = json.loads(f.read())

        if 'url' in config:
            url = config['url']

        if 'streamUrl' in config:
            stream_url = config['streamUrl']

        if 'out' in config:
            out = config['out']

        if 'padding' in config:
            padding = config['padding']

        if 'paddingEnd' in config:
            padding_end = config['paddingEnd']

        if 'blacklist' in config:
            blacklist = config['blacklist']

        if 'reBlacklist' in config:
            re_blacklist = config['reBlacklist']

        if 'pollInterval' in config:
            poll_interval = config['pollInterval']

        if 'retryDelay' in config:
            retry_delay = config['retryDelay']

        if 'minPlayTime' in config:
            min_play_time = config['minPlayTime']

    print(f'======================================')
    print(f'|   Aberdeen Student Radio Scraper   |')
    print(f'======================================\n')
    print(f'Author: Sidney Pauly')
    print(f'GitHub: https://github.com/sidney-pauly/uoa_radio_recorder')
    print(f'Version: 0.0.2\n')
    print(f'---CONFIG---')
    print(f'Output:          {out}')
    print(f'Config file:     {args.config}')


    if 'mode' in args and str.lower(args.mode) == 'single':
        print(f'\nSingle mode, downloading current show....')
        await stream_and_save_current_show(url, stream_url, out, timedelta(minutes=padding))
        return

    if 'mode' in args and str.lower(args.mode) == 'continuous':
        print('\nContinuous mode: recording shows as they get scheduled')
        await record_continuous(
            url,
            stream_url,
            out,
            timedelta(minutes=padding),
            timedelta(minutes=padding_end),
            blacklist,
            re_blacklist,
            retry_delay=timedelta(seconds=retry_delay),
            poll_interval=timedelta(minutes=poll_interval),
            min_play_time=timedelta(seconds=min_play_time)
        )
        return

    print(f'Unknown mode: {args.mode}')
    

if __name__ == "__main__":
    asyncio.run(main())