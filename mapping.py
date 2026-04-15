'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
from pickletools import int4
import numpy
from numpy._typing import NDArray
from typing import Any, cast
import pdb
import time
import cProfile

import bpy
import bmesh

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import attrib_utils as attribUtils
from . import mesh_utils as meshUtils
from . import props
from . import stuc

class MappingInfo:
	def __init__(
		self,
		target : props.StucTarget,
		mapArr : stuc.StucMapArr,
		commonAttribs : ctypes.Array[ctypes.Array[stuc.StucBlendOptArr]],
		objEval : bpy.types.Object,
		stucObj : meshUtils.StucObjData,
		inIndexedArr : stuc.StucAttribIndexedArr,
		wScale : float,
		receiveLen : float,
		editMode : bool
	) -> None:
		self.target = target
		self.mapArr = mapArr
		self.commonAttribs = commonAttribs
		self.objEval = objEval
		self.stucObj = stucObj
		self.inIndexedArr = inIndexedArr
		self.wScale = wScale
		self.receiveLen = receiveLen
		self.editMode = editMode

class TargetJob: 
	done = False
	def __init__(
		self,
		info : MappingInfo,
		jobHandle : stuc.PixthJob,
		outMesh : stuc.StucMesh,
		outIndexedAttribs : stuc.StucAttribIndexedArr
	) -> None:
		self.info = info
		self.jobHandle = jobHandle
		self.outMesh = outMesh
		self.outIndexedAttribs = outIndexedAttribs

def createMatIdxAttrib(
	mesh : bpy.types.Mesh
)-> stuc.StucAttribIndexedArr:
	idxAttribs = stuc.StucAttribIndexedArr()
	idxAttribs.count = 1
	idxAttribs.pArr = ctypes.pointer(stuc.StucAttribIndexed())
	inMats = idxAttribs.pArr.contents
	inMats.count = len(mesh.materials)
	inMats.core.type = stuc.StucAttribType.STRING.value
	utils.copyString(inMats.core.name, "materials", stuc.STUC_ATTRIB_NAME_MAX_LEN)
	StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
	inMatsArr = (StucString * inMats.count)()
	inMats.core.pData = ctypes.cast(inMatsArr, ctypes.c_void_p)
	i = 0
	for mat in mesh.materials:
		utils.copyString(inMatsArr[i], mat.name, stuc.STUC_ATTRIB_STRING_MAX_LEN)
		i += 1
	return idxAttribs

def createMapArr(
	context : bpy.types.Context,
	objEval : bpy.types.Object,
	meshEval : bpy.types.Mesh,
	commonAttribs : ctypes.Array[ctypes.Array[stuc.StucBlendOptArr]]
) -> stuc.StucMapArr | None:
	targetMats = utils.getMatsInStucMats(context, meshEval)
	targetMatCount = len(targetMats)
	if not targetMatCount:
		return None
	mapArr = stuc.StucMapArr()
	mapArr.pArr = (stuc.StucMapArrEntry * targetMatCount)()
	mapArr.count = targetMatCount
	i = 0
	for mat in targetMats:
		stucLib.stucBlenderMapHandleGet.restype = ctypes.c_void_p
		pMap = stucLib.stucBlenderMapHandleGet(mat.map.encode('utf-8'))
		if not pMap:
			return None #map for this material isn't loaded
		mapArr.pArr[i].map.ptr = pMap
		mapArr.pArr[i].blendOptArr = commonAttribs[i]
		mapArr.pArr[i].matIdx = objEval.material_slots.find(mat.mat.name)
		i += 1
	return mapArr

#returns None if aborted
def prepTargetForMapping(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph | None,
	target: props.StucTarget,
	requireSelInEdit: bool = True
) -> tuple[MappingInfo, int, None] | tuple[None, int, None] | tuple[None, int, bpy.types.Object]:
	#TODO return tuple/ lists like this should probably be dicts
	if type(target.obj.data) != bpy.types.Mesh:
		return (None, 0, None)
	if target.obj.mode == 'OBJECT':
		obj = target.obj
	elif target.obj.mode == 'EDIT':
		obj = meshUtils.bmEditToObj(target.obj, requireSelInEdit)
		if not obj or not obj.data or type(obj.data) != bpy.types.Mesh:
			return (None, 1, None)
	else:
		return (None, 1, None)

	commonAttribs = attribUtils.updateCommonAttribs(
		stucLib,
		context,
		obj,
		target.commonAttribTable, #type:ignore
		target.activeAttribs, #type:ignore
		depsgraph
	)
	#hide_viewport is the moniter icon, and hide_get is the eye
	if not commonAttribs or obj.hide_viewport or obj.hide_get():
		return (None, 1, obj if target.obj.mode == 'EDIT' else None) #type:ignore
	wScale = obj.get("stucWScale", None)
	if wScale == None:
		wScale = context.scene.stuc.wScale #type:ignore
		obj["stucWScale"] = wScale

	receiveLen = obj.get("stucReceiveLen", None)
	if receiveLen == None:
		receiveLen = -1.0
	
	if depsgraph:
		objEval = obj.evaluated_get(depsgraph)
	else:
		objEval = obj
	meshEval = objEval.data
	
	mapArr = createMapArr(context, objEval, meshEval, commonAttribs) #type:ignore
	if not mapArr:
		return (None, 1, obj if target.obj.mode == 'EDIT' else None) #type:ignore
	inIndexedArr = createMatIdxAttrib(meshEval) #type:ignore
	stucObj = meshUtils.formatAsStucObj(
		objEval,
		True,
		depsgraph,
		True,
		target.activeAttribs #type:ignore
	)
	info = MappingInfo(
		target,
		mapArr,
		commonAttribs,
		objEval,
		stucObj,
		inIndexedArr,
		wScale,
		receiveLen,
		target.obj.mode == 'EDIT'
	)
	return (info, 0, None)

def pushMappingJobToQueue(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget,
	targetCache: list[TargetJob],
	triangulate: bool
) -> int:
	infoTuple = prepTargetForMapping(context, depsgraph, target)
	if not infoTuple[0]:
		return infoTuple[1]
	info = infoTuple[0]
	workMesh = stuc.StucMesh()
	outIndexedAttribs = stuc.StucAttribIndexedArr()
	jobHandle = stuc.PixthJob()
	pushedJobs = ctypes.c_bool()
	result = stucLib.stucBlenderMapToMesh(
		ctypes.pointer(jobHandle),
		ctypes.pointer(info.mapArr),
		ctypes.pointer(info.stucObj.meshData.mesh),
		ctypes.pointer(info.inIndexedArr),
		ctypes.pointer(workMesh),
		ctypes.pointer(outIndexedAttribs),
		ctypes.c_float(info.wScale),
		ctypes.c_float(info.receiveLen),
		ctypes.pointer(pushedJobs),
		ctypes.c_bool(triangulate)
	)
	if not pushedJobs:
		return 1
	if result != 1:
		raise Exception("error pushing job to queue")
	targetCache.append(TargetJob(
		info,
		jobHandle,
		workMesh,
		outIndexedAttribs
	))
	return 0

def getStucCol(context: bpy.types.Context) -> bpy.types.Collection:
	stucCol = bpy.data.collections.get("_STUC_OUT", None)
	if not stucCol:
		stucCol = bpy.data.collections.new(name = "_STUC_OUT")
	if not stucCol.name in context.scene.collection.children:
		context.scene.collection.children.link(stucCol)
	return stucCol

def addOrUpdateBlendMesh(
	context: bpy.types.Context,
	stucObj: stuc.StucObject,
	idxAttribs: stuc.StucAttribIndexedArr,
	name: str
) -> None:
	objName = name + ".Stuc"
	obj = bpy.data.objects.get(objName, None)
	stucCol = getStucCol(context)
	if not(obj):
		mesh = bpy.data.meshes.new(objName)
		obj = bpy.data.objects.new(objName, mesh)
		stucCol.objects.link(obj)
	else:
		meshOld = obj.data
		if not meshOld or type(meshOld) != bpy.types.Mesh:
			raise Exception("old mesh is None or not a mesh")
		meshOld.name += ".Old"
		mesh = bpy.data.meshes.new(objName)
		obj.data = mesh
		bpy.data.meshes.remove(meshOld)
	utils.setBlenderMatrix(obj.matrix_world, stucObj.transform)
	stucMeshPtr = ctypes.cast(stucObj.pData, ctypes.POINTER(stuc.StucMesh))
	meshUtils.copyStucMeshToBlenderMesh(
		stucLib,
		mesh,
		stucMeshPtr.contents,
		idxAttribs
	)
	stucLib.stucBlenderMeshDestroy(stucMeshPtr)
	normalBlendAttrib = mesh.attributes.get("normal", None)
	if (normalBlendAttrib):
		mesh.attributes.remove(normalBlendAttrib)
	matBlendAttrib = mesh.attributes.get("materials", None)
	if (matBlendAttrib):
		mesh.attributes.remove(matBlendAttrib)

def waitForAndCopyOutMeshes(
	context: bpy.types.Context,
	jobs: list[TargetJob],
	exportCtx: ctypes.c_void_p | None = None,
	tillRemain: int = 0
) -> None:
	doneCount = 0
	jobCount = len(jobs)
	while doneCount < jobCount - tillRemain:
		for item in jobs:
			if item.done:
				continue
			done = ctypes.c_bool()
			result = stucLib.stucBlenderWaitForJobs(
				1,
				ctypes.pointer(item.jobHandle),
				False,
				ctypes.pointer(done)
			)
			if not done.value:
				continue
			if result != 1:
				err = stucLib.stucBlenderTargetCacheClear(item.info.target.id)
				if err != 1:
					raise Exception("error clearing target mesh cache")
				print(f"Stuc python, map to mesh failed on obj {item.info.objEval.name}, skipping")
			elif not item.outMesh.faceCount:
				#outmesh is empty
				if (item.outMesh.cornerCount or item.outMesh.vertCount):
					raise Exception("out-mesh is invalid")
			elif exportCtx:
				stucObj = stuc.StucObject()
				utils.setStucMatrix(stucObj.transform, item.info.objEval.matrix_world)
				stucObj.pData = ctypes.cast(
					ctypes.cast(ctypes.pointer(item.outMesh), ctypes.c_void_p),
					ctypes.POINTER(stuc.StucObjectData)
				)
				err = stucLib.stucBlenderSceneExportObj(
					exportCtx,
					item.info.objEval.name.encode('utf-8'),
					ctypes.pointer(stucObj)
				)
				if err != 1:
					raise Exception()
				err = stucLib.stucBlenderSceneExportIdxAttribs(
					exportCtx,
					ctypes.pointer(item.outIndexedAttribs)
				)
				if err != 1:
					raise Exception()
			else:
				cacheTarget(
					item.info.target,
					stucMesh = item.outMesh,
					idxAttribs = item.outIndexedAttribs
				)
			item.done = True
			doneCount += 1
			jobs.remove(item)

def appendSelAttrib(obj: bpy.types.Object, mesh: stuc.StucMesh) -> None:
	selFaces = (ctypes.c_float * mesh.cornerCount)()
	selEdges = (ctypes.c_float * mesh.edgeCount)()
	size = mesh.edgeCount * 2
	edges = (ctypes.c_int32 * size)()
	attribUtils.appendAttrib(
		mesh.cornerAttribs,
		"selFaces",
		stuc.StucAttribType.F32.value,
		stuc.StucAttribUse.MISC.value,
		ctypes.cast(selFaces, ctypes.c_void_p),
		activeAttribs = mesh.activeAttribs,
		domain = stuc.StucDomain.CORNER
	)
	attribUtils.appendAttrib(
		mesh.edgeAttribs,
		"selEdges",
		stuc.StucAttribType.F32.value,
		stuc.StucAttribUse.MASK.value,
		ctypes.cast(selEdges, ctypes.c_void_p),
		activeAttribs = mesh.activeAttribs,
		domain = stuc.StucDomain.EDGE
	)
	attribUtils.appendAttrib(
		mesh.edgeAttribs,
		"edgeCorners",
		stuc.StucAttribType.V2_I32.value,
		stuc.StucAttribUse.EDGE_CORNERS.value,
		ctypes.cast(edges, ctypes.c_void_p),
		activeAttribs = mesh.activeAttribs,
		domain = stuc.StucDomain.EDGE
	)

	selFacesNumpy = numpy.empty(mesh.faceCount, dtype = numpy.int8)
	obj.data.polygons.foreach_get("select", selFacesNumpy) #type:ignore
	selEdgesNumpy = numpy.empty(mesh.edgeCount, dtype = numpy.int8)
	obj.data.edges.foreach_get("select", selEdgesNumpy) #type:ignore
	stucLib.stucBlenderMeshCastSel(
		ctypes.pointer(mesh),
		selFaces,
		numpy.ctypeslib.as_ctypes(selFacesNumpy),
		selEdges,
		numpy.ctypeslib.as_ctypes(selEdgesNumpy)
	)
	edgesNumpy = numpy.ctypeslib.as_array(edges, shape = (size, 1))
	obj.data.edges.foreach_get("vertices", edgesNumpy) #type:ignore

def cacheTarget(
	target: props.StucTarget,
	edit: bool = False,
	objOverride: bpy.types.Object | None = None,
	stucMesh: stuc.StucMesh | None = None,
	idxAttribs: stuc.StucAttribIndexedArr | None = None
) -> None:
	obj = objOverride if objOverride else target.obj
	if stucMesh and not stucMesh.faceCount or\
	   not obj or type(obj.data) != bpy.types.Mesh or not len(obj.data.polygons):
		err = stucLib.stucBlenderTargetCacheClear(target.id)
		if err != 1:
			raise Exception()
		return
	if not edit and bool(stucMesh) != bool(idxAttribs):
		raise Exception()
	cacheType =\
		stuc.MeshCacheType.MESH_CACHE_IN_EDIT if edit\
		else stuc.MeshCacheType.MESH_CACHE_OUT if stucMesh\
		else stuc.MeshCacheType.MESH_CACHE_IN
	meshRender = None
	if not stucMesh:
		stucObj = meshUtils.formatAsStucObj(
			obj,
			True,
			None,
			mats = True,
			activeNames = target.activeAttribs, #type:ignore
			getTangents = False,
			getEdges = False,
			getVertNormals = False
		)
		stucMesh = stucObj.meshData.mesh
	if edit:
		appendSelAttrib(obj, stucMesh) #type:ignore
	cpyAndTris = cacheType != stuc.MeshCacheType.MESH_CACHE_OUT
	meshRender = meshUtils.prepStucMeshForRender(stucMesh, cpyAndTris, cpyAndTris)

	err = stucLib.stucBlenderTargetCacheAdd(
		target.id,
		ctypes.c_double(time.time()),
		ctypes.pointer(meshRender),
		ctypes.pointer(idxAttribs) if idxAttribs else None,
		cacheType.value
	)
	if err != 1:
		raise Exception()

def mapToTarget(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget,
	jobs: list[TargetJob],
	cache: bool
) -> None:
	if type(target.obj.data) != bpy.types.Mesh:
		return
	match target.obj.mode:
		case 'OBJECT':
			result = pushMappingJobToQueue(context, depsgraph, target, jobs, cache)
			if result and cache:
				cacheTarget(target)
		case 'EDIT':
			if not cache:
				return
			#TODO add a ui option to enable mapping in edit mode
			#it's just laggy
			info = prepTargetForMapping(
				bpy.context,
				None,
				target,
				requireSelInEdit = False
			)
			if info[0]:
				cacheTarget(target, stucMesh = info[0].stucObj.meshData.mesh, edit = True)
			elif info[2]:
				cacheTarget(target, objOverride = info[2], edit = True)
			else:
				err = stucLib.stucBlenderTargetCacheClear(target.id)
				if err != 1:
					raise Exception()
		case _:
			if cache:
				cacheTarget(target)

def mapToTargetsInScene(
	context: bpy.types.Context,
	selOnly: bool = True,
	exportCtx: ctypes.c_void_p | None = None
) -> None:
	try:
		depsgraph = context.evaluated_depsgraph_get()
		jobs = []
		for target in context.scene.stucTargets: #type:ignore
			if selOnly and target.obj not in context.selected_objects:
				continue
			if len(jobs) >= 32:
				waitForAndCopyOutMeshes(context, jobs, exportCtx = exportCtx, tillRemain = 16)
			mapToTarget(context, depsgraph, target, jobs, not exportCtx)
		waitForAndCopyOutMeshes(context, jobs, exportCtx = exportCtx)
	except Exception as e:
		raise e