# Nightmode Scripts Usage

## Step 1

Create a file named `filelist.txt` with a list of mkv files.
Ex:
```
../Video 1.mkv
../Video 2.mkv
/path/to/Video 3.mkv
```

## Step 2

run `gen_nightmode.py` which will ask a series of questions for each file
in `filelist.txt`.

1. Exclude this file
2. List of audio tracks to keep
3. Which tracks to create nightmode tracks from and their languages. (currently supports `eng` and `jpn`)
4. What codec the nightmode tracks will be. (`flac` or `aac`)

This will generate a `workDict.json` file which can be read like so.
```
$ cat workDict.json | json_pp
```

## Step 3

Run `replace_nightmode.py`. It will take a while depending on the size and number of mkvs,
and the speed of your storage device.

### TODO

* Do a complete rewrite in order to simplify usage.
* Instead of asking about each file, ask for global settings, then if a file
has a different number of tracks from the rest ask for input.
(this will be nice for shows that have commentary tracks in a few episodes)

## Requirements

* ffmpeg
* mkvtoolnix
