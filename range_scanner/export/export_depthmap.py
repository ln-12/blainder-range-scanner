import random
import bpy
import numpy as np
import os
import png

def export(filePath, fileName, data, depthMinDistance, depthMaxDistance, width, height):
    print("Saving scene as depthmap...")

    bitdepth = 16
    scalingFactor = 2**bitdepth

    # is is possible to render a depthmap with Blenders compositing functions
    # see: https://blender.stackexchange.com/a/101600/95167
    # with that, we have no information about reflections etc. so we generate it from 
    # our own data

    pixels = np.full(width * height, 0) 

    for hit in data:
        distance = hit.distance

        # map the values the same way, the Kinect does it
        # 0 means outside range
        if distance < depthMinDistance:
            intensity = 0
        elif distance > depthMaxDistance:
            intensity = 0
        else:
            # else, map the values to the given interval
            intensity = distance / depthMaxDistance

        pixels[(hit.y * width) + hit.x] = intensity * scalingFactor # scale to 16 bit

    f = open(os.path.join(filePath, "%s_image_depthmap.png" % fileName), 'wb') 
    w = png.Writer(width, height, greyscale=True, bitdepth=bitdepth)
    out = pixels.reshape((height, width))
    w.write(f, out)
    f.close()   

    print("Done.")