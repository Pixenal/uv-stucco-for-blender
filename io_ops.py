'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
import os
import math
from pickletools import int4
from typing import Any, cast
import pdb

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mesh_utils as meshUtils
from . import stuc
from . import mapping

class CutoffTable():
	def __init__(self):
		self.dict = {}
		self.count = 0

def addFlatCutoff(
	handle : ctypes.c_void_p,
	depsgraph : bpy.types.Depsgraph,
	cutoffTable : CutoffTable,
	flatCutoff : bpy.types.Object
) -> stuc.StucFlatCutoffIdx:
	if flatCutoff.type != 'MESH':
		raise Exception("flat-cutoff object is not a mesh")
	cutoffIdx = cutoffTable.dict.get(flatCutoff.name, None)
	if not cutoffIdx:
		cutoffObj = meshUtils.formatAsStucObj(flatCutoff, True, depsgraph, False)
		err = stucLib.stucBlenderMapExportUsgCutoffAdd(
			handle,
			ctypes.pointer(cutoffObj.obj)
		)
		if err != 1:
			raise Exception("stuc map export usg-cutoff add failed")
		cutoffIdx = cutoffTable.count
		cutoffTable.count += 1
		cutoffTable.dict.update({flatCutoff.name : cutoffIdx})
	return stuc.StucFlatCutoffIdx(cutoffIdx, True)

def addUsgToMapExport(
	handle : ctypes.c_void_p,
	depsgraph : bpy.types.Depsgraph,
	obj : bpy.types.Object,
	cutoffTable : CutoffTable
) -> None:
	stucObj = meshUtils.formatAsStucObj(obj, True, depsgraph, False)
	usg = stuc.StucUsg()
	usg.obj = stucObj.obj
	flatCutoff = obj.get("stucUsgFlatCutoff", None).evaluated_get(depsgraph)
	if (flatCutoff):
		usg.flatCutoff =\
			addFlatCutoff(handle, depsgraph, cutoffTable, flatCutoff)
	err = stucLib.stucBlenderMapExportUsgAdd(handle, ctypes.pointer(usg))
	if err != 1:
		raise Exception("stuc map export usg add failed")
	
def addObjToMapExport(
	context : bpy.types.Context,
	handle : ctypes.c_void_p,
	depsgraph : bpy.types.Depsgraph,
	obj : bpy.types.Object
) -> None:
	target = None
	for item in context.scene.stucTargets: #type:ignore
		if (item.obj.name == obj.name):
			target = item
			break
	if target:
		info = mapping.prepTargetForMapping(context, depsgraph, target)
		if info:
			stucLib.stucBlenderMapExportTargetAdd.argtypes = (
				ctypes.c_void_p,
				ctypes.POINTER(stuc.StucMapArr),
				ctypes.POINTER(stuc.StucObject),
				ctypes.POINTER(stuc.StucAttribIndexedArr),
				ctypes.c_float,
				ctypes.c_float
			)
			err = stucLib.stucBlenderMapExportTargetAdd(
				handle,
				ctypes.pointer(info.mapArr),
				ctypes.pointer(info.stucObj.obj),
				ctypes.pointer(info.inIndexedArr),
				info.wScale,
				info.receiveLen
			)
			if err != 1:
				raise Exception("stuc map export target add failed")
			return
	idxAttribs = mapping.createMatIdxAttrib(obj.data) #type:ignore
	stucObj = meshUtils.formatAsStucObj(obj, True, depsgraph, True)
	err = stucLib.stucBlenderMapExportObjAdd(
		handle,
		ctypes.pointer(stucObj.obj),
		ctypes.pointer(idxAttribs)
	)
	if err != 1:
		raise Exception("stuc map export obj add failed")

def addToMapExport(context : bpy.types.Context, handle : ctypes.c_void_p) -> None:
	depsgraph = context.evaluated_depsgraph_get()
	cutoffTable = CutoffTable()

	for obj in context.selected_objects:
		objEval = obj.evaluated_get(depsgraph)
		if objEval.type != 'MESH':
			continue
		isUsg = obj.get("StucUsg", None)
		if isUsg:
			addUsgToMapExport(handle, depsgraph, objEval, cutoffTable)
		else:
			addObjToMapExport(context, handle, depsgraph, objEval)

class STUC_OT_StucExportStucFile(bpy.types.Operator, ExportHelper):
	bl_idname = "stuc.export_stuc_file"
	bl_label = "STUC Export"
	bl_options = {'REGISTER'}

	filename_ext = ".stuc"
	filter_glob :\
		bpy.props.StringProperty(default = "*.stuc", options = {'HIDDEN'}) #type:ignore
	
	compress : bpy.props.BoolProperty(name = "Compress", default = True) #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			if (len(context.selected_objects) == 0):
				self.report({'WARNING'}, "Nothing was exported, no objects selected")
				return {'CANCELLED'}
			
			filepath = self.filepath #type:ignore
			filePathUtf8 = filepath.encode('utf-8')

			handle = ctypes.c_void_p()

			err = stucLib.stucBlenderMapExportInit(
				ctypes.pointer(handle),
				filePathUtf8,
				self.compress
			)
			if err != 1:
				raise Exception("stuc map export init failed")
			addToMapExport(context, handle)
			err = stucLib.stucBlenderMapExportEnd(ctypes.pointer(handle))
			if err != 1:
				raise Exception("stuc map file export end failed")
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

@ctypes.CFUNCTYPE(
	None,
	ctypes.c_char_p,
	ctypes.POINTER(stuc.PixtyStrArr),
	ctypes.POINTER(ctypes.c_byte)
)
def getMapInDirs(mapNameUtf8: ctypes.c_char_p, dirArrPtr, path) -> None:
	mapName = mapNameUtf8.decode('utf-8') #type:ignore

	dirArr = dirArrPtr.contents
	i = 0
	while i < dirArr.count:
		for root, dirs, files in os.walk(dirArr.pArr[i].decode('utf-8')):
			for name in files:
				if name == mapName:
					utils.copyString(path, os.path.join(root, name), 32768)
					return
		i += 1

def getDepDirs(context: bpy.types.Context, filepath: str) -> stuc.PixtyStrArr:
	dirs = stuc.PixtyStrArr()
	dirs.size = len(context.scene.stucDepDirs) + 1 #type:ignore
	dirs.pArr = (ctypes.c_char_p * dirs.size)()
	dirUtf8 = os.path.dirname(filepath).encode('utf-8') #type:ignore
	dirs.pArr[0] = dirUtf8
	dirs.count = 1
	depDirsUtf8 = []
	for dir in context.scene.stucDepDirs: #type:ignore
		depDirsUtf8.append(dir.encode('utf-8'))
		dirs.pArr[dirs.count] = ctypes.pointer(depDirsUtf8[-1])
		dirs.count += 1
	return dirs

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
			print(f"name is {name}, path is {self.filepath}") #type:ignore
			filepathUtf8 = self.filepath.encode('utf-8') #type:ignore
			nameUtf8 = name.encode('utf-8')

			dirs = getDepDirs(context, self.filepath) #type:ignore

			timestamp = os.path.getmtime(self.filepath) #type:ignore
			for map in context.scene.stucMaps: #type:ignore
				if (name == map.name):
					if (timestamp == float(map.timestamp)):
						continue
					map.timestamp = str(timestamp)
					stucLib.stucBlenderMapFileLoad(
						filepathUtf8,
						nameUtf8,
						ctypes.pointer(dirs),
						getMapInDirs
					)
					return {'FINISHED'}
			newMap = context.scene.stucMaps.add() #type:ignore
			newMap.name = name
			newMap.dir = os.path.dirname(self.filepath) #type:ignore
			if len(bpy.data.filepath) and context.scene.stuc.relPaths: #type:ignore
				newMap.dir = bpy.path.relpath(newMap.dir)
			print(f"saving map dir as {newMap.dir}")
			newMap.timestamp = str(timestamp)
			context.scene.stucMapsIdx = len(context.scene.stucMaps) #type:ignore
			err = stucLib.stucBlenderMapFileLoad(
				filepathUtf8,
				nameUtf8,
				ctypes.pointer(dirs),
				getMapInDirs
			)
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
				print(f"name is {map.name}, path is {filepath}")
				timestamp = os.path.getmtime(filepath)
				print(f"timestamp {timestamp}, map-timestamp {float(map.timestamp)}")
				if (timestamp == float(map.timestamp)):
					continue
				map.timestamp = str(timestamp)
				filepathUtf8 = filepath.encode('utf-8')
				nameUtf8 = map.name.encode('utf-8')
				dirs = getDepDirs(context, filepath) #type:ignore
				err = stucLib.stucBlenderMapFileLoad(
					filepathUtf8,
					nameUtf8,
					ctypes.pointer(dirs),
					getMapInDirs
				)
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
