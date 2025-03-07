import bpy
import ctypes
import numpy
from numpy._typing import NDArray
import mathutils
from typing import Any, cast
import pdb
from enum import Enum

STUC_ATTRIB_NAME_MAX_LEN = 96
STUC_ATTRIB_STRING_MAX_LEN = 64

class StucAttribType(Enum):
	I8 = 0
	I16 = 1
	I32 = 2
	I64 = 3
	F32 = 4
	F64 = 5
	V2_I8 = 6
	V2_I16 = 7
	V2_I32 = 8
	V2_I64 = 9
	V2_F32 = 10
	V2_F64 = 11
	V3_I8 = 12
	V3_I16 = 13
	V3_I32 = 14
	V3_I64 = 15
	V3_F32 = 16
	V3_F64 = 17
	V4_I8 = 18
	V4_I16 = 19
	V4_I32 = 20
	V4_I64 = 21
	V4_F32 = 22
	V4_F64 = 23
	STRING = 24
	NONE = 25
	ENUM_COUNT = 26

class StucObjectType(Enum):
	NULL = 0
	MESH = 1
	MESH_INTERN = 2
	MESH_BUF = 3

class StucAttribUse(Enum):
	NONE = 0
	POS = 1
	UV = 2
	NORMAL = 3
	PRESERVE_EDGE = 4
	RECEIVE = 5
	PRESERVE_VERT = 6
	USG = 7
	TANGENT = 8
	TSIGN = 9
	WSCALE = 10
	IDX = 11
	EDGE_LEN = 12
	SEAM_EDGE = 13
	SEAM_VERT = 14
	NUM_ADJ_PRESERVE = 15
	EDGE_CORNERS = 16
	SP_ENUM_COUNT = 17
	COLOR = 18
	MASK = 19
	SCALAR = 20
	ENUM_COUNT = 21

class StucBlendMode(Enum):
	REPLACE = 0
	MULTIPLY = 1
	DIVIDE = 2
	ADD = 3
	SUBTRACT = 4
	ADD_SUB = 5
	LIGHTEN = 6
	DARKEN = 7
	OVERLAY = 8
	SOFT_LIGHT = 9
	COLOR_DODGE = 10
	APPEND = 11

class StucDomain(Enum):
	NONE = 0
	FACE = 1
	CORNER = 2
	EDGE = 3
	VERT = 4

class StucVec2(ctypes.Structure):
	_fields_ = [
		("x", ctypes.c_float),
		("y", ctypes.c_float)
	]

class StucVec3(ctypes.Structure):
	_fields_ = [
		("x", ctypes.c_float),
		("y", ctypes.c_float),
		("z", ctypes.c_float)
	]
	
Stuc_M4x4_F32 = ctypes.c_float * 16

class StucAttribCore(ctypes.Structure):
	_fields_ = [
		("pData", ctypes.c_void_p),
		#use c_byte instead of c_char, as the latter is immutable
		("name", ctypes.c_byte * STUC_ATTRIB_NAME_MAX_LEN),
		("type", ctypes.c_int32),
		("use", ctypes.c_int32)
	]

class StucAttrib(ctypes.Structure):
	_fields_ = [
		("core", StucAttribCore),
		("origin", ctypes.c_int32),
		("copyOpt", ctypes.c_int32),
		("interpolate", ctypes.c_int32)
	]
	
class StucAttribIndexed(ctypes.Structure):
	_fields_ = [
		("core", StucAttribCore),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]
	
class StucAttribIndexedArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucAttribIndexed)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

class StucAttribArray(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucAttrib)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]
	
class StucObjectData(ctypes.Structure):
	_fields_ = [
		("type", ctypes.c_int32)
	]
	
class StucAttribActive(ctypes.Structure):
	_fields_ = [
		("domain", ctypes.c_int32),
		("idx", ctypes.c_int16),
		("active", ctypes.c_bool)
	]

#TODO rename loop attribs here as well
#when working with stuc geo of course. Use loop when
#referncing blender geometry of course
class StucMesh(ctypes.Structure):
	_fields_ = [
		("type", StucObjectData),
		("activeAttribs", StucAttribActive * StucAttribUse.ENUM_COUNT.value),
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
		("vertCount", ctypes.c_int32)
	]
	
class StucObject(ctypes.Structure):
	_fields_ = [
		("pData", ctypes.POINTER(StucObjectData)),
		("transform", Stuc_M4x4_F32)
	]

class StucBlendConfig(ctypes.Structure):
	_fields_ = [
		("fMin", ctypes.c_double),
		("fMax", ctypes.c_double),
		("iMin", ctypes.c_int64),
		("iMax", ctypes.c_int64),
		("blend", ctypes.c_int32),
		("opacity", ctypes.c_float),
		("clamp", ctypes.c_bool),
		("order", ctypes.c_bool)
	]

class StucCommonAttrib(ctypes.Structure):
	#use c_byte instead of c_char, as the latter is immutable
	_fields_ = [
		("name", ctypes.c_byte * STUC_ATTRIB_NAME_MAX_LEN),
		("blendConfig", StucBlendConfig)
	]

class StucCommonAttribArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucCommonAttrib)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

class StucCommonAttribList(ctypes.Structure):
	_fields_ = [
		("mesh", StucCommonAttribArr),
		("face", StucCommonAttribArr),
		("corner", StucCommonAttribArr),
		("edge", StucCommonAttribArr),
		("vert", StucCommonAttribArr),
	]

class StucBlenderMapArr(ctypes.Structure):
	_fields_ = [
		("ppArr", ctypes.POINTER(ctypes.POINTER(ctypes.c_byte))),
		("pMatIdxArr", ctypes.POINTER(ctypes.c_byte)),
		("pCommonAttribArr", ctypes.POINTER(StucCommonAttribList)),
		("count", ctypes.c_int32)
	]
	
class StucUsg(ctypes.Structure):
	_fields_ = [
		("obj", StucObject),
		("pFlatCutoff", ctypes.POINTER(StucObject))
	]
	
class StucBlenderMatTable(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(ctypes.c_byte)),
		("count", ctypes.c_byte)
	]
	
class StucBlenderMatTableArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucBlenderMatTable)),
		("count", ctypes.c_int32)
	]

def getAttribType(attrib: bpy.types.Attribute) -> tuple[int, Any]:
	attribType = type(attrib)
	match attribType:
		case bpy.types.BoolAttribute:
			return (StucAttribType.I8.value, ctypes.c_int8)
		case bpy.types.ByteColorAttribute:
			return (StucAttribType.V4_I8.value, ctypes.c_int8 * 4)
		case bpy.types.ByteIntAttribute:
			return (StucAttribType.I8.value, ctypes.c_int8)
		case bpy.types.Float2Attribute:
			return (StucAttribType.V2_F32.value, ctypes.c_float * 2)
		case bpy.types.FloatAttribute:
			return (StucAttribType.F32.value, ctypes.c_float)
		case bpy.types.FloatColorAttribute:
			return (StucAttribType.V4_F32.value, ctypes.c_float * 4)
		case bpy.types.FloatVectorAttribute:
			return (StucAttribType.V3_F32.value, ctypes.c_float * 3)
		case bpy.types.Int2Attribute:
			return (StucAttribType.V2_I32.value, ctypes.c_int32 * 2)
		case bpy.types.IntAttribute:
			return (StucAttribType.I32.value, ctypes.c_int32)
		case bpy.types.QuaternionAttribute:
			return (StucAttribType.V4_F32.value, ctypes.c_float * 4)
		case bpy.types.StringAttribute:
			return (StucAttribType.STRING.value, ctypes.POINTER(ctypes.c_char))
		case _:
			raise Exception("invalid attrib type")
		
def getAttribUse(
	target: bpy.types.Mesh,
	activeNames: bpy.types.Collection | None,
	attrib: bpy.types.Attribute
) -> int:
	#check overrides first
	if activeNames:
		if attrib.name == activeNames[0].name:
			return StucAttribUse.POS.value
		if len(activeNames[1].name) and attrib.name == activeNames[1].name:
			return StucAttribUse.NORMAL.value
		if attrib.name == activeNames[2].name:
			return StucAttribUse.UV.value
		if attrib.name == activeNames[3].name:
			return StucAttribUse.COLOR.value
	else:
		if attrib.name == "position":
			return StucAttribUse.POS.value

	uv = target.uv_layers.get(attrib.name, None)
	if uv:
		return StucAttribUse.UV.value
	col = target.color_attributes.get(attrib.name, None)
	if col:
		return StucAttribUse.COLOR.value
	
	return StucAttribUse.NONE.value

def getAttribBlenderType(attrib: StucAttrib) -> str:
	match attrib.core.type:
		#TODO add bool type to UVS lib, as semantics are lost here
		#TODO in general, try include all types, including semantic
		#types, in Blender, Houdini, and USD. This includes unsigned
		#ints, quaternions, etc. If someone puts an attribute in, they need to get the
		#same type out. IMPORTANT: it may be best to split the semantic info off
		#into a separate enum
		case StucAttribType.I8.value:
			return 'BOOLEAN'
		case StucAttribType.V4_I8.value:
			return 'BYTE_COLOR' 
		case StucAttribType.I8.value:
			return 'INT8'
		case StucAttribType.V2_F32.value:
			return 'FLOAT2'
		case StucAttribType.F32.value:
			return 'FLOAT'
		case StucAttribType.V4_F32.value:
			return 'FLOAT_COLOR'
		case StucAttribType.V3_F32.value:
			return 'FLOAT_VECTOR'
		case StucAttribType.V2_I32.value:
			return 'INT32_2D'
		case StucAttribType.I32.value:
			return 'INT'
		case StucAttribType.V4_F32.value:
			return 'TODO FIX THIS'
		case StucAttribType.STRING.value:
			return 'STRING' 
		case _:
			raise Exception("invalid attrib type")

def createSingleAttrib(mesh: bpy.types.Mesh, attrib: StucAttrib, domain: str) -> None:
	attribType = getAttribBlenderType(attrib)
	name = ctypes.cast(attrib.core.name, ctypes.c_char_p).value
	if not name:
		raise Exception("attrib name is none")
	mesh.attributes.new(
		name = name.decode("utf-8"),
		type = cast(Any, attribType),
		domain = cast(Any, domain)
	)

def createAttribs(mesh: bpy.types.Mesh, attribs: StucAttrib, domain: str) -> None:
	i = 0
	while (i < attribs.count):
		createSingleAttrib(mesh, attribs.pArr[i], domain)
		i += 1

def createAllAttribs(mesh: bpy.types.Mesh, stucMesh: StucMesh) -> None:
	createAttribs(mesh, stucMesh.faceAttribs, "FACE")
	createAttribs(mesh, stucMesh.loopAttribs, "CORNER")
	#createAttribs(mesh, stucMesh.pEdgeAttribs, stucMesh.edgeAttribCount, "EDGE")
	#createAttribs(mesh, stucMesh.pVertAttribs, stucMesh.vertAttribCount, "POINT")

def getNormalAttrib(mesh: StucMesh) -> StucAttrib:
	i = 0
	while (i < mesh.loopAttribs.count):
		name = ctypes.cast(mesh.loopAttribs.pArr[i].core.name, ctypes.c_char_p).value
		if not name:
			raise Exception("normal attrib name is None")
		if (name.decode("utf-8") == "normal"):
			return mesh.loopAttribs.pArr[i]
		i += 1
	raise Exception("normal attrib not found")

def getAttribCounts(
	attribCount : dict[str, int],
	target: bpy.types.Mesh,
	getNormals: bool
) -> None:
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
			case _:
				raise Exception("invalid attrib domain")

def copyString(dest: bytes, src: str, maxLen: int) -> None:
	length = len(src)
	if (length > maxLen):
		#TODO add proper exception handling in general
		print("string length exceeds max")
		return
	srcUtf8 = src.encode('utf-8')
	i = 0
	while (i < length):
		cast(Any, dest)[i] = srcUtf8[i]
		i += 1

def allocAttribs(mesh: StucMesh, attribCounts: dict[str, int]) -> None:
	FaceAttribsArray = StucAttrib * attribCounts["face"]
	mesh.faceAttribs.pArr = FaceAttribsArray()
	LoopAttribsArray = StucAttrib * (attribCounts["loop"] + 3) # +3 for normals, tangents, & tsign
	mesh.loopAttribs.pArr = LoopAttribsArray()
	EdgeAttribsArray = StucAttrib * attribCounts["edge"]
	mesh.edgeAttribs.pArr = EdgeAttribsArray()
	VertAttribsArray = StucAttrib * attribCounts["vert"]
	mesh.vertAttribs.pArr = VertAttribsArray()

def initAttribEntry(
		attrib: bpy.types.Attribute,
		target: bpy.types.Mesh,
		activeNames: bpy.types.Collection | None,
		attribEntry: StucAttrib,
		metaOnly: bool,
		interpolate: bool
) -> None:
	copyString(attribEntry.core.name, attrib.name, STUC_ATTRIB_NAME_MAX_LEN)
	attribEntry.core.type = getAttribType(attrib)[0]
	attribEntry.core.use = getAttribUse(target, activeNames, attrib)
	attribEntry.interpolate = interpolate
	if not(metaOnly):
		attribData = cast(Any, attrib).data[0].as_pointer()
		attribEntry.core.pData = ctypes.cast(attribData, ctypes.c_void_p)

def isAttribActive(
	target: bpy.types.Mesh,
	attrib: bpy.types.Attribute,
	activeNames: bpy.types.Collection | None
) -> bool:
	if activeNames:
		if attrib.name == activeNames[0].name:
			return True
		if len(activeNames[1].name) and attrib.name == activeNames[1].name:
			return True
		if attrib.name == activeNames[2].name:
			return True
		if attrib.name == activeNames[3].name:
			return True
		
	if attrib.name == "position":
		return True
	for uv in target.uv_layers:
		if uv.active:
			if attrib.name == uv.name:
				return True
			break
	activeColIdx = target.attributes.active_color_index
	if activeColIdx:
		if activeColIdx >= 0 and\
			attrib.name == target.color_attributes[activeColIdx].name:
			return True
	return False

def initAttribs(
	mesh: StucMesh,
	target: bpy.types.Mesh,
	activeNames: bpy.types.Collection | None,
	metaOnly: bool,
	getNormals: bool
) -> None:
	overrideNormal = activeNames and len(activeNames[1].name)
	for attrib in target.attributes:
		if '.' in attrib.name or\
			(getNormals and not overrideNormal and attrib.name == "normal") or\
			attrib.name == "material_index":
			continue
		attribArr = None
		interpolate = False #TODO setting this uniformly right now
		match attrib.domain:
			case 'FACE':
				attribArr = mesh.faceAttribs
				interpolate = False
			case 'CORNER':
				attribArr = mesh.loopAttribs
				interpolate = True
			case 'EDGE':
				attribArr = mesh.edgeAttribs
				interpolate = False
			case 'POINT':
				attribArr = mesh.vertAttribs
				interpolate = True
			case _:
				raise Exception("invalid attrib domain")
		attribEntry = attribArr.pArr[attribArr.count]
		initAttribEntry(
			attrib,
			target,
			activeNames,
			attribEntry,
			metaOnly,
			interpolate
		)
		if attribEntry.core.use and isAttribActive(target, attrib, activeNames):
			mesh.activeAttribs[attribEntry.core.use].active = True
			mesh.activeAttribs[attribEntry.core.use].idx = attribArr.count
		attribArr.count += 1

def setStucMatrix(dest: ctypes.Array[ctypes.c_float], src: mathutils.Matrix) -> None:
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

def setBlenderMatrix(dest: mathutils.Matrix, src: ctypes.Array[ctypes.c_float]) -> None:
	j = 0
	while j < 4:
		k = 0
		while k < 4:
			linearIndex = k + j * 4
			dest[j][k] = src[linearIndex]
			k += 1
		j += 1
	dest.transpose()

def appendAttrib(
	attribs: StucAttribArray,
	name: str,
	type: int,
	use: int,
	data: ctypes.c_void_p,
	activeAttribs: ctypes.Array[StucAttribActive] | None = None
) -> None:
	attribEntry = attribs.pArr[attribs.count]
	copyString(attribEntry.core.name, name, STUC_ATTRIB_NAME_MAX_LEN)
	attribEntry.core.type = type
	attribEntry.core.use = use
	if activeAttribs:
		#attrib is active
		activeAttribs[use].active = True
		activeAttribs[use].idx = attribs.count
	attribEntry.core.pData = data
	attribs.count += 1

#returns a tuple containing the mesh, and the edges numpy array.
#in order to prevent the reference tot he edge array from becoming invalid
#after the function returns
def formatAsStucMesh(
	target: bpy.types.Mesh,
	metaOnly: bool,
	getNormals: bool,
	mats: bool = False,
	activeNames: bpy.types.Collection | None = None
) -> tuple[StucMesh, NDArray[Any], ctypes.c_void_p | None, NDArray[Any] | None]:
	mesh = StucMesh()
	mesh.type.type = StucObjectType.MESH.value

	mesh.faceCount = len(target.polygons)
	mesh.loopCount = len(target.loops)
	mesh.edgeCount = len(target.edges)
	mesh.vertCount = len(target.vertices)

	facesPtr = target.polygons[0].as_pointer()
	mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int32))

	loopsPtr = target.loops[0].as_pointer()
	mesh.pLoops = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int32))

	edges = numpy.empty(mesh.loopCount, dtype = numpy.int32)
	target.loops.foreach_get("edge_index", cast(Any, edges))
	mesh.pEdges = edges.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))

	attribCount = {"face" : 0, "loop" : 0, "edge" : 0, "vert" : 0}
	getAttribCounts(attribCount, target, getNormals)
	if mats:
		attribCount["face"] += 1 #for material indices
	allocAttribs(mesh, attribCount)
	initAttribs(mesh, target, activeNames, metaOnly, getNormals)

	matIndices = None
	if mats:
		matIndices = numpy.empty(mesh.faceCount, dtype = numpy.int8)
		target.polygons.foreach_get("material_index", cast(Any, matIndices))
		appendAttrib(
			mesh.faceAttribs,
			"materials",
			0,
			StucAttribUse.IDX.value,
			matIndices.ctypes.data_as(ctypes.c_void_p),
			mesh.activeAttribs
		)

	if not getNormals:
			return (mesh, edges, None, None)
	normals = None
	if not mesh.activeAttribs[StucAttribUse.NORMAL.value].active:
		#normal attrib wasn't overriden, so we need to add it
		
		#afaik, normals are not accessable as an attribute.
		#atleast not at the time of writing.
		if bpy.app.version < (4, 1, 0) and not len(target.corner_normals):
			target.calc_normals_split() #type:ignore
		normalsPtr = target.corner_normals[0].as_pointer()
		normals = ctypes.cast(normalsPtr, ctypes.c_void_p)
			
		appendAttrib(
			mesh.loopAttribs,
			"normal",
			StucAttribType.V3_F32.value,
			StucAttribUse.NORMAL.value,
			normals,
			mesh.activeAttribs
		)

	#to avoid garbage collection, edges, normals, & matIndices are returned as well
	#is there a better way to do this? TODO maybe make edges, normals, & matIndices
	#out params, so there's a reference in the calling function. Probably cleaner than this.
	return (mesh, edges, normals, matIndices)

def formatAsStucObj(
	obj: bpy.types.Object,
	depsgraph: bpy.types.Depsgraph,
	mats: bool = False,
	matDict: dict[str, int] | None = None,
	matTable: StucBlenderMatTableArr | None = None,
	activeNames: bpy.types.Collection | None = None
) -> tuple[StucObject, tuple[StucMesh, NDArray[Any], ctypes.c_void_p | None, NDArray[Any] | None]]:
	stucObj = StucObject()
	objEval = obj.evaluated_get(depsgraph)
	meshEval = objEval.data
	if type(meshEval) != bpy.types.Mesh:
		raise Exception("object is not a mesh")
	meshTuple = formatAsStucMesh(meshEval, False, True, mats, activeNames)
	if matTable and matDict:
		matTable.count = len(meshEval.materials)
		MatSlots = ctypes.c_byte * matTable.count
		matTable.pArr = MatSlots()
		#list global indices of materials in current object,
		#this will be used as a lookup table, as per face mat indices are obj local
		i = 0
		while i < matTable.count:
			mat = meshEval.materials[i]
			if not mat:
				raise Exception("material in matTable is None")
			matTable.pArr[i] = list(matDict.keys()).index(mat.name)
			i += 1
	stucObj.pData = ctypes.cast(ctypes.pointer(meshTuple[0]), ctypes.POINTER(StucObjectData))
	setStucMatrix(stucObj.transform, obj.matrix_world)
	#the mesh tuple is returned here as well to ensure the mesh contents arn't garbage collected
	return (stucObj, meshTuple)

def setTargetCommonAttribs(
	targetAttribs: bpy.types.Collection,
	attribs: StucCommonAttribArr
):
	i = 0
	while i < attribs.count:
		#TODO make this name conversion a generic function
		name = attribs.pArr[i].name
		name = ctypes.cast(name, ctypes.c_char_p).value
		if not name:
			raise Exception("name is None")
		name = name.decode("utf-8")
		entry = targetAttribs.get(name, None)
		if not entry:
			entry = targetAttribs.add() #type:ignore
			entry.name = name
			entry.blend = str(attribs.pArr[i].blendConfig.blend)
			entry.opacity = attribs.pArr[i].blendConfig.opacity
			entry.order = str(int(attribs.pArr[i].blendConfig.order))
		attribs.pArr[i].blendConfig.blend = int(entry.blend)
		attribs.pArr[i].blendConfig.opacity = entry.opacity
		attribs.pArr[i].blendConfig.order = int(entry.order)
		i += 1

def findMatInCol(
	mat: bpy.types.Material,
	col: bpy.types.Collection
) -> int | None:
	i = 0
	for item in col:
		if item.mat and item.mat.name == mat.name:
			return i
		i += 1
	return None

def findObjInCol(
	obj: bpy.types.Object,
	col: bpy.types.Collection
) -> int | None:
	i = 0
	for item in col:
		if item.obj.name == obj.name:
			return i
		i += 1
	return None

def getMatsInStucMats(context: bpy.types.Context, mesh: bpy.types.Mesh) -> list[Any]:
	targetMats = []
	for mat in mesh.materials:
		idx = findMatInCol(mat, cast(Any, context.scene).stucMats)
		if idx != None:
			targetMats.append(cast(Any, context.scene).stucMats[idx])
	return targetMats

def getAttrib(arr: StucAttribIndexedArr, name: str) -> StucAttribIndexed:
	nameUtf8 = name.encode('utf-8')
	i = 0
	while i < arr.count:
		if ctypes.cast(arr.pArr[i].core.name, ctypes.c_char_p).value == nameUtf8:
			return arr.pArr[i]
		i += 1
	raise

from . import UvStuccoB_Props as stucBProps
def updateCommonAttribs(
		stucLib: ctypes.CDLL,
		activeNames: bpy.types.Collection,
		context: bpy.types.Context,
		target: stucBProps.StucTarget,
		depsgraph: bpy.types.Depsgraph
) -> ctypes.Array[StucCommonAttribList] | None:
	objEval = cast(bpy.types.Object, target.obj).evaluated_get(depsgraph)
	meshEval = objEval.data
	if type(meshEval) != bpy.types.Mesh:
		raise Exception("target object isn't a mesh")
	#clean common attrib entries for mat's no longer assigned to obj
	for entry in target.commonAttribTable: #type:ignore
		mat = meshEval.materials.get(entry.mat.name, None)
		if not mat:
			target.commonAttribTable.remove(entry) #type:ignore
			
	targetMats = getMatsInStucMats(context, meshEval)
	targetMatCount = len(targetMats)
	if targetMatCount == 0:
		return None
	CommonAttribList = StucCommonAttribList * targetMatCount
	commonAttribList = CommonAttribList()
	meshTuple = formatAsStucMesh(meshEval, True, False, True, activeNames)
	i = 0
	for mat in targetMats:
		if not len(mat.map):
			continue
		idx = findMatInCol(mat.mat, cast(Any, target).commonAttribTable)
		if idx != None:
			entry = target.commonAttribTable[idx] #type:ignore
		else:
			entry = target.commonAttribTable.add() #type:ignore
			entry.mat = mat.mat
		mapUtf8 = mat.map.encode('utf-8')
		stucLib.stucBlenderQueryCommonAttribs(
			meshTuple[0],
			mapUtf8,
			ctypes.pointer(commonAttribList[i])
		)
		setTargetCommonAttribs(
			entry.faces,
			commonAttribList[i].face,
		)
		setTargetCommonAttribs(
			entry.corners,
			commonAttribList[i].corner,
		)
		setTargetCommonAttribs(
			entry.edges,
			commonAttribList[i].edge,
		)
		setTargetCommonAttribs(
			entry.verts,
			commonAttribList[i].vert,
		)
		i += 1
	return commonAttribList

def copyStucMeshToBlenderMesh(
		stucLib: ctypes.CDLL,
		mesh: bpy.types.Mesh,
		workMesh: StucMesh,
		outIndexedAttribs: StucAttribIndexedArr | None = None
) -> None:
	if (outIndexedAttribs):
		#TODO this should be done on the c side, in uv-stucco, not uv-stucco-blender.
		#this will make it easier to merge duplicate materials.
		#pass inMesh materials to stucMapToMesh, and it will pass back
		#an outMesh mat arr (in a separate out param), which contains
		#the final material slots, and their mat names.
		outMats = getAttrib(outIndexedAttribs, "materials")
		StucString = ctypes.c_byte * STUC_ATTRIB_STRING_MAX_LEN
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
	meshStucFormat = formatAsStucMesh(mesh, False, False)

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
		mesh.polygons.foreach_set("material_index", cast(Any, matIndicesNumpy))

	#meshStuc.uv_layers.new(name="uvmap")
	#uvPtr = meshStuc.uv_layers[0].data[0].as_pointer()
	#stucMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(StucVec2))
	mesh.update()
	meshStucFormat = formatAsStucMesh(mesh, False, False)
	stucLib.stucBlenderCopyMeshAttribs(
		ctypes.pointer(meshStucFormat[0]),
		ctypes.pointer(workMesh)
	)
	normalAttrib = getNormalAttrib(workMesh)
	normalsNumpy = numpy.ctypeslib.as_array(
		ctypes.cast(normalAttrib.core.pData,
		ctypes.POINTER(ctypes.c_float)),
		shape = [workMesh.loopCount, 3]
	)
	mesh.normals_split_custom_set(cast(Any, normalsNumpy))
	if (bpy.app.version < (4, 1, 0)):
		mesh.use_auto_smooth = True #type:ignore

def blendObjFromStuc(
		stucLib: ctypes.CDLL,
		stucObj: StucObject,
		col: bpy.types.Collection,
		name: str, displayType: str,
		isUsg: bool,
		mats: StucAttribIndexedArr | None = None
) -> bpy.types.Object:
	mesh = bpy.data.meshes.new(f"{name}Mesh")
	obj = bpy.data.objects.new(name, mesh)
	col.objects.link(obj)
	meshStuc = ctypes.cast(stucObj.pData, ctypes.POINTER(StucMesh))
	copyStucMeshToBlenderMesh(stucLib, mesh, meshStuc.contents, mats)
	setBlenderMatrix(obj.matrix_world, stucObj.transform)
	obj.display_type = cast(Any, displayType)
	if isUsg:
		obj['StucUsg'] = isUsg
	return obj

def getUsgCountInSelObjs(context: bpy.types.Context) -> int:
	count = 0
	for obj in context.selected_objects:
		isUsg = obj.get("StucUsg", None)
		if isUsg:
			count += 1
	return count