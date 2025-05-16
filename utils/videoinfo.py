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
import shutil
import math


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

    DVMetadataFile = None
    HDR10PlusMetadataFile = None

    # Values that need to be passed to x265
    # (y4m doesn't carry this information I guess)
    ColorMatrix = None
    ColorTransfer = None
    ColorPrimaries = None
    ColorRange = None

    # Other Useful values
    Height = None
    Width = None
    FPS = None

    DoviTool = "dovi_tool"
    HDR10PlusTool = "hdr10plus_tool"

    ffprobeInfo = dict()

    def __init__(self, in_file: str):
        self.inFile = in_file
        self.DVMetadataFile = in_file + "_dv.rpu"
        self.HDR10PlusMetadataFile = in_file + "_hdrplus.json"
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
                if not self.ColorMatrix and "color_space" in stream:
                    self.ColorMatrix = stream["color_space"]
                if not self.ColorTransfer and "color_transfer" in stream:
                    self.ColorTransfer = stream["color_transfer"]
                if not self.ColorPrimaries and "color_primaries" in stream:
                    self.ColorPrimaries = stream["color_primaries"]

                if not self.ColorRange and "color_range" in stream:
                    if stream["color_range"] == "tv":
                        self.ColorRange = "limited"
                    else:
                        self.ColorRange = "full"

                if not self.Width and "width" in stream:
                    self.Width = stream["width"]
                if not self.Height and "height" in stream:
                    self.Height = stream["height"]
                if not self.FPS and "r_frame_rate" in stream:
                    self.FPS = math.ceil(eval(stream["r_frame_rate"]))
                if not self.FPS and "avg_frame_rate" in stream:
                    self.FPS = math.ceil(eval(stream["avg_frame_rate"]))

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

    def extractDoviHEVC(self, outFile: str):
        if not shutil.which(self.DoviTool):
            return 1

        # Convert RPU to profile 8.1 and drop Enhancement Layer.
        doviCmd = [
            "dovi_tool",
            "-m",
            "2",
            "convert",
            "--discard",
            "--output",
            outFile,
            "-",
        ]

        ffmpegProcess = sp.Popen(
            (
                "ffmpeg",
                "-loglevel",
                "fatal",
                "-stats",
                "-i",
                self.inFile,
                "-map",
                "0:0",
                "-c:v",
                "copy",
                "-bsf:v",
                "hevc_mp4toannexb",
                "-f",
                "hevc",
                "-",
            ),
            stdout=sp.PIPE,
        )
        DoviProcess = sp.Popen(doviCmd, stdin=ffmpegProcess.stdout)
        DoviProcess.communicate()
        return 0

    def extractHDR10PlusMetadata(self):
        if not shutil.which(self.HDR10PlusTool):
            return 1

        HDR10PlusCmd = [
            "hdr10plus_tool",
            "extract",
            "--output",
            self.HDR10PlusMetadataFile,
            "-",
        ]

        ffmpegProcess = sp.Popen(
            (
                "ffmpeg",
                "-loglevel",
                "fatal",
                "-stats",
                "-i",
                self.inFile,
                "-map",
                "0:0",
                "-c:v",
                "copy",
                "-f",
                "hevc",
                "-",
            ),
            stdout=sp.PIPE,
        )
        HDR10PlusProcess = sp.Popen(HDR10PlusCmd, stdin=ffmpegProcess.stdout)
        HDR10PlusProcess.communicate()
        return 0

    def extractDoviRPU(self):
        if not shutil.which(self.DoviTool):
            return 1

        doviCmd = [
            "dovi_tool",
            "--mode",
            "2",
            "extract-rpu",
            "--rpu-out",
            self.DVMetadataFile,
            "-",
        ]

        ffmpegProcess = sp.Popen(
            (
                "ffmpeg",
                "-loglevel",
                "fatal",
                "-stats",
                "-i",
                self.inFile,
                "-map",
                "0:" + str(self.DVTrack),
                "-c:v",
                "copy",
                "-f",
                "hevc",
                "-",
            ),
            stdout=sp.PIPE,
        )
        doviProcess = sp.Popen(doviCmd, stdin=ffmpegProcess.stdout)
        doviProcess.communicate()
        return 0

    def __getContentLightLeveData(self, sideDataList):
        for sideData in sideDataList:
            if (
                sideData["side_data_type"].lower()
                == "Content light level metadata".lower()
            ):
                if len(sideData) > 1:
                    return sideData

    def __getMasterDisplayData(self, sideDataList):
        for sideData in sideDataList:
            if (
                sideData["side_data_type"].lower()
                == "Mastering display metadata".lower()
            ):
                if len(sideData) > 1:
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
        # I guess some x265 encoded files don't include these values.
        # I'm guessing "L(10000000,1)" is the default.
        if (
            "min_luminance" in self.HDR10MasterDisplayData
            and "max_luminance" in self.HDR10MasterDisplayData
        ):
            masterDisplayString += "L({},{})".format(
                self.__getMasterDisplayColorValue(
                    self.HDR10MasterDisplayData["min_luminance"], 10000
                ),
                self.__getMasterDisplayColorValue(
                    self.HDR10MasterDisplayData["max_luminance"], 10000
                ),
            )
        else:
            masterDisplayString += "L(10000000,1)"

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
            if "stream_index" not in frame:
                continue
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
