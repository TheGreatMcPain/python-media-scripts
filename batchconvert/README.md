# Batch Encode Usage

Each `source.mkv` will sit in its own folder, and along
with it will be a `info.json`.

The `info.json` file contains information about the video which
will determine the resulting video file.

To be more flexable without having to modify the script itself
the`info.json` also requires `x264opts` which contains arguments for
`x264`. The script will read them like this.
```
x264 --demuxer y4m <your x264opts will be here> --frames <num of frames> --output video.mkv -
```

Along with `x264opts` there is also the `vapoursynth` option.
This option contains python code related to VapourSynth.
Make sure to name each clip `video` when writting your own VapourSynth code.

Also the script will run these lines of code automatically.
```
import vapoursynth as vs
core = vs.core
```

The script will also handle hardcoding forced subtitles via VapourSynth automatically.

Not sure if I'll keep the `vapoursynth` option, or make it a separate file
that sits next to the `info.json` file.\
(Might be easier for more complex vapoursynth scripts)

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

If you have `encode_extras.py` in the same directory as an `info.json` the script
will only convert one file.
