
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
    ap.add_argument('-u', "--url", metavar='url', default=DEFAULT_URL)
    ap.add_argument('-s', "--stream-url", metavar='stream_url', default=DEFAULT_STREAM_URL)
    ap.add_argument("-c", "--config", metavar="config")
    ap.add_argument("-o", "--output", metavar="output", default='./out')
    ap.add_argument("-p", "--padding", default=10, help='Time in minutes added to recording before and after show is scheduled to start/end')
    ap.add_argument("-m", "--mode", metavar="mode", default='CONTINUOUS', help='Mode options are "SINGLE" or "CONTINUOUS"')

    args = ap.parse_args()

    config = None
    url: str = args.url
    out: str = args.output
    stream_url: str = args.stream_url
    padding: int = args.padding

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

    print(f'    Aberdeen Student Radio Scraper    ')
    print(f'--------------------------------------')
    print(f'Author: Sidney Pauly')
    print(f'GitHub: ')
    print(f'Version: 0.0.1\n')
    print(f'---CONFIG---')
    print(f'URL:        {url}')
    print(f'Output:     {out}')

    if 'mode' in args and str.lower(args.mode) == 'single':
        print(f'\nSingle mode, downloading current show....')
        await stream_and_save_current_show(url, stream_url, out, timedelta(minutes=padding))
        return

    if 'mode' in args and str.lower(args.mode) == 'continuous':
        print('Continuous mode recording shows as they get scheduled')
        await record_continuous(url, stream_url, out, timedelta(minutes=padding), timedelta(minutes=padding))
        return

    print(f'Unknown mode: {args.mode}')
    

if __name__ == "__main__":
    asyncio.run(main())