# DSD to FLAC
Creates a copy of your NativeDSD music library, and converts the DSF/DSD files to FLAC.

## Usage

`./dsd-to-flac.py --input NativeDSD --output NativeDSD_flac`

| Option | Description |
|:---:|:--- |
| `-h,-help` | Print usage message |
| `-s,-samplerate <samepl-rate>` | Specify output sample-rate. (Default: 192000) |
| `-b,-bitdepth <bitdepth>` | Specify output bitdepth. Must be 24 or 16. (Default: 24) |
| `-i,--input <dsd directory>` | Input directory containing DSD files. |
| `-o,--output <flac directory>` | Output directory which will contain FLAC files. |
