import vapoursynth as vs
import havsfunc as haf
import sys
import os
import psutil
import threading
import subprocess as sp

core = vs.core
"""
This will be imported by 'batchencode.py'.

By making it a seperate file customization can be done easily
without cluttering up the main script.

"batchencode will call 'vapoursynthFilter' just to be clear."
"""

VIDEO_ENCODE_NAME = 'video.h265'
# Change this to get VapourSynth's buffer size. (in MB)
VSCORE_MEM_CACHE_MAX = 1024


class encodeInfo:
    def __init__(self, sourcefile):
        self.sourcefile = sourcefile

    def vapoursynthFilter(self):
        if VSCORE_MEM_CACHE_MAX is not None:
            core.max_cache_size = VSCORE_MEM_CACHE_MAX
        video = core.ffms2.Source(source=self.sourcefile)
        video = core.std.CropRel(video, top=140, bottom=140)
        video = haf.GSMC(video, thSAD=150, radius=2)
        video = core.f3kdb.Deband(video, dynamic_grain=True, preset='Low')
        video = core.std.AddBorders(video, top=140, bottom=140)
        return video

    def getVSCore(self):
        return core

    def getEncodeCmd(self):
        video = self.vapoursynthFilter()
        framecount = video.num_frames
        cmd = [
            'x265', '--y4m', '--preset', 'medium', '--crf', '16', '--qcomp',
            '0.75', '--output-depth', '10', '--range', 'limited',
            '--colorprim', 'bt709', '--transfer', 'bt709', '--frames',
            str(framecount), '--input', '-', '--output', VIDEO_ENCODE_NAME
        ]
        return cmd

    def getEncodeFile(self):
        return VIDEO_ENCODE_NAME


# A single under-score basically marks this function as private 'module-level'
# meaning this function won't be imported via "from <module> import *"
def _encodeVideo(info: encodeInfo):
    video = info.vapoursynthFilter()
    cmd = info.getEncodeCmd()

    p = sp.Popen(cmd, stdin=sp.PIPE, shell=False)
    video.output(p.stdin, y4m=True)


# A encode test program
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:", sys.argv[0], " <in-file> <encode>")
        print()
        print("    <in-file> Is the video file")
        print("    <encode> can be nothing or a \"y\"")
        exit(1)

    # Tries to mimic vspipe's --info option.
    info = encodeInfo(sys.argv[1])
    video = info.vapoursynthFilter()
    print('Width:', video.width)
    print('Height:', video.height)
    print('FPS:', video.fps)
    print('Format Name:', video.format.name)
    print('Color Family:', str(video.format.color_family).split('.')[-1])
    print('Sample Type:', str(video.format.sample_type).split('.')[-1])
    print('Bits:', video.format.bits_per_sample)
    print('SubSampling W:', video.format.subsampling_w)
    print('SubSampling H:', video.format.subsampling_h)

    if len(sys.argv) == 3:
        if sys.argv[2].lower() == "y":
            # run encode program.
            ps = psutil.Process(os.getpid())
            ps.nice(15)

            t = threading.Thread(target=_encodeVideo, args=[info])

            try:
                t.start()
            except KeyboardInterrupt:
                pass
        else:
            print(sys.argv[2], "is an invalid option.")
