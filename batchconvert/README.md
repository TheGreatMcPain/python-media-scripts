# Batch Encode Usage

Each `source.mkv` will sit in its own folder, and along
with it will be a `info.json`.

The `info.json` file contains information about the video which
will determine the resulting video file.

#### There's an example `info.json` in this folder.

Once that is done place `encode_extras.py` in the parent directory and run it.

Example directory structure:
```
bloopers/source.mkv
bloopers/info.json
deleted-scenes/source.mkv
deleted-scenes/info.json
encode_extras.py
```

## TODO

* Add Ability to transcode audio tracks to different formats.
* Create nightmode tracks option.
