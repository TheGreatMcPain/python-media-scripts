#!/usr/bin/env python3
import sys
import xml.etree.cElementTree as ET


def tc2sec(timecode: str, framerate: float) -> float:
    # Timecode format %02d:%02d:%02d:%02d hour:minutes:seconds:frame
    hours = float(timecode.split(":")[0])
    minutes = float(timecode.split(":")[1])
    seconds = float(timecode.split(":")[2])
    frame = float(timecode.split(":")[3])

    hours2seconds = hours * 3600  # 60 minutes times 60
    minutes2seconds = minutes * 60
    frame2seconds = frame / framerate

    return hours2seconds + minutes2seconds + seconds + frame2seconds


def getBnxmlFps(BDNXMLroot: ET.Element) -> float:
    return float(next(BDNXMLroot.iter("Format")).attrib["FrameRate"])


def isOverlap(event1: ET.Element, event2: ET.Element, fps1: float, fps2: float) -> bool:
    in1 = tc2sec(event1.attrib["InTC"], fps1)
    out1 = tc2sec(event1.attrib["OutTC"], fps1)
    in2 = tc2sec(event2.attrib["InTC"], fps2)
    out2 = tc2sec(event2.attrib["OutTC"], fps2)

    latestStart = max(in1, in2)
    earliestEnd = min(out1, out2)

    delta = earliestEnd - latestStart

    if delta > 0:
        return True
    return False


if __name__ == "__main__":
    BDNXML = sys.argv[1]
    BDNXML2 = sys.argv[2]

    tree1 = ET.parse(BDNXML)
    root1 = tree1.getroot()
    tree2 = ET.parse(BDNXML2)
    root2 = tree2.getroot()

    fps1 = getBnxmlFps(root1)
    fps2 = getBnxmlFps(root2)

    overlaps = 0
    for event in root1.iter("Event"):
        for event2 in root2.iter("Event"):
            if isOverlap(event, event2, fps1, fps2):
                event.set("Forced", "True")
                overlaps += 1

    # Write BDNXML with forced enabled for comparison
    tree1.write(BDNXML.split(".xml")[0] + "-forced.xml")

    for event in root1.iter("Event"):
        if event.attrib["Forced"] in "False":
            event.set("Forced", "True")
        else:
            event.set("Forced", "False")
    tree1.write(BDNXML.split(".xml")[0] + "-nonforced.xml")

    print("Number of overlaps:", overlaps)
