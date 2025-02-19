import bpy
import ctypes
import numpy
import pdb

class StucVec2(ctypes.Structure):
	_fields_ = [("x", ctypes.c_float),
				("y", ctypes.c_float)]

class StucVec3(ctypes.Structure):
	_fields_ = [("x", ctypes.c_float),
				("y", ctypes.c_float),
				("z", ctypes.c_float)]
	
Stuc_M4x4_F32 = ctypes.c_float * 16

class StucAttribCore(ctypes.Structure):
	_fields_ = [("pData", ctypes.c_void_p),
				#use c_byte instead of c_char, as the latter is immutable
				("name", ctypes.c_byte * 96),
				("type", ctypes.c_int32),
				("use", ctypes.c_int32)]

class StucAttrib(ctypes.Structure):
	_fields_ = [("core", StucAttribCore),
				("origin", ctypes.c_int32),
				("interpolate", ctypes.c_int32)]
	
class StucAttribIndexed(ctypes.Structure):
	_fields_ = [("core", StucAttribCore),
				("size", ctypes.c_int32),
				("count", ctypes.c_int32)]
	
class StucAttribIndexedArr(ctypes.Structure):
	_fields_ = [("pArr", ctypes.POINTER(StucAttribIndexed)),
				("size", ctypes.c_int32),
				("count", ctypes.c_int32)]

class StucAttribArray(ctypes.Structure):
	_fields_ = [("pArr", ctypes.POINTER(StucAttrib)),
				("size", ctypes.c_int32),
				("count", ctypes.c_int32)]
	
class StucObjectData(ctypes.Structure):
	_fields_ = [("type", ctypes.c_int32)]
	
class StucBlenderMapArr(ctypes.Structure):
	_fields_ = [("ppArr", ctypes.POINTER(ctypes.POINTER(ctypes.c_byte))),
				("pMatIdxArr", ctypes.POINTER(ctypes.c_byte)),
				("count", ctypes.c_byte)]

#TODO rename loop attribs here as well
#when working with stuc geo of course. Use loop when
#referncing blender geometry of course
class StucMesh(ctypes.Structure):
	_fields_ = [("type", StucObjectData),
				("pFaces", ctypes.POINTER(ctypes.c_int32)),
				("pLoops", ctypes.POINTER(ctypes.c_int32)),
				("pEdges", ctypes.POINTER(ctypes.c_int32)),
				("meshAttribs", StucAttribArray),
				("faceAttribs", StucAttribArray),
				("loopAttribs", StucAttribArray),
				("edgeAttribs", StucAttribArray),
				("vertAttribs", StucAttribArray),
				("faceCount", ctypes.c_int32),
				("loopCount", ctypes.c_int32),
				("edgeCount", ctypes.c_int32),
				("vertCount", ctypes.c_int32)]
				
	
class StucObject(ctypes.Structure):
	_fields_ = [("pData", ctypes.POINTER(StucObjectData)),
				("transform", Stuc_M4x4_F32)]

class StucBlendConfig(ctypes.Structure):
	_fields_ = [("blend", ctypes.c_int32),
				("opacity", ctypes.c_float),
				("order", ctypes.c_bool)]

class StucCommonAttrib(ctypes.Structure):
	#use c_byte instead of c_char, as the latter is immutable
	_fields_ = [("name", ctypes.c_byte * 96),
				("blendConfig", StucBlendConfig)]

class StucCommonAttribList(ctypes.Structure):
	_fields_ = [("pMesh", ctypes.POINTER(StucCommonAttrib)),
				("pFace", ctypes.POINTER(StucCommonAttrib)),
				("pCorner", ctypes.POINTER(StucCommonAttrib)),
				("pEdge", ctypes.POINTER(StucCommonAttrib)),
				("pVert", ctypes.POINTER(StucCommonAttrib)),
				("meshCount", ctypes.c_int32),
				("faceCount", ctypes.c_int32),
				("cornerCount", ctypes.c_int32),
				("edgeCount", ctypes.c_int32),
				("vertCount", ctypes.c_int32)]
	
class StucUsg(ctypes.Structure):
	_fields_ = [("obj", StucObject),
				("pFlatCutoff", ctypes.POINTER(StucObject))]
	
class StucBlenderMatTable(ctypes.Structure):
	_fields_ = [("pArr", ctypes.POINTER(ctypes.c_byte)),
				("count", ctypes.c_byte)]
	
class StucBlenderMatTableArr(ctypes.Structure):
	_fields_ = [("pArr", ctypes.POINTER(StucBlenderMatTable)),
				("count", ctypes.c_int32)]

def getAttribType(attrib):
	attribType = type(attrib)
	match attribType:
		case bpy.types.BoolAttribute:
			return (0, ctypes.c_int8) #UVS_I8
		case bpy.types.ByteColorAttribute:
			return (18, ctypes.c_int8 * 4) #UVS_V4_I8
		case bpy.types.ByteIntAttribute:
			return (0, ctypes.c_int8) #UVS_I8
		case bpy.types.Float2Attribute:
			return (10, ctypes.c_float * 2) #UVS_V2_F32
		case bpy.types.FloatAttribute:
			return (4, ctypes.c_float) #UVS_F32
		case bpy.types.FloatColorAttribute:
			return (22, ctypes.c_float * 4) #UVS_V4_F32
		case bpy.types.FloatVectorAttribute:
			return (16, ctypes.c_float * 3) #UVS_V3_F32
		case bpy.types.Int2Attribute:
			return (8, ctypes.c_int32 * 2) #UVS_V2_I32
		case bpy.types.IntAttribute:
			return (2, ctypes.c_int32) #UVS_I32
		case bpy.types.QuaternionAttribute:
			return (22, ctypes.c_float * 4) #UVS_V4_F32
		case bpy.types.StringAttribute:
			return (24, ctypes.POINTER(ctypes.c_char)) #UVS_STRING
		case _:
			return None

def getAttribBlenderType(attrib):
	match attrib.core.type:
		#TODO add bool type to UVS lib, as semantics are lost here
		#TODO in general, try include all types, including semantic
		#types, in Blender, Houdini, and USD. This includes unsigned
		#ints, quaternions, etc. If someone puts an attribute in, they need to get the
		#same type out. IMPORTANT: it may be best to split the semantic info off
		#into a separate enum
		case 0: #UVS_I8
			return 'BOOLEAN'
		case 18: #UVS_V4_I8
			return 'BYTE_COLOR' 
		case 0: #UVS_I8
			return 'INT8'
		case 10: #UVS_V2_F32
			return 'FLOAT2'
		case 4: #UVS_F32
			return 'FLOAT'
		case 22: #UVS_V4_F32
			return 'FLOAT_COLOR'
		case 16: #UVS_V3_F32
			return 'FLOAT_VECTOR'
		case 8: #UVS_V2_I32
			return 'INT32_2D'
		case 2: #UVS_I32
			return 'INT'
		case 22: #UVS_V4_F32
			return 'TODO FIX THIS'
		case 24: #UVS_STRING
			return 'STRING' 
		case _:
			return None

def createSingleAttrib(mesh, attrib, domain):
	attribType = getAttribBlenderType(attrib)
	name = ctypes.cast(attrib.core.name, ctypes.c_char_p).value
	mesh.attributes.new(name = name.decode("utf-8"), type = attribType, domain = domain)

def createAttribs(mesh, attribs, domain):
	i = 0
	while (i < attribs.count):
		createSingleAttrib(mesh, attribs.pArr[i], domain)
		i += 1

def createAllAttribs(mesh, stucMesh):
	createAttribs(mesh, stucMesh.faceAttribs, "FACE")
	createAttribs(mesh, stucMesh.loopAttribs, "CORNER")
	#createAttribs(mesh, stucMesh.pEdgeAttribs, stucMesh.edgeAttribCount, "EDGE")
	#createAttribs(mesh, stucMesh.pVertAttribs, stucMesh.vertAttribCount, "POINT")

def getNormalAttrib(mesh):
	i = 0
	while (i < mesh.loopAttribs.count):
		name = ctypes.cast(mesh.loopAttribs.pArr[i].core.name, ctypes.c_char_p).value
		if (name.decode("utf-8") == "normal"):
			return ctypes.pointer(mesh.loopAttribs.pArr[i])
		i += 1
	return None

def getAttribCounts(attribCount, target, getNormals):
	for attrib in target.attributes:
		if '.' in attrib.name or (getNormals and attrib.name == "normal") or\
		attrib.name == "material_index":
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
				


def copyString(dest, src, maxLen):
	length = len(src)
	if (length > maxLen):
		#TODO add proper exception handling in general
		print("string length exceeds max")
		return
	srcUtf8 = src.encode('utf-8')
	i = 0
	while (i < length):
		dest[i] = srcUtf8[i]
		i += 1

def allocAttribs(mesh, attribCounts):
	FaceAttribsArray = StucAttrib * attribCounts["face"]
	mesh.faceAttribs.pArr = FaceAttribsArray()
	LoopAttribsArray = StucAttrib * (attribCounts["loop"] + 3) # +3 for normals, tangents, & tsign
	mesh.loopAttribs.pArr = LoopAttribsArray()
	EdgeAttribsArray = StucAttrib * attribCounts["edge"]
	mesh.edgeAttribs.pArr = EdgeAttribsArray()
	VertAttribsArray = StucAttrib * attribCounts["vert"]
	mesh.vertAttribs.pArr = VertAttribsArray()

def initAttribEntry(attrib, attribEntry, dataLen, metaOnly, interpolate):
	copyString(attribEntry.core.name, attrib.name, 96)
	attribType = getAttribType(attrib)
	attribEntry.core.type = attribType[0]
	attribEntry.interpolate = interpolate
	if not(metaOnly):
		attribData = attrib.data[0].as_pointer()
		attribEntry.core.pData = ctypes.cast(attribData, ctypes.c_void_p)

def initAttribs(mesh, target, metaOnly, getNormals):
	for attrib in target.attributes:
		if '.' in attrib.name or (getNormals and attrib.name == "normal") or\
		attrib.name == "material_index":
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

def setStucMatrix(dest, src):
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

def setBlenderMatrix(blenderMatrix, stucMatrix):
	j = 0
	while j < 4:
		k = 0
		while k < 4:
			linearIndex = k + j * 4
			blenderMatrix[j][k] = stucMatrix[linearIndex]
			k += 1
		j += 1
	blenderMatrix.transpose()

def appendAttrib(attribs, name, type, data):
	attribEntry = attribs.pArr[attribs.count]
	copyString(attribEntry.core.name, name, 96)
	attribEntry.core.type = type
	attribEntry.core.pData = data
	attribs.count += 1

#returns a tuple containing the mesh, and the edges numpy array.
#in order to prevent the reference tot he edge array from becoming invalid
#after the function returns
def formatAsStucMesh(target, metaOnly, getNormals, mats = None, matTable = None):
	mesh = StucMesh()
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
	if (mats):
		attribCount["face"] += 1 #for material indices
	allocAttribs(mesh, attribCount)
	initAttribs(mesh, target, metaOnly, getNormals)

	matIndices = None
	if mats:
		matIndices = numpy.empty(mesh.faceCount, dtype = numpy.int8)
		target.polygons.foreach_get("material_index", matIndices)
		appendAttrib(
			mesh.faceAttribs,
			"StucMaterialIndices",
			0,
			matIndices.ctypes.data_as(ctypes.c_void_p)
		)
	if matTable:
		matTable.count = len(target.materials)
		MatSlots = ctypes.c_byte * matTable.count
		matTable.pArr = MatSlots()
		#list global indices of materials in current object,
		#this will be used as a lookup table, as per face mat indices are obj local
		i = 0
		while i < matTable.count:
			matTable.pArr[i] = list(mats.keys()).index(target.materials[i].name)
			i += 1

	if not getNormals:
		return (mesh, edges)
	#afaik, normals are not accessable as an attribute.
	#atleast not at the time of writing.
	normals = numpy.empty(mesh.loopCount * 3, dtype = numpy.float32)
	target.calc_normals_split()
	target.loops.foreach_get("normal", normals)
	appendAttrib(
		mesh.loopAttribs,
		"normal",
		16, #16 is V3_F32
		normals.ctypes.data_as(ctypes.c_void_p)
	)
	Tangents = StucVec3 * mesh.loopCount
	tangents = Tangents()
	appendAttrib(
		mesh.loopAttribs,
		"StucTangent",
		16,
		ctypes.cast(tangents,
		ctypes.c_void_p)
	)
	TSigns = ctypes.c_float * mesh.loopCount
	tSigns = TSigns()
	appendAttrib(
		mesh.loopAttribs,
		"StucTSign",
		4, #4 is F32
		ctypes.cast(tSigns, ctypes.c_void_p)
	) 
	
	#TODO this is temp, setup a menu to allow user to set use per attrib
	# have defaults though an attrib named 'Color' or 'Col' defaults to Color
	i = 0
	while i < mesh.loopAttribs.count:
		name = mesh.loopAttribs.pArr[i].core.name
		name = ctypes.cast(name, ctypes.c_char_p).value
		name = name.decode("utf-8")
		if name == "Color":
			mesh.loopAttribs.pArr[i].core.use = 1
		i += 1
	#to avoid garbage collection, edges, normals, & matIndices are returned as well
	#is there a better way to do this? TODO maybe make edges, normals, & matIndices
	#out params, so there's a reference in the calling function. Probably cleaner than this.
	return (mesh, edges, normals, matIndices)

def formatAsStucObj(obj, depsgraph, mats = None, matTable = None):
	stucObj = StucObject()
	objEval = obj.evaluated_get(depsgraph)
	meshEval = objEval.data
	meshTuple = formatAsStucMesh(meshEval, False, True, mats, matTable)
	stucObj.pData = ctypes.cast(ctypes.pointer(meshTuple[0]), ctypes.POINTER(StucObjectData))
	setStucMatrix(stucObj.transform, obj.matrix_world)
	#the mesh tuple is returned here as well to ensure the mesh contents arn't garbage collected
	return (stucObj, meshTuple)

def setTargetCommonAttribs(targetAttribs, count, attribs):
	i = 0
	while i < count:
		#TODO make this name conversion a generic function
		name = attribs[i].name
		name = ctypes.cast(name, ctypes.c_char_p).value
		name = name.decode("utf-8")
		entry = targetAttribs.get(name, None)
		if not entry:
			entry = targetAttribs.add()
			entry.name = name
			entry.blend = str(attribs[i].blendConfig.blend)
			entry.opacity = attribs[i].blendConfig.opacity
			entry.order = str(int(attribs[i].blendConfig.order))
		attribs[i].blendConfig.blend = int(entry.blend)
		attribs[i].blendConfig.opacity = entry.opacity
		attribs[i].blendConfig.order = int(entry.order)
		i += 1
		
def findMatInCol(mat, col):
	i = 0
	for item in col:
		if item.mat.name == mat.name:
			return i
		i += 1
	return None

def findObjInCol(obj, col):
	i = 0
	for item in col:
		if item.obj.name == obj.name:
			return i
		i += 1
	return None

def getMatsInStucMats(context, mesh):
	targetMats = []
	for mat in mesh.materials:
		idx = findMatInCol(mat, context.scene.stucMats)
		if idx != None:
			targetMats.append(context.scene.stucMats[idx])
	return targetMats

#remove this and replace references with getAttrib once commonAttrib arrs
#have count included in the struct
def getCommonAttrib(arr, count, name):
	nameUtf8 = name.encode('utf-8')
	i = 0
	while i < count:
		if ctypes.cast(arr[i].core.name, ctypes.c_char_p).value == nameUtf8:
			return arr[i]
		i += 1
	return None

def getAttrib(arr, name):
	nameUtf8 = name.encode('utf-8')
	i = 0
	while i < arr.count:
		if ctypes.cast(arr.pArr[i].core.name, ctypes.c_char_p).value == nameUtf8:
			return arr.pArr[i]
		i += 1
	return None

def updateCommonAttribs(stucLib, context, target, depsgraph):
	objEval = target.obj.evaluated_get(depsgraph)
	meshEval = objEval.data
	#clean common attrib entries for mat's no longer assigned to obj
	for entry in target.commonAttribTable:
		mat = meshEval.materials.get(entry.mat.name, None)
		if not mat:
			target.commonAttribTable.remove(entry)
			
	targetMats = getMatsInStucMats(context, meshEval)
	targetMatCount = len(targetMats)
	if targetMatCount == 0:
		return None
	CommonAttribList = StucCommonAttribList * targetMatCount
	commonAttribList = CommonAttribList()
	meshTuple = formatAsStucMesh(meshEval, True, False, True)
	i = 0
	for mat in targetMats:
		if not len(mat.map):
			continue
		idx = findMatInCol(mat.mat, target.commonAttribTable)
		if idx != None:
			entry = target.commonAttribTable[idx]
		else:
			entry = target.commonAttribTable.add()
			entry.mat = mat.mat
		mapUtf8 = mat.map.encode('utf-8')
		stucLib.stucBlenderQueryCommonAttribs(
			meshTuple[0],
			mapUtf8,
			ctypes.pointer(commonAttribList[i])
		)
		setTargetCommonAttribs(
			entry.faces,
			commonAttribList[i].faceCount,
			commonAttribList[i].pFace
		)
		setTargetCommonAttribs(
			entry.corners,
			commonAttribList[i].cornerCount,
			commonAttribList[i].pCorner
		)
		setTargetCommonAttribs(
			entry.edges,
			commonAttribList[i].edgeCount,
			commonAttribList[i].pEdge
		)
		setTargetCommonAttribs(
			entry.verts,
			commonAttribList[i].vertCount,
			commonAttribList[i].pVert
		)
		i += 1
	return commonAttribList

def copyStucMeshToBlenderMesh(stucLib, mesh, workMesh, outIndexedAttribs, commonAttribs = None):
	if (outIndexedAttribs):
		#TODO this should be done on the c side, in uv-stucco, not uv-stucco-blender.
		#this will make it easier to merge duplicate materials.
		#pass inMesh materials to stucMapToMesh, and it will pass back
		#an outMesh mat arr (in a separate out param), which contains
		#the final material slots, and their mat names.
		outMats = getAttrib(outIndexedAttribs, "StucMaterials")
		StucString = ctypes.c_byte * 64
		outMatsCast = ctypes.cast(outMats.core.pData, ctypes.POINTER(StucString))
		i = 0
		while i < outMats.count:
			matName = ctypes.cast(outMatsCast[i], ctypes.c_char_p).value.decode()
			mat = bpy.data.materials.get(matName, None)
			if not mat:
				#this should throw an error of some kind, or a warning
				#there shouldn't be any dups
				mat = bpy.data.materials.new(name = matName)
			mesh.materials.append(mat)
			i += 1

	mesh.vertices.add(workMesh.vertCount)
	mesh.loops.add(workMesh.loopCount)
	mesh.polygons.add(workMesh.faceCount)
	createAllAttribs(mesh, workMesh)
	meshStucFormat = formatAsStucMesh(mesh, False, False, None)

	stucLib.stucBlenderCopyMeshCore(
		ctypes.pointer(meshStucFormat[0]),
		ctypes.pointer(workMesh)
	)

	matIndices = None
	i = 0
	while i < workMesh.faceAttribs.count:
		name = ctypes.cast(workMesh.faceAttribs.pArr[i].core.name, ctypes.c_char_p).value
		if name == b"StucMaterialIndices":
			matIndices = workMesh.faceAttribs.pArr[i]
			break
		i += 1
	if matIndices:
		matIndicesNumpy = numpy.ctypeslib.as_array(
			ctypes.cast(matIndices.core.pData,
			ctypes.POINTER(ctypes.c_byte)),
			shape = [workMesh.faceCount]
		)
		mesh.polygons.foreach_set("material_index", matIndicesNumpy)

	#meshStuc.uv_layers.new(name="uvmap")
	#uvPtr = meshStuc.uv_layers[0].data[0].as_pointer()
	#stucMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(StucVec2))
	mesh.update()
	meshStucFormat = formatAsStucMesh(mesh, False, False, None)
	stucLib.stucBlenderCopyMeshAttribs(
		ctypes.pointer(meshStucFormat[0]),
		ctypes.pointer(workMesh)
	)
	normalsArraySize = workMesh.loopCount * 3
	normalAttrib = getNormalAttrib(workMesh)
	normalsNumpy = numpy.ctypeslib.as_array(
		ctypes.cast(normalAttrib.contents.core.pData,
		ctypes.POINTER(ctypes.c_float)),
		shape = [normalsArraySize]
	)
	#this is necessary to set custom normals it seems
	mesh.normals_split_custom_set(tuple(zip(*(iter(normalsNumpy),) * 3)))
	mesh.use_auto_smooth = True

def blendObjFromStuc(stucObj, col, name, displayType, isUsg, mats):
	mesh = bpy.data.meshes.new(f"{name}Mesh")
	obj = bpy.data.objects.new(name, mesh)
	col.objects.link(obj)
	meshStuc = ctypes.cast(stucObj.pData, ctypes.POINTER(StucMesh))
	copyStucMeshToBlenderMesh(mesh, meshStuc.contents, mats)
	setBlenderMatrix(obj.matrix_world, stucObj.transform)
	obj.display_type = displayType
	if (isUsg):
		obj['StucUsg'] = isUsg
	return obj

def getUsgCountInSelObjs(context):
	count = 0
	for obj in context.selected_objects:
		isUsg = obj.get("StucUsg", None)
		if isUsg:
			count += 1
	return count