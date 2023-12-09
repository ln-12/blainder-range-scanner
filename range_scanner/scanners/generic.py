import bpy
import sys
import bmesh
from mathutils.bvhtree import BVHTree
import numpy as np
from . import hit_info
import os
import time

from enum import Enum
ScannerType = Enum('ScannerType', 'static rotating sideScan')

from . import lidar
from . import sonar
from ..export import exporter
from .. import material_helper
from ..scanners import generic

# source: https://blender.stackexchange.com/a/30739/95167
def updateProgress(job_title, progress):
    length = 20 # modify this to change the length
    block = int(round(length*progress))
    msg = "\r{0}: [{1}] {2}%".format(job_title, "#"*block + "-"*(length-block), round(progress*100, 2))
    if progress >= 1: msg += " DONE\r\n"
    sys.stdout.write(msg)
    sys.stdout.flush()

def addLine(v1, v2):
    mesh = bpy.data.meshes.new(name='mesh object')

    bm = bmesh.new()
    v1 = bm.verts.new(v1)  # add a new vert
    v2 = bm.verts.new(v2)  # add a new vert
    
    bm.edges.new((v1, v2))

    # make the bmesh the object's mesh
    bm.to_mesh(mesh)  
    bm.free()  # always do this when finished
        
    # We're done setting up the mesh values, update mesh object and 
    # let Blender do some checks on it
    mesh.update()
    mesh.validate()

    # Create Object whose Object Data is our new mesh
    obj = bpy.data.objects.new('ray', mesh)

    # Add *Object* to the scene, not the mesh
    scene = bpy.context.scene
    scene.collection.objects.link(obj)


def getTargetIndices(targets, debugOutput):
    # we need indices to store which point belongs to which object
    # there are to types of indices: 
    #   TOP LEVEL: the category of the top level object in our scene, e.g. chair, table
    #   CHILD LEVEL: the category of the child object, e.g. leg, plate

    # for that we iterate over all "groupID" custom properties and put them in the dictionary
    categoryIDs = {}
    partIDs = {}

    categoryIndex = 0
    partIndex = 0

    for target in targets:
        if not "categoryID" in target:
            # the custom property is not set, fallback is the targets name
            if debugOutput:
                print("WARNING: no categoryID given for target %s! Using name instead." % target.name)  
            target["categoryID"] = target.name

        categoryID = target["categoryID"]

        # only add the index if this group is not already in our dictionary
        if not categoryID in categoryIDs:
            categoryIDs[categoryID] = categoryIndex
            categoryIndex += 1


        if not "partID" in target:
            # the custom property is not set
            # in this case, the fallback is the material index for the given point on the mesh
            if debugOutput:
                print("WARNING: no partID given for target %s! Using material instead." % target.name)  
            
        else:
            partID = target["partID"]

            # only add the index if this group is not already in our dictionary
            if not partID in partIDs:
                partIDs[partID] = partIndex
                partIndex += 1
       

    # add all materials to dictionary
    for material in bpy.data.materials:
        materialName = material.name

        if not materialName in partIDs:
            partIDs[materialName] = partIndex
            partIndex += 1

    return (categoryIDs, partIDs)

def addMeshToScene(name, values, useNoiseLocation):
    # Create new mesh to store all measurements as points
    mesh = bpy.data.meshes.new(name='created mesh')
    bm = bmesh.new()        

    # iterate over all possible hits
    if useNoiseLocation:
        for hit in values:                
            bm.verts.new((hit.noiseLocation.x, hit.noiseLocation.y, hit.noiseLocation.z))
    else:
        for hit in values:                
            bm.verts.new((hit.location.x, hit.location.y, hit.location.z))

    # make the bmesh the object's mesh
    bm.to_mesh(mesh)  
    bm.free()  # always do this when finished
        
    # We're done setting up the mesh values, update mesh object and 
    # let Blender do some checks on it
    mesh.update()
    mesh.validate()

    # Create Object whose Object Data is our new mesh
    obj = bpy.data.objects.new(name, mesh)

    # Add *Object* to the scene, not the mesh
    scene = bpy.context.scene
    scene.collection.objects.link(obj)

def getClosestHit(targets, trees, origin, direction, maxRange, debugOutput, debugLines):
    closestLocation = None
    closestFaceNormal = None
    closestFaceIndex = None
    closestDistance = maxRange
    closestTarget = None

    # iterate over all targets to find the closest hit
    for target in targets:
        if debugOutput:
            print("Scanning target ", target.name, "...")

        # perform the actual ray casting
        # see: https://docs.blender.org/api/current/mathutils.bvhtree.html#mathutils.bvhtree.BVHTree.ray_cast
        #      https://github.com/blender/blender/blob/master/source/blender/blenlib/BLI_kdopbvh.h#L81
        location, faceNormal, faceIndex, distance = trees[target][0].ray_cast(origin, direction, closestDistance)

        # we use the current closest distance as maximum range, because we don't need to consider geometry which 
        # is further away than the current closest hit

        # if there was a hit and it is closer to the origin, update closest hit
        # but we need a workaround for rounding errors:
        # sometimes when we fire a ray from an object, that ray immediately hits that
        # same object again, so we just ignore it
        if distance is not None and distance < closestDistance:
            if debugOutput:
                print("Old hit ", closestLocation, closestFaceNormal, closestFaceIndex, closestDistance, closestTarget)
                print("New hit ", location, faceNormal, faceIndex, distance, target)

            closestLocation = location
            closestFaceNormal = faceNormal
            closestFaceIndex = faceIndex
            closestDistance = distance
            closestTarget = target
            
    if closestLocation is not None:
        if debugLines:
            addLine(origin, closestLocation)
        
        return hit_info.HitInfo(closestLocation, closestFaceNormal, closestFaceIndex, closestDistance, closestTarget)
    else:
        return None

# remove invalid characters
# source https://blender.stackexchange.com/a/104877
def removeInvalidCharatersFromFileName(name):  
    for char in " !@#$%^&*(){}:\";'[]<>,.\\/?":
        name = name.replace(char, '_')
    return name.lower().strip()

def startScan(context, dependencies_installed, properties, objectName):   
    if objectName is None:
        cleanedFileName = removeInvalidCharatersFromFileName(properties.dataFileName)
    else:
        cleanedFileName = removeInvalidCharatersFromFileName("%s_%s" % (properties.dataFileName, objectName))
    
    if not cleanedFileName == properties.dataFileName:
        print("WARNING: File name contains invalid characters. New file name: %s" % cleanedFileName)


    if properties.singleRay:
        allTargets = [properties.targetObject]
    else:
        allTargets = []
        for viewLayer in bpy.context.scene.view_layers:
            for obj in viewLayer.objects:
                # get all visible objects
                # filters:
                # - object has some kind of geometry
                # - is not excluded
                # - has a material set
                if obj.type == 'MESH' and \
                    obj.hide_get() == False and \
                    obj.active_material != None:
                        allTargets.append(obj)

    if properties.scannerObject == None:
        print("No scanner object selected!")
        return {'FINISHED'}   

    if properties.measureTime:
            startTime = time.time()

    targets = []
    materialMappings = {}

    version = bpy.app.version

    for target in allTargets:
        # we need to know which material belongs to which face, get the mapping for each target
        if len(target.material_slots) == 0:
            if properties.debugOutput:
                print("No material set for object %s! Skipping..." % target.name)
            continue
        
        # Blender's modifiers can change an objetc's shape although it seems
        # already modified in the viewport
        # so wen need to apply all modifiers here
        context.view_layer.objects.active = target

        for modifier in target.modifiers:
            # apply_as was removed, see https://blender.stackexchange.com/a/187711/95167
            if version >= (2, 91, 0):
                bpy.ops.object.modifier_apply(modifier=modifier.name)    
            else:
                bpy.ops.object.modifier_apply(apply_as='DATA', modifier=modifier.name)

        try:
            targetMaterials = material_helper.getTargetMaterials(properties.debugOutput, target)
        except ValueError as e:
            print(e)
            print(f"The target object with name {target.name} will be ignored! ")
            continue

        targets.append(target)

        # get the face->material mappings for the current object
        targetMappings =  material_helper.getFaceMaterialMapping(target.data)
        
        materialMappings[target] = (targetMaterials, targetMappings)

    (categoryIDs, partIDs) = getTargetIndices(targets, properties.debugOutput)

    if properties.debugOutput:
        print("CategoryIDs ", categoryIDs)
        print("PartIDs ", partIDs)

    if properties.scannerType == ScannerType.sideScan.name:
        if properties.scannerObject.matrix_world.translation.z > properties.surfaceHeight:
            print("ERROR: Sensor is above water level!")
            return {'FINISHED'}

        if properties.simulateWaterProfile:
            # as the fill value (black) is a tuple, we need some special packing
            # see: https://stackoverflow.com/a/40711408/13440564
            value = np.empty((), dtype=object)
            value[()] = (0.0, 0.0, 0.0) 

            depthList = np.full(len(context.scene.custom.items()), value)

            for index, item in enumerate(context.scene.custom.items()):                
                # store all values in a new array
                # the depth is measured relative to the water surface level
                depthList[index] = (properties.surfaceHeight - item[1].depth, item[1].speed, item[1].density)
        else:
            depthList = []

        sonar.performScan(context, 
                    properties.scannerType, properties.scannerObject,
                    properties.maxDistance,
                    properties.fovSonar, properties.sonarStepDegree, properties.sonarMode3D, properties.sonarKeepRotation,
                    properties.sourceLevel, properties.noiseLevel, properties.directivityIndex, properties.processingGain, properties.receptionThreshold,   
                    properties.simulateWaterProfile, depthList,   
                    properties.addNoise, properties.noiseType, properties.mu, properties.sigma, properties.addConstantNoise, properties.noiseAbsoluteOffset, properties.noiseRelativeOffset,
                    properties.addMesh,
                    properties.exportLAS and dependencies_installed, properties.exportHDF and dependencies_installed, properties.exportCSV, properties.exportPLY and dependencies_installed, properties.exportSingleFrames,
                    properties.dataFilePath, cleanedFileName,
                    properties.debugLines, properties.debugOutput, properties.outputProgress, properties.measureTime, properties.singleRay, properties.destinationObject, properties.targetObject,
                    properties.enableAnimation, properties.frameStart, properties.frameEnd, properties.frameStep,
                    targets, materialMappings,
                    categoryIDs, partIDs)

    else:
        if properties.enableAnimation:
            # read the needed camera settings
            # alternative: get needed values from the main Blender GUI ('Output Properties' tab on the right)
            firstFrame = properties.frameStart  # bpy.context.scene.frame_start
            lastFrame = properties.frameEnd     # bpy.context.scene.frame_end
            frameStep = properties.frameStep    # bpy.context.scene.frame_step
            frameRate = properties.frameRate    # bpy.context.scene.render.fps / bpy.context.scene.render.fps_base

            # calculate the angle which the sensor covers in each frame
            angularFractionPerFrame = properties.rotationsPerSecond / frameRate * (properties.fovX)

            # more than 360° (one rotation) makes no sense, as we would compute some rays more than once
            if angularFractionPerFrame > 360.0:
                angularFractionPerFrame = 360.0

        else:
            firstFrame = bpy.context.scene.frame_current
            lastFrame = bpy.context.scene.frame_current
            frameStep = 1
            frameRate = 1

            angularFractionPerFrame = properties.fovX

        if properties.scannerType == ScannerType.rotating.name or properties.scannerType == ScannerType.sideScan.name:
            stepsX = properties.xStepDegree
            stepsY = properties.yStepDegree
        elif properties.scannerType == ScannerType.static.name:
            stepsX = int(properties.resolutionX * (properties.resolutionPercentage / 100))
            stepsY = int(properties.resolutionY * (properties.resolutionPercentage / 100))
        else:
            print("Unsupported scanner type %s!" % properties.scannerType)
            return {'FINISHED'}





        if properties.scannerType == ScannerType.rotating.name:
            # defining sensor properties
            # [-180, 180] degree
            xSteps = angularFractionPerFrame / stepsX + 1

            # [-90, 90] degree
            ySteps = properties.fovY / stepsY + 1

            totalNumberOfRays = int(xSteps) * int(ySteps)
        elif properties.scannerType == ScannerType.static.name:
            totalNumberOfRays = stepsX * stepsY
        else:
            print("ERROR: Unknown scanner type %s!" % properties.scannerType)
            return {'FINISHED'}

        frameRange = range(firstFrame, lastFrame + 1, frameStep)

        # array to store hit information
        # we don't know how many of our rays will actually hit an object, so we allocate
        # memory for the worst case of every ray hitting the scene
        # (TODO depending on the RAM usage, it might be a good idea to use some kind of caching/splitting)
        scannedValues = np.full(len(frameRange) * totalNumberOfRays, None, dtype=hit_info.HitInfo)

        startIndex = 0

        # graph needed for BVH tree
        depsgraph = context.evaluated_depsgraph_get()

        trees = {}

        for frameNumber in frameRange:
            print("Rendering frame %d..." % frameNumber)

            trees = generic.getBVHTrees(trees, targets, depsgraph)

            halfFOV = properties.fovX / 2.0

            # get the angle which the sensor needs to cover in the current frame
            if properties.enableAnimation and properties.scannerType == ScannerType.rotating.name:
                # if animation is enabled, only scan the area which is covered in the time of one frame
                intervalStart = -halfFOV + ((frameNumber - 1) * angularFractionPerFrame) % 360
                intervalEnd = intervalStart + angularFractionPerFrame
            else:
                # else, just scan from start to end
                intervalStart = -halfFOV
                intervalEnd = halfFOV

            if properties.enableAnimation:
                # set the current scene frame
                # IMPORTANT: don't use frame_current our the (internal) data might not
                # be updated before calculating the point data!
                bpy.context.scene.frame_set(frameNumber)

            numberOfHits = lidar.performScan(context, 
                                properties.scannerType, properties.scannerObject,
                                properties.reflectivityLower, properties.distanceLower, properties.reflectivityUpper, properties.distanceUpper, properties.maxReflectionDepth,
                                intervalStart, intervalEnd, properties.fovX, stepsX, properties.fovY, stepsY, properties.resolutionPercentage,
                                scannedValues, startIndex,
                                firstFrame, lastFrame, frameNumber, properties.rotationsPerSecond,
                                properties.addNoise, properties.noiseType, properties.mu, properties.sigma, properties.addConstantNoise, properties.noiseAbsoluteOffset, properties.noiseRelativeOffset,
                                properties.simulateRain, properties.rainfallRate,
                                properties.simulateDust, properties.particleRadius, properties.particlesPcm, properties.dustCloudLength, properties.dustCloudStart,
                                properties.addMesh and properties.exportSingleFrames,
                                properties.exportLAS and dependencies_installed and properties.exportSingleFrames, properties.exportHDF and dependencies_installed and properties.exportSingleFrames, properties.exportCSV and properties.exportSingleFrames, properties.exportPLY and dependencies_installed and properties.exportSingleFrames, 
                                properties.exportRenderedImage, properties.exportSegmentedImage, properties.exportPascalVoc and dependencies_installed, properties.exportDepthmap, properties.depthMinDistance, properties.depthMaxDistance, 
                                properties.dataFilePath, cleanedFileName,
                                properties.debugLines, properties.debugOutput, properties.outputProgress, properties.measureTime, properties.singleRay, properties.destinationObject, properties.targetObject,
                                targets, materialMappings,
                                categoryIDs, partIDs, trees, depsgraph)

            startIndex += numberOfHits

        if not properties.exportSingleFrames:
            # we now have the final number of hits so we could shrink the array here
            # as explained here (https://stackoverflow.com/a/32398318/13440564), resizing
            # would cause a copy, so we slice the array instead
            slicedScannedValues = scannedValues[:startIndex]

            if properties.addMesh:
                addMeshToScene("real_values_frames_%d_to_%d" % (firstFrame, lastFrame), slicedScannedValues, False)

                if (properties.addNoise or properties.simulateRain):
                    addMeshToScene("noise_values_frames_%d_to_%d" % (firstFrame, lastFrame), slicedScannedValues, True)

            exportNoiseData = properties.addNoise or properties.simulateRain

            if len(slicedScannedValues) > 0:
                # setup exporter with our data
                if (properties.exportLAS and dependencies_installed) or (properties.exportHDF and dependencies_installed) or (properties.exportCSV and dependencies_installed) or (properties.exportPLY and dependencies_installed):
                    fileExporter = exporter.Exporter(properties.dataFilePath, "%s_frames_%d_to_%d" % (cleanedFileName, firstFrame, lastFrame), cleanedFileName, slicedScannedValues, targets, categoryIDs, partIDs, materialMappings, exportNoiseData, stepsX, stepsY)

                    print(fileExporter.fileName)

                    # export to each format
                    if properties.exportLAS:
                        fileExporter.exportLAS()

                    if properties.exportHDF:
                        fileExporter.exportHDF(fileNameExtra="_frames_%d_to_%d_merged" % (firstFrame, lastFrame))

                    if properties.exportCSV:
                        fileExporter.exportCSV()
                        
                    if properties.exportPLY:
                        fileExporter.exportPLY()
            else:
                print("No data to export!")
    if properties.measureTime:
        print("Scan time: %s s" % (time.time() - startTime))

def getBVHTrees(trees, targets, depsgraph):
    for target in targets:
        # check if the target is already in the tree map
        if target in trees:
            # if so, get the old values
            (existingTree, matrix_world) = trees[target]

            # if the object did not change its world matrix, we
            # don't have to recompute the tree
            if matrix_world == target.matrix_world:
                continue

        # the easy way would be to use this function, but then we would have to transform all
        # coordinates into the object's local coordinate system
        #trees[target] = BVHTree.FromObject(target, depsgraph)
        
        # source: https://developer.blender.org/T57861
        bm = bmesh.new()
        bm.from_object(target, depsgraph=depsgraph)
        bm.transform(target.matrix_world)
        
        trees[target] = (BVHTree.FromBMesh(bm), target.matrix_world.copy())

        bm.free()  # always do this when finished

    return trees