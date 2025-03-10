import ctypes
from typing import Any, cast
from bpy.app.handlers import persistent

import bpy

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import attrib_utils as attribUtils
from . import mesh_utils as meshUtils
from . import stuc

@persistent
def stucLoadPostHandler(dummy) -> None:
	stucLib.stucBlenderInit()
	bpy.context.scene.stucMaps.clear() #type:ignore

@persistent
def stucLoadPreHandler(dummy) -> None:
	stucLib.stucBlenderDestroy()

@persistent
def stucDepsgraphUpdatePostHandler(dummy) -> None:
	scene = bpy.context.scene
	active = bpy.context.active_object
	if (active):
		if type(active.data) == bpy.types.Mesh:
			idx = utils.findObjInCol(active, cast(Any, scene).stucTargets)
			if idx != None:
				scene.stucTargetsIndex = idx #type:ignore
	depsgraph = bpy.context.evaluated_depsgraph_get()
	class TargetCache: 
		done = False
		def __init__(
			self,
			obj,
			jobHandle,
			mapArr,
			inMeshTuple,
			inIndexedAttribs,
			outMesh,
			outIndexedAttribs,
			commonAttribs,
			matCount
		) -> None:
			self.obj = obj
			self.jobHandle = jobHandle
			self.mapArr = mapArr
			self.inMeshTuple = inMeshTuple
			self.inIndexedAttribs = inIndexedAttribs
			self.outMesh = outMesh
			self.outIndexedAttribs = outIndexedAttribs
			self.commonAttribs = commonAttribs
			self.matCount = matCount

	targetCache = []
	for target in scene.stucTargets: #type:ignore
		obj = target.obj
		if obj not in bpy.context.selected_objects and not obj == active:
			continue
		elif obj.mode != 'OBJECT':
			continue
		commonAttribs = attribUtils.updateCommonAttribs(
			stucLib,
			target.activeAttribs,
			bpy.context,
			target,
			depsgraph
		)
		#hide_viewport is the moniter icon, and hide_get is the eye
		if not commonAttribs or obj.hide_viewport or obj.hide_get():
			continue
		wScale = obj.get("stucWScale", None)
		if wScale == None:
			print("Target obj has no w scale. Setting to default")
			wScale = scene.stuc.wScale #type:ignore
			obj["stucWScale"] = wScale

		receiveLen = obj.get("stucReceiveLen", None)
		if receiveLen == None:
			receiveLen = -1.0
		
		objEval = obj.evaluated_get(depsgraph)
		meshEval = objEval.data
		
		targetMats = utils.getMatsInStucMats(bpy.context, meshEval)
		matCount = len(targetMats)
		if not matCount:
			continue
		mapArr = stuc.StucBlenderMapArr()
		mapArr.ppArr = (ctypes.POINTER(ctypes.c_byte) * matCount)()
		mapArr.pMatIdxArr = (ctypes.c_byte * matCount)()
		mapArr.pCommonAttribArr = commonAttribs
		mapArr.count = matCount
		mapStrs = []
		
		inIndexedAttribs = stuc.StucAttribIndexedArr()
		inIndexedAttribs.count = 1
		inIndexedAttribs.pArr = ctypes.pointer(stuc.StucAttribIndexed())
		inMats = inIndexedAttribs.pArr.contents
		inMats.count = matCount
		inMats.core.type = stuc.StucAttribType.STRING.value
		utils.copyString(inMats.core.name, "materials", stuc.STUC_ATTRIB_NAME_MAX_LEN)
		StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
		inMatsArr = (StucString * inMats.count)()
		inMats.core.pData = ctypes.cast(inMatsArr, ctypes.c_void_p)
		
		i = 0
		for mat in targetMats:
			utils.copyString(inMatsArr[i], mat.mat.name, stuc.STUC_ATTRIB_STRING_MAX_LEN)
			mapStrs.append(mat.map.encode('utf-8'))
			mapArr.ppArr[i] = ctypes.cast(mapStrs[i], ctypes.POINTER(ctypes.c_byte))
			mapArr.pMatIdxArr[i] = objEval.material_slots.find(mat.mat.name)
			i += 1
		
		meshTuple = meshUtils.formatAsStucMesh(meshEval, False, True, True, target.activeAttribs)
		workMesh = stuc.StucMesh()
		stucLib.stucBlenderMapToMesh.argtypes = (
			ctypes.POINTER(ctypes.c_void_p),
			ctypes.POINTER(stuc.StucBlenderMapArr),
			ctypes.POINTER(stuc.StucMesh), ctypes.POINTER(stuc.StucAttribIndexedArr),
			ctypes.POINTER(stuc.StucMesh), ctypes.POINTER(stuc.StucAttribIndexedArr),
			ctypes.c_float,
			ctypes.c_float
		)
		i = 0
		while i < meshTuple[0].faceAttribs.count:
			StucName = ctypes.c_byte * stuc.STUC_ATTRIB_NAME_MAX_LEN
			nameCast = ctypes.cast(
				meshTuple[0].faceAttribs.pArr[i].core.name,
				ctypes.POINTER(StucName)
			)
			attribName = ctypes.cast(nameCast, ctypes.c_char_p).value.decode()
			if attribName == "materials":
				matIdxArr = ctypes.cast(
					meshTuple[0].faceAttribs.pArr[i].core.pData,
					ctypes.POINTER(ctypes.c_byte)
				)
				print(f"face mat indices 5 on the python side is {matIdxArr[5]}")
			i += 1
		outIndexedAttribs = stuc.StucAttribIndexedArr()
		jobHandle = ctypes.c_void_p()
		result = stucLib.stucBlenderMapToMesh(
			ctypes.pointer(jobHandle),
			ctypes.pointer(mapArr),
			ctypes.pointer(meshTuple[0]),
			ctypes.pointer(inIndexedAttribs),
			ctypes.pointer(workMesh),
			ctypes.pointer(outIndexedAttribs),
			wScale,
			receiveLen
		)
		if result != 0:
			print("Stuc python map to mesh failed, error pushing job to queue")
			return
		targetCache.append(TargetCache(
			objEval,
			jobHandle,
			mapArr,
			meshTuple,
			inIndexedAttribs,
			workMesh,
			outIndexedAttribs,
			commonAttribs,
			matCount)
		)
	cacheCount = len(targetCache)
	if not cacheCount:
		return
	print("-----------------------------------------------waiting for finished jobs")
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
			if result != 0:
				print(f"Stuc python, map to mesh failed on obj {item.obj.name}, skipping")
			print(f"---------------------------------------------------------------Stuc python, map to mesh returned success on obj {item.obj.name}")
			
			nameStuc = item.obj.name + ".Stuc"
			objStuc = bpy.data.objects.get(nameStuc, None)
			if not(objStuc):
				meshStuc = bpy.data.meshes.new(nameStuc)
				objStuc = bpy.data.objects.new(nameStuc, meshStuc)
				bpy.context.scene.collection.objects.link(objStuc)
			else:
				meshStucOld = objStuc.data
				if not meshStucOld or type(meshStucOld) != bpy.types.Mesh:
					raise Exception("old mesh is None or not a mesh")
				meshStucOld.name += ".Old"
				meshStuc = bpy.data.meshes.new(nameStuc)
				objStuc.data = meshStuc
				bpy.data.meshes.remove(meshStucOld)

			meshUtils.copyStucMeshToBlenderMesh(
				stucLib,
				meshStuc,
				item.outMesh,
				item.outIndexedAttribs
			)
			stucLib.stucBlenderMeshDestroy(item.outMesh)
			normalBlendAttrib = meshStuc.attributes.get("normal", None)
			if (normalBlendAttrib):
				meshStuc.attributes.remove(normalBlendAttrib)
			matBlendAttrib = meshStuc.attributes.get("materials", None)
			if (matBlendAttrib):
				meshStuc.attributes.remove(matBlendAttrib)
			
			i = 0
			while i < item.matCount:
				stucLib.stucBlenderDestroyCommonAttribs(ctypes.pointer(item.commonAttribs[i]))
				i += 1
			print("FinishedUpdating")

def register() -> None:
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)

def unregister() -> None:
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)