'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
from math import e
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

class TargetCache: 
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
		print(f"name is {mat.map}")
		stucLib.stucBlenderMapHandleGet.restype = ctypes.c_void_p
		pMap = stucLib.stucBlenderMapHandleGet(mat.map.encode('utf-8'))
		if not pMap:
			return None #map for this material isn't loaded
		mapArr.pArr[i].map.ptr = pMap
		mapArr.pArr[i].blendOptArr = commonAttribs[i]
		mapArr.pArr[i].matIdx = objEval.material_slots.find(mat.mat.name)
		i += 1
	return mapArr

def removeHiddenInEditMesh(bm: bmesh.types.BMesh)-> bool:
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
	if noSelFaces or len(toDel) == len(bm.faces):
		return True
	bmesh.ops.delete(bm, geom = toDel, context = 'FACES')
	return False

#returns None if aborted
def prepTargetForMapping(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget
) -> MappingInfo | None:
	if target.obj not in context.selected_objects or\
		type(target.obj.data) != bpy.types.Mesh:
		return None
	if target.obj.mode == 'OBJECT':
		obj = target.obj
	elif target.obj.mode == 'EDIT':
		obj = target.obj.copy()
		obj.name = "STUC_TEMP_WORK_OBJ"
		obj.data = target.obj.data.copy()
		obj.data.name = "STUC_TEMP_WORK_MESH"
		bm = bmesh.from_edit_mesh(target.obj.data) #type:ignore
		bm = bm.copy()
		if removeHiddenInEditMesh(bm):
			bm.clear()
			return None
		bm.to_mesh(obj.data)
		bm.clear()
	else:
		return None

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
	wScale = obj.get("stucWScale", None)
	if wScale == None:
		wScale = context.scene.stuc.wScale #type:ignore
		obj["stucWScale"] = wScale

	receiveLen = obj.get("stucReceiveLen", None)
	if receiveLen == None:
		receiveLen = -1.0
	
	objEval = obj.evaluated_get(depsgraph)
	meshEval = objEval.data
	
	mapArr = createMapArr(context, objEval, meshEval, commonAttribs) #type:ignore
	if not mapArr:
		return None
	inIndexedArr = createMatIdxAttrib(meshEval) #type:ignore
	stucObj = meshUtils.formatAsStucObj(
		objEval,
		True,
		depsgraph,
		True,
		target.activeAttribs #type:ignore
	)
	return MappingInfo(
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

def pushMappingJobToQueue(
	context: bpy.types.Context,
	depsgraph: bpy.types.Depsgraph,
	target: props.StucTarget,
	targetCache: list[TargetCache]
) -> None:
	info = prepTargetForMapping(context, depsgraph, target)
	if not info:
		return
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
		ctypes.pointer(pushedJobs)
	)
	if not pushedJobs:
		return
	if result != 1:
		raise Exception("error pushing job to queue")
	targetCache.append(TargetCache(
		info,
		jobHandle,
		workMesh,
		outIndexedAttribs
	))

def addOrUpdateBlendMesh(context: bpy.types.Context, item: TargetCache) -> None:
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
	targetCache: list[TargetCache],
	cacheCount: int
) -> None:
	doneCount = 0
	while doneCount < cacheCount:
		for item in targetCache:
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
				print(f"Stuc python, map to mesh failed on obj {item.info.objEval.name}, skipping")
				continue
			print(f"Stuc python, map to mesh returned success on obj {item.info.objEval.name}")
			
			if item.outMesh.faceCount:
				addOrUpdateBlendMesh(context, item)
			print("FinishedUpdating")

def mapToSelTargets(context: bpy.types.Context) -> None:
	depsgraph = context.evaluated_depsgraph_get()
	targetCache = []
	for target in context.scene.stucTargets: #type:ignore
		pushMappingJobToQueue(context, depsgraph, target, targetCache)
	cacheCount = len(targetCache)
	if not cacheCount:
		return
	print("waiting for finished jobs")
	waitForAndCopyOutMeshes(context, targetCache, cacheCount)
