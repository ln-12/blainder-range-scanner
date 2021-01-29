# context.area: VIEW_3D

# add-on skeleton taken from: https://blender.stackexchange.com/a/57332

bl_info = {
    "name" : "range_scanner",
    "author" : "Lorenzo Neumann",
    "description" : "Range scanner simulation for Blender",
    "blender" : (2, 81, 0),
    "version" : (0, 0, 1),
    "location" : "3D View > Scanner",
    "warning" : "",
    "category" : "3D View",
    "wiki_url": "https://git.informatik.tu-freiberg.de/masterarbeit/blender-range-scanner",
}

from .ui import user_interface

# register all needed classes on startup
def register():
    user_interface.register()

# delete all classes on shutdown
def unregister():
    user_interface.unregister()