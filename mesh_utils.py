'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
import pdb
from numpy._typing import NDArray
import numpy
from typing import Any, cast

import bpy
import bmesh

from . import stuc
from . import utils
from . import attrib_utils as attribUtils
from . import c_lib
stucLib = c_lib.stucLib

class StucMeshData:
	def __init__(
		self,
		mesh : stuc.StucMesh,
		edges : NDArray[Any] | None,
		normals : ctypes.c_void_p | None,
		matIdx : ctypes.c_void_p | None,
		vertNormals : ctypes.c_void_p | None,
		tangents : ctypes.c_void_p | None,
		tSign : ctypes.c_void_p | None
	) -> None:
		self.mesh = mesh
		self.edges = edges
		self.normals = normals
		self.matIdx = matIdx
		self.vertNormals = vertNormals
		self.tangents = tangents
		self.tSign = tSign

class StucObjData:
	def __init__(self, obj : stuc.StucObject, meshData : StucMeshData) -> None:
		self.obj = obj
		self.meshData = meshData

def formatAsStucMesh(
	target: bpy.types.Mesh,
	metaOnly: bool,
	getNormals: bool,
	mats: bool = False,
	activeNames: bpy.types.Collection | None = None,
	getTangents: bool = False,
	getEdges: bool = True,
	getVertNormals: bool = True
) -> StucMeshData:
	mesh = stuc.StucMesh()
	mesh.type.type = stuc.StucObjectType.MESH.value

	mesh.faceCount = len(target.polygons)
	mesh.cornerCount = len(target.loops)
	mesh.edgeCount = len(target.edges)
	mesh.vertCount = len(target.vertices)

	facesPtr = target.polygons[0].as_pointer()
	mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int32))

	loopsPtr = target.loops[0].as_pointer()
	mesh.pCorners = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int32))
	
	edges = None
	if getEdges:
		edges = numpy.empty(mesh.cornerCount, dtype = numpy.int32)
		target.loops.foreach_get("edge_index", cast(Any, edges))
		mesh.pEdges = edges.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))

	attribCount = {"face" : 0, "corner" : 0, "edge" : 0, "vert" : 0}
	attribUtils.getAttribCounts(attribCount, target, getNormals)
	if mats:
		attribCount["face"] += 1 #for material indices
	attribUtils.allocAttribs(mesh, attribCount)
	attribUtils.initAttribs(mesh, target, activeNames, metaOnly, getNormals)

	matIndices = None
	if mats:
		matIndices = (ctypes.c_int8 * mesh.faceCount)()
		matAttrib = target.attributes.get("material_index", None)
		#mat idx attrib won't be present if all faces are assigned to slot 0
		if matAttrib:
			indicesI32 = ctypes.cast(
				matAttrib.data[0].as_pointer(), #type:ignore
				ctypes.POINTER(ctypes.c_int32)
			)
			stucLib.stucBlenderArrayCast(matIndices, 1, indicesI32, 4, mesh.faceCount)
		matIndices = ctypes.cast(matIndices, ctypes.c_void_p)
		attribUtils.appendAttrib(
			mesh.faceAttribs,
			"materials",
			0,
			stuc.StucAttribUse.IDX.value,
			matIndices,
			mesh.activeAttribs
		)

	if not getNormals:
			return StucMeshData(mesh, edges, None, None, None, None, None)
	vertNormals = None
	if getVertNormals:
		vertNormalsPtr = target.vertex_normals[0].as_pointer()
		vertNormals = ctypes.cast(vertNormalsPtr, ctypes.c_void_p)
		attribUtils.appendAttrib(
			mesh.vertAttribs,
			"vertNormals",
			stuc.StucAttribType.V3_F32.value,
			stuc.StucAttribUse.NORMALS_VERT.value,
			vertNormals,
			mesh.activeAttribs
		)
	normals = None
	if not mesh.activeAttribs[stuc.StucAttribUse.NORMAL.value].active:
		#normal attrib wasn't overriden, so we need to add it
		
		#afaik, normals are not accessable as an attribute.
		#atleast not at the time of writing.
		if bpy.app.version < (4, 1, 0) and not len(target.corner_normals):
			target.calc_normals_split() #type:ignore
		normalsPtr = target.corner_normals[0].as_pointer()
		normals = ctypes.cast(normalsPtr, ctypes.c_void_p)		
		attribUtils.appendAttrib(
			mesh.cornerAttribs,
			"normal",
			stuc.StucAttribType.V3_F32.value,
			stuc.StucAttribUse.NORMAL.value,
			normals,
			mesh.activeAttribs
		)
	tangents = None
	tSign = None
	if getTangents:
		target.calc_tangents()
		tangents = (ctypes.c_float * 3 * mesh.cornerCount)()
		tangentsNumpy = numpy.ctypeslib.as_array(
			ctypes.cast(tangents, ctypes.POINTER(ctypes.c_float)),
			shape = (mesh.cornerCount * 3, 1)
		)
		target.loops.foreach_get(
			"tangent",
			tangentsNumpy #type:ignore
		)
		tangents = ctypes.cast(tangents, ctypes.c_void_p)
		tSign = (ctypes.c_float * mesh.cornerCount)()
		target.loops.foreach_get(
			"bitangent_sign",
			numpy.ctypeslib.as_array(tSign, shape = (mesh.cornerCount, 1)) #type:ignore
		)
		tSign = ctypes.cast(tSign, ctypes.c_void_p)
		target.free_tangents()
		attribUtils.appendAttrib(
			mesh.cornerAttribs,
			"tangent",
			stuc.StucAttribType.V3_F32.value,
			stuc.StucAttribUse.TANGENT.value,
			tangents,
			mesh.activeAttribs
		)
		attribUtils.appendAttrib(
			mesh.cornerAttribs,
			"tSign",
			stuc.StucAttribType.F32.value,
			stuc.StucAttribUse.TSIGN.value,
			tSign,
			mesh.activeAttribs
		)


	#to avoid garbage collection, edges, normals, & matIndices are returned as well
	#is there a better way to do this? TODO maybe make edges, normals, & matIndices
	#out params, so there's a reference in the calling function. Probably cleaner than this.
	return StucMeshData(mesh, edges, normals, matIndices, vertNormals, tangents, tSign)

def copyStucMeshToBlenderMesh(
		stucLib: ctypes.CDLL,
		mesh: bpy.types.Mesh,
		workMesh: stuc.StucMesh,
		outIndexedAttribs: stuc.StucAttribIndexedArr | None = None
) -> None:
	if (outIndexedAttribs):
		outMats = attribUtils.getIdxAttrib(outIndexedAttribs, b"materials")
		StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
		outMatsCast = ctypes.cast(outMats.core.pData, ctypes.POINTER(StucString))
		i = 0
		while i < outMats.count:
			namePtr = ctypes.cast(outMatsCast[i], ctypes.c_char_p)
			if not namePtr.value:
				raise Exception("invalid material name")
			matName = namePtr.value.decode()
			mat = bpy.data.materials.get(matName, None)
			if not mat:
				#this should throw an error of some kind, or a warning
				#there shouldn't be any dups
				mat = bpy.data.materials.new(name = matName)
			mesh.materials.append(mat)
			i += 1

	mesh.vertices.add(workMesh.vertCount)
	mesh.loops.add(workMesh.cornerCount)
	mesh.polygons.add(workMesh.faceCount)
	attribUtils.createAllAttribs(mesh, workMesh)
	meshStucFormat = formatAsStucMesh(mesh, False, False)

	stucLib.stucBlenderCopyMeshCore(
		ctypes.pointer(meshStucFormat.mesh),
		ctypes.pointer(workMesh)
	)

	matIndices = None
	i = 0
	while i < workMesh.faceAttribs.count:
		name = ctypes.cast(workMesh.faceAttribs.pArr[i].core.name, ctypes.c_char_p).value
		if name == b"materials":
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

	mesh.update()
	meshStucFormat = formatAsStucMesh(mesh, False, False)
	stucLib.stucBlenderCopyMeshAttribs(
		ctypes.pointer(meshStucFormat.mesh),
		ctypes.pointer(workMesh)
	)
	normalAttrib = attribUtils.getNormalAttrib(workMesh)
	normalsNumpy = numpy.ctypeslib.as_array(
		ctypes.cast(normalAttrib.core.pData,
		ctypes.POINTER(ctypes.c_float)),
		shape = [workMesh.cornerCount, 3]
	)
	mesh.normals_split_custom_set(cast(Any, normalsNumpy))
	if (bpy.app.version < (4, 1, 0)):
		mesh.use_auto_smooth = True #type:ignore

def formatAsStucObj(
	obj: bpy.types.Object,
	isEval : bool,
	depsgraph: bpy.types.Depsgraph | None,
	mats: bool = False,
	activeNames: bpy.types.Collection | None = None,
	getTangents: bool = False,
	getEdges: bool = True,
	getVertNormals: bool = True
) -> StucObjData:
	stucObj = stuc.StucObject()
	if isEval or not depsgraph:
		objEval = obj
	else:
		objEval = obj.evaluated_get(depsgraph)
	meshEval = objEval.data
	
	if type(meshEval) != bpy.types.Mesh:
		raise Exception("object is not a mesh")
	meshTuple = formatAsStucMesh(meshEval, False, True, mats, activeNames, getTangents, getEdges, getVertNormals)
	stucObj.pData = ctypes.cast(ctypes.pointer(meshTuple.mesh), ctypes.POINTER(stuc.StucObjectData))
	utils.setStucMatrix(stucObj.transform, obj.matrix_world)
	return StucObjData(stucObj, meshTuple)

def blendObjFromStuc(
		stucLib: ctypes.CDLL,
		stucObj: stuc.StucObject,
		col: bpy.types.Collection,
		name: str, displayType: str,
		isUsg: bool,
		mats: stuc.StucAttribIndexedArr | None = None
) -> bpy.types.Object:
	mesh = bpy.data.meshes.new(f"{name}Mesh")
	obj = bpy.data.objects.new(name, mesh)
	col.objects.link(obj)
	meshStuc = ctypes.cast(stucObj.pData, ctypes.POINTER(stuc.StucMesh))
	copyStucMeshToBlenderMesh(stucLib, mesh, meshStuc.contents, mats)
	utils.setBlenderMatrix(obj.matrix_world, stucObj.transform)
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

def getMapMesh(
	name: str,
	forRender: bool = False
) -> list[stuc.StucMesh | stuc.StucAttribIndexedArr]:
	mesh = ctypes.POINTER(stuc.StucMesh)()
	idxAttribs = ctypes.POINTER(stuc.StucAttribIndexedArr)()
	err = stucLib.stucBlenderMapMeshGet(
		name.encode('utf-8'),
		ctypes.pointer(mesh),
		ctypes.pointer(idxAttribs),
		forRender
	)
	if err != 1:
		raise Exception("unable to get map mesh")
	return [mesh.contents, idxAttribs.contents]

def prepStucMeshForRender(
	src: stuc.StucMesh,
	cpy: bool,
	triangulate: bool
) -> stuc.StucMesh:
	if not src.faceCount:
		raise Exception("src mesh is empty")
	meshRender = None
	if cpy:
		meshRender = stuc.StucMesh()
		err = stucLib.stucBlenderMeshCpy(ctypes.pointer(meshRender), ctypes.pointer(src))
		if err != 1 or not meshRender.faceCount:
			raise Exception("unable to copy mesh")
	else:
		meshRender = src
		
	err = stucLib.stucBlenderMeshPrepForRender(
		ctypes.pointer(meshRender),
		ctypes.c_bool(triangulate)
	)
	if err != 1:
		raise Exception("unable to make render mesh")
	return meshRender

def removeHiddenInEditMesh(bm: bmesh.types.BMesh, requireSelInEdit: bool)-> bool:
	noSelFaces = True
	toDel = []
	for face in bm.faces:
		if face.hide:
			toDel.append(face)
		elif noSelFaces and face.select:
			noSelFaces = False
	if noSelFaces:
		for vert in bm.verts:
			if vert.select:
				noSelFaces = False
				break
	if noSelFaces:
		for edge in bm.edges:
			if edge.select:
				noSelFaces = False
				break
	if noSelFaces and requireSelInEdit or len(toDel) == len(bm.faces):
		return True
	bmesh.ops.delete(bm, geom = toDel, context = 'FACES')
	return False

def bmEditToObj(
	targetObj: bpy.types.Object,
	requireSel: bool = True
) -> bpy.types.Object | None:
	if not targetObj.data or type(targetObj.data) != bpy.types.Mesh:
		return None
	bm = bmesh.from_edit_mesh(targetObj.data) #type:ignore
	bm = bm.copy()
	if removeHiddenInEditMesh(bm, requireSel):
		bm.clear()
		return None
	obj = targetObj.copy()
	obj.name = "STUC_TEMP_WORK_OBJ"
	obj.data = targetObj.data.copy()
	obj.data.name = "STUC_TEMP_WORK_MESH"
	bm.to_mesh(obj.data)
	bm.clear()
	return obj