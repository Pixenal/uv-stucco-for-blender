import bpy
import pdb
import ctypes
from . import UvStuccoB_CLib
stucLib = UvStuccoB_CLib.stucLib
from . import Utils as utils

def targetObjUpdate(self, context):
    print(f"updating name from {self.name} to {self.obj.name}")
    self.name = self.obj.name

def usgFlatCutoffPoll(self, obj):
    return self != obj and not obj.get("StucUsg", None)

def stucMatPoll(self, obj):
    return not obj.get("StucMat", None)

def stucMatUpdate(self, context):
    if self.matCpy and self.mat != self.matCpy:
        del self.matCpy["StucMat"]
    self.matCpy = self.mat
    if self.mat:
        self.mat["StucMat"] = True

class StucMap(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()

class StucTarget(bpy.types.PropertyGroup):
    obj : bpy.props.PointerProperty(type = bpy.types.Object,
                                    update = targetObjUpdate)
    
class StucMat(bpy.types.PropertyGroup):
    mat : bpy.props.PointerProperty(type = bpy.types.Material, poll = stucMatPoll,
                                    update = stucMatUpdate)
    #matCpy exists to allow stucMatUpdate to see the mat a material pointed to before
    #it was changed (there doesn't seem to be a pre-update callback)
    matCpy : bpy.props.PointerProperty(type = bpy.types.Material)
    map : bpy.props.StringProperty()

class StucCommonAttrib(bpy.types.PropertyGroup):
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
    opacity : bpy.props.FloatProperty(default = 1.0)
    order : bpy.props.EnumProperty(default = '0', items = [
        ('0', "Map Over Mesh", ""),
        ('1', "Mesh Over Map", "")
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
    
class StucCommonAttribTableEntry(bpy.types.PropertyGroup):
    mat : bpy.props.PointerProperty(type = bpy.types.Material)

classes = [StucProperties,
           StucTarget,
           StucCommonAttrib,
           StucCommonAttribTableEntry,
           StucMap,
           StucMat]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    #TODO add these as needed, rather than adding it to every object like this
    bpy.types.Object.stucUsgFlatCutoff = bpy.props.PointerProperty(type = bpy.types.Object,
                                                                   name = "Stuc USG Flatten Cut-Off",
                                                                   poll = usgFlatCutoffPoll)
    bpy.types.Scene.stuc = bpy.props.PointerProperty(type = StucProperties)
    bpy.types.Scene.stucTargets = bpy.props.CollectionProperty(name = "Targets", type = StucTarget)
    bpy.types.Scene.stucTargetsIndex = bpy.props.IntProperty(name = "Targets Index")
    bpy.types.Scene.stucMaps = bpy.props.CollectionProperty(name = "Maps", type = StucMap)
    bpy.types.Scene.stucMapsIndex = bpy.props.IntProperty(name = "Maps Index")
    bpy.types.Scene.stucMats = bpy.props.CollectionProperty(name = "Mats", type = StucMat)
    bpy.types.Scene.stucMatsIndex = bpy.props.IntProperty(name = "Mats Index")
    StucCommonAttribTableEntry.mesh = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucCommonAttribTableEntry.faces = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucCommonAttribTableEntry.corners = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucCommonAttribTableEntry.edges = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucCommonAttribTableEntry.verts = bpy.props.CollectionProperty(type = StucCommonAttrib)
    StucTarget.commonAttribTable = bpy.props.CollectionProperty(type = StucCommonAttribTableEntry)

#TODO don't you need to delete the other props as well?
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.Stuc
