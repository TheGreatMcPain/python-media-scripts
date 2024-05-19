## TODO: Update this whole README.md

# Batch Encode Usage

Each `source.mkv` will sit in its own folder, and along
with it will be a `info.json`.

The `info.json` file contains information about the video which
will determine the resulting video file.

The functions within the script `encodeInfo.py` can be modified to change how the video will be encoded.
Keep in-mind that the output format, and filename, must be supported by mkvmerge.
Also, the `encodeInfo.py` script must be next to `batchconvert.py` as batchconvert will import `encodeInfo.py`
as a python module.

The script will also handle hardcoding forced subtitles via VapourSynth automatically.

#### There's an example `info.json` in this folder.

Once that is done place `batchconvert.py` in the parent directory and run it.

Example directory structure:

```
bloopers/source.mkv
bloopers/info.json
deleted-scenes/source.mkv
deleted-scenes/info.json
encodeInfo.py
batchconvert.py
```

If you have `batchconvert.py` in the same directory as an `info.json` the script
will only convert one file. (Such as the main movie file.)

# Requirements (I think I got all of them.)

- mkvtoolnix
- ffmpeg
- bdsup2sub (or bdsup2sub++) "The script needs to know where bdsup2sub is at."
- VapourSynth
- psutil (Only used for setting cpu priority)
