import sys
import ctypes
import re
from enum import Enum
import os
import pdb

import bpy

from . import c_lib
stucLib = c_lib.stucLib
from . import stuc
from . import mapping
from . import client

def sceneImportInit(shmName: str) -> stuc.PixioShmCtx:
	shmCtx = stuc.PixioShmCtx()
	err = stucLib.stucBlenderSceneImportInit(
		ctypes.pointer(shmCtx),
		shmName.encode('utf-8')
	)
	if err != 1:
		raise Exception()
	
	'''
	size = ctypes.c_int32()
	desc = ctypes.c_int32()
	err = stucLib.stucBlenderSceneImportQuery(
		shmCtx,
		ctypes.pointer(size),
		ctypes.pointer(desc),
		None
	)
	if err != 1 or desc != stuc.ShmDesc.STUCB_SHM_NAME.value:
		raise Exception()
	bSceneDir = (ctypes.c_byte * size.value)()
	err = stucLib.stucBlenderSceneImportStr(shmCtx, bSceneDir)
	if err != 1 or size.value < 1:
		raise Exception()
	
	err = stucLib.stucBlenderSceneImportQuery(
		shmCtx,
		ctypes.pointer(size),
		ctypes.pointer(desc),
		None
	)
	if err != 1 or desc != stuc.ShmDesc.STUCB_SHM_DIR.value:
		raise Exception()
	bSceneName = (ctypes.c_byte * size.value)()
	err = stucLib.stucBlenderSceneImportStr(shmCtx, bSceneName)
	if err != 1 or size.value < 1:
		raise Exception()
	sceneDir = ctypes.cast(bSceneDir, ctypes.c_char_p).value.decode('utf-8') #type:ignore
	sceneName = ctypes.cast(bSceneName, ctypes.c_char_p).value.decode('utf-8') #type:ignore
	'''
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
			raise Exception() #remaining items in ShmDesc are currently handled in above 2 cases

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