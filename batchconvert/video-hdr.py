#!/usr/bin/env python
# This script will grab HDR metadata from UHD bluray
# and re-encode it using x265. HDR+ and Dolby Vision included.
import subprocess as sp
import shutil
import argparse
from pathlib import Path
import vapoursynth as vs
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils import videoinfo

core = vs.core

# Process priority
# import os
# import psutil
# ps = psutil.Process(os.getpid())
# ps.nice(19)
# ps.ionice(psutil.IOPRIO_CLASS_IDLE)


def main():
    parser = argparse.ArgumentParser(
        description="Simple x265 script with Dolby Vision and HDR+"
    )
    parser.add_argument(
        "-i", "--input", dest="input_file", type=str, help="Input video file (mkv)"
    )
    parser.add_argument(
        "-o", "--output", dest="output_file", type=str, help="Output HEVC file (hevc)"
    )
    parser.add_argument(
        "--skip-encode",
        dest="skip_encode",
        action=argparse.BooleanOptionalAction,
        help="Create Dolby Vision profile 8 video without re-encode",
    )
    parser.set_defaults(skip_encode=False)

    args = parser.parse_args()

    if not args.input_file:
        parser.print_usage()
        exit(1)
    if not args.output_file:
        parser.print_usage()
        exit(1)

    encode_video_x265(
        args.input_file,
        args.output_file,
        args.skip_encode,
    )


# Returns the a ffmpeg cmd that sends raw video over stdout.
# for use with sp.Popen
def ffmpeg_video_cmd(in_file: str, track: int, stats: bool, decode: bool) -> list:
    ffmpeg_cmd = ["ffmpeg", "-loglevel", "fatal"]
    # ffmpeg_cmd = ["ffmpeg"]

    # Used for streaming the raw hevc data
    copy_hdr = ["-c:v", "copy", "-vbsf", "hevc_mp4toannexb", "-f", "hevc"]

    # Used for passing to x265
    decode_stream = ["-f", "yuv4mpegpipe", "-strict", "-1"]

    if stats:
        ffmpeg_cmd += ["-stats"]

    ffmpeg_cmd += [
        "-i",
        in_file,
        "-map",
        "0:" + str(track),
    ]

    if decode:
        ffmpeg_cmd += decode_stream
    else:
        ffmpeg_cmd += copy_hdr

    ffmpeg_cmd += [
        "-",
    ]

    return ffmpeg_cmd


def extract_hdr10plus_metadata(in_file: str, metadata_json: str):
    if not shutil.which("hdr10plus_tool"):
        return None

    hdr10plus_cmd = ["hdr10plus_tool", "extract", "--output", metadata_json, "-i", "-"]

    ffmpeg_process = sp.Popen(ffmpeg_video_cmd(in_file, 0, True, False), stdout=sp.PIPE)
    hdr10plus_process = sp.Popen(hdr10plus_cmd, stdin=ffmpeg_process.stdout)

    hdr10plus_process.communicate()


# Check and extract Dolby Vision RPU from hevc file.
def extract_dovi_rpu(in_file: str, rpu_file: str, dv_track: int):
    # Check if dovi_tool exists in path.
    if not shutil.which("dovi_tool"):
        return None

    dovi_cmd = [
        "dovi_tool",
        "--mode",
        "2",
        "extract-rpu",
        "--rpu-out",
        rpu_file,
        "-",
    ]

    ffmpeg_process = sp.Popen(
        ffmpeg_video_cmd(in_file, dv_track, True, False), stdout=sp.PIPE
    )
    dovi_process = sp.Popen(dovi_cmd, stdin=ffmpeg_process.stdout)

    dovi_process.communicate()


def extract_video(input_file: str, output_file: str):
    ffmpeg_cmd = ffmpeg_video_cmd(input_file, 0, True, False)

    with open(output_file, "wb") as out:
        ffmpeg_process = sp.Popen(ffmpeg_cmd, stdout=out)
        ffmpeg_process.communicate()


def inject_dv_metadata(input_file: str, RPU: str, output_file: str):
    dovi_cmd = [
        "dovi_tool",
        "inject-rpu",
        "--input",
        input_file,
        "--output",
        output_file,
        "--rpu-in",
        RPU,
    ]

    dovi_process = sp.Popen(dovi_cmd)
    dovi_process.communicate()


def get_vs_filter(input_file: str):
    video = core.ffms2.Source(source=input_file)
    return video


def encode_video_x265(
    input_file: str,
    output_file: str,
    skip_encode: bool,
):
    inputInfo = videoinfo.videoInfo(input_file)

    hdrplus_metadata = input_file + "_hdrplus.json"
    dolby_vision_rpu = input_file + "_dv.rpu"

    if inputInfo.HDR10Plus:
        print("HDR10+ detected!!")
        print("Extracting it with 'hdr10plus_tool'.")
        extract_hdr10plus_metadata(input_file, hdrplus_metadata)
    if inputInfo.DolbyVision:
        print("Dolby Vision detected!!")
        print("Extracting RPU with 'dovi_tool'. (converts to Dolby Vision Profile 8.1)")
        extract_dovi_rpu(input_file, dolby_vision_rpu, inputInfo.DVTrack)

    if skip_encode:
        print("'--skip-encode' enabled!!")
        print("Skipping x265 re-encode")
        print()
        print("Extracting raw video track")
        temp_video = Path(output_file)

        if inputInfo.DolbyVision:
            temp_video = Path(input_file).with_suffix(".temp.hevc")

        extract_video(input_file, temp_video.name)

        if inputInfo.DolbyVision:
            print("Injecting Dolby Vision Profile 8 metadata")
            inject_dv_metadata(temp_video.name, dolby_vision_rpu, output_file)
            print("Deleting", temp_video.name)
            temp_video.unlink()

        print("Done!!")
        return

    dv_x265_opts = [
        "--dolby-vision-rpu",
        dolby_vision_rpu,
        "--dolby-vision-profile",
        "8.1",
        "--vbv-bufsize",
        "50000",
        "--vbv-maxrate",
        "50000",
    ]

    hdrplus_x265_opts = ["--dhdr10-info=" + hdrplus_metadata]

    tenbit_x265_opts = [
        "--input-depth",
        "10",
        "--output-depth",
        "10",
    ]

    hdr_x265_opts = [
        "--hdr10-opt",
    ]

    if inputInfo.HDR10MasterDisplayData:
        if inputInfo.HDR10MasterDisplayData:
            hdr_x265_opts += ["--master-display", inputInfo.X265HDR10MasterDisplayString]

        if inputInfo.HDR10ContentLightLeveData:
            hdr_x265_opts += ["--max-cll", inputInfo.X265HDR10CLLString]

    color_x265_opts = [
        "--colorprim",
        inputInfo.ColorPrimaries,
        "--transfer",
        inputInfo.ColorTransfer,
        "--colormatrix",
        inputInfo.ColorMatrix,
        "--range",
        inputInfo.ColorRange,
    ]

    cmd = [
        "x265",
        "--y4m",
        "--input",
        "-",
        "--output",
        output_file,
        "--preset",
        "medium",
        "--crf",
        "20",
        "--tune",
        "grain",
        "--qcomp",
        "0.75",
    ]

    cmd += tenbit_x265_opts + hdr_x265_opts + color_x265_opts

    if inputInfo.HDR10Plus:
        cmd += hdrplus_x265_opts
    if inputInfo.DolbyVision:
        cmd += dv_x265_opts

    video = get_vs_filter(inputInfo.inFile)
    cmd += ["--frames", str(video.num_frames)]

    print("==START x265 CMD==")
    print(" ".join(cmd))
    print("==END x265 CMD==")

    # ffmpeg_process = ffmpeg_video_stdout(input_file, False, True)
    x265_process = sp.Popen(cmd, stdin=sp.PIPE)
    video.output(x265_process.stdin, y4m=True)
    # x265_process = sp.Popen(cmd, stdin=ffmpeg_process.stdout)

    x265_process.communicate()


if __name__ == "__main__":
    main()
