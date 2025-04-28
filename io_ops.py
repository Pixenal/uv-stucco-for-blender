'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
import os
import math
from typing import Any, cast
import pdb

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mesh_utils as meshUtils
from . import stuc

class STUC_OT_StucExportStucFile(bpy.types.Operator, ExportHelper):
	bl_idname = "stuc.export_stuc_file"
	bl_label = "STUC Export"
	bl_options = {'REGISTER'}

	filename_ext = ".stuc"
	filter_glob :\
		bpy.props.StringProperty(default = "*.stuc", options = {'HIDDEN'}) #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			if (len(context.selected_objects) == 0):
				self.report({'WARNING'}, "Nothing was exported, no objects selected")
				return {'CANCELLED'}
			
			filepath = self.filepath #type:ignore
			filePathUtf8 = filepath.encode('utf-8')
		
			depsgraph = context.evaluated_depsgraph_get()
			ObjArr = stuc.StucObject * len(context.selected_objects)
			UsgArr = stuc.StucUsg * len(context.selected_objects)
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
			matTable = stuc.StucBlenderMatTableArr()
			matTable.count = objCount
			MatTableArr = stuc.StucBlenderMatTable * matTable.count
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
				if not isUsg:
					objTuple = meshUtils.formatAsStucObj(
						obj,
						depsgraph,
						True,
						mats,
						matTable.pArr[objIdx]
					)
					objArr[objIdx] = objTuple[0]
					tuples.append(objTuple)
					objIdx += 1
					continue
				objTuple = meshUtils.formatAsStucObj(obj, depsgraph, False)
				usgArr[usgCount].obj = objTuple[0]
				tuples.append(objTuple)
				flatCutoff = obj.get("stucUsgFlatCutoff", None)
				if (flatCutoff):
					if flatCutoff.type == 'MESH':
						cutoffPtr = cutoffs.get(flatCutoff.name, None)
						if not cutoffPtr:
							cutoffObjTuple =\
								meshUtils.formatAsStucObj(flatCutoff, depsgraph, False)
							cutoffPtr = ctypes.pointer(cutoffObjTuple[0])
							cutoffs.update({flatCutoff.name : cutoffPtr})
							tuples.append(cutoffObjTuple)
						usgArr[usgCount].pFlatCutoff = cutoffPtr
				usgCount += 1
			
			indexedAttribCount = 0
			indexedAttribs = stuc.StucAttribIndexedArr()
			if matCount:
				if not mats:
					raise Exception("mats is None")
				MatArr = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN * matCount
				matArr = MatArr()
				i = 0
				for matName in mats.keys():
					utils.copyString(matArr[i], matName, stuc.STUC_ATTRIB_NAME_MAX_LEN)
					i += 1
				matAttrib = stuc.StucAttribIndexed()
				matAttrib.core.pData =  ctypes.cast(matArr, ctypes.c_void_p)
				utils.copyString(
					matAttrib.core.name,
					"materials",
					stuc.STUC_ATTRIB_NAME_MAX_LEN
				)
				matAttrib.core.type = stuc.StucAttribType.STRING.value
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
				raise Exception("stuc map file export returned error")
		except Exception as e:
			self.report({'ERROR'}, "Export failed")
			raise e
		return {'FINISHED'}
	
class STUC_OT_StucLoadStucFileForEdit(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.load_stuc_file_for_edit"
	bl_label = "Load STUC File For Edit"
	bl_options = {"REGISTER"}

	filename_ext = ".stuc"
	filter_glob :\
		bpy.props.StringProperty(default = "*.stuc", options = {'HIDDEN'}) #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			filepathUtf8 = self.filepath.encode('utf-8') #type:ignore
			name = os.path.basename(self.filepath) #type:ignore
			objCount = ctypes.c_int()
			usgCount = ctypes.c_int()
			flatCutoffCount = ctypes.c_int()
			objArr = ctypes.POINTER(stuc.StucObject)()
			usgArr = ctypes.POINTER(stuc.StucUsg)()
			flatCutoffArr = ctypes.POINTER(stuc.StucObject)()
			indexedAttribs = stuc.StucAttribIndexedArr()
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
				raise Exception("stuc map file load returned error")
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
				meshUtils.blendObjFromStuc(stucLib, objArr[i], col, "Stuc", 'TEXTURED', False, mats)
				i += 1
			stucLib.stucBlenderObjArrDestroy(objCount, objArr)

			usgCol = bpy.data.collections.new(f"{name}_Usg")
			col.children.link(usgCol)
			cutoffCol = bpy.data.collections.new(f"{name}_FlatCutoff")
			col.children.link(cutoffCol)
			cutoffBlend = []
			i = 0
			while (i < flatCutoffCount.value):
				cutoff = meshUtils.blendObjFromStuc(stucLib, flatCutoffArr[i], cutoffCol,  "FlatCutoff", 'WIRE', False)
				cutoffBlend.append(cutoff)
				i += 1
			i = 0
			while (i < usgCount.value):
				usg = meshUtils.blendObjFromStuc(stucLib, usgArr[i].obj, usgCol, "Usg", 'WIRE', True)
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
		except Exception as e:
			self.report({'ERROR'}, "Load failed")
			raise e
		return {'FINISHED'}

class STUC_OT_StucLoadStucFile(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.load_stuc_file"
	bl_label = "Load STUC File"
	bl_options = {"REGISTER"}

	filename_ext = ".stuc"
	filter_glob :\
		bpy.props.StringProperty(default = "*.stuc", options = {'HIDDEN'}) #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			name = os.path.basename(self.filepath) #type:ignore
			filepathUtf8 = self.filepath.encode('utf-8') #type:ignore
			nameUtf8 = name.encode('utf-8')
			timestamp = os.path.getmtime(self.filepath) #type:ignore
			for map in context.scene.stucMaps: #type:ignore
				if (name == map.name):
					if (timestamp == float(map.timestamp)):
						continue
					map.timestamp = str(timestamp)
					stucLib.stucBlenderMapFileReload(filepathUtf8, nameUtf8)
					return {'FINISHED'}
			newMap = context.scene.stucMaps.add() #type:ignore
			newMap.name = name
			newMap.dir = os.path.dirname(self.filepath) #type:ignore
			if len(bpy.data.filepath) and context.scene.stuc.relPaths: #type:ignore
				newMap.dir = bpy.path.relpath(newMap.dir)
			print(f"saving map dir as {newMap.dir}")
			newMap.timestamp = str(timestamp)
			context.scene.stucMapsIdx = len(context.scene.stucMaps) #type:ignore
			err = stucLib.stucBlenderMapFileLoad(filepathUtf8, nameUtf8)
			if err != 1:
				raise Exception("stuc map file load returned error")
		except Exception as e:
			self.report({'ERROR'}, "Load failed")
			raise e
		return {'FINISHED'}

class STUC_OT_StucReloadStucFile(bpy.types.Operator):
	bl_idname = "stuc.reload_stuc_file"
	bl_label = "Reload STUC File"
	bl_options = {"REGISTER"}

	@classmethod
	def poll(cls, context) -> bool:
		return len(context.scene.stucMaps) > 0 #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			for map in context.scene.stucMaps: #type:ignore
				print(f"refreshing in {map.dir}")
				filepath = os.path.join(bpy.path.abspath(map.dir), map.name)
				print(f"filepath {filepath}")
				timestamp = os.path.getmtime(filepath)
				print(f"timestamp {timestamp}, map-timestamp {float(map.timestamp)}")
				if (timestamp == float(map.timestamp)):
					continue
				map.timestamp = str(timestamp)
				filepathUtf8 = filepath.encode('utf-8')
				nameUtf8 = map.name.encode('utf-8')
				err = stucLib.stucBlenderMapFileReload(filepathUtf8, nameUtf8)
				if err != 1:
					self.report({'ERROR'}, "Failed to reload map file")
		except Exception as e:
			self.report({'ERROR'}, "Reload failed")
			raise e
		return {'FINISHED'}
	
classes = [
	STUC_OT_StucExportStucFile,
	STUC_OT_StucLoadStucFileForEdit,
	STUC_OT_StucLoadStucFile,
	STUC_OT_StucReloadStucFile
]

def register() -> None:
	
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
