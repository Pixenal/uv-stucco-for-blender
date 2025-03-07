import bpy
import ctypes
from typing import Any, cast
from . import UvStuccoB_CLib
stucLib = UvStuccoB_CLib.stucLib
import numpy
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from . import Utils as utils
import os
import pdb

#TODO calc_normals_split has been removed in 4.1, so you'll need to handle that
#TODO It seems that normals can be accessed as contiguous arrays now,
#using the polygon_normals, or vertex_normals, properties, in a mesh.
#see if you can use this.
#TODO You'll need to separetly handle seams and creases and such as well,
#these seem to have been converted to attributes in 4.0 versions.
#So probably only need to do it for pre 4.0 versions.

class STUC_OT_StucSetAsUsg(bpy.types.Operator):
	bl_idname = "stuc.set_as_usg"
	bl_label = "Set As USG"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
		return utils.getUsgCountInSelObjs(context) < len(context.selected_objects)

	def execute(self, context: bpy.types.Context) -> set[str]:
		for obj in context.selected_objects:
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				continue
			obj["StucUsg"] = True
			obj.display_type = 'WIRE'
		return {'FINISHED'}
	
class STUC_OT_StucUnsetUsg(bpy.types.Operator):
	bl_idname = "stuc.unset_usg"
	bl_label = "Unset USG"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
		return utils.getUsgCountInSelObjs(context) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		for obj in context.selected_objects:
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				del obj["StucUsg"]
				obj["stucUsgFlatCutoff"] = None
				obj.display_type = 'TEXTURED'
		return {'FINISHED'}
	
class STUC_OT_StucSetFlatCutoff(bpy.types.Operator):
	bl_idname = "stuc.set_flat_cutoff"
	bl_label = "Set Flatten Cut-Off"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
		return utils.getUsgCountInSelObjs(context) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		activeObj = context.view_layer.objects.active
		for obj in context.selected_objects:
			if obj == activeObj:
				continue
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				obj["stucUsgFlatCutoff"] = activeObj
		return {'FINISHED'}

class STUC_OT_StucExportStucFile(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.export_stuc_file"
	bl_label = "STUC Export"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		if (len(context.selected_objects) == 0):
			print("STUC export failed, no objects selected.")
			return {'CANCELLED'}
		
		filepath = self.filepath #type:ignore
		filePathUtf8 = filepath.encode('utf-8')
		
		depsgraph = context.evaluated_depsgraph_get()
		ObjArr = utils.StucObject * len(context.selected_objects)
		UsgArr = utils.StucUsg * len(context.selected_objects)
		objArr = ObjArr()
		usgArr = UsgArr()
		objCount = 0
		usgCount = 0
		cutoffs = {}
		mats = {}
		tuples = []
		objCount = 0
		for obj in context.selected_objects:
			if obj.type != 'MESH':
				continue
			isUsg = obj.get("StucUsg", None)
			if not isUsg:
				objCount += 1
		matTable = utils.StucBlenderMatTableArr()
		matTable.count = objCount
		MatTableArr = utils.StucBlenderMatTable * matTable.count
		matTable.pArr = MatTableArr()
		
		for obj in context.selected_objects:
			if obj.type != 'MESH':
				continue
			isUsg = obj.get("StucUsg", None)
			if not isUsg:
				for slot in obj.material_slots:
					entry = mats.get(slot.name, None)
					if not entry:
						mats[slot.name] = True
		matCount = len(mats)
		if not matCount:
			mats = None
						
		objIdx = 0
		for obj in context.selected_objects:
			if obj.type != 'MESH':
				continue
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				objTuple = utils.formatAsStucObj(obj, depsgraph, False)
				usgArr[usgCount].obj = objTuple[0]
				tuples.append(objTuple)
				flatCutoff = obj.get("stucUsgFlatCutoff", None)
				if (flatCutoff):
					if flatCutoff.type == 'MESH':
						cutoffPtr = cutoffs.get(flatCutoff.name, None)
						if not cutoffPtr:
							cutoffObjTuple = utils.formatAsStucObj(flatCutoff, depsgraph, False)
							cutoffPtr = ctypes.pointer(cutoffObjTuple[0])
							cutoffs.update({flatCutoff.name : cutoffPtr})
							tuples.append(cutoffObjTuple)
						usgArr[usgCount].pFlatCutoff = cutoffPtr
				usgCount += 1
			else:
				objTuple = utils.formatAsStucObj(obj, depsgraph, True, mats, matTable.pArr[objIdx])
				objArr[objIdx] = objTuple[0]
				tuples.append(objTuple)
				objIdx += 1
		
		indexedAttribCount = 0
		indexedAttribs = utils.StucAttribIndexedArr()
		if matCount:
			if not mats:
				raise Exception("mats is None")
			MatArr = ctypes.c_byte * utils.STUC_ATTRIB_STRING_MAX_LEN * matCount
			matArr = MatArr()
			i = 0
			for matName in mats.keys():
				utils.copyString(matArr[i], matName, utils.STUC_ATTRIB_NAME_MAX_LEN)
				i += 1
			matAttrib = utils.StucAttribIndexed()
			matAttrib.core.pData =  ctypes.cast(matArr, ctypes.c_void_p)
			utils.copyString(matAttrib.core.name, "materials", utils.STUC_ATTRIB_NAME_MAX_LEN)
			matAttrib.core.type = utils.StucAttribType.STRING.value
			matAttrib.count = matCount
			matAttrib.size = matCount
			indexedAttribCount = 1
			indexedAttribs.pArr = ctypes.pointer(matAttrib)
		indexedAttribs.count = indexedAttribCount
		indexedAttribs.size = indexedAttribCount
		
		err = stucLib.stucBlenderMapFileExport(
			filePathUtf8,
			objCount,
			objArr,
			usgCount,
			usgArr,
			ctypes.pointer(indexedAttribs),
			ctypes.pointer(matTable)
		)
		if err != 1:
			self.report({'ERROR'}, "Export failed")
			return {'CANCELLED'}
		return {'FINISHED'}

class STUC_OT_StucAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_assign"
	bl_label = "STUC Assign"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		if len(context.selected_objects) == 0:
			return {'CANCELLED'}
		for obj in context.selected_objects:
			if type(obj.data) != bpy.types.Mesh:
				continue
			exists = False
			for target in context.scene.stucTargets: #type:ignore
				if target.obj == obj:
					exists = True
					break
			if exists:
				continue
			newTarget = context.scene.stucTargets.add() #type:ignore
			newTarget.obj = obj.id_data
			obj["stucWScale"] = context.scene.stuc.wScale #type:ignore
			obj["stucReceiveLen"] = -1.0
			newTarget.activeAttribs.add().name = "position"
			newTarget.activeAttribs.add().name = ""
			uvEntry = newTarget.activeAttribs.add()
			for uv in obj.data.uv_layers:
				if uv.active:
					uvEntry.name = uv.name
					break
			colEntry = newTarget.activeAttribs.add()
			activeColIdx = obj.data.attributes.active_color_index
			if activeColIdx and activeColIdx >= 0:
				colEntry.name = obj.data.color_attributes[activeColIdx].name

		return {'FINISHED'}
	
class STUC_OT_StucMatAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_assign"
	bl_label = "STUC Mat Assign"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		item = context.scene.stucMats.add() #type:ignore
		return {'FINISHED'}
	
class STUC_OT_StucLoadStucFileForEdit(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.load_stuc_file_for_edit"
	bl_label = "Load STUC File For Edit"
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		filepathUtf8 = self.filepath.encode('utf-8') #type:ignore
		name = os.path.basename(self.filepath) #type:ignore
		objCount = ctypes.c_int()
		usgCount = ctypes.c_int()
		flatCutoffCount = ctypes.c_int()
		objArr = ctypes.POINTER(utils.StucObject)()
		usgArr = ctypes.POINTER(utils.StucUsg)()
		flatCutoffArr = ctypes.POINTER(utils.StucObject)()
		indexedAttribs = utils.StucAttribIndexedArr()
		err = stucLib.stucBlenderMapFileLoadForEdit(
			filepathUtf8,
			ctypes.pointer(objCount),
			ctypes.pointer(objArr),
			ctypes.pointer(usgCount),
			ctypes.pointer(usgArr),
			ctypes.pointer(flatCutoffCount),
			ctypes.pointer(flatCutoffArr),
			ctypes.pointer(indexedAttribs)
		)
		if err != 1:
			self.report({'ERROR'}, "Load failed")
			return {'CANCELLED'}
		mats = None
		i = 0
		while i < indexedAttribs.count:
			attribName = ctypes.cast(indexedAttribs.pArr[i].core.name, ctypes.c_char_p).value
			if attribName == b"materials":
				mats = indexedAttribs.pArr[i]
				break
			i += 1

		col = bpy.data.collections.new(f"StucEdit_{name}")
		context.collection.children.link(col)
		i = 0
		while (i < objCount.value):
			utils.blendObjFromStuc(stucLib, objArr[i], col, "Stuc", 'TEXTURED', False, mats)
			i += 1
		stucLib.stucBlenderObjArrDestroy(objCount, objArr)

		usgCol = bpy.data.collections.new(f"{name}_Usg")
		col.children.link(usgCol)
		cutoffCol = bpy.data.collections.new(f"{name}_FlatCutoff")
		col.children.link(cutoffCol)
		cutoffBlend = []
		i = 0
		while (i < flatCutoffCount.value):
			cutoff = utils.blendObjFromStuc(stucLib, flatCutoffArr[i], cutoffCol,  "FlatCutoff", 'WIRE', False)
			cutoffBlend.append(cutoff)
			i += 1
		i = 0
		while (i < usgCount.value):
			usg = utils.blendObjFromStuc(stucLib, usgArr[i].obj, usgCol, "Usg", 'WIRE', True)
			if (usgArr[i].pFlatCutoff):
				j = 0
				while (j < flatCutoffCount.value):
					cutoffPtr = ctypes.cast(ctypes.pointer(flatCutoffArr[j]), ctypes.c_void_p)
					usgCutoffPtr = ctypes.cast(usgArr[i].pFlatCutoff, ctypes.c_void_p)
					if cutoffPtr.value == usgCutoffPtr.value:
						usg["stucUsgFlatCutoff"] = cutoffBlend[j]
					j += 1
			i += 1
		stucLib.stucBlenderUsgArrDestroy(usgCount.value, usgArr)
		stucLib.stucBlenderObjArrDestroy(flatCutoffCount.value, flatCutoffArr)
		
		return {'FINISHED'}

class STUC_OT_StucLoadStucFile(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.load_stuc_file"
	bl_label = "Load STUC File"
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		name = os.path.basename(self.filepath) #type:ignore
		for map in context.scene.stucMaps: #type:ignore
			if (name == map.name):
				return {'CANCELLED'}
		filepathUtf8 = self.filepath.encode('utf-8') #type:ignore
		newMap = context.scene.stucMaps.add() #type:ignore
		newMap.name = name
		nameUtf8 = newMap.name.encode('utf-8')
		context.scene.stucMapsIndex = len(context.scene.stucMaps) #type:ignore
		err = stucLib.stucBlenderMapFileLoad(filepathUtf8, nameUtf8)
		if err != 1:
			self.report({'ERROR'}, "Load failed")
			return {'CANCELLED'}
		return {'FINISHED'}

#fix this
class STUC_OT_StucReloadStucFile(bpy.types.Operator):
	bl_idname = "stuc.reload_stuc_file"
	bl_label = "Reload STUC File"
	bl_options = {"REGISTER"}

	@classmethod
	def poll(cls, context) -> bool:
		return False

	def execute(self, context: bpy.types.Context) -> set[str]:
		currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex] #type:ignore
		mapUtf8 = ""
		err = stucLib.stucBlenderMapFileUnload(mapUtf8)
		if err != 1:
			self.report({'ERROR'}, "Map reload failed. Couldn't unload existing map")
		mapStr = mapUtf8.decode()
		exists = False
		for map in context.scene.stucMaps: #type:ignore
			if (mapStr == map.filepath):
				exists = True
				break
		if not exists:
			self.report({'ERROR'}, "Cannot reload map which is not loaded. How did this get called?")
			return {'CANCELLED'}
		err = stucLib.stucBlenderMapFileLoad(mapUtf8)
		if err != 1:
			self.report({'ERROR'}, "Load failed")
			return {'CANCELLED'}
		return {'FINISHED'}

class STUC_OT_StucPreviewImage(bpy.types.Operator):
	bl_idname = "stuc.stuc_preview_image"
	bl_label = "Preview Image"
	bl_options = {"REGISTER"}

	@classmethod
	def poll(cls, context) -> bool:
		#currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
		return False

	def execute(self, context: bpy.types.Context) -> set[str]:
		currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex] #type:ignore
		mapUtf8 = ""
		previewRes = 512
		dataLen = previewRes * previewRes * 4
		preview = numpy.empty(dataLen, dtype = numpy.float32)
		previewCtypes = preview.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
		stucLib.stucBlenderMapFileGenPreviewImage(
			mapUtf8,
			previewRes,
			previewCtypes
		)
		previewName = "Stuc_" + currentTarget.map
		image = bpy.data.images.get(previewName, None)
		if image:
			bpy.data.images.remove(image)
		image = bpy.data.images.new(previewName, previewRes, previewRes)
		image.pixels.foreach_set(preview) #type:ignore
		return {'FINISHED'}

class STUC_OT_StucRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_remove"
	bl_label = "STUC Remove"
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		scene = context.scene
		if scene.stucTargetsIndex >= len(scene.stucTargets): #type:ignore
			return {'CANCELLED'}
		del scene.stucTargets[scene.stucTargetsIndex].obj["stucWScale"] #type:ignore
		scene.stucTargets.remove(scene.stucTargetsIndex) #type:ignore
		return {'FINISHED'}

class STUC_OT_StucMatRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_remove"
	bl_label = "STUC Mat Remove"
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		pdb.set_trace()
		print("hi")
		return {'FINISHED'}

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
		commonAttribs = utils.updateCommonAttribs(
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
		mapArr = utils.StucBlenderMapArr()
		mapArr.ppArr = (ctypes.POINTER(ctypes.c_byte) * matCount)()
		mapArr.pMatIdxArr = (ctypes.c_byte * matCount)()
		mapArr.pCommonAttribArr = commonAttribs
		mapArr.count = matCount
		mapStrs = []
		
		inIndexedAttribs = utils.StucAttribIndexedArr()
		inIndexedAttribs.count = 1
		inIndexedAttribs.pArr = ctypes.pointer(utils.StucAttribIndexed())
		inMats = inIndexedAttribs.pArr.contents
		inMats.count = matCount
		inMats.core.type = utils.StucAttribType.STRING.value
		utils.copyString(inMats.core.name, "materials", utils.STUC_ATTRIB_NAME_MAX_LEN)
		StucString = ctypes.c_byte * utils.STUC_ATTRIB_STRING_MAX_LEN
		inMatsArr = (StucString * inMats.count)()
		inMats.core.pData = ctypes.cast(inMatsArr, ctypes.c_void_p)
		
		i = 0
		for mat in targetMats:
			utils.copyString(inMatsArr[i], mat.mat.name, utils.STUC_ATTRIB_STRING_MAX_LEN)
			mapStrs.append(mat.map.encode('utf-8'))
			mapArr.ppArr[i] = ctypes.cast(mapStrs[i], ctypes.POINTER(ctypes.c_byte))
			mapArr.pMatIdxArr[i] = objEval.material_slots.find(mat.mat.name)
			i += 1
		
		meshTuple = utils.formatAsStucMesh(meshEval, False, True, True, target.activeAttribs)
		workMesh = utils.StucMesh()
		stucLib.stucBlenderMapToMesh.argtypes = (
			ctypes.POINTER(ctypes.c_void_p),
			ctypes.POINTER(utils.StucBlenderMapArr),
			ctypes.POINTER(utils.StucMesh), ctypes.POINTER(utils.StucAttribIndexedArr),
			ctypes.POINTER(utils.StucMesh), ctypes.POINTER(utils.StucAttribIndexedArr),
			ctypes.c_float,
			ctypes.c_float
		)
		i = 0
		while i < meshTuple[0].faceAttribs.count:
			StucName = ctypes.c_byte * utils.STUC_ATTRIB_NAME_MAX_LEN
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
		outIndexedAttribs = utils.StucAttribIndexedArr()
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

			utils.copyStucMeshToBlenderMesh(
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
		

@persistent
def stucLoadPostHandler(dummy) -> None:
	stucLib.stucBlenderInit()
	bpy.context.scene.stucMaps.clear() #type:ignore

@persistent
def stucLoadPreHandler(dummy) -> None:
	stucLib.stucBlenderDestroy()

classes = [
	STUC_OT_StucSetAsUsg,
	STUC_OT_StucUnsetUsg,
	STUC_OT_StucSetFlatCutoff,
	STUC_OT_StucExportStucFile,
	STUC_OT_StucAssign,
	STUC_OT_StucMatAssign,
	STUC_OT_StucRemove,
	STUC_OT_StucMatRemove,
	STUC_OT_StucLoadStucFileForEdit,
	STUC_OT_StucLoadStucFile,
	STUC_OT_StucReloadStucFile,
	STUC_OT_StucPreviewImage
]

def register() -> None:
	
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)
