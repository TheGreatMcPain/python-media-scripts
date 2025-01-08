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

TODO

## Batch Encode

The `batchencode` folder has a script that prepares mkvs for use in my server.

I wrote it with the intent of batch reproducing Blu-ray rips in the case of data loss.

## Misc Subtitle Scripts

`forced-subtitles` Creates forced subtitles by comparing two BDNXML subtitles
and marking subs as forced where they overlap. This was very useful for the
Planet of the Apes reboot movies, where I wanted to burn in the sign language
subtitles, but didn't want any overlaps from the regular subtitles.

#### Usage for these scripts are in their respective folders.
