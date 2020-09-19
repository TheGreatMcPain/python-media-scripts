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


def vapoursynthFilter(sourcefile):
    video = core.ffms2.Source(source=sourcefile)
    video = core.std.CropRel(video, top=140, bottom=140)
    video = haf.GSMC(video, thSAD=150, radius=2)
    video = core.f3kdb.Deband(video, dynamic_grain=True, preset='Low')
    video = core.std.AddBorders(video, top=140, bottom=140)

    return video


# Just so that we don't need to import vapoursynth
# with in the main script.
def getVSCore():
    return core


# Tries to mimic vspipe's --info option.
if __name__ == "__main__":
    # Supply video source as argument. For testing.
    video = vapoursynthFilter(sys.argv[1])
    print('Width:', video.width)
    print('Height:', video.height)
    print('FPS:', video.fps)
    print('Format Name:', video.format.name)
    print('Color Family:', str(video.format.color_family).split('.')[-1])
    print('Sample Type:', str(video.format.sample_type).split('.')[-1])
    print('Bits:', video.format.bits_per_sample)
    print('SubSampling W:', video.format.subsampling_w)
    print('SubSampling H:', video.format.subsampling_h)
