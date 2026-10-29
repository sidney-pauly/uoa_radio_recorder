
import argparse
import json

from webscraper import scrape_slides

DEFAULT_URL = 'https://aberdeenstudentradio.com/'

def main():
    ap = argparse.ArgumentParser(description="Scrape ASR homepage slide reel")
    ap.add_argument('-u', "--url", metavar='url', default=DEFAULT_URL)
    ap.add_argument("-c", "--config", metavar="config")
    ap.add_argument("-o", "--output", metavar="output", default='./out')
    args = ap.parse_args()

    config = None
    url = args.url
    out = args.output

    if 'config' in args and args.config is not None:
        with open(args.config) as f:
            config = json.loads(f.read())

        if 'url' in config:
            url = config.url

        if 'out' in config:
            out = config.out

    print(f'    Aberdeen Student Radio Scraper    ')
    print(f'--------------------------------------')
    print(f'Author: Sidney Pauly')
    print(f'GitHub: ')
    print(f'Version: 0.0.1\n')
    print(f'---CONFIG---')
    print(f'URL:        {url}')
    print(f'Output:     {out}')

    print(scrape_slides(url))

if __name__ == "__main__":
    main()