'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from hmac import new
import sys
import ctypes
import re
from enum import Enum
import os
import pdb
import shutil

import bpy

from . import c_lib
stucLib = c_lib.stucLib
from . import stuc
from . import mapping
from . import client
from . import props

def sceneImportInit(shmName: str) -> stuc.PixioShmCtx:
	shmCtx = stuc.PixioShmCtx()
	err = stucLib.stucBlenderSceneImportInit(
		ctypes.pointer(shmCtx),
		shmName.encode('utf-8')
	)
	if err != 1:
		raise Exception()
	return shmCtx

def sceneImportDestroy(shmCtx: ctypes.c_void_p) -> None:
	err = stucLib.stucBlenderSceneImportDestroy(shmCtx)
	if err != 1:
		raise Exception()
	shmCtx = ctypes.c_void_p()

def sceneImport(shmCtx: ctypes.c_void_p) -> None:
	size = ctypes.c_int32()
	desc = ctypes.c_int32()
	close = ctypes.c_bool()
	while True:
		err = stucLib.stucBlenderSceneImportQuery(
			shmCtx,
			ctypes.pointer(size),
			ctypes.pointer(desc),
			ctypes.pointer(close)
		)
		if err != 1:
			raise Exception()
		if close.value:
			break
		if desc.value == stuc.ShmDesc.STUCB_SHM_OBJ.value:
			name = (ctypes.c_byte * size.value)()
			err = stucLib.stucBlenderSceneImportStr(shmCtx, name)
			if err != 1:
				raise Exception()
			err = stucLib.stucBlenderSceneImportQuery(
				shmCtx,
				ctypes.pointer(size),
				ctypes.pointer(desc),
				None
			)
			if err != 1 or desc.value != stuc.ShmDesc.STUCB_SHM_XFORM.value:
				raise Exception()
			stucObj = stuc.StucObject()
			stucMesh = stuc.StucMesh()
			stucObj.pData = ctypes.cast(
				ctypes.cast(ctypes.pointer(stucMesh), ctypes.c_void_p),
				ctypes.POINTER(stuc.StucObjectData)
			)
			err = stucLib.stucBlenderSceneImportObj(shmCtx, ctypes.pointer(stucObj))
			if err != 1:
				raise Exception()
			err = stucLib.stucBlenderSceneImportQuery(
				shmCtx,
				ctypes.pointer(size),
				ctypes.pointer(desc),
				None
			)
			if err != 1 or desc.value != stuc.ShmDesc.STUCB_SHM_IDX_ATTRIB_ARR.value:
				raise Exception()
			idxAttribs = stuc.StucAttribIndexedArr()
			err = stucLib.stucBlenderSceneImportIdxAttribs(
				shmCtx,
				ctypes.pointer(idxAttribs)
			)
			if err != 1:
				raise Exception()
			mapping.addOrUpdateBlendMesh(
				bpy.context,
				stucObj,
				idxAttribs,
				ctypes.cast(name, ctypes.c_char_p).value.decode('utf-8') #type:ignore
			)
		else: 
			raise Exception()

def sceneImportToFile(shmName: str, shmServer: str) -> None:
	try:
		shmCtx = sceneImportInit(shmName)
		shmCtxPtr = ctypes.cast(ctypes.pointer(shmCtx), ctypes.c_void_p)
		sceneImport(shmCtxPtr)
		sceneImportDestroy(shmCtxPtr)
		bpy.ops.wm.save_mainfile(filepath = client.createCachePath(shmServer))
	except Exception:
		pass
	bpy.ops.wm.quit_blender()

def linkCache(context: bpy.types.Context, filepath: str) -> None:
	cachePath = client.createCachePath(filepath)
	stucCol = bpy.data.collections.get("_STUC_CACHE", None)
	#reload existing linked objects if present
	cacheLib = bpy.data.libraries.get(bpy.path.basename(cachePath), None)
	if cacheLib:
		cacheLib.reload()
	#now link in any new objects from cache
	cacheLib = bpy.data.libraries.load(
		cachePath,
		link = True,
		create_liboverrides = True
	)
	with cacheLib as (dataSrc, dataDest):
		dataDest.objects = [
			name for name in dataSrc.objects if
			".Stuc" in name and (not stucCol or not name in stucCol.objects)
		]
	if not stucCol:
		stucCol = bpy.data.collections.new(name = "_STUC_CACHE")
		context.scene.collection.children.link(stucCol)
	for obj in dataDest.objects:
		stucCol.objects.link(obj)

def getCacheIfVisible(context: bpy.types.Context) -> bpy.types.Collection | None:
	stucLayCol = context.view_layer.layer_collection.children.get("_STUC_CACHE", None)
	if not stucLayCol or not stucLayCol.is_visible:
		return None
	stucCol = bpy.data.collections.get("_STUC_CACHE", None)
	if not stucCol or stucCol.hide_viewport or not context.scene.user_of_id(stucCol): #type:ignore
		return None
	return stucCol

def getTargetInCacheIfVisible(
	col: bpy.types.Collection,
	target: props.StucTarget
) -> bpy.types.Object | None:
	obj = col.objects.get(target.obj.name + ".Stuc", None)
	if obj and not obj.hide_viewport and not obj.hide_get():
		return obj
	return None

def correctCacheLib() -> None:
	for lib in bpy.data.libraries:
		if "_STUC_CACHE" in lib.name:
			newPath = os.path.abspath(client.createCachePath(bpy.data.filepath))
			oldPath = os.path.abspath(lib.filepath)
			if newPath == oldPath:
				return
			if not os.path.exists(newPath) and os.path.exists(oldPath):
				shutil.copyfile(oldPath, newPath)
			lib.name = bpy.path.basename(newPath)
			lib.filepath = newPath
		