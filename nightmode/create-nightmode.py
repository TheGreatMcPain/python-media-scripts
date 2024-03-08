#!/usr/bin/env python3
import sys
import getopt
from ..utils import nightmode

# Nightmode Downmixing settings.
SUR_CHANNEL_VOL = 0.707  # Volume level to set the non-center channels to.
LFE_CHANNEL_VOL = 1.0  # Volume to set the LFE channel to.
CENTER_CHANNEL_VOL = 1.0  # Volume to set the center channel to.
MAXDB = "-0.5"


def main():
    codec = None
    fileIn = None

    try:
        options, args = getopt.getopt(
            sys.argv[1:], "hc:i:", ["help", "codec=", "input="]
        )
        for name, value in options:
            if name in ("-h", "--help"):
                Usage()
                sys.exit()
            if name in ("-c", "--codec"):
                codec = value
            if name in ("-i", "--input"):
                fileIn = value
    except getopt.GetoptError as err:
        print(str(err))
        Usage()
        sys.exit(1)

    if codec is None:
        Usage()
        sys.exit(1)
    if fileIn is None:
        Usage()
        sys.exit(1)

    if len(args) > 0:
        print("Error: Trailing arguments")
        sys.exit(1)

    ext = fileIn.split(".")[-1]

    nightmode.createNightmodeTracks(codec, ext, fileIn)


def Usage():
    print("Usage:", sys.argv[0], "-c,--codec <flac,aac,both> -i,--input <input file>")


if __name__ == "__main__":
    main()
