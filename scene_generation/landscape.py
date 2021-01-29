#!/usr/bin/env python3

import bpy
from random import seed, randint, random, uniform
import numpy as np
from pathlib import Path
import os

# seed random number generator
seed()

# definde the size of the landscape
landscapeSize = 25

# define the number of objects in the scene
numberOfTrees = randint(1, landscapeSize)
numberOfRocks = randint(1, landscapeSize * 2)
numberOfGrass = landscapeSize * 500


############################################################# 
#                                                           #
#                          LANDSCAPE                        #
#                                                           #
#############################################################

# add landscape
bpy.ops.mesh.landscape_add(refresh=True)

lscp = bpy.context.object.ant_landscape

# randomize landscape
newSeed = randint(0, 99999)
lscp.random_seed = newSeed

# scale landscape
sizeFactor = 2
lscp.mesh_size_x = sizeFactor
lscp.mesh_size_y = sizeFactor

# set number of squares in each direction
lscp.subdivision_x = 128
lscp.subdivision_y = 128

bpy.context.object.ant_landscape.height = 0.2
bpy.context.object.ant_landscape.falloff_x = 10
bpy.context.object.ant_landscape.falloff_y = 10

# triangulate faces
bpy.context.object.ant_landscape.tri_face = True

# make things smooth
lscp.smooth_mesh = True

obj = bpy.context.object

# resize landscape object
scale = landscapeSize / sizeFactor

obj.scale[0] = scale
obj.scale[1] = scale
obj.scale[2] = scale# / (randint(10, 50) / 10.0)

# update landscape
bpy.ops.mesh.ant_landscape_regenerate()

landscapeObject = bpy.context.object

# convert local vertex coordinates to world coordinates
# https://blender.stackexchange.com/a/1313/95167
coords = [(landscapeObject.matrix_world @ v.co) for v in landscapeObject.data.vertices]

# set green color as grass
mat = bpy.data.materials.new(name="MaterialName4")     
mat.diffuse_color = (0, 0.0699782, 0.000608268, 1)
landscapeObject.data.materials.append(mat)






############################################################# 
#                                                           #
#                            GRASS                          #
#                                                           #
############################################################# 

bpy.ops.object.particle_system_add()
settings = landscapeObject.particle_systems[0].settings
settings.type = 'HAIR'
settings.hair_length = 0.5
settings.hair_step = 5
settings.count = numberOfGrass
settings.use_rotations = True
settings.rotation_mode = 'GLOB_Z'
settings.rotation_factor_random = 0.1
settings.phase_factor_random = 2.0
# settings.render_type = 'OBJECT'
settings.render_type = 'COLLECTION'
settings.size_random = 0.5
settings.use_rotation_instance = True
settings.use_scale_instance = True
settings.particle_size = 1
# settings.instance_object = bpy.data.objects["grass"]
settings.instance_collection = bpy.data.collections["grass_blueprints"]
bpy.ops.object.duplicates_make_real()






############################################################# 
#                                                           #
#                            TREES                          #
#                                                           #
#############################################################

# add one tree
# the add-on has to be fixed: https://blender.stackexchange.com/a/79657
#                             https://developer.blender.org/T77949
# just remove the comment around the bend property and change line 705 to "bend: FloatProperty" in:
# C:\Program Files\Blender Foundation\Blender 2.83\2.83\scripts\addons\add_curve_sapling\__init__.py
bpy.ops.curve.tree_add(do_update=True, chooseSet='5', bevel=True, prune=False, showLeaves=True, useArm=False, seed=0, handleType='0', levels=2, 
    length=(0.8, 0.6, 0.5, 0.1), lengthV=(0, 0.1, 0, 0), taperCrown=0.5, branches=(0, 55, 10, 1), curveRes=(8, 5, 3, 1), curve=(0, -15, 0, 0), 
    curveV=(20, 50, 75, 0), curveBack=(0, 0, 0, 0), baseSplits=3, segSplits=(0.1, 0.5, 0.2, 0), splitByLen=True, rMode='rotate', 
    splitAngle=(18, 18, 22, 0), splitAngleV=(5, 5, 5, 0), scale=5, scaleV=2, attractUp=(3.5, -1.89984, 0, 0), attractOut=(0, 0.8, 0, 0), shape='7', 
    shapeS='10', customShape=(0.5, 1, 0.3, 0.5), branchDist=1.5, nrings=0, baseSize=0.3, baseSize_s=0.16, splitHeight=0.2, splitBias=0.55, ratio=0.015, 
    minRadius=0.0015, closeTip=False, rootFlare=1, autoTaper=True, taper=(1, 1, 1, 1), radiusTweak=(1, 1, 1, 1), ratioPower=1.2, 
    downAngle=(0, 26.21, 52.56, 30), downAngleV=(0, 10, 10, 10), useOldDownAngle=True, useParentAngle=True, rotate=(99.5, 137.5, 137.5, 137.5), 
    rotateV=(15, 0, 0, 0), scale0=1, scaleV0=0.1, pruneWidth=0.34, pruneBase=0.12, pruneWidthPeak=0.5, prunePowerHigh=0.5, prunePowerLow=0.001, 
    pruneRatio=0.75, leaves=100, leafDownAngle=30, leafDownAngleV=-10, leafRotate=137.5, leafRotateV=15, leafScale=0.4, leafScaleX=0.2, leafScaleT=0.1, 
    leafScaleV=0.15, leafShape='hex', leafangle=-12, horzLeaves=True, leafDist='6', bevelRes=1, resU=4, armAnim=False, previewArm=False, leafAnim=False, 
    frameRate=1, loopFrames=0, wind=1, gust=1, gustF=0.075, af1=1, af2=1, af3=4, makeMesh=False, armLevels=2, boneStep=(1, 1, 1, 1))

# seed once again as tree_add overrides it with the same number every time
seed()

# select tree
# https://blender.stackexchange.com/a/132829/95167
tree = bpy.context.scene.objects["tree"]
bpy.ops.object.select_all(action='DESELECT') 
bpy.context.view_layer.objects.active = tree   
tree.select_set(True)                          

# convert tree curves to meshes
bpy.ops.object.convert(target='MESH')

# set some color for bark and leaves
mat = bpy.data.materials.new(name="MaterialName")
mat.diffuse_color = (0.0173877, 0.00428225, 0, 1)
tree.data.materials.append(mat)

leaves = tree.children[0]
mat = bpy.data.materials.new(name="MaterialName2")
mat.diffuse_color = (0, 0.0173367, 0.00106319, 1)
leaves.data.materials.append(mat) 

# move tree to the center
tree.location = coords[randint(0, len(coords) - 1)]

# scale tree with factor in [0.8, 1.2]
scale = (randint(8, 12) / 10.0)
tree.scale = (scale, scale, scale)

# spawn some more trees
# use copies to speed things up: https://stackoverflow.com/a/48819995/13440564
for _ in range(numberOfTrees):
    index = randint(0, len(coords))
            
    m = tree.data.copy()
    o = bpy.data.objects.new("cube", m)
    o.location = coords[index]
    scale = (randint(5, 15) / 10.0)
    o.scale = (scale, scale, scale)
    rotX = uniform(0, 0.1)
    rotY = uniform(0, 0.1)
    rotZ = uniform(0, 3.141)
    o.rotation_euler[0] = rotX
    o.rotation_euler[1] = rotY
    o.rotation_euler[2] = rotZ
    bpy.context.scene.collection.objects.link(o)
    

    m = leaves.data.copy()
    o = bpy.data.objects.new("cube", m)
    o.location = coords[index]
    o.scale = (scale, scale, scale)
    o.rotation_euler[0] = rotX
    o.rotation_euler[1] = rotY
    o.rotation_euler[2] = rotZ
    bpy.context.scene.collection.objects.link(o)

mat = bpy.data.materials.new(name="MaterialName3")
mat.diffuse_color = (0.110689, 0.110689, 0.110689, 1)









############################################################# 
#                                                           #
#                            ROCKS                          #
#                                                           #
############################################################# 

# randomly decide if we want to have rocks in the scene
if randint(0,1) == 0:
    for _ in range(numberOfRocks):
        index = randint(0, len(coords))

        bpy.ops.mesh.add_mesh_rock()
        
        rock = bpy.context.object
        
        rock.data.materials.append(mat) #add the material to the object
        
        scale = randint(1, 5) / 10.0
        rock.scale = (scale, scale, scale)
        
        rockCoords = [(rock.matrix_world @ v.co) for v in rock.data.vertices]
        
        minZ = np.inf
        
        for coord in rockCoords:
            if coord[2] < minZ:
                minZ = coord[2]
        
        rock.location = (coords[index][0], coords[index][1], coords[index][2] - (minZ * scale * random()))










############################################################# 
#                                                           #
#                           EXPORT                          #
#                                                           #
############################################################# 

# save file
path = bpy.path.abspath("//generated")
Path(path).mkdir(parents=True, exist_ok=True)
path = os.path.join(path, "generated_landscape_%d_%d.blend" % (newSeed, numberOfTrees))
print("Saving file to %s..." % path)
bpy.ops.wm.save_as_mainfile(filepath=path)
