# University of Aberdeen student radio recorder

This script records the stream from https://aberdeenstudentradio.com/

```
Options:  
  -h, --help            show this help message and exit  
  -u, --url url         Url of the website to scrape the metadata and scheduled shows  
  -s, --stream-url      Url of the mp3 stream  
  -c, --config config   Config file path  
  -o, --output output   Output folder  
  -p, --padding         Time in minutes added to recording before and after show is scheduled to start/end
  -m, --mode mode       Mode options are "SINGLE" or "CONTINUOUS"
```

The script can either be run once to record the current show or in continuous mode as a service to record all shows. Shows are broken up into separate mp3 files with padding added at the start/end to account for shows not starting exactly at the scheduled time posted


### AI disclaimer

Some of the code in this repository has been written with the help of AI. All code has been manually modified/reviewed for security and functionality


