'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import bpy
import ctypes
from typing import Any, cast
import pdb

from . import stuc
from . import utils
from . import mesh_utils as meshUtils

def pyStrFromC(cStr: Any) -> str:
	namePtr = ctypes.cast(cStr, ctypes.c_char_p)
	if not namePtr.value:
		raise Exception("invalid c string")
	return namePtr.value.decode('utf-8')

def getAttribType(attrib: bpy.types.Attribute) -> tuple[int, Any]:
	attribType = type(attrib)
	match attribType:
		case bpy.types.BoolAttribute:
			return (stuc.StucAttribType.I8.value, ctypes.c_int8)
		case bpy.types.ByteColorAttribute:
			return (stuc.StucAttribType.V4_I8.value, ctypes.c_int8 * 4)
		case bpy.types.ByteIntAttribute:
			return (stuc.StucAttribType.I8.value, ctypes.c_int8)
		case bpy.types.Float2Attribute:
			return (stuc.StucAttribType.V2_F32.value, ctypes.c_float * 2)
		case bpy.types.FloatAttribute:
			return (stuc.StucAttribType.F32.value, ctypes.c_float)
		case bpy.types.FloatColorAttribute:
			return (stuc.StucAttribType.V4_F32.value, ctypes.c_float * 4)
		case bpy.types.FloatVectorAttribute:
			return (stuc.StucAttribType.V3_F32.value, ctypes.c_float * 3)
		case bpy.types.Int2Attribute:
			return (stuc.StucAttribType.V2_I32.value, ctypes.c_int32 * 2)
		case bpy.types.IntAttribute:
			return (stuc.StucAttribType.I32.value, ctypes.c_int32)
		case bpy.types.QuaternionAttribute:
			return (stuc.StucAttribType.V4_F32.value, ctypes.c_float * 4)
		case bpy.types.StringAttribute:
			return (stuc.StucAttribType.STRING.value, ctypes.POINTER(ctypes.c_char))
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
			return stuc.StucAttribUse.POS.value
		if len(activeNames[1].name) and attrib.name == activeNames[1].name:
			return stuc.StucAttribUse.NORMAL.value
		if attrib.name == activeNames[2].name:
			return stuc.StucAttribUse.UV.value
		if attrib.name == activeNames[3].name:
			return stuc.StucAttribUse.COLOR.value
		if attrib.name == activeNames[4].name:
			return stuc.StucAttribUse.PRESERVE_EDGE.value
		if attrib.name == activeNames[5].name:
			return stuc.StucAttribUse.PRESERVE_VERT.value
		if attrib.name == activeNames[6].name:
			return stuc.StucAttribUse.RECEIVE.value
		if attrib.name == activeNames[7].name:
			return stuc.StucAttribUse.WSCALE.value
	else:
		if attrib.name == "position":
			return stuc.StucAttribUse.POS.value

	uv = target.uv_layers.get(attrib.name, None)
	if uv:
		return stuc.StucAttribUse.UV.value
	col = target.color_attributes.get(attrib.name, None)
	if col:
		return stuc.StucAttribUse.COLOR.value
	
	return stuc.StucAttribUse.NONE.value

def getAttribBlenderType(attrib: stuc.StucAttrib) -> str:
	match attrib.core.type:
		#TODO add bool type to UVS lib, as semantics are lost here
		#TODO in general, try include all types, including semantic
		#types, in Blender, Houdini, and USD. This includes unsigned
		#ints, quaternions, etc. If someone puts an attribute in, they need to get the
		#same type out. IMPORTANT: it may be best to split the semantic info off
		#into a separate enum
		case stuc.StucAttribType.I8.value:
			return 'BOOLEAN'
		case stuc.StucAttribType.V4_I8.value:
			return 'BYTE_COLOR' 
		case stuc.StucAttribType.I8.value:
			return 'INT8'
		case stuc.StucAttribType.V2_F32.value:
			return 'FLOAT2'
		case stuc.StucAttribType.F32.value:
			return 'FLOAT'
		case stuc.StucAttribType.V4_F32.value:
			return 'FLOAT_COLOR'
		case stuc.StucAttribType.V3_F32.value:
			return 'FLOAT_VECTOR'
		case stuc.StucAttribType.V2_I32.value:
			return 'INT32_2D'
		case stuc.StucAttribType.I32.value:
			return 'INT'
		case stuc.StucAttribType.V4_F32.value:
			return 'TODO FIX THIS'
		case stuc.StucAttribType.STRING.value:
			return 'STRING' 
		case _:
			raise Exception("invalid attrib type")

def createSingleAttrib(mesh: bpy.types.Mesh, attrib: stuc.StucAttrib, domain: str) -> None:
	attribType = getAttribBlenderType(attrib)
	name = ctypes.cast(attrib.core.name, ctypes.c_char_p).value
	if not name:
		raise Exception("attrib name is none")
	mesh.attributes.new(
		name = name.decode("utf-8"),
		type = cast(Any, attribType),
		domain = cast(Any, domain)
	)

def createAttribs(mesh: bpy.types.Mesh, attribs: stuc.StucAttrib, domain: str) -> None:
	i = 0
	while (i < attribs.count):
		createSingleAttrib(mesh, attribs.pArr[i], domain)
		i += 1

def createAllAttribs(mesh: bpy.types.Mesh, stucMesh: stuc.StucMesh) -> None:
	createAttribs(mesh, stucMesh.faceAttribs, "FACE")
	createAttribs(mesh, stucMesh.cornerAttribs, "CORNER")
	#createAttribs(mesh, stuc.StucMesh.pEdgeAttribs, stuc.StucMesh.edgeAttribCount, "EDGE")
	#createAttribs(mesh, stuc.StucMesh.pVertAttribs, stuc.StucMesh.vertAttribCount, "POINT")

def getNormalAttrib(mesh: stuc.StucMesh) -> stuc.StucAttrib:
	i = 0
	while (i < mesh.cornerAttribs.count):
		name = ctypes.cast(mesh.cornerAttribs.pArr[i].core.name, ctypes.c_char_p).value
		if not name:
			raise Exception("normal attrib name is None")
		if (name.decode("utf-8") == "normal"):
			return mesh.cornerAttribs.pArr[i]
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
				attribCount["corner"] += 1
			case 'EDGE':
				attribCount["edge"] += 1
			case 'POINT':
				attribCount["vert"] += 1
			case _:
				raise Exception("invalid attrib domain")
			
def allocAttribs(mesh: stuc.StucMesh, attribCounts: dict[str, int]) -> None:
	FaceAttribsArray = stuc.StucAttrib * (attribCounts["face"] + 1)
	mesh.faceAttribs.pArr = FaceAttribsArray()
	CornerAttribsArray = stuc.StucAttrib * (attribCounts["corner"] + 4)# +4 for normals, tangents, tsign, & select
	mesh.cornerAttribs.pArr = CornerAttribsArray()
	EdgeAttribsArray = stuc.StucAttrib * (attribCounts["edge"] + 2)# +2 for edge corners/verts and select
	mesh.edgeAttribs.pArr = EdgeAttribsArray()
	VertAttribsArray = stuc.StucAttrib * (attribCounts["vert"] + 1) # +1 for vert normals
	mesh.vertAttribs.pArr = VertAttribsArray()

def initAttribEntry(
		attrib: bpy.types.Attribute,
		target: bpy.types.Mesh,
		activeNames: bpy.types.Collection | None,
		attribEntry: stuc.StucAttrib,
		metaOnly: bool,
		interpolate: bool
) -> None:
	utils.copyString(attribEntry.core.name, attrib.name, stuc.STUC_ATTRIB_NAME_MAX_LEN)
	attribEntry.core.type = getAttribType(attrib)[0]
	attribEntry.core.use = getAttribUse(target, activeNames, attrib)
	attribEntry.copyOpt = stuc.StucAttribCopyOpt.COPY.value
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
		if attrib.name == activeNames[4].name:
			return True
		if attrib.name == activeNames[5].name:
			return True
		if attrib.name == activeNames[6].name:
			return True
		if attrib.name == activeNames[7].name:
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
	mesh: stuc.StucMesh,
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
				attribArr = mesh.cornerAttribs
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
		if attribEntry.core.use != stuc.StucAttribUse.NONE.value and\
			isAttribActive(target, attrib, activeNames):

			mesh.activeAttribs[attribEntry.core.use].active = True
			mesh.activeAttribs[attribEntry.core.use].idx = attribArr.count
		attribArr.count += 1

def appendAttrib(
	attribs: stuc.StucAttribArray,
	name: str,
	type: int,
	use: int,
	data: ctypes.c_void_p,
	activeAttribs: ctypes.Array[stuc.StucAttribActive] | None = None,
	domain: stuc.StucDomain | None = None
) -> stuc.StucAttrib:
	attribEntry = attribs.pArr[attribs.count]
	utils.copyString(attribEntry.core.name, name, stuc.STUC_ATTRIB_NAME_MAX_LEN)
	attribEntry.core.type = type
	attribEntry.core.use = use
	if activeAttribs:
		#attrib is active
		activeAttribs[use].active = True
		activeAttribs[use].idx = attribs.count
		if (domain):
			activeAttribs[use].domain = domain.value
	attribEntry.core.pData = data
	attribs.count += 1
	return attribEntry

def setTargetCommonAttribs(
	targetAttribs: bpy.types.Collection,
	attribs: stuc.StucBlendOptArr,
	meshAttribs : stuc.StucAttribArray
) -> None:
	i = 0
	while i < attribs.count:
		attribIdx = attribs.pArr[i].attrib
		name = meshAttribs.pArr[attribIdx].core.name
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

def getIdxAttrib(
	arr: stuc.StucAttribIndexedArr,
	name: bytes
) -> stuc.StucAttribIndexed:
	i = 0
	while i < arr.count:
		if ctypes.cast(arr.pArr[i].core.name, ctypes.c_char_p).value == name:
			return arr.pArr[i]
		i += 1
	raise Exception("attrib doesn't exist")

def getAttribFromUse(
	arr: stuc.StucAttribArray,
	use: int
) -> stuc.StucAttrib | None:
	i = 0
	while i < arr.count:
		if arr.pArr[i].core.use == use:
			return arr.pArr[i]
		i += 1
	return None

def getAttribArr(
	mesh: stuc.StucMesh,
	domain: int
) -> stuc.StucAttribArray:
	match domain:
		case stuc.StucDomain.FACE.value:
			return mesh.faceAttribs
		case stuc.StucDomain.CORNER.value:
			return mesh.cornerAttribs
		case stuc.StucDomain.EDGE.value:
			return mesh.edgeAttribs
		case stuc.StucDomain.VERT.value:
			return mesh.vertAttribs
		case _:
			raise Exception("invalid domain")
		
def getActiveAttrib(
	mesh: stuc.StucMesh,
	use: stuc.StucAttribUse
) -> stuc.StucAttrib | None:
	activeEntry = mesh.activeAttribs[use.value]
	if not activeEntry.active:
		return None
	attribArr = getAttribArr(mesh, activeEntry.domain)
	return getAttribFromUse(attribArr, use.value)

def updateCommonAttribs(
		stucLib: ctypes.CDLL,
		context: bpy.types.Context,
		obj: bpy.types.Object,
		table: bpy.types.Collection,
		activeNames: bpy.types.Collection,
		depsgraph: bpy.types.Depsgraph | None,
) -> ctypes.Array[ctypes.Array[stuc.StucBlendOptArr]] | None:
	if depsgraph:
		objEval = obj.evaluated_get(depsgraph)
	else:
		objEval = obj
	meshEval = objEval.data
	if type(meshEval) != bpy.types.Mesh:
		raise Exception("target object isn't a mesh")
	#clean common attrib entries for mat's no longer assigned to obj
	i = 0
	for entry in table: #type:ignore
		mat = meshEval.materials.get(entry.mat.name, None)
		if not mat:
			table.remove(i) #type:ignore
			i -= 1
		i += 1
			
	targetMats = utils.getMatsInStucMats(context, meshEval)
	targetMatCount = len(targetMats)
	if targetMatCount == 0:
		return None
	commonAttribList = (stuc.StucBlendOptDomainArrs * targetMatCount)()
	meshTuple = meshUtils.formatAsStucMesh(meshEval, True, False, True, activeNames)
	i = 0
	for mat in targetMats:
		if not len(mat.map):
			continue
		stucLib.stucBlenderMapHandleGet.restype = ctypes.c_void_p
		mapHandle = stucLib.stucBlenderMapHandleGet(mat.map.encode('utf-8'))
		if not mapHandle:
			continue
		idx = utils.findMatInCol(mat.mat, table)
		if idx != None:
			entry = table[idx] #type:ignore
		else:
			entry = table.add() #type:ignore
			entry.mat = mat.mat
			entry.map = mat.map

		stucLib.stucBlenderQueryCommonAttribs.argtypes = (
			ctypes.c_void_p,
			ctypes.c_void_p,
			ctypes.c_void_p
		)
		err = stucLib.stucBlenderQueryCommonAttribs(
			ctypes.pointer(meshTuple.mesh),
			mapHandle,
			ctypes.pointer(commonAttribList[i])
		)
		if err != 1:
			raise Exception("map loaded on py side, but not in c lib")

		if (entry.map != mat.map):
			#map has changed. clear common attrib configs
			entry.map = mat.map
			entry.faces.clear()
			entry.corners.clear()
			entry.edges.clear()
			entry.verts.clear()
		setTargetCommonAttribs(
			entry.faces,
			commonAttribList[i][stuc.StucDomain.FACE.value],
			meshTuple.mesh.faceAttribs
		)
		setTargetCommonAttribs(
			entry.corners,
			commonAttribList[i][stuc.StucDomain.CORNER.value],
			meshTuple.mesh.cornerAttribs
		)
		setTargetCommonAttribs(
			entry.edges,
			commonAttribList[i][stuc.StucDomain.EDGE.value],
			meshTuple.mesh.edgeAttribs
		)
		setTargetCommonAttribs(
			entry.verts,
			commonAttribList[i][stuc.StucDomain.VERT.value],
			meshTuple.mesh.vertAttribs
		)
		i += 1
	return commonAttribList if i == targetMatCount else None

def attribNameToStr(attrib: stuc.StucAttrib)-> str:
	return ctypes.cast(attrib.core.name, ctypes.c_char_p).value.decode('utf-8') #type:ignore

def attribArrToCol(col: Any, arr: stuc.StucAttribArray, map: Any)-> None:
	i = 0
	while i < arr.count:
		attrib = arr.pArr[i].core
		name = ctypes.cast(attrib.name, ctypes.c_char_p).value.decode('utf-8') #type:ignore
		entry = col.get(name, None)
		if not entry:
			entry = col.add()
			entry.name = name
		entry.use = attrib.use
		i += 1