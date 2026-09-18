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
from . import scene_cache as sceneCache

class MappingInfo:
	def __init__(
		self,
		target : props.StucTarget,
		mapArr : stuc.StucMapArr,
		commonAttribs : ctypes.Array[ctypes.Array[stuc.StucBlendOptArr]],
		objEval : bpy.types.Object,
		stucObj : meshUtils.StucObjData,
		inIndexedArr : stuc.StucAttribIndexedArr,
		editMode : bool
	) -> None:
		self.target = target
		self.mapArr = mapArr
		self.commonAttribs = commonAttribs
		self.objEval = objEval
		self.stucObj = stucObj
		self.inIndexedArr = inIndexedArr
		self.editMode = editMode

class TargetJob: 
	done = False
	def __init__(
		self,
		info : MappingInfo,
		jobHandle : stuc.PixthJob,
		outMesh : stuc.StucMesh,
		outIndexedAttribs : stuc.StucAttribIndexedArr,
		crc : ctypes.c_uint64
	) -> None:
		self.info = info
		self.jobHandle = jobHandle
		self.outMesh = outMesh
		self.outIndexedAttribs = outIndexedAttribs
		self.crc = crc

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
	commonAttribs : ctypes.Array[ctypes.Array[stuc.StucBlendOptArr]],
	wMode: int,
	wScale: float,
	receiveLen: float
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
		mapArr.pArr[i].wMode = wMode
		mapArr.pArr[i].wScale = wScale
		mapArr.pArr[i].receiveLen = receiveLen
		i += 1
	return mapArr

def getTargetObj(
	target: props.StucTarget,
	requireSelInEdit: bool = True
) -> bpy.types.Object | None:
	if type(target.obj.data) != bpy.types.Mesh:
		return None
	if target.obj.mode == 'OBJECT':
		obj = target.obj
	elif target.obj.mode == 'EDIT':
		obj = meshUtils.bmEditToObj(target.obj, requireSelInEdit)
	else:
		return None
	if not obj or not obj.data or type(obj.data) != bpy.types.Mesh:
		return None
	return obj

#returns None if aborted
def prepTargetForMapping(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph | None,
	target: props.StucTarget,
	obj: bpy.types.Object
) -> MappingInfo | None:
	#TODO return tuple/ lists like this should probably be dicts
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
		return None
	
	if depsgraph:
		objEval = obj.evaluated_get(depsgraph)
	else:
		objEval = obj
	meshEval = objEval.data
	if type(meshEval) != bpy.types.Mesh:
		raise Exception()
	
	mapArr = createMapArr(
		context,
		objEval,
		meshEval,
		commonAttribs,
		int(target.wMode),
		target.wScale,
		target.receiveLen
	)
	if not mapArr:
		return None
	inIndexedArr = createMatIdxAttrib(meshEval)
	stucObj = meshUtils.formatAsStucObj(
		objEval,
		True,
		depsgraph,
		True,
		target.activeAttribs#type:ignore
	)
	info = MappingInfo(
		target,
		mapArr,
		commonAttribs,
		objEval,
		stucObj,
		inIndexedArr,
		target.obj.mode == 'EDIT'
	)
	return info

def isTargetCrcEqual(
	target: props.StucTarget,
	info: MappingInfo,
	crcOut: ctypes.c_uint64
) -> bool:
	crc = ctypes.c_uint64(0)
	type =\
		stuc.MeshCacheType.MESH_CACHE_IN_EDIT if info.editMode else\
		stuc.MeshCacheType.MESH_CACHE_OUT
	err = stucLib.stucBlenderTargetCrc(target.id, type.value, ctypes.pointer(crc))
	if err != 3:#doesn't equal PIX_ERR_QUIET (QUIET is returned if target isn't in cache)
		if err != 1:
			raise Exception("error getting cached target crc")
		newCrc = ctypes.c_uint64(0)
		err = stucLib.stucBlenderCrcFromTarget(
			ctypes.cast(info.stucObj.obj.pData, ctypes.c_void_p),
			ctypes.pointer(info.inIndexedArr),
			ctypes.pointer(info.mapArr),
			ctypes.pointer(newCrc)
		)
		if err != 1:
			raise Exception("error generating target crc")
		if target.dirty:
			target.dirty = False
		elif newCrc.value == crc.value:
			#print(f"skipping target {target.obj.name}")
			crcOut.value = crc.value
			return True #assume mesh is unchanged, cancel mapping this target
		crc = newCrc
	crcOut.value = crc.value
	return False

#returns true if target should be cached
def pushMappingJobToQueue(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget,
	targetCache: list[TargetJob],
	triangulate: bool,
	checkCrc: bool,
	force: bool = False
) -> bool:
	obj = getTargetObj(target)
	if not obj:
		return False
	info = prepTargetForMapping(context, depsgraph, target, obj)
	crc = ctypes.c_uint64(0)
	if not info:
		return True
	if checkCrc and isTargetCrcEqual(target, info, crc) and not force:
		return False
	
	#print(f"mapping target {target.obj.name}")
	workMesh = stuc.StucMesh()
	outIndexedAttribs = stuc.StucAttribIndexedArr()
	jobHandle = stuc.PixthJob()
	pushedJobs = ctypes.c_bool()
	err = stucLib.stucBlenderMapToMesh(
		ctypes.pointer(jobHandle),
		ctypes.pointer(info.mapArr),
		ctypes.pointer(info.stucObj.meshData.mesh),
		ctypes.pointer(info.inIndexedArr),
		ctypes.pointer(workMesh),
		ctypes.pointer(outIndexedAttribs),
		ctypes.pointer(pushedJobs),
		ctypes.c_bool(triangulate)
	)
	if not pushedJobs:
		return True
	if err != 1:
		raise Exception("error pushing job to queue")
	targetCache.append(TargetJob(
		info,
		jobHandle,
		workMesh,
		outIndexedAttribs,
		crc = crc
	))
	return False

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
			err = stucLib.stucBlenderWaitForJobs(
				1,
				ctypes.pointer(item.jobHandle),
				False,
				ctypes.pointer(done)
			)
			if not done.value:
				continue
			if err != 1:
				err = stucLib.stucBlenderTargetCacheClear(
					item.info.target.id,
					stuc.MeshCacheType.MESH_CACHE_OUT.value
				)
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
					item.crc,
					stucMesh = item.outMesh,
					idxAttribs = item.outIndexedAttribs
				)
			item.done = True
			doneCount += 1
			jobs.remove(item)

def appendSelAttrib(obj: bpy.types.Object, mesh: stuc.StucMesh) -> None:
	selFaces = (ctypes.c_float * mesh.cornerCount)()
	size = mesh.edgeCount * 2#type:ignore
	edges = (ctypes.c_int32 * size)()#type:ignore
	attribUtils.appendAttrib(
		mesh.cornerAttribs,
		"selFaces",
		stuc.StucAttribType.F32.value,
		stuc.StucAttribUse.MISC.value,
		ctypes.cast(selFaces, ctypes.c_void_p),
		activeAttribs = mesh.activeAttribs,
		domain = stuc.StucDomain.CORNER
	)
	if bpy.context.tool_settings.mesh_select_mode[0]:#if vert selection mode
		selVerts = (ctypes.c_int8 * mesh.vertCount)()
		attribUtils.appendAttrib(
			mesh.vertAttribs,
			"selVerts",
			stuc.StucAttribType.I8.value,
			stuc.StucAttribUse.MASK.value,
			ctypes.cast(selVerts, ctypes.c_void_p),
			activeAttribs = mesh.activeAttribs,
			domain = stuc.StucDomain.VERT
		)
		selVertsNumpy = numpy.ctypeslib.as_array(selVerts, shape = (mesh.vertCount, 1))
		obj.data.vertices.foreach_get("select", selVertsNumpy) #type:ignore
	else:
		selEdges = (ctypes.c_int8 * mesh.edgeCount)()
		attribUtils.appendAttrib(
			mesh.edgeAttribs,
			"selEdges",
			stuc.StucAttribType.I8.value,
			stuc.StucAttribUse.MASK.value,
			ctypes.cast(selEdges, ctypes.c_void_p),
			activeAttribs = mesh.activeAttribs,
			domain = stuc.StucDomain.EDGE
		)
		selEdgesNumpy = numpy.ctypeslib.as_array(selEdges, shape = (mesh.edgeCount, 1))
		obj.data.edges.foreach_get("select", selEdgesNumpy) #type:ignore
	
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
	stucLib.stucBlenderMeshCastSel(
		ctypes.pointer(mesh),
		selFaces,
		numpy.ctypeslib.as_ctypes(selFacesNumpy)
	)

	edgesNumpy = numpy.ctypeslib.as_array(edges, shape = (size, 1))#type:ignore
	obj.data.edges.foreach_get("vertices", edgesNumpy) #type:ignore

def cacheTarget(
	target: props.StucTarget,
	crc: ctypes.c_uint64,
	edit: bool = False,
	objOverride: bpy.types.Object | None = None,
	stucMesh: stuc.StucMesh | None = None,
	idxAttribs: stuc.StucAttribIndexedArr | None = None
) -> None:
	obj = objOverride if objOverride else target.obj
	cacheType =\
		stuc.MeshCacheType.MESH_CACHE_IN_EDIT if edit\
		else stuc.MeshCacheType.MESH_CACHE_OUT if stucMesh\
		else stuc.MeshCacheType.MESH_CACHE_IN
	if stucMesh and not stucMesh.faceCount or\
	   not obj or type(obj.data) != bpy.types.Mesh or not len(obj.data.polygons):
		err = stucLib.stucBlenderTargetCacheClear(target.id, cacheType.value)
		if err != 1:
			raise Exception()
		return
	if not edit and bool(stucMesh) != bool(idxAttribs):
		raise Exception()
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
		cacheType.value,
		crc
	)
	if err != 1:
		raise Exception()

def mapToTarget(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget,
	jobs: list[TargetJob],
	cache: bool,
	force: bool = False
) -> None:
	if type(target.obj.data) != bpy.types.Mesh:
		return
	crc = ctypes.c_uint64(0) #dummy
	match target.obj.mode:
		case 'OBJECT':
			cacheInMesh = pushMappingJobToQueue(
				context,
				depsgraph,
				target,
				jobs,
				cache,
				cache,
				force = force
			)
			if cacheInMesh and cache:
				cacheTarget(target, crc)
		case 'EDIT':
			area = utils.getArea()
			if not area:
				return
			shadingType = area.spaces.active.shading.type #type:ignore
			if not cache or context.scene.stuc.dontDraw or shadingType == 'SOLID':#type:ignore
				return
			#TODO add a ui option to enable mapping in edit mode
			#it's just laggy
			obj = getTargetObj(target, requireSelInEdit = False)
			if not obj:
				err = stucLib.stucBlenderTargetCacheClear(
					target.id,
					stuc.MeshCacheType.MESH_CACHE_IN_EDIT.value
				)
				if err != 1:
					raise Exception()
			cacheTarget(target, crc, objOverride = obj, edit = True)
		case _:
			if cache:
				cacheTarget(target, crc)

def setCacheObjVisibility(
	context: bpy.types.Context,
	col: bpy.types.Collection | None,
	target: props.StucTarget,
	hide: bool
) -> None:
	if not col or context.scene.stuc.allowCacheSel:#type:ignore
		return
	cacheObj = sceneCache.getTargetInCache(col, target, False)
	if cacheObj:
		cacheObj.hide_set(hide)
		cacheObj.select_set(False)

def mapToTargetsInScene(
	context: bpy.types.Context,
	selOnly: bool = True,
	exportCtx: ctypes.c_void_p | None = None,
	force: bool = False
) -> None:
	try:
		depsgraph = context.evaluated_depsgraph_get()
		jobs = []
		cacheCol = sceneCache.getCacheIfVisible(context)
		for target in context.scene.stucTargets: #type:ignore
			isSel = target.obj in context.selected_objects
			setCacheObjVisibility(context, cacheCol, target, isSel)
			if selOnly and not isSel:
				continue
			if len(jobs) >= 32:
				waitForAndCopyOutMeshes(context, jobs, exportCtx = exportCtx, tillRemain = 16)
			mapToTarget(context, depsgraph, target, jobs, not exportCtx, force = force)
		waitForAndCopyOutMeshes(context, jobs, exportCtx = exportCtx)
	except Exception as e:
		raise e