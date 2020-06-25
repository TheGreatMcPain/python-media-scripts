# ffmpegSlideshow.py Usage

Just drop some jpgs in to the same directory of this script and run it like so...

```
$ ./ffmpegSlideshow.py \<display time in seconds\> \<output file\>
```

It's currently hard-coded to encode the video with libx264 with...
(-preset veryfast, -tune stillimage, -crf 15)
