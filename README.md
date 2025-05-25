# Some Python scripts I use for BluRay re-encodes

One of my hobbies is managing a media server which involves backing up BluRays,
and preparing their contents for my server.

These are some Python scripts I wrote to make the process more automatic.

## Extract Bluray

The `extract_bluray` script will batch mkvmerge files from a BluRay.

It will ask the user for filenames with the extension mpls, or m2ts,
and will ask for an output folder name which will be automatically created later.

After that the script will begin creating `source.mkv` files.

The script will also create a `bluray_data.json` file in the event that the script
is killed prematurely. If the script finds the `bluray_data.json` file on the next run
it will ask the user if they want to just use the json file instead of creating a new list
of files to extract.

# 'batchconvert.py' Usage

Each `source.mkv` will sit in its own folder, and along
with it will be a `info.json`.

The `info.json` file contains information about the video which
will determine the resulting video file.

(`utils/info.py` can be used to generate an `info.json`)

`vapoursynth-filter.py` can be used to pre-process the video via VapourSynth during transcoding.
This is useful for deinterlacing, cropping, and/or resizing.

(See example `info.json` and `vapoursynth-filter.py`)

Example directory structure:

```
bloopers/source.mkv
bloopers/info.json
deleted-scenes/source.mkv
deleted-scenes/info.json
deleted-scenes/vapoursynth-filter.py
batchconvert.py
```

## Requirements (I think I got all of them.)

- mkvtoolnix
- ffmpeg
- bdsup2sub (or bdsup2sub++) "The script needs to know where bdsup2sub is at."
- VapourSynth
- psutil (Only used for setting cpu priority)
- sup2srt
