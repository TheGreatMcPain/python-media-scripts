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
is killed prematurely.  If the script finds the `bluray_data.json` file on the next run
it will ask the user if they want to just use the json file instead of creating a new list
of files to extract.

## Nightmode

The `nightmode` folder contains scripts I use to automatically add
"Nightmode" tracks to groups of mkvs.  It will use a choosen surround
sound track, and create two new audio tracks in either flac or aac.

A "Nightmode Loudnorm" track which boosts the center channel, and applies
ffmpeg's `loudnorm` filter to add minor loudness normalization.

A "Nightmode Loudnorm+DRC" track which does the same as the previous track,
but adds ffmpeg's `acompress=ratio=4` to the audio filter-chain to add
a more agressive dynamic range compression.

I used this [reddit post](https://www.reddit.com/r/PleX/comments/9rc7sp/thought_id_share_some_ffmpeg_scripts_i_made_to/)
to get the ffmpeg filter-chains.

## Batch Encode

The `batchencode` folder has a script that prepares mkvs for use in my server.

I wrote it with the intent of batch converting BluRay extras will usually
only have a video track, english stereo/5.1 ac3 track, and english PGS subtitles.

The script will extract the audio, and subtitles, via `mkvextract`, extract
any forced subtitles via `BDSup2Sub`, remove the forced subtitles from the original
subtitles file, re-encode the video, while embedding forced subtitles, via `Vapoursynth/x264`,
and finally mux a new mkv via `mkvmerge`.

## Generate Combined MKV

The `generate-combined-mkv` folder has a script that combines a set of mkvs into
one big mkv.

It was made for extras from BluRays that decide to put deleted scenes into seperate
files.

It simply appends a set of mkv files into one mkv via mkvmerge.

Along with that it also asks the user for custom chapter names for each mkv file.

#### Usage for these scripts are in their respective folders.
