import bpy

def targetMapUpdate(self, context):
    bpy.operators.ruvmQueryCommonAttribs()

class RuvmMap(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty()
    #id : bpy.props.IntProperty(default = -1)
    filepath : bpy.props.StringProperty(subtype = 'FILE_PATH')

class RuvmTarget(bpy.types.PropertyGroup):
    id : bpy.props.IntProperty(default = -1)
    #ruvmFilePath : bpy.props.StringProperty(name = "RUVM File")
    map : bpy.props.StringProperty(update = targetMapUpdate)
    obj : bpy.props.PointerProperty(type = bpy.types.Object)

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

classes = [RuvmProperties,
           RuvmTarget,
           RuvmCommonAttrib,
           RuvmMap]

#Register
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.ruvmTargetId = bpy.props.IntProperty(name = "RUVM Target ID", default = -1)
    bpy.types.Scene.ruvm = bpy.props.PointerProperty(type = RuvmProperties)
    bpy.types.Scene.ruvmTargets = bpy.props.CollectionProperty(name = "Targets", type = RuvmTarget)
    bpy.types.Scene.ruvmTargetsIndex = bpy.props.IntProperty(name = "Targets Index")
    bpy.types.Scene.ruvmMaps = bpy.props.CollectionProperty(name = "Maps", type = RuvmMap)
    bpy.types.Scene.ruvmMapsIndex = bpy.props.IntProperty(name = "Maps Index")
    RuvmTarget.commonAttribs = bpy.props.CollectionProperty(type = RuvmCommonAttrib)

#Unregister
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.Ruvm
