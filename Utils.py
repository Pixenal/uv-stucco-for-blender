import bpy
import ctypes
import numpy

class RuvmVec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float),
                ("y", ctypes.c_float)]

class RuvmVec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float),
                ("y", ctypes.c_float),
                ("z", ctypes.c_float)]
    
Ruvm_M4x4_F32 = ctypes.c_float * 16

class RuvmAttrib(ctypes.Structure):
    _fields_ = [("pData", ctypes.c_void_p),
                #use c_byte instead of c_char, as the latter is immutable
                ("name", ctypes.c_byte * 96),
                ("type", ctypes.c_int32),
                ("origin", ctypes.c_int32),
                ("interpolate", ctypes.c_int32)]
    
class RuvmAttribIndexed(ctypes.Structure):
    _fields_ = [("pData", ctypes.c_void_p),
                ("name", ctypes.c_byte * 96),
                ("type", ctypes.c_int32),
                ("count", ctypes.c_int32)]

class RuvmAttribArray(ctypes.Structure):
    _fields_ = [("pArr", ctypes.POINTER(RuvmAttrib)),
                ("count", ctypes.c_int32),
                ("size", ctypes.c_int32)]
    
class RuvmAttribIndexedArr(ctypes.Structure):
    _fields_ = [("pArr", ctypes.POINTER(RuvmAttribIndexed)),
                ("count", ctypes.c_int32),
                ("size", ctypes.c_int32)]
    
class RuvmObjectData(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int32)]

class RuvmMesh(ctypes.Structure):
    _fields_ = [("type", RuvmObjectData),
                ("meshAttribs", RuvmAttribArray),
                ("faceCount", ctypes.c_int32),
                ("pFaces", ctypes.POINTER(ctypes.c_int32)),
                ("faceAttribs", RuvmAttribArray),
                ("loopCount", ctypes.c_int32),
                ("pLoops", ctypes.POINTER(ctypes.c_int32)),
                ("loopAttribs", RuvmAttribArray),
                ("edgeCount", ctypes.c_int32),
                ("pEdges", ctypes.POINTER(ctypes.c_int32)),
                ("edgeAttribs", RuvmAttribArray),
                ("vertCount", ctypes.c_int32),
                ("vertAttribs", RuvmAttribArray)]
    
class RuvmObject(ctypes.Structure):
    _fields_ = [("pData", ctypes.POINTER(RuvmObjectData)),
                ("transform", Ruvm_M4x4_F32)]

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
    
class RuvmUsg(ctypes.Structure):
    _fields_ = [("obj", RuvmObject),
                ("pFlatCutoff", ctypes.POINTER(RuvmObject))]

def getTargetMapAsUtf8(target):
    map = bpy.context.scene.uvsMaps.get(target.map, None)
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



def getAttribCounts(attribCount, target, getNormals):
    for attrib in target.attributes:
        if '.' in attrib.name or (getNormals and attrib.name == "normal"):
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
    mesh.faceAttribs.pArr = FaceAttribsArray()
    LoopAttribsArray = RuvmAttrib * (attribCounts["loop"] + 3) # +3 for normals, tangents, & tsign
    mesh.loopAttribs.pArr = LoopAttribsArray()
    EdgeAttribsArray = RuvmAttrib * attribCounts["edge"]
    mesh.edgeAttribs.pArr = EdgeAttribsArray()
    VertAttribsArray = RuvmAttrib * attribCounts["vert"]
    mesh.vertAttribs.pArr = VertAttribsArray()

def initAttribEntry(attrib, attribEntry, dataLen, metaOnly, interpolate):
    copyAttribName(attribEntry.name, attrib.name)
    attribType = getAttribType(attrib)
    attribEntry.type = attribType[0]
    attribEntry.interpolate = interpolate
    if not(metaOnly):
        attribData = attrib.data[0].as_pointer()
        attribEntry.pData = ctypes.cast(attribData, ctypes.c_void_p)

def initAttribs(mesh, target, metaOnly, getNormals):
    for attrib in target.attributes:
        if '.' in attrib.name or (getNormals and attrib.name == "normal"):
            continue
        match attrib.domain:
            case 'FACE':
                attribEntry = mesh.faceAttribs.pArr[mesh.faceAttribs.count]
                initAttribEntry(attrib, attribEntry, mesh.faceCount, metaOnly, 0)
                mesh.faceAttribs.count += 1
            case 'CORNER':
                attribEntry = mesh.loopAttribs.pArr[mesh.loopAttribs.count]
                initAttribEntry(attrib, attribEntry, mesh.loopCount, metaOnly, 1)
                mesh.loopAttribs.count += 1
            case 'EDGE':
                attribEntry = mesh.edgeAttribs.pArr[mesh.edgeAttribs.count]
                initAttribEntry(attrib, attribEntry, mesh.edgeCount, metaOnly, 0)
                mesh.edgeAttribs.count += 1
            case 'POINT':
                attribEntry = mesh.vertAttribs.pArr[mesh.vertAttribs.count]
                initAttribEntry(attrib, attribEntry, mesh.vertCount, metaOnly, 0)
                mesh.vertAttribs.count += 1

def setRuvmMatrix(dest, src):
    matWorld = src.copy()
    matWorld.transpose()
    j = 0
    while j < 4:
        k = 0
        while k < 4:
            linearIndex = k + j * 4
            dest[linearIndex] = matWorld[j][k]
            k += 1
        j += 1

def setBlenderMatrix(blenderMatrix, uvsMatrix):
    j = 0
    while j < 4:
        k = 0
        while k < 4:
            linearIndex = k + j * 4
            blenderMatrix[j][k] = uvsMatrix[linearIndex]
            k += 1
        j += 1
    blenderMatrix.transpose()

def appendAttrib(attribs, name, type, data):
    attribEntry = attribs.pArr[attribs.count]
    copyAttribName(attribEntry.name, name)
    attribEntry.type = type
    attribEntry.pData = data
    attribs.count += 1

#returns a tuple containing the mesh, and the edges numpy array.
#in order to prevent the reference tot he edge array from becoming invalid
#after the function returns
def formatAsRuvmMesh(target, metaOnly, getMatIndices, getNormals):
    mesh = RuvmMesh()
    mesh.type.type = 1

    mesh.faceCount = len(target.polygons)
    mesh.loopCount = len(target.loops)
    mesh.edgeCount = len(target.edges)
    mesh.vertCount = len(target.vertices)

    facesPtr = target.polygons[0].as_pointer()
    mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int32))

    loopsPtr = target.loops[0].as_pointer()
    mesh.pLoops = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int32))

    edges = numpy.empty(mesh.loopCount, dtype = numpy.int32)
    target.loops.foreach_get("edge_index", edges)
    mesh.pEdges = edges.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))

    attribCount = {"face" : 0, "loop" : 0, "edge" : 0, "vert" : 0}
    getAttribCounts(attribCount, target, getNormals)
    if (getMatIndices):
        attribCount["face"] += 1 #for material indices
    allocAttribs(mesh, attribCount)
    initAttribs(mesh, target, metaOnly, getNormals)

    if getMatIndices:
        matIndices = numpy.empty(mesh.faceCount, dtype = numpy.int32)
        target.polygons.foreach_get("material_index", matIndices)
        appendAttrib(mesh.faceAttribs, "RuvmMaterialIndices", 2, matIndices.ctypes.data_as(ctypes.c_void_p))

    if not getNormals:
        return (mesh, edges)
    #afaik, normals are not accessable as an attribute.
    #atleast not at the time of writing.
    normals = numpy.empty(mesh.loopCount * 3, dtype = numpy.float32)
    target.calc_normals_split()
    target.loops.foreach_get("normal", normals)
    appendAttrib(mesh.loopAttribs, "normal", 16, #16 is V3_F32
                 normals.ctypes.data_as(ctypes.c_void_p))
    Tangents = RuvmVec3 * mesh.loopCount
    tangents = Tangents()
    appendAttrib(mesh.loopAttribs, "RuvmTangent", 16, ctypes.cast(tangents, ctypes.c_void_p))
    TSigns = ctypes.c_float * mesh.loopCount
    tSigns = TSigns()
    appendAttrib(mesh.loopAttribs, "RuvmTSign", 4, ctypes.cast(tSigns, ctypes.c_void_p)) #4 is F32
    #to avoid garbage collection, edges and normals are returned as well
    return (mesh, edges, normals)

def formatAsRuvmObj(obj, depsgraph, getMatIndices):
    uvsObj = RuvmObject()
    objEval = obj.evaluated_get(depsgraph)
    meshEval = objEval.data
    meshTuple = formatAsRuvmMesh(meshEval, False, getMatIndices, True)
    uvsObj.pData = ctypes.cast(ctypes.pointer(meshTuple[0]), ctypes.POINTER(RuvmObjectData))
    setRuvmMatrix(uvsObj.transform, obj.matrix_world)
    #the mesh tuple is returned here as well to ensure the mesh contents arn't garbage collected
    return (uvsObj, meshTuple)