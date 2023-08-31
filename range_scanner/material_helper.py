import bpy
import math
import colorsys
from mathutils import Vector
from mathutils.interpolate import poly_3d_calc
from bpy.types import Scene, Mesh, MeshPolygon, Image
from collections import namedtuple
import numpy as np

def getSurfaceReflectivity(color):
    # Blender uses different color models for RGB / HSV / HEX, so there might be some
    # different values in the GUI
    # see: https://blender.stackexchange.com/a/80047/95167
    # return colorsys.rgb_to_hsv(color[0], color[1], color[2])[2]
    
    # better and unambiguously way: simply use the alpha channel
    return color[3]

class MaterialProperty:
    def __init__(self, color, texture, metallic, ior):
        self.color = color
        self.texture = texture
        self.metallic = metallic
        self.ior = ior

class Image:
    def __init__(self, pixels, size):
        self.pixels = pixels
        self.size = size

def getTargetMaterials(debugOutput, target):
    materialCount = len(target.material_slots)
    targetMaterials = np.empty(materialCount, dtype=MaterialProperty)

    for materialIndex in range(materialCount):
        material = target.material_slots[materialIndex].material

        if material is not None:
            if material.use_nodes == False:
                # diffuse_color, metallic, specular_intensity, roughness
                rgba = material.diffuse_color
                metallic = material.metallic

                targetMaterials[materialIndex] = MaterialProperty(rgba, None, metallic, 0.0)
                continue
            else:
                # the easy way would be to get the active node:
                # node = material.node_tree.nodes.active
                # the problem here is that also no node can be active so this returns None

                # instead, we get the Material Output node and look at the connected nodes
                # see: https://blender.stackexchange.com/a/5471/95167
                links = material.node_tree.nodes["Material Output"].inputs["Surface"].links
   
                if len(links) == 0:
                    raise ValueError(f"ERROR: Material with name '{material.name}' does not have any links! "
                                     "Please remove the material or check that the 'Material Output'-node of this material is properly connected. ")

                for link in links:
                    # get the node of the connected link
                    node = link.from_node

                    # node tree
                    if node.type == 'BSDF_GLASS':
                        # glass
                        rgba = node.inputs['Color'].default_value
                        ior = node.inputs['IOR'].default_value

                        targetMaterials[materialIndex] = MaterialProperty(rgba, None, 0.0, ior)
                        continue
                    elif node.type == 'BSDF_PRINCIPLED':
                        # check if an image texture is connected to the BSDF node
                        connectedLinks = node.inputs['Base Color'].links
                        if len(connectedLinks) > 0 and connectedLinks[0].from_node.type == "TEX_IMAGE":
                            # image texture
                            image = connectedLinks[0].from_node.image
                            texture = Image(image.pixels[:], image.size)

                            # retrieve metallic factor
                            metallic = node.inputs['Metallic'].default_value

                            targetMaterials[materialIndex] = MaterialProperty(None, texture, metallic, 0.0)
                            continue

                        # no texture, just a simple color
                        rgba = node.inputs['Base Color'].default_value
                        metallic = node.inputs['Metallic'].default_value
        
                        targetMaterials[materialIndex] = MaterialProperty(rgba, None, metallic, 0.0)
                        continue
                    else:
                        # unknown material
                        print("Unknown material type for object %s!" % target.name)
                        print(node.type)
        else:
            # no material set
            if debugOutput:
                print("WARNING: No material set for object %s!" % target.name)

    return targetMaterials

def getMaterialColorAndMetallic(hit, materialMappings, depsgraph, debugOutput):
    # each face can have an individual material so we need to get the correct one here

    materialIndex = materialMappings[hit.target][1][hit.faceIndex]
    material = materialMappings[hit.target][0][materialIndex]

    if material.texture is not None:
        # caculate point location in relation to the hit target
        newPoint = hit.target.matrix_world.inverted() @ hit.location

        # retrieve color
        material.color = getUVPixelColor(hit.target.data, hit.faceIndex, newPoint, material.texture)
    
    return material
    """
    if material is not None:
        if material.use_nodes == False:
            # diffuse_color, metallic, specular_intensity, roughness
            rgba = material.diffuse_color
            metallic = material.metallic

            return MaterialProperty(rgba, metallic, 0.0)
        else:
            # the easy way would be to get the active node:
            # node = material.node_tree.nodes.active
            # the problem here is that also no node can be active so this returns None

            # instead, we get the Material Output node and look at the connected nodes
            # see: https://blender.stackexchange.com/a/5471/95167
            links = material.node_tree.nodes["Material Output"].inputs["Surface"].links

            for link in links:
                # get the node of the connected link
                node = link.from_node

                # node tree
                if node.type == 'BSDF_GLASS':
                    # glass
                    rgba = node.inputs['Color'].default_value
                    ior = node.inputs['IOR'].default_value

                    return MaterialProperty(rgba, 0.0, ior)
                elif node.type == 'BSDF_PRINCIPLED':
                    # check if an image texture is connected to the BSDF node
                    connectedLinks = node.inputs['Base Color'].links
                    if len(connectedLinks) > 0 and connectedLinks[0].from_node.type == "TEX_IMAGE":
                        # image texture
                    
                        # retrieve color
                        rgba = getUVPixelColor(hit.target.data, hit.faceIndex, hit.location, connectedLinks[0].from_node.image)
                        
                        # retrieve metallic factor
                        metallic = node.inputs['Metallic'].default_value

                        return MaterialProperty(rgba, metallic, 0.0)

                    # simple color
                    rgba = node.inputs['Base Color'].default_value
                    metallic = node.inputs['Metallic'].default_value
    
                    return MaterialProperty(rgba, metallic, 0.0)
                else:
                    # unknown material
                    print("Unknown material type for object %s!" % hit.target.name)
                    print(node.type)
    else:
        # no material set
        if debugOutput:
            print("WARNING: No material set for object %s!" % hit.target.name)

    return None
    """

# source: https://blender.stackexchange.com/a/139399/95167
def getUVPixelColor(mesh:Mesh, face_idx:int, point:Vector, image:Image):
    """ get RGBA value for point in UV image at specified face index
    mesh     -- target mesh (must be uv unwrapped)
    face_idx -- index of face in target mesh to grab texture color from
    point    -- location (in 3D space on the specified face) to grab texture color from
    image    -- UV image used as texture for 'mesh' object
    """
    # ensure image contains at least one pixel
    assert image is not None and image.pixels is not None and len(image.pixels) > 0
    
    # get closest material using UV map
    face = mesh.polygons[face_idx]
    
    # get uv coordinate based on nearest face intersection
    uv_coord = getUVCoord(mesh, face, point, image.size)
    
    # retrieve rgba value at uv coordinate
    rgba = getPixel(image.pixels, image.size, uv_coord)

    return rgba


def getUVCoord(mesh:Mesh, face:MeshPolygon, point:Vector, imageSize):
    """ returns UV coordinate of target point in source mesh image texture
    mesh  -- mesh data from source object
    face  -- face object from mesh
    point -- coordinate of target point on source mesh
    image -- image texture for source mesh
    """
    
    # get active uv layer data
    uv_layer = mesh.uv_layers.active
    assert uv_layer is not None # ensures mesh has a uv map
    
    uv = uv_layer.data

    # get 3D coordinates of face's vertices
    lco = [mesh.vertices[i].co for i in face.vertices]
    
    # get uv coordinates of face's vertices
    luv = [uv[i].uv for i in face.loop_indices]
    
    # calculate barycentric weights for point
    lwts = poly_3d_calc(lco, point)
    
    # multiply barycentric weights by uv coordinates
    uv_loc = sum((p*w for p,w in zip(luv,lwts)), Vector((0,0)))
    
    # ensure uv_loc is in range(0,1)
    # TODO: possibly approach this differently? currently, uv verts that are outside the image are wrapped to the other side
    uv_loc = Vector((uv_loc[0] % 1, uv_loc[1] % 1))
    
    # convert uv_loc in range(0,1) to uv coordinate
    image_size_x, image_size_y = imageSize
    x_co = round(uv_loc.x * (image_size_x - 1))
    y_co = round(uv_loc.y * (image_size_y - 1))
    uv_coord = (x_co, y_co)

    # return resulting uv coordinate
    return Vector(uv_coord)


# reference: https://svn.blender.org/svnroot/bf-extensions/trunk/py/scripts/addons/uv_bake_texture_to_vcols.py
def getPixel(uv_pixels, imageSize, uv_coord):
    """ get RGBA value for specified coordinate in UV image
    pixels    -- list of pixel data from UV texture image
    uv_coord  -- UV coordinate of desired pixel value
    """
    #uv_pixels = img.pixels # Accessing pixels directly is quite slow. Copy to new array and pass as an argument for massive performance-gain if you plan to run this function many times on the same image (img.pixels[:]).
     
    pixelNumber = (imageSize[0] * int(uv_coord.y)) + int(uv_coord.x)
    
    r = uv_pixels[pixelNumber*4 + 0]
    g = uv_pixels[pixelNumber*4 + 1]
    b = uv_pixels[pixelNumber*4 + 2]
    a = uv_pixels[pixelNumber*4 + 3]
    
    return (r, g, b, a)

def getFaceMaterialMapping(mesh):
    # https://blender.stackexchange.com/a/52429/95167
    numberOfPolygons = len(mesh.polygons.items())
    mapping = np.empty(numberOfPolygons, dtype=int)

    for f in mesh.polygons: 
        mapping[f.index] = f.material_index

    return mapping