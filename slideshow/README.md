# ffmpegSlideshow.py Usage

Just drop some jpgs in to the same directory of this script and run it like so...

```
$ ./ffmpegSlideshow.py \<width\> \<height\> \<display time in seconds\> \<output file\>
```

It's currently hard-coded to encode the video with libx264 with...
(-preset veryfast, -tune stillimage, -crf 15)

## Requirements

- ffmpeg (if it wasn't obvious)

## Example command

```
./ffmpegSlideshow.py 1024 682 5 slideshow-14.mkv
```
