import bpy
import ctypes
from . import RUVM_CLib
uvsLib = RUVM_CLib.uvsLib
from . import Utils as utils

def addCommonAttribs(count, attribs, selfAttribs):
    i = 0
    while i < count:
        name = attribs[i].name
        name = ctypes.cast(name, ctypes.c_char_p).value
        name = name.decode("utf-8")
        entry = selfAttribs.get(name, None)
        if not entry:
            entry = selfAttribs.add()
            entry.name = name
        i += 1

def targetMapUpdate(self, context):
    depsgraph = context.evaluated_depsgraph_get()
    objEval = self.obj.evaluated_get(depsgraph)
    meshEval = objEval.data
    meshTuple = utils.formatAsRuvmMesh(meshEval, False, True)
    mapUtf8 = utils.getTargetMapAsUtf8(self)
    commonAttribs = utils.RuvmCommonAttribList()
    uvsLib.uvsBlenderQueryCommonAttribs(ctypes.pointer(meshTuple[0]), mapUtf8,
                                          ctypes.pointer(commonAttribs))
    addCommonAttribs(commonAttribs.faceCount, commonAttribs.pFace,
                     self.commonFaceAttribs)
    addCommonAttribs(commonAttribs.loopCount, commonAttribs.pLoop,
                     self.commonCornerAttribs)
    addCommonAttribs(commonAttribs.edgeCount, commonAttribs.pEdge,
                     self.commonEdgeAttribs)
    addCommonAttribs(commonAttribs.vertCount, commonAttribs.pVert,
                     self.commonVertAttribs)

def targetObjUpdate(self, context):
    self.name = self.obj.name

def usgFlatCutoffPoll(self, obj):
    return self != obj and not obj.get("RuvmUsg", None)

class RuvmMap(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    #id : bpy.props.IntProperty(default = -1)
    filepath : bpy.props.StringProperty(subtype = 'FILE_PATH')

class RuvmTarget(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    id : bpy.props.IntProperty(default = -1)
    map : bpy.props.StringProperty(update = targetMapUpdate)
    obj : bpy.props.PointerProperty(type = bpy.types.Object,
                                    update = targetObjUpdate)

class RuvmCommonAttrib(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    domain : bpy.props.EnumProperty(items = [
        ('FACE', "Face", ""),
        ('CORNER', "Face Corner", ""),
        ('EDGE', "Edge", ""),
        ('POINT', "Vertex", "")
    ])
    blend : bpy.props.EnumProperty(default = 'REPLACE', items = [
        ('REPLACE', "Replace", ""),
        ('MULTIPLY', "Multiply", ""),
        ('DIVIDE', "Divide", ""),
        ('ADD', "Add", ""), 
        ('SUBTRACT', "Subtract", ""),
        ('ADD_SUB', "Add Sub", ""),
        ('LIGHTEN', "Lighten", ""),
        ('DARKEN', "Darken", ""),
        ('OVERLAY', "Overlay", ""),
        ('SOFT_LIGHT', "Soft Light", ""),
        ('COLOR_DODGE', "Color Dodge", "")
    ])
    order : bpy.props.EnumProperty(default = 'MESH_OVER_MAP', items = [
        ('MESH_OVER_MAP', "Mesh Over Map", ""),
        ('MAP_OVER_MESH', "Map Over Mesh", "")
    ])

class RuvmProperties(bpy.types.PropertyGroup):
    nextTargetId : bpy.props.IntProperty(default = 0)
    commonAttribDomain : bpy.props.EnumProperty(items = [
        ('FACE', "Face", ""),
        ('CORNER', "Face Corner", ""),
        ('EDGE', "Edge", ""),
        ('POINT', "Vertex", "")
    ])
    commonAttribIndex : bpy.props.IntProperty(default = 0)
    wScale : bpy.props.FloatProperty(name = "w Scale", default = 1.0)

classes = [RuvmProperties,
           RuvmTarget,
           RuvmCommonAttrib,
           RuvmMap]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.uvsTargetId = bpy.props.IntProperty(name = "UVS Target ID", default = -1)
    bpy.types.Object.uvsUsgFlatCutoff = bpy.props.PointerProperty(type = bpy.types.Object,
                                                                   name = "Ruvm USG Flatten Cut-Off",
                                                                   poll = usgFlatCutoffPoll)
    bpy.types.Scene.uvs = bpy.props.PointerProperty(type = RuvmProperties)
    bpy.types.Scene.uvsTargets = bpy.props.CollectionProperty(name = "Targets", type = RuvmTarget)
    bpy.types.Scene.uvsTargetsIndex = bpy.props.IntProperty(name = "Targets Index")
    bpy.types.Scene.uvsMaps = bpy.props.CollectionProperty(name = "Maps", type = RuvmMap)
    bpy.types.Scene.uvsMapsIndex = bpy.props.IntProperty(name = "Maps Index")
    RuvmTarget.commonMeshAttribs = bpy.props.CollectionProperty(type = RuvmCommonAttrib)
    RuvmTarget.commonFaceAttribs = bpy.props.CollectionProperty(type = RuvmCommonAttrib)
    RuvmTarget.commonCornerAttribs = bpy.props.CollectionProperty(type = RuvmCommonAttrib)
    RuvmTarget.commonEdgeAttribs = bpy.props.CollectionProperty(type = RuvmCommonAttrib)
    RuvmTarget.commonVertAttribs = bpy.props.CollectionProperty(type = RuvmCommonAttrib)

#TODO don't you need to delete the other props as well?
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.Ruvm
