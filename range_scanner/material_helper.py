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

MaterialProperty = namedtuple('MaterialProperty', 'color metallic ior')

def getMaterialColorAndMetallic(hit, materialMappings, depsgraph, debugOutput):
    # each face can have an individual material so we need to get the correct one here
    materialIndex = materialMappings[hit.target][hit.faceIndex]
    material = hit.target.material_slots[materialIndex].material

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
    uv_coord = getUVCoord(mesh, face, point, image)
    
    # retrieve rgba value at uv coordinate
    rgba = getPixel(image, uv_coord)
    return rgba


def getUVCoord(mesh:Mesh, face:MeshPolygon, point:Vector, image:Image):
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
    image_size_x, image_size_y = image.size
    x_co = round(uv_loc.x * (image_size_x - 1))
    y_co = round(uv_loc.y * (image_size_y - 1))
    uv_coord = (x_co, y_co)

    # return resulting uv coordinate
    return Vector(uv_coord)


# reference: https://svn.blender.org/svnroot/bf-extensions/trunk/py/scripts/addons/uv_bake_texture_to_vcols.py
def getPixel(img, uv_coord):
    """ get RGBA value for specified coordinate in UV image
    pixels    -- list of pixel data from UV texture image
    uv_coord  -- UV coordinate of desired pixel value
    """
    uv_pixels = img.pixels # Accessing pixels directly is quite slow. Copy to new array and pass as an argument for massive performance-gain if you plan to run this function many times on the same image (img.pixels[:]).
    
    pixelNumber = (img.size[0] * int(uv_coord.y)) + int(uv_coord.x)
    
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