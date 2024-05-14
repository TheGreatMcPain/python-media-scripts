import vapoursynth as vs
import havsfunc as haf


def vapoursynthFilter(inputFile: str):
    video = vs.core.ffms2.Source(source=inputFile)
    # video = core.std.CropRel(video, top=140, bottom=140)
    # video = haf.GSMC(video, thSAD=150, radius=2)
    # video = core.f3kdb.Deband(video, dynamic_grain=True, preset="Low")
    # video = core.std.AddBorders(video, top=140, bottom=140)
    return video
