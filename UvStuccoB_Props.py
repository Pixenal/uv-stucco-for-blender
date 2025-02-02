import bpy
import ctypes
from . import UvStuccoB_CLib
stucLib = UvStuccoB_CLib.stucLib
from . import Utils as utils

def targetObjUpdate(self, context):
    self.name = self.obj.name

def usgFlatCutoffPoll(self, obj):
    return self != obj and not obj.get("StucUsg", None)

class StucMap(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    #id : bpy.props.IntProperty(default = -1)
    filepath : bpy.props.StringProperty(subtype = 'FILE_PATH')

class StucTarget(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    id : bpy.props.IntProperty(default = -1)
    map : bpy.props.StringProperty()
    obj : bpy.props.PointerProperty(type = bpy.types.Object,
                                    update = targetObjUpdate)

class StucCommonAttrib(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    domain : bpy.props.EnumProperty(items = [
        ('FACE', "Face", ""),
        ('CORNER', "Face Corner", ""),
        ('EDGE', "Edge", ""),
        ('POINT', "Vertex", "")
    ])
    blend : bpy.props.EnumProperty(default = '0', items = [
        ('0', "Replace", ""),
        ('1', "Multiply", ""),
        ('2', "Divide", ""),
        ('3', "Add", ""), 
        ('4', "Subtract", ""),
        ('5', "Add Sub", ""),
        ('6', "Lighten", ""),
        ('7', "Darken", ""),
        ('8', "Overlay", ""),
        ('9', "Soft Light", ""),
        ('10', "Color Dodge", "")
    ])
    order : bpy.props.EnumProperty(default = '0', items = [
        ('0', "Mesh Over Map", ""),
        ('1', "Map Over Mesh", "")
    ])

class StucProperties(bpy.types.PropertyGroup):
    nextTargetId : bpy.props.IntProperty(default = 0)
    commonAttribDomain : bpy.props.EnumProperty(items = [
        ('FACE', "Face", ""),
        ('CORNER', "Face Corner", ""),
        ('EDGE', "Edge", ""),
        ('POINT', "Vertex", "")
    ])
    commonAttribIndex : bpy.props.IntProperty(default = 0)
    wScale : bpy.props.FloatProperty(name = "w Scale", default = 1.0)

classes = [StucProperties,
           StucTarget,
           StucCommonAttrib,
           StucMap]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.stucTargetId = bpy.props.IntProperty(name = "UVS Target ID", default = -1)
    bpy.types.Object.stucUsgFlatCutoff = bpy.props.PointerProperty(type = bpy.types.Object,
                                                                   name = "Stuc USG Flatten Cut-Off",
                                                                   poll = usgFlatCutoffPoll)
    bpy.types.Scene.stuc = bpy.props.PointerProperty(type = StucProperties)
    bpy.types.Scene.stucTargets = bpy.props.CollectionProperty(name = "Targets", type = StucTarget)
    bpy.types.Scene.stucTargetsIndex = bpy.props.IntProperty(name = "Targets Index")
    bpy.types.Scene.stucMaps = bpy.props.CollectionProperty(name = "Maps", type = StucMap)
    bpy.types.Scene.stucMapsIndex = bpy.props.IntProperty(name = "Maps Index")
    StucTarget.commonMeshAttribs = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucTarget.commonFaceAttribs = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucTarget.commonCornerAttribs = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucTarget.commonEdgeAttribs = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucTarget.commonVertAttribs = bpy.props.CollectionProperty(type = StucCommonAttrib)

#TODO don't you need to delete the other props as well?
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.Stuc
