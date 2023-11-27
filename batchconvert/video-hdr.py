#!/usr/bin/env python
# This script will grab HDR metadata from UHD bluray
# and re-encode it using x265. HDR+ and Dolby Vision included.
import subprocess as sp
import json
import shutil
import argparse
import vapoursynth as vs

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
        "--input", dest="input_file", type=str, help="Input video file (mkv)"
    )
    parser.add_argument(
        "--output", dest="output_file", type=str, help="Output HEVC file (hevc)"
    )
    parser.add_argument(
        "--dolby-vision",
        dest="dolby_vision",
        action=argparse.BooleanOptionalAction,
        help="Process Dolby Vision metadata",
    )
    parser.set_defaults(dolby_vision=False)
    parser.add_argument(
        "--dv-separate-layer",
        dest="dv_separate_layer",
        action=argparse.BooleanOptionalAction,
        help="Dolby Vision is on separate track",
    )
    parser.set_defaults(dv_separate_layer=False)
    parser.add_argument(
        "--hdr-plus",
        dest="hdr_plus",
        action=argparse.BooleanOptionalAction,
        help="Process HDR+ metadata",
    )
    parser.set_defaults(hdr_plus=False)
    parser.add_argument(
        "--bt709",
        dest="bt709",
        action=argparse.BooleanOptionalAction,
        help="Use bt709 instead of bt2020",
    )
    parser.set_defaults(bt709=False)

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
        args.dolby_vision,
        args.dv_separate_layer,
        args.hdr_plus,
        args.bt709,
    )


# Returns the subprocess which ffmpeg sends
# raw video track over stdout.
# (will only show ffmpeg progress stats)
def ffmpeg_video_stdout(
    in_file: str, track: int, stats: bool, decode: bool
) -> sp.Popen:
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

    return sp.Popen(ffmpeg_cmd, stdout=sp.PIPE)


def extract_hdr10plus_metadata(in_file: str, metadata_json: str):
    if not shutil.which("hdr10plus_tool"):
        return None

    hdr10plus_cmd = ["hdr10plus_tool", "extract", "--output", metadata_json, "-i", "-"]

    ffmpeg_process = ffmpeg_video_stdout(in_file, 0, True, False)
    hdr10plus_process = sp.Popen(hdr10plus_cmd, stdin=ffmpeg_process.stdout)

    hdr10plus_process.communicate()


# Check and extract Dolby Vision RPU from hevc file.
def extract_dovi_rpu(in_file: str, rpu_file: str, separate_track: bool):
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

    video_track = 0
    if separate_track:
        video_track = 1

    ffmpeg_process = ffmpeg_video_stdout(in_file, video_track, True, False)
    dovi_process = sp.Popen(dovi_cmd, stdin=ffmpeg_process.stdout)

    dovi_process.communicate()


# Grab HDR metadata from input file using ffprobe.
def get_hdr_info_ffprobe(in_file):
    """ffprobe font-end."""
    return dict(
        json.loads(
            sp.check_output(
                (
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-select_streams",
                    "v",
                    "-show_frames",
                    "-read_intervals",
                    "%+#1",
                    "-show_entries",
                    "frame=color_space,color_primaries,color_transfer,side_data_list,pix_fmt",
                    in_file,
                ),
                encoding="utf-8",
            )
        )
    )


def get_master_display_color_value(color_fraction: str, target_denominator: int):
    numerator = int(color_fraction.split("/")[0])
    denominator = int(color_fraction.split("/")[1])

    return (target_denominator // denominator) * numerator


def get_x265_master_display_string(in_file: str):
    hdr_info = get_hdr_info_ffprobe(in_file)

    master_display = None
    content_light_level = None

    for side_data in hdr_info["frames"][0]["side_data_list"]:
        if side_data["side_data_type"].lower() == "Mastering display metadata".lower():
            master_display = side_data

        if (
            side_data["side_data_type"].lower()
            == "Content light level metadata".lower()
        ):
            content_light_level = side_data

    if not master_display:
        return None

    if not content_light_level:
        return None

    master_display_string = "G({},{})".format(
        get_master_display_color_value(master_display["green_x"], 50000),
        get_master_display_color_value(master_display["green_y"], 50000),
    )
    master_display_string += "B({},{})".format(
        get_master_display_color_value(master_display["blue_x"], 50000),
        get_master_display_color_value(master_display["blue_y"], 50000),
    )
    master_display_string += "R({},{})".format(
        get_master_display_color_value(master_display["red_x"], 50000),
        get_master_display_color_value(master_display["red_y"], 50000),
    )
    master_display_string += "WP({},{})".format(
        get_master_display_color_value(master_display["white_point_x"], 50000),
        get_master_display_color_value(master_display["white_point_y"], 50000),
    )
    master_display_string += "L({},{})".format(
        get_master_display_color_value(master_display["max_luminance"], 10000),
        get_master_display_color_value(master_display["min_luminance"], 10000),
    )

    content_light_level_string = "{},{}".format(
        content_light_level["max_content"], content_light_level["max_average"]
    )

    results = {}
    results["master_display"] = master_display_string
    results["content_light_level"] = content_light_level_string

    return results


def get_vs_filter(input_file: str):
    video = core.ffms2.Source(source=input_file)
    return video


def encode_video_x265(
    input_file: str,
    output_file: str,
    dolby_vision: bool,
    dv_separate_layer: bool,
    hdrplus: bool,
    bt709: bool,
):
    master_display_info = get_x265_master_display_string(input_file)

    if not master_display_info:
        return

    hdrplus_metadata = input_file + "_hdrplus.json"
    dolby_vision_rpu = input_file + "_dv.rpu"

    if hdrplus:
        print("Extracting HDR10+ metadata")
        extract_hdr10plus_metadata(input_file, hdrplus_metadata)
    if dolby_vision:
        print("Extracting Dolby Vision metadata")
        extract_dovi_rpu(input_file, dolby_vision_rpu, dv_separate_layer)

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
        "--master-display",
        master_display_info["master_display"],
        "--max-cll",
        master_display_info["content_light_level"],
    ]

    bt2020_x265_opts = [
        "--colorprim",
        "bt2020",
        "--transfer",
        "smpte2084",
        "--colormatrix",
        "bt2020nc",
        "--range",
        "limited",
    ]

    bt709_x265_opts = [
        "--colorprim",
        "bt709",
        "--transfer",
        "bt709",
        "--colormatrix",
        "bt709",
        "--range",
        "limited",
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

    cmd += tenbit_x265_opts + hdr_x265_opts

    if bt709:
        cmd += bt709_x265_opts
    else:
        cmd += bt2020_x265_opts
    if hdrplus:
        cmd += hdrplus_x265_opts
    if dolby_vision:
        cmd += dv_x265_opts

    video = get_vs_filter(input_file)
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
