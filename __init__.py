bl_info = {
    "name": "Reverse UV Mapper",
    "description": "An addon for projecting geometry onto the surface of a mesh, using UVs",
    "author": "Pixenal",
    "version": (1, 0),
    "blender": (3, 6, 0),
    "location": "View",
    "category": "3D View"
}

import importlib

if ("bpy" in locals()):
    importlib.reload(UvStuccoB_Props)
    importlib.reload(UvStuccoB_Ops)
    importlib.reload(UvStuccoB_Ui)
else:
    from . import UvStuccoB_Props
    from . import UvStuccoB_Ops
    from . import UvStuccoB_Ui

def register():
    print("Registering UvStuccoB")
    UvStuccoB_Props.register()
    UvStuccoB_Ops.register()
    UvStuccoB_Ui.register()

def unregister():
    print("Registering UvStuccoB")
    UvStuccoB_Props.unregister()
    UvStuccoB_Ops.unregister()
    UvStuccoB_Ui.unregister()

