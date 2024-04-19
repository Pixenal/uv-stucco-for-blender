import bpy
import ctypes
import numpy
import bmesh
import sys
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
import os
import pdb

#TODO calc_normals_split has been removed in 4.1, so you'll need to handle that
#TODO It seems that normals can be accessed as contiguous arrays now,
#using the polygon_normals, or vertex_normals, properties, in a mesh.
#see if you can use this.
#TODO You'll need to separetly handle seams and creases and such as well,
#these seem to have been converted to attributes in 4.0 versions.
#So probably only need to do it for pre 4.0 versions.


if sys.platform == "win32":
    ruvmLibPath = "T:/workshop_folders/RUVM_Blender/Build/Win/Debug/RUVMBlender.dll"
elif sys.platform == "linux" or "linux2":
    ruvmLibPath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM_Blender/Build/Debug/libRUVMBlender.so"
ruvmLib = ctypes.cdll.LoadLibrary(ruvmLibPath)


class RuvmVec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float),
                ("y", ctypes.c_float)]

class RuvmVec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float),
                ("y", ctypes.c_float),
                ("z", ctypes.c_float)]

class RuvmAttrib(ctypes.Structure):
    _fields_ = [("pData", ctypes.c_void_p),
                #use c_byte instead of c_char, as the latter is immutable
                ("name", ctypes.c_byte * 96),
                ("type", ctypes.c_int32),
                ("origin", ctypes.c_int32),
                ("interpolate", ctypes.c_int32)]

class RuvmMesh(ctypes.Structure):
    _fields_ = [("meshAttribCount", ctypes.c_int32),
                ("pMeshAttribs", ctypes.POINTER(RuvmAttrib)),
                ("faceCount", ctypes.c_int32),
                ("pFaces", ctypes.POINTER(ctypes.c_int32)),
                ("faceAttribCount", ctypes.c_int32),
                ("pFaceAttribs", ctypes.POINTER(RuvmAttrib)),
                ("loopCount", ctypes.c_int32),
                ("pLoops", ctypes.POINTER(ctypes.c_int32)),
                ("loopAttribCount", ctypes.c_int32),
                ("pLoopAttribs", ctypes.POINTER(RuvmAttrib)),
                ("edgeCount", ctypes.c_int32),
                ("pEdges", ctypes.POINTER(ctypes.c_int32)),
                ("edgeAttribCount", ctypes.c_int32),
                ("pEdgeAttribs", ctypes.POINTER(RuvmAttrib)),
                ("vertCount", ctypes.c_int32),
                ("vertAttribCount", ctypes.c_int32),
                ("pVertAttribs", ctypes.POINTER(RuvmAttrib))]

class RuvmBlendConfig(ctypes.Structure):
    _fields_ = [("blend", ctypes.c_int32),
                ("order", ctypes.c_int8)]

class RuvmCommonAttrib(ctypes.Structure):
    #use c_byte instead of c_char, as the latter is immutable
    _fields_ = [("name", ctypes.c_byte * 96),
                ("blendConfig", RuvmBlendConfig)]

class RuvmCommonAttribList(ctypes.Structure):
    _fields_ = [("meshCount", ctypes.c_int32),
                ("pMesh", ctypes.POINTER(RuvmCommonAttrib)),
                ("faceCount", ctypes.c_int32),
                ("pFace", ctypes.POINTER(RuvmCommonAttrib)),
                ("loopCount", ctypes.c_int32),
                ("pLoop", ctypes.POINTER(RuvmCommonAttrib)),
                ("edgeCount", ctypes.c_int32),
                ("pEdge", ctypes.POINTER(RuvmCommonAttrib)),
                ("vertCount", ctypes.c_int32),
                ("pVert", ctypes.POINTER(RuvmCommonAttrib))]

def getTargetMapAsUtf8(target):
    map = bpy.context.scene.ruvmMaps.get(target.map, None)
    if map == None:
        print("Target has no map")
        return None
    return map.filepath.encode('utf-8')

def getAttribType(attrib):
    attribType = type(attrib)
    match attribType:
        case bpy.types.BoolAttribute:
            return (0, ctypes.c_int8) #RUVM_I8
        case bpy.types.ByteColorAttribute:
            return (18, ctypes.c_int8 * 4) #RUVM_V4_I8
        case bpy.types.ByteIntAttribute:
            return (0, ctypes.c_int8) #RUVM_I8
        case bpy.types.Float2Attribute:
            return (10, ctypes.c_float * 2) #RUVM_V2_F32
        case bpy.types.FloatAttribute:
            return (4, ctypes.c_float) #RUVM_F32
        case bpy.types.FloatColorAttribute:
            return (22, ctypes.c_float * 4) #RUVM_V4_F32
        case bpy.types.FloatVectorAttribute:
            return (16, ctypes.c_float * 3) #RUVM_V3_F32
        case bpy.types.Int2Attribute:
            return (8, ctypes.c_int32 * 2) #RUVM_V2_I32
        case bpy.types.IntAttribute:
            return (2, ctypes.c_int32) #RUVM_I32
        case bpy.types.QuaternionAttribute:
            return (22, ctypes.c_float * 4) #RUVM_V4_F32
        case bpy.types.StringAttribute:
            return (24, ctypes.POINTER(ctypes.c_char)) #RUVM_STRING
        case _:
            return None

def getAttribBlenderType(attrib):
    match attrib.type:
        #TODO add bool type to RUVM lib, as semantics are lost here
        #TODO in general, try include all types, including semantic
        #types, in Blender, Houdini, and USD. This includes unsigned
        #ints, quaternions, etc. If someone puts an attribute in, they need to get the
        #same type out. IMPORTANT: it may be best to split the semantic info off
        #into a separate enum
        case 0: #RUVM_I8
            return 'BOOLEAN'
        case 18: #RUVM_V4_I8
            return 'BYTE_COLOR' 
        case 0: #RUVM_I8
            return 'INT8'
        case 10: #RUVM_V2_F32
            return 'FLOAT2'
        case 4: #RUVM_F32
            return 'FLOAT'
        case 22: #RUVM_V4_F32
            return 'FLOAT_COLOR'
        case 16: #RUVM_V3_F32
            return 'FLOAT_VECTOR'
        case 8: #RUVM_V2_I32
            return 'INT32_2D'
        case 2: #RUVM_I32
            return 'INT'
        case 22: #RUVM_V4_F32
            return 'TODO FIX THIS'
        case 24: #RUVM_STRING
            return 'STRING' 
        case _:
            return None



def getAttribCounts(attribCount, target):
    for attrib in target.attributes:
        if '.' in attrib.name:
            continue
        match attrib.domain:
            case 'FACE':
                attribCount["face"] += 1
            case 'CORNER':
                attribCount["loop"] += 1
            case 'EDGE':
                attribCount["edge"] += 1
            case 'POINT':
                attribCount["vert"] += 1

def copyAttribName(dest, src):
    length = len(src)
    if (length > 96):
        #TODO add proper exception handling in general
        print("Attribute name length exceeds max")
        return
    srcUtf8 = src.encode('utf-8')
    i = 0
    while (i < length):
        dest[i] = srcUtf8[i]
        i += 1

def allocAttribs(mesh, attribCounts):
    FaceAttribsArray = RuvmAttrib * attribCounts["face"]
    mesh.pFaceAttribs = FaceAttribsArray()
    LoopAttribsArray = RuvmAttrib * (attribCounts["loop"] + 1) # +1 is for normals
    mesh.pLoopAttribs = LoopAttribsArray()
    EdgeAttribsArray = RuvmAttrib * attribCounts["edge"]
    mesh.pEdgeAttribs = EdgeAttribsArray()
    VertAttribsArray = RuvmAttrib * attribCounts["vert"]
    mesh.pVertAttribs = VertAttribsArray()

def initAttribEntry(attrib, attribEntry, dataLen, metaOnly, interpolate):
    copyAttribName(attribEntry.name, attrib.name)
    attribType = getAttribType(attrib)
    attribEntry.type = attribType[0]
    attribEntry.interpolate = interpolate
    if not(metaOnly):
        attribData = attrib.data[0].as_pointer()
        attribEntry.pData = ctypes.cast(attribData, ctypes.c_void_p)

def initAttribs(mesh, target, metaOnly):
    for attrib in target.attributes:
        if '.' in attrib.name:
            continue
        match attrib.domain:
            case 'FACE':
                attribEntry = mesh.pFaceAttribs[mesh.faceAttribCount]
                initAttribEntry(attrib, attribEntry, mesh.faceCount, metaOnly, 0)
                mesh.faceAttribCount += 1;
            case 'CORNER':
                attribEntry = mesh.pLoopAttribs[mesh.loopAttribCount]
                initAttribEntry(attrib, attribEntry, mesh.loopCount, metaOnly, 1)
                mesh.loopAttribCount += 1;
            case 'EDGE':
                attribEntry = mesh.pEdgeAttribs[mesh.edgeAttribCount]
                initAttribEntry(attrib, attribEntry, mesh.edgeCount, metaOnly, 0)
                mesh.edgeAttribCount += 1
            case 'POINT':
                attribEntry = mesh.pVertAttribs[mesh.vertAttribCount]
                initAttribEntry(attrib, attribEntry, mesh.vertCount, metaOnly, 0)
                mesh.vertAttribCount += 1

#returns a tuple containing the mesh, and the edges numpy array.
#in order to prevent the reference tot he edge array from becoming invalid
#after the function returns
def formatAsRuvmMesh(target, metaOnly, getNormals):
    mesh = RuvmMesh()

    mesh.faceCount = len(target.polygons)
    mesh.loopCount = len(target.loops)
    mesh.edgeCount = len(target.edges)
    mesh.vertCount = len(target.vertices)

    facesPtr = target.polygons[0].as_pointer()
    mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int32))

    loopsPtr = target.loops[0].as_pointer()
    mesh.pLoops = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int32))

    edges = numpy.zeros(mesh.loopCount, dtype = numpy.int32)
    target.loops.foreach_get("edge_index", edges)
    mesh.pEdges = edges.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))

    attribCount = {"face" : 0, "loop" : 0, "edge" : 0, "vert" : 0}
    getAttribCounts(attribCount, target)
    allocAttribs(mesh, attribCount)
    initAttribs(mesh, target, metaOnly)

    if not getNormals:
        return (mesh, edges)
    #afaik, normals are not accessable as an attribute.
    #atleast not at the time of writing.
    normals = numpy.zeros(mesh.loopCount * 3, dtype = numpy.float32)
    target.calc_normals_split()
    target.loops.foreach_get("normal", normals)
    attribEntry = mesh.pLoopAttribs[mesh.loopAttribCount]
    name = "normal"
    copyAttribName(attribEntry.name, name)
    attribEntry.type = 16 #RUVM_V3_F32
    attribEntry.pData = normals.ctypes.data_as(ctypes.c_void_p)
    mesh.loopAttribCount += 1
    return (mesh, edges, normals)

class RUVM_OT_RuvmExportRuvmFile(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_export_ruvm_file"
    bl_label = "RUVM Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        #pdb.set_trace()
        if (len(context.selected_objects) == 0):
            print("RUVM export failed, no objects selected.")
            return {'CANCELLED'}
        if (len(context.selected_objects) > 1):
            print("RUVM export failed, more than one object selected.")
            return {'CANCELLED'}
        obj = context.selected_objects[0]
        depsgraph = context.evaluated_depsgraph_get()
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        meshTuple = formatAsRuvmMesh(meshEval, False, True)

        #ruvmLib.ruvmBlenderMapFileExport.argtypes = (ctypes.POINTER(RuvmMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"))
        ruvmLib.ruvmBlenderMapFileExport(ctypes.pointer(meshTuple[0]))

        return {'FINISHED'}

class RUVM_OT_RuvmAssign(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_assign"
    bl_label = "RUVM Assign"
    bl_options = {'REGISTER'}

    def execute(self, context):
        ruvm = context.scene.ruvm
        if len(context.selected_objects) == 0:
            return {'CANCELLED'}
        for obj in context.selected_objects:
            exists = False
            for target in context.scene.ruvmTargets:
                if target.obj == obj:
                    exists = True
                    break
            if exists:
                continue
            newTarget = context.scene.ruvmTargets.add()
            newTarget.obj = obj.id_data
            newTarget.id = ruvm.nextTargetId
            obj.ruvmTargetId = ruvm.nextTargetId
            ruvm.nextTargetId += 1
        return {'FINISHED'}

class RUVM_OT_RuvmLoadRuvmFile(bpy.types.Operator, ImportHelper):
    bl_idname = "ruvm.load_ruvm_file"
    bl_label = "Load RUVM File"
    bl_options = {"REGISTER"}

    def execute(self, context):
        #pdb.set_trace()
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        newMap = context.scene.ruvmMaps.add()
        newMap.name = os.path.basename(filepath)
        newMap.filepath = filepath
        context.scene.ruvmMapsIndex = len(context.scene.ruvmMaps)
        ruvmLib.ruvmBlenderMapFileLoad(filePathUtf8)
        return {'FINISHED'}

class RUVM_OT_RuvmRemove(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_remove"
    bl_label = "RUVM Remove"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        if scene.ruvmTargetsIndex >= len(scene.ruvmTargets):
            return {'CANCELLED'}
        del scene.ruvmTargets[scene.ruvmTargetsIndex].obj["ruvmTargetId"]
        scene.ruvmTargets.remove(scene.ruvmTargetsIndex)
        return {'FINISHED'}

def setTargetCommonAttribs(target, commonAttribs, commonAttribsCount, domain):
    i = 0
    while (i < commonAttribsCount):
        targetAttrib = target.commonAttribs.get(commonAttribs[i].name, None)
        if not(targetAttrib):
            targetAttrib = target.commonAttribs.append()
            targetAttrib.name = commonAttribs[i].name
        targetAttrib.domain = domain
        targetAttrib.blend = commonAttribs[i].blend
        targetAttrib.order = commonAttribs[i].order
        i += 1

class RUVM_OT_RuvmQueryCommonAttribs(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_query_common_attribs"
    bl_label = "RUVM Query Common Attributes"
    bl_options = {'REGISTER'}

    def execute(self, context):
        pdb.set_trace()
        scene = context.scene
        target = scene.ruvmTargets[scene.ruvmTargetsIndex].obj
        depsgraph = context.evaluated_depsgraph_get()
        objEval = target.obj.evaluated_get(depsgraph)
        meshEval = objEval.mesh
        meshTuple = formatAsRuvmMesh(meshEval, True, False)
        mapUtf8 = getTargetMapAsUtf8(target)
        if not(mapUtf8):
            return
        commonAttribList = RuvmCommonAttribList()
        ruvmLib.ruvmBlenderQueryCommonAttribs(meshTuple[0], mapUtf8, ctypes.pointer(commonAttribList))
        setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "FACE")
        setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "CORNER")
        setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "EDGE")
        setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "POINT")

def createSingleAttrib(mesh, attrib, domain):
    attribType = getAttribBlenderType(attrib)
    name = ctypes.cast(attrib.name, ctypes.c_char_p).value
    mesh.attributes.new(name = name.decode("utf-8"), type = attribType, domain = domain)

def createAttribs(mesh, attribs, attribCount, domain):
    i = 0
    while (i < attribCount):
        createSingleAttrib(mesh, attribs[i], domain)
        i += 1

def createAllAttribs(mesh, ruvmMesh):
    #createAttribs(mesh, ruvmMesh.pFaceAttribs, ruvmMesh.faceAttribCount, "FACE")
    createAttribs(mesh, ruvmMesh.pLoopAttribs, ruvmMesh.loopAttribCount, "CORNER")
    #createAttribs(mesh, ruvmMesh.pEdgeAttribs, ruvmMesh.edgeAttribCount, "EDGE")
    #createAttribs(mesh, ruvmMesh.pVertAttribs, ruvmMesh.vertAttribCount, "POINT")

def getNormalAttrib(mesh):
    i = 0
    while (i < mesh.loopAttribCount):
        name = ctypes.cast(mesh.pLoopAttribs[i].name, ctypes.c_char_p).value
        if (name.decode("utf-8") == "normal"):
            return ctypes.pointer(mesh.pLoopAttribs[i])
        i += 1
    return None

@persistent
def ruvmDepsgraphUpdatePostHandler(dummy):
    
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for target in scene.ruvmTargets:
        obj = target.obj
        if not(obj in bpy.context.selected_objects):
            continue
        elif obj.mode != 'OBJECT':
            continue
        
        mesh = obj.data
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        meshTuple = formatAsRuvmMesh(meshEval, False, True)

        workMesh = RuvmMesh()

        mapUtf8 = getTargetMapAsUtf8(target)
        if not(mapUtf8):
            continue
        print("Mapping to mesh with map ", mapUtf8)

        #ruvmLib.ruvmBlenderMapToMesh.argtypes = (
        #    ctypes.POINTER(ctypes.c_char),
        #    ctypes.POINTER(RuvmMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_int32, flags="C_CONTIGUOUS"),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),
        #    ctypes.POINTER(RuvmMesh)
        #)
        commonAttribs = RuvmCommonAttribList()
        ruvmLib.ruvmBlenderQueryCommonAttribs(ctypes.pointer(meshTuple[0]), mapUtf8,
                                              ctypes.pointer(commonAttribs))
        result = ruvmLib.ruvmBlenderMapToMesh(mapUtf8, ctypes.pointer(meshTuple[0]),
                                              ctypes.pointer(workMesh),
                                              ctypes.pointer(commonAttribs))
        ruvmLib.ruvmBlenderDestroyCommonAttribs(ctypes.pointer(commonAttribs))
        if result:
            print("Ruvm python map to mesh failed, map to mesh returned error")
            return
        
        nameRuvm = obj.name + ".Ruvm"
        objRuvm = bpy.data.objects.get(nameRuvm, None)
        if not(objRuvm):
            meshRuvm = bpy.data.meshes.new(nameRuvm)
            objRuvm = bpy.data.objects.new(nameRuvm, meshRuvm)
            bpy.context.scene.collection.objects.link(objRuvm)
        else:
            meshRuvmOld = objRuvm.data
            meshRuvmOld.name += ".Old"
            meshRuvm = bpy.data.meshes.new(nameRuvm)
            objRuvm.data = meshRuvm
            bpy.data.meshes.remove(meshRuvmOld)
        
        print("workMesh.vertCount ", workMesh.vertCount)
        print("workMesh.loopCount ", workMesh.loopCount)
        print("workMesh.faceCount ", workMesh.faceCount)
        #pdb.set_trace()
        meshRuvm.vertices.add(workMesh.vertCount)
        meshRuvm.loops.add(workMesh.loopCount)
        meshRuvm.polygons.add(workMesh.faceCount)
        createAllAttribs(meshRuvm, workMesh)
        meshRuvmFormat = formatAsRuvmMesh(meshRuvm, False, False)

        ruvmLib.ruvmBlenderCopyMeshCore(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))

        #meshRuvm.uv_layers.new(name="uvmap")
        #uvPtr = meshRuvm.uv_layers[0].data[0].as_pointer()
        #ruvmMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))
        meshRuvm.update()
        meshRuvmFormat = formatAsRuvmMesh(meshRuvm, False, False)
        #pdb.set_trace()
        ruvmLib.ruvmBlenderCopyMeshAttribs(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))
        normalsArraySize = workMesh.loopCount * 3
        normalAttrib = getNormalAttrib(workMesh)
        normalsNumpy = numpy.ctypeslib.as_array(ctypes.cast(normalAttrib.contents.pData, ctypes.POINTER(ctypes.c_float)),
                                                shape = [normalsArraySize])
        #this is necessary to set custom normals it seems
        meshRuvm.normals_split_custom_set(tuple(zip(*(iter(normalsNumpy),) * 3)))
        meshRuvm.use_auto_smooth = True
        ruvmLib.ruvmBlenderMeshDestroy(ctypes.pointer(workMesh))
        print("FinishedUpdating")
        

@persistent
def ruvmLoadPostHandler(dummy):
    ruvmLib.ruvmBlenderInit()

@persistent
def ruvmLoadPreHandler(dummy):
    ruvmLib.ruvmBlenderDestroy()

classes = [RUVM_OT_RuvmExportRuvmFile,
           RUVM_OT_RuvmAssign,
           RUVM_OT_RuvmRemove,
           RUVM_OT_RuvmLoadRuvmFile]

#Register
def register():
    
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.depsgraph_update_post.append(ruvmDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.append(ruvmLoadPostHandler)
    bpy.app.handlers.load_pre.append(ruvmLoadPreHandler)

#Unregister
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.app.handlers.depsgraph_update_post.remove(ruvmDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.remove(ruvmLoadPostHandler)
    bpy.app.handlers.load_pre.remove(ruvmLoadPreHandler)
