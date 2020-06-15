#!/usr/bin/env python3
import math
import os
import sys
import xml.etree.cElementTree as ET
import subprocess as sp

# Globals
IMEXE = 'convert'


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage:", sys.argv[0], "<depths.xml> <outputdir> --rightfirst")
        exit(1)

    if len(args) == 3:
        if args[2] == '--rightfirst':
            leftfirst = -1
    leftfirst = 1
    print(leftfirst)

    convertXMLto3DSBS(os.path.expanduser(args[0]),
                      os.path.expanduser(args[1]) + '.xml', leftfirst)


def convertXMLto3DSBS(inXML, outXML, leftfirst):
    outdir = outXML.split('.')[0]
    os.mkdir(outdir)

    if not os.path.isdir(outdir):
        print("Failed to create directory.")
        exit(1)

    tree = ET.parse(inXML)
    inxml = tree.getroot()
    totalsubs = len(list(inxml.iter('Graphic')))
    numsubs = 0
    imexe = IMEXE
    framewidth = 1920
    frameheight = 1080
    indir = os.path.dirname(inXML)

    numwarnings = 0

    for graphic in inxml.iter('Graphic'):
        numsubs += 1

        width = int(graphic.attrib['Width'])
        height = int(graphic.attrib['Height'])
        x = int(graphic.attrib['X'])
        y = int(graphic.attrib['Y'])

        if graphic.attrib['Depth']:
            origDepth = int(graphic.attrib['Depth'])
        else:
            origDepth = 0

        # Workaround for malformed subtitles as found on Amphibious 3D
        if width == framewidth and x < 0:
            x = 0
        if height == frameheight and y < 0:
            y = 0

        pngfn = graphic.text

        depth = origDepth * leftfirst

        if (width < framewidth) and (width + (abs(depth / 2)) > framewidth):
            newdepth = (framewidth - width) * 2
            if depth < 0:
                newdepth = newdepth * -1
            print("Warning: Subtitle " + numsubs + ": The depth (" + depth +
                  ") ",
                  end='')
            print("is too great for the width of the subtitle (" + width +
                  "). ",
                  end='')
            print("Depth reduced to " + newdepth)
            depth = newdepth
            numwarnings += 1

        newwidth = width + framewidth - depth
        newheight = height
        gravity1 = 'West'
        gravity2 = 'East'
        resize = '50%%x100%%!'
        finalwidth = (newwidth + 1) // 2
        finalheight = height
        newx = math.ceil((x + (depth / 2)) / 2)
        newy = y

        outpng = "sub_{0:04d}.png".format(numsubs)

        if newx < 0:
            print(newx)
            cropx = newx * -1
            finalwidth += newx
            newx = 0
            if finalwidth > framewidth:
                finalwidth = framewidth

            cmd = [
                imexe, '(', '(', '(', '-size',
                str(newwidth) + 'x' + str(newheight), 'xc:none',
                os.path.join(indir,
                             pngfn), '-gravity', gravity1, '-composite', ')',
                os.path.join(indir, pngfn), '-gravity', gravity2, '-composite',
                ')', '-filter', 'Mitchell', '-resize', resize, ')', '-crop',
                str(finalwidth) + 'x' + str(finalheight) + '+' + str(cropx) +
                '+0',
                os.path.join(outdir, outpng)
            ]
        else:
            cmd = [
                imexe, '(', '(', '-size',
                str(newwidth) + 'x' + str(newheight), 'xc:none',
                os.path.join(indir,
                             pngfn), '-gravity', gravity1, '-composite', ')',
                os.path.join(indir, pngfn), '-gravity', gravity2, '-composite',
                ')', '-filter', 'Mitchell', '-resize', resize,
                os.path.join(outdir, outpng)
            ]

        p = sp.Popen(cmd)
        p.communicate()

        graphic.attrib['Width'] = str(finalwidth)
        graphic.attrib['Height'] = str(finalheight)
        graphic.attrib['X'] = str(newx)
        graphic.attrib['Y'] = str(newy)
        graphic.attrib.pop('Depth')
        graphic.attrib['OrigDepth'] = str(origDepth)
        graphic.text = outpng
        status = str(numsubs) + " Subs out of " + str(totalsubs) + " Subs"
        print(f'{status}\r', end='')
        print("\033[K", end='')
    print("Finished processing", numsubs, "subtitles.")
    print(numwarnings)

    tree.write(os.path.join(outdir, outXML),
               xml_declaration=True,
               encoding="utf8",
               method="xml")


if __name__ == "__main__":
    main()
