# Batch Encode Usage

Each `source.mkv` will sit in its own folder, and along
with it will be a `info.json`.

The `info.json` file contains information about the video which
will determine the resulting video file.

To be more flexable without having to modify the script itself
the`info.json` also requires an encoding command, `encodingcmd`, which
will contain the command that will reencode the file.

"Must be able to take `stdin`, and must output as `video.mkv`"

The script requires a vapoursynth script named `vpyScript.py`.
An example script is available for reference. This script will be imported
as a module by `batchconvert.py`, and call the function `vapoursynthFilter`.
The script will also call `getVSCore`, so that it doesn't have to import vapoursynth.

The script will also handle hardcoding forced subtitles via VapourSynth automatically.

#### There's an example `info.json` in this folder.

Once that is done place `batchconvert.py` in the parent directory and run it.

Example directory structure:
```
bloopers/source.mkv
bloopers/info.json
bloopers/video.py
deleted-scenes/source.mkv
deleted-scenes/info.json
deleted-scenes/video.py
batchconvert.py
```

If you have `batchconvert.py` in the same directory as an `info.json` the script
will only convert one file.
