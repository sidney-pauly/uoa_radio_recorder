# University of Aberdeen student radio recorder

This script records the stream from https://aberdeenstudentradio.com/

### Cmd options

```
Options:  
  -h, --help                        show this help message and exit
  -u, --url url                     Url of the website to scrape the metadata and scheduled shows
  -s, --stream-url stream_url       Url of the mp3 stream
  -c, --config config               Config file path
  -o, --output output               Output folder
  -p, --padding PADDING             Time in minutes added to recording before and after show is scheduled to start/end (if --padding-end is set only applies to start padding)
  -e, --padding-end padding_end     Time in minutes added to recording after show is scheduled end
  -m, --mode mode                   Mode options are "SINGLE" or "CONTINUOUS"
  -i, --poll-interval poll_interval Poll interval to query for new shows and schedule them (in minutes)
  -d, --retry-delay retry_delay     Retry delay if an error occurs (in seconds)
  -t, --min-play-time min_play_time Min remaining play time plus padding for a recording to be made of a show (in seconds)
```

The script can either be run once to record the current show or in continuous mode as a service to record all shows. Shows are broken up into separate mp3 files with padding added at the start/end to account for shows not starting exactly at the scheduled time posted.

### Config

The config file can contain the following options (if the config file contains a value it overwrites the command line argument)

```json
{
  "url": "https://aberdeenstudentradio.com/",
  "streamUrl": "https://streaming.broadcast.radio/aberdeenstudentradio",
  "out": "/example/output/path",
  "padding": 10,
  "paddingEnd": 10,
  "blacklist": ["After hours with Aberdeen Student Radio"],
  "reBlacklist": [],
  "pollInterval": 5,
  "retryDelay": 120,
  "minPlayTime": 180
}
```

`blacklist` applies to all titles of shows, if any match the show is not recorded.
`reBlacklist` are regular expressions used as a blacklist (see https://regex101.com/ to test your regular expressions). Uses python flavoured re
See matching command line arguments for details on other options.


### AI disclaimer

Some of the code in this repository has been written with the help of AI. All code has been manually modified/reviewed for security and functionality


