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
from . import mapping
from . import props
from . import attrib_utils as attribUtils

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
	bl_options = {'REGISTER'}

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
	ctypes.c_int32,
	ctypes.c_char_p,
	ctypes.POINTER(stuc.PixtyStrArr),
	ctypes.POINTER(ctypes.c_byte),
	ctypes.POINTER(ctypes.c_double)
)
def getMapInDirs(mapNameUtf8: ctypes.c_char_p, dirArrPtr, path, timestamp) -> int:
	mapName = mapNameUtf8.decode('utf-8') #type:ignore
	map = bpy.context.scene.stucMaps.get(mapName, None) #type:ignore
	if map:
		pathAsStr = os.path.join(bpy.path.abspath(map.dir), map.name)
		if os.path.exists(pathAsStr):
			fileTimestamp = os.path.getmtime(pathAsStr)
			if float(map.timestamp) == fileTimestamp:
				return 0 #map is up to date
			else:
				utils.copyString(path, pathAsStr, 32768)
				timestamp.contents.value = fileTimestamp
				return 0
	dirArr = dirArrPtr.contents
	i = 0
	while i < dirArr.count:
		for root, dirs, files in os.walk(dirArr.pArr[i].decode('utf-8')):
			for name in files:
				if name == mapName:
					pathAsStr = os.path.join(root, name)
					utils.copyString(path, pathAsStr, 32768)
					timestamp.contents = ctypes.c_double(os.path.getmtime(pathAsStr)) #type:ignore
					return 0
		i += 1
	return 1

def addOrUpdateMap(
	context: bpy.types.Context,
	name: str,
	path: str,
	timestamp: float,
	status: int,
	deps: stuc.PixtyStrArr
) -> props.StucMap:
	map = context.scene.stucMaps.get(name, None) #type:ignore
	if map:
		map.deps.clear()
		map.depsIdx = 0
	else:
		map = context.scene.stucMaps.add() #type:ignore
		map.name = name
	map.dir = os.path.dirname(path)
	map.timestamp = str(timestamp)
	map.status = str(status)
	map.age = context.scene.stucAgeNext #type:ignore
	context.scene.stucAgeNext += 1 #type:ignore

	i = 0
	while i < deps.count:
		entry = map.deps.add()
		depName = deps.pArr[i].decode('utf-8')
		entry.name = depName
		i += 1

	map.attribs.clear() #type:ignore
	mesh = meshUtils.getMapMesh(name)
	attrib = attribUtils.getActiveAttrib(mesh, stuc.StucAttribUse.POS)
	if not attrib:
		raise Exception("map mesh missing position attrib")
	utils.initActiveAttrib(map, "position", "").name = attribUtils.attribNameToStr(attrib)
	attrib = attribUtils.getActiveAttrib(mesh, stuc.StucAttribUse.NORMAL)
	if not attrib:
		raise Exception("map mesh missing normal attrib")
	utils.initActiveAttrib(map, "normal", "").name = attribUtils.attribNameToStr(attrib)
	attrib = attribUtils.getActiveAttrib(mesh, stuc.StucAttribUse.UV)
	if attrib:
		utils.initActiveAttrib(map, "UV", "").name = attribUtils.attribNameToStr(attrib)
	attrib = attribUtils.getActiveAttrib(mesh, stuc.StucAttribUse.COLOR)
	col = utils.initActiveAttrib(map, "Color", "")
	if attrib:
		col.name = attribUtils.attribNameToStr(attrib)
	attribUtils.attribArrToCol(map.attribs, mesh.faceAttribs, map) #type:ignore
	attribUtils.attribArrToCol(map.attribs, mesh.cornerAttribs, map) #type:ignore
	attribUtils.attribArrToCol(map.attribs, mesh.edgeAttribs, map) #type:ignore
	attribUtils.attribArrToCol(map.attribs, mesh.vertAttribs, map) #type:ignore
	return map

@ctypes.CFUNCTYPE(
	None,
	ctypes.c_char_p,
	ctypes.c_char_p,
	ctypes.c_double,
	ctypes.c_int32,
	ctypes.POINTER(stuc.PixtyStrArr)
)
def storeMap(
	name: ctypes.c_char_p,
	path: ctypes.c_char_p,
	timestamp: float,
	status: int,
	deps: Any
) -> None:
	addOrUpdateMap(
		bpy.context,
		name.decode('utf-8'),#type:ignore
		path.decode('utf-8'),#type:ignore
		timestamp,
		status,
		deps.contents
	)

def getDepDirs(
	context: bpy.types.Context,
	filepath: str,
	depDirsList: list[Any]
) -> stuc.PixtyStrArr:
	dirs = stuc.PixtyStrArr()
	dirs.size = len(context.scene.stucDepDirs) + 1 #type:ignore
	dirs.pArr = (ctypes.c_char_p * dirs.size)()
	dirUtf8 = os.path.dirname(filepath).encode('utf-8') #type:ignore
	dirs.pArr[0] = dirUtf8
	dirs.count = 1
	for dir in context.scene.stucDepDirs: #type:ignore
		depDirsList.append(dir.name.encode('utf-8'))
		dirs.pArr[dirs.count] = depDirsList[-1]
		dirs.count += 1
	return dirs

def loadMap(
	context: bpy.types.Context,
	filepath: str,
	name: str
) -> int:
	timestamp = os.path.getmtime(filepath) #type:ignore
	map = context.scene.stucMaps.get(name, None) #type:ignore
	dirty = isMapDirty(timestamp, map)
	depDirsList = [] #declared here to keep relevant in memory
	dirs = getDepDirs(context, filepath, depDirsList) #type:ignore

	err = stucLib.stucBlenderMapFileLoad(
		filepath.encode('utf-8'),
		name.encode('utf-8'),
		ctypes.c_double(timestamp),
		ctypes.pointer(dirs),
		getMapInDirs,
		storeMap,
		dirty
	)
	if err != 1:
		return err
	
	context.scene.stucMapsIdx = context.scene.stucMaps.find(name) #type:ignore
	return err

def isMapDirty(timestamp: float, map: props.StucMap) -> bool:
	if not map or map.status != 1: #status != LOADED
		return True
	#print(f"timestamp {timestamp}, map-timestamp {float(map.timestamp)}")
	if timestamp != float(map.timestamp):
		return True
	for dep in map.deps: #type:ignore
		if dep.map and dep.map.age > map.age:
			return True
	return False

class STUC_OT_StucLoadStucFile(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.load_stuc_file"
	bl_label = "Load STUC File"
	bl_options = {'REGISTER'}

	filename_ext = ".stuc"
	filter_glob :\
		bpy.props.StringProperty(default = "*.stuc", options = {'HIDDEN'}) #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			name = os.path.basename(self.filepath) #type:ignore
			err = loadMap(context, self.filepath, name) #type:ignore
			if err != 1:
				raise Exception("error loading map")
		except Exception as e:
			self.report({'ERROR'}, "Load failed")
			raise e
		return {'FINISHED'}

class STUC_OT_StucReloadStucFile(bpy.types.Operator):
	bl_idname = "stuc.reload_stuc_file"
	bl_label = "Reload STUC File"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
		return len(context.scene.stucMaps) > 0 #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			err = 1
			for map in context.scene.stucMaps: #type:ignore
				filepath = os.path.join(bpy.path.abspath(map.dir), map.name)
				if loadMap(context, filepath, map.name) != 1:
					err = 2
			if err != 1:
				raise Exception("error loading one or more maps")
		except Exception as e:
			self.report({'ERROR'}, "Reload failed")
			raise e
		return {'FINISHED'}
	
class STUC_OT_StucExtraDepDirAdd(bpy.types.Operator, ImportHelper):
	bl_idname = "stuc.extra_dep_dir_add"
	bl_label = "Add Dep Dir"
	bl_options = {'REGISTER'}

	directory : bpy.props.StringProperty(subtype = 'DIR_PATH') #type:ignore
	filter_glob : bpy.props.StringProperty(default = "", options = {'HIDDEN'}) #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			dir = utils.makeRel(context, self.directory)
			entry = context.scene.stucDepDirs.get(dir, None) #type:ignore
			if not entry:
				entry = context.scene.stucDepDirs.add() #type:ignore
				entry.name = dir
		except Exception as e:
			self.report({'ERROR'}, "Failed to add dependency dir")
			raise e
		return {'FINISHED'}

class STUC_OT_StucExtraDepDirRemove(bpy.types.Operator):
	bl_idname = "stuc.extra_dep_dir_remove"
	bl_label = "Remove Dep Dir"
	bl_options = {'REGISTER'}

	item : bpy.props.StringProperty(subtype = 'DIR_PATH') #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			idx = context.scene.stucDepDirs.find(self.item) #type:ignore
			context.scene.stucDepDirs.remove(idx) #type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to add dependency dir")
			raise e
		return {'FINISHED'}

classes = [
	STUC_OT_StucExportStucFile,
	STUC_OT_StucLoadStucFileForEdit,
	STUC_OT_StucLoadStucFile,
	STUC_OT_StucReloadStucFile,
	STUC_OT_StucExtraDepDirAdd,
	STUC_OT_StucExtraDepDirRemove
]

def register() -> None:
	
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
