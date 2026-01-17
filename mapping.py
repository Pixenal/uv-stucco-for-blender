'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
import numpy
from numpy._typing import NDArray
from typing import Any, cast
import pdb

import bpy
import bmesh

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import attrib_utils as attribUtils
from . import mesh_utils as meshUtils
from . import props
from . import stuc
from . import draw

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
		jobHandle : ctypes.c_void_p,
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
		#print(f"name is {mat.map}")
		stucLib.stucBlenderMapHandleGet.restype = ctypes.c_void_p
		pMap = stucLib.stucBlenderMapHandleGet(mat.map.encode('utf-8'))
		if not pMap:
			return None #map for this material isn't loaded
		mapArr.pArr[i].map.ptr = pMap
		mapArr.pArr[i].blendOptArr = commonAttribs[i]
		mapArr.pArr[i].matIdx = objEval.material_slots.find(mat.mat.name)
		i += 1
	return mapArr

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

#returns None if aborted
def prepTargetForMapping(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph | None,
	target: props.StucTarget,
	requireSelInEdit: bool = True
) -> tuple[MappingInfo, int, None] | tuple[None, int, None] | tuple[None, int, bpy.types.Object]:
	#return tuple/ lists like this should probably be dicts
	if target.obj not in context.selected_objects or\
		type(target.obj.data) != bpy.types.Mesh:
		return (None, 0, None)
	if target.obj.mode == 'OBJECT':
		obj = target.obj
	elif target.obj.mode == 'EDIT':
		obj = target.obj.copy()
		obj.name = "STUC_TEMP_WORK_OBJ"
		obj.data = target.obj.data.copy()
		obj.data.name = "STUC_TEMP_WORK_MESH"
		bm = bmesh.from_edit_mesh(target.obj.data) #type:ignore
		bm = bm.copy()
		if removeHiddenInEditMesh(bm, requireSelInEdit):
			bm.clear()
			return (None, 1, None)
		bm.to_mesh(obj.data)
		bm.clear()
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
		return (None, 1, obj if target.obj.mode == 'EDIT' else None)
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
		return (None, 1, obj if target.obj.mode == 'EDIT' else None)
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
	targetCache: list[TargetJob]
) -> int:
	infoTuple = prepTargetForMapping(context, depsgraph, target)
	if not infoTuple[0]:
		return infoTuple[1]
	info = infoTuple[0]
	workMesh = stuc.StucMesh()
	outIndexedAttribs = stuc.StucAttribIndexedArr()
	jobHandle = ctypes.c_void_p()
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
		ctypes.c_bool(True)
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

def addOrUpdateBlendMesh(context: bpy.types.Context, item: TargetJob) -> None:
	nameStuc = item.info.target.obj.name + ".Stuc"
	objStuc = bpy.data.objects.get(nameStuc, None)
	if not(objStuc):
		meshStuc = bpy.data.meshes.new(nameStuc)
		objStuc = bpy.data.objects.new(nameStuc, meshStuc)
		context.scene.collection.objects.link(objStuc)
	else:
		meshStucOld = objStuc.data
		if not meshStucOld or type(meshStucOld) != bpy.types.Mesh:
			raise Exception("old mesh is None or not a mesh")
		meshStucOld.name += ".Old"
		meshStuc = bpy.data.meshes.new(nameStuc)
		objStuc.data = meshStuc
		bpy.data.meshes.remove(meshStucOld)
	objStuc.matrix_world = item.info.objEval.matrix_world

	meshUtils.copyStucMeshToBlenderMesh(
		stucLib,
		meshStuc,
		item.outMesh,
		item.outIndexedAttribs
	)
	stucLib.stucBlenderMeshDestroy(ctypes.pointer(item.outMesh))
	normalBlendAttrib = meshStuc.attributes.get("normal", None)
	if (normalBlendAttrib):
		meshStuc.attributes.remove(normalBlendAttrib)
	matBlendAttrib = meshStuc.attributes.get("materials", None)
	if (matBlendAttrib):
		meshStuc.attributes.remove(matBlendAttrib)

def waitForAndCopyOutMeshes(
	context: bpy.types.Context,
	jobs: list[TargetJob]
) -> None:
	doneCount = 0
	jobCount = len(jobs)
	while doneCount < jobCount:
		for item in jobs:
			if item.done:
				continue
			jobHandlePtr = ctypes.POINTER(ctypes.c_void_p)()
			jobHandlePtr = ctypes.pointer(item.jobHandle)
			done = ctypes.c_bool()
			result = stucLib.stucBlenderWaitForJobs(
				1,
				jobHandlePtr,
				False,
				ctypes.pointer(done)
			)
			if not done.value:
				continue
			item.done = True
			doneCount += 1
			if result != 1:
				err = stucLib.stucBlenderTargetCacheClear(item.info.target.id)
				if err != 1:
					raise Exception("error clearing target mesh cache")
				print(f"Stuc python, map to mesh failed on obj {item.info.objEval.name}, skipping")
				continue
			#print(f"Stuc python, map to mesh returned success on obj {item.info.objEval.name}")

			cacheTarget(
				item.info.target,
				stucMesh = item.outMesh,
				idxAttribs = item.outIndexedAttribs
			)
			#addOrUpdateBlendMesh(context, item)
				
			#print("FinishedUpdating")

def appendSelAttrib(obj: bpy.types.Object, mesh: stuc.StucMesh) -> None:
	selFlag = (ctypes.c_float * mesh.cornerCount)()
	attribUtils.appendAttrib(
		mesh.cornerAttribs,
		"select",
		stuc.StucAttribType.F32.value,
		stuc.StucAttribUse.MISC.value,
		ctypes.cast(selFlag, ctypes.c_void_p)
	)
	selFaces = numpy.empty(mesh.faceCount, dtype = numpy.int8)
	obj.data.polygons.foreach_get("select", selFaces) #type:ignore
	stucLib.stucBlenderSelCornersFromFaces(
		ctypes.pointer(mesh),
		selFlag,
		numpy.ctypeslib.as_ctypes(selFaces)
	)

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
	if bool(stucMesh) != bool(idxAttribs):
		raise Exception()
	cacheType =\
		stuc.MeshCacheType.MESH_CACHE_OUT if stucMesh\
		else stuc.MeshCacheType.MESH_CACHE_IN_EDIT if edit\
		else stuc.MeshCacheType.MESH_CACHE_IN
	meshRender = None
	if stucMesh:
		meshRender = meshUtils.prepStucMeshForRender(stucMesh, False, False) #type:ignore
	else:
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
		meshRender = meshUtils.prepStucMeshForRender(stucMesh, True, True) #type:ignore
		
	err = stucLib.stucBlenderTargetCacheAdd(
		target.id,
		meshRender,
		idxAttribs,
		cacheType.value
	)
	if err != 1:
		raise Exception()

def mapToTarget(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget,
	jobs: list[TargetJob]
) -> None:
	if type(target.obj.data) != bpy.types.Mesh:
		return
	match target.obj.mode:
		case 'OBJECT':
			result = pushMappingJobToQueue(context, depsgraph, target, jobs)
			if result:
				cacheTarget(target)
		case 'EDIT':
			#TODO add a ui option to enable mapping in edit mode
			#it's just laggy
			info = prepTargetForMapping(
				bpy.context,
				None,
				target,
				requireSelInEdit = False
			)
			if info[0]:
				cacheTarget(target, stucMesh = info[0].stucObj.meshData.mesh) #type:ignore
			elif info[2]:
				cacheTarget(target, objOverride = info[2], edit = True)
			else:
				cacheTarget(target, edit = True)
		case _:
			cacheTarget(target)

def mapToSelTargets(context: bpy.types.Context) -> None:
	try:
		depsgraph = context.evaluated_depsgraph_get()
		jobs = []
		for target in context.scene.stucTargets: #type:ignore
			print("mapping target")
			mapToTarget(context, depsgraph, target, jobs)
		if not len(jobs):
			return
		#print("waiting for finished jobs")
		waitForAndCopyOutMeshes(context, jobs)
	except Exception as e:
		raise e