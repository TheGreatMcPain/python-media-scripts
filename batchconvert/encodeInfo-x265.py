import vapoursynth as vs
import havsfunc as haf
import sys
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


# Tries to mimic vspipe's --info option.
if __name__ == "__main__":
    # Supply video source as argument. For testing.
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
