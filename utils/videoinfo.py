#!/usr/bin/env python
# Class designed for use with my video encoding scripts
# Assumes that input video is mkv and contains 1 primary video stream
# and/or 1 Dolby Vision Enhancement Layer video stream.
#
# Mainly to help handle HDR content, but also to provide extra parameters that
# are not compression related.
import json
import subprocess as sp
import sys


class videoInfo:
    inFile = ""

    # HDR Related variables
    HDR10 = False
    HDR10MasterDisplayData = None
    HDR10ContentLightLeveData = None
    X265HDR10MasterDisplayString = None
    X265HDR10CLLString = None
    DolbyVision = False
    DVTrack = 0
    HDR10Plus = False

    # Values that need to be passed to x265
    # (y4m doesn't carry this information I guess)
    ColorMatrix = None
    ColorTransfer = None
    ColorPrimaries = None
    ColorRange = None

    ffprobeInfo = dict()

    def __init__(self, in_file: str):
        self.inFile = in_file
        self.ffprobeInfo = dict(
            json.loads(
                sp.check_output(
                    (
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_format",
                        "-show_streams",
                        "-show_frames",
                        "-read_intervals",
                        "%+#20",
                        in_file,
                    ),
                    encoding="utf-8",
                )
            )
        )

        # Go through each video stream and check for HDR metadata.
        for stream in self.ffprobeInfo["streams"]:
            if stream["codec_type"] == "video":
                if not self.ColorMatrix:
                    self.ColorMatrix = stream["color_space"]
                if not self.ColorTransfer:
                    self.ColorTransfer = stream["color_transfer"]
                if not self.ColorPrimaries:
                    self.ColorPrimaries = stream["color_primaries"]

                if not self.ColorRange:
                    if stream["color_range"] == "tv":
                        self.ColorRange = "limited"
                    else:
                        self.ColorRange = "full"

                sideDataList = self.__getFrameSideDataList(stream)

                if not sideDataList:
                    continue

                self.HDR10Plus = self.__isHDR10Plus(sideDataList)

                self.DolbyVision = self.__isDolbyVision(sideDataList)
                # Sometimes DV metadata is located on a separate stream.
                if self.DolbyVision:
                    self.DVTrack = int(stream["index"])

                # I don't want to overwrite our HDR10 metadata.
                if self.HDR10:
                    continue

                self.HDR10MasterDisplayData = self.__getMasterDisplayData(sideDataList)
                self.X265HDR10MasterDisplayString = self.__getX265MasterDisplayString()
                self.HDR10ContentLightLeveData = self.__getContentLightLeveData(
                    sideDataList
                )
                self.X265HDR10CLLString = self.__getX265CLLString()
                if self.HDR10MasterDisplayData:
                    self.HDR10 = True

    def __getContentLightLeveData(self, sideDataList):
        for sideData in sideDataList:
            if (
                sideData["side_data_type"].lower()
                == "Content light level metadata".lower()
            ):
                return sideData

    def __getMasterDisplayData(self, sideDataList):
        for sideData in sideDataList:
            if (
                sideData["side_data_type"].lower()
                == "Mastering display metadata".lower()
            ):
                return sideData

    def __getMasterDisplayColorValue(self, colorFraction: str, targetDenominator: int):
        numerator = int(colorFraction.split("/")[0])
        denominator = int(colorFraction.split("/")[1])

        return (targetDenominator // denominator) * numerator

    def __getX265MasterDisplayString(self):
        if not self.HDR10MasterDisplayData:
            return None

        masterDisplayString = "G({},{})".format(
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["green_x"], 50000
            ),
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["green_y"], 50000
            ),
        )
        masterDisplayString += "B({},{})".format(
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["blue_x"], 50000
            ),
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["blue_y"], 50000
            ),
        )
        masterDisplayString += "R({},{})".format(
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["red_x"], 50000
            ),
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["red_y"], 50000
            ),
        )
        masterDisplayString += "WP({},{})".format(
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["white_point_x"], 50000
            ),
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["white_point_y"], 50000
            ),
        )
        masterDisplayString += "L({},{})".format(
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["min_luminance"], 10000
            ),
            self.__getMasterDisplayColorValue(
                self.HDR10MasterDisplayData["max_luminance"], 10000
            ),
        )

        return masterDisplayString

    def __getX265CLLString(self):
        if not self.HDR10ContentLightLeveData:
            return None

        CLLString = "{},{}".format(
            self.HDR10ContentLightLeveData["max_content"],
            self.HDR10ContentLightLeveData["max_average"],
        )
        return CLLString

    def __isDolbyVision(self, sideDataList):
        for sideData in sideDataList:
            if sideData["side_data_type"].lower() == "Dolby Vision Metadata".lower():
                return True
        return False

    def __isHDR10Plus(self, sideDataList):
        for sideData in sideDataList:
            if (
                sideData["side_data_type"].lower()
                == "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)".lower()
            ):
                return True
        return False

    def __getFrameSideDataList(self, stream):
        for frame in self.ffprobeInfo["frames"]:
            if frame["stream_index"] == stream["index"]:
                if "side_data_list" not in frame:
                    return None

                return frame["side_data_list"]


if __name__ == "__main__":
    testInfo = videoInfo(sys.argv[1])

    print(testInfo.HDR10)
    print(testInfo.DolbyVision)
    print(testInfo.DVTrack)
    print(testInfo.HDR10Plus)
    print(testInfo.ColorMatrix)
    print(testInfo.ColorPrimaries)
    print(testInfo.ColorTransfer)
    print(testInfo.ColorRange)