# Some Python scripts I use for BluRay re-encodes

### TODO: Update README's and combine some of this into one program

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

## Nightmode

The `nightmode` folder contains scripts I use to add "Nightmode" tracks to mkvs.
Originally made for devices in the house that have terrible downmixing/DRC options.
It will take a surround sound track, and create three audio tracks in either flac and/or aac.

A "Nightmode DownmixOnly" track which boosts the center channel a bit
without applying any extra filters.
I find this works well with dialogue heavy movies like Oppenheimer.

A "Nightmode Loudnorm" track which boosts the center channel, and applies
ffmpeg's `loudnorm` filter to add minor loudness normalization.
I tend to prefer this for most movies especially those with DTSHD tracks,
since those don't have built-in Dynamic-Range-Compression like Dolby's TrueHD/AC3 do.

A "Nightmode Loudnorm+DRC" track which does the same as the previous track,
but adds ffmpeg's `acompress=ratio=4` to the audio filter-chain to add
a more agressive dynamic range compression. I don't really use this one much.
It might work for when it's 3am and you don't want to wake anyone, hate subtitles,
and also hate wearing headphones for some reason.

I used this [reddit post](https://www.reddit.com/r/PleX/comments/9rc7sp/thought_id_share_some_ffmpeg_scripts_i_made_to/)
to get the ffmpeg filter-chains.

## Batch Encode

The `batchencode` folder has a script that prepares mkvs for use in my server.

I wrote it with the intent of batch converting BluRay extras will usually
only have a video track, english stereo/5.1 ac3 track, and english PGS subtitles.

The script will extract the audio, and subtitles, via `mkvextract`, extract
any forced subtitles via `BDSup2Sub`, remove the forced subtitles from the original
subtitles file, re-encode the video, while embedding forced subtitles,
and finally mux a new mkv via `mkvmerge`.

## Misc Subtitle Scripts (subtitles folder)

`compare-forced-subtitles` Created forced subtitles by comparing two BDNXML subtitles
and marking subs as forced where they overlap. This was very useful for the
Planet of the Apes reboot movies, where I wanted to burn in the sign language
subtitles, but didn't want any overlaps from the regular subtitles.

## 2D to 3D Subtitle Convertion Scripts

`3d-misc` has a bunch of WIP scripts that are ported code from
the program BD3D2MK3D which is written 'tcl'. I'm working on porting some
of the subtitle related stuff to Python. They do require ''3D-Plane' metadata
which can be obtained by `OFSExtractor` or `MVCPlanes2OFS`.
`OFSExtractor` can be found [here](https://gitlab.com/TheGreatMcPain/OFSExtractor),
but both can be found in `BD3D2MK3D`'s `toolset` folder.

#### Usage for these scripts are in their respective folders.
