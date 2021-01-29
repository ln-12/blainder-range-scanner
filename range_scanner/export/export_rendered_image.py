import random
import bpy
import numpy as np
import os

def export(filePath, fileName):
    print("Saving scene as image...")

    # render image with Blenders internal rendering engine
    scene = bpy.context.scene

    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.join(filePath, "%s_image_rendered.png" % fileName)
    bpy.ops.render.render(write_still=True)

    # BE CAREFUL: image rendering resets all key point controled values to their current state!
    # so this means the scene might change after rendering as Blender restores all attributes... :(

    print("Done.")