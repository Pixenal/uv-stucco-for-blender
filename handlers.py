'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast
import ctypes
import pdb
import sys
import re
from enum import Enum
import os
import cProfile

import bpy
from bpy.app.handlers import persistent

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mapping
from . import stuc
from . import props
from . import scene_cache as sceneCache
from . import client

@persistent
def stucLoadPostHandler(dummy) -> None:
	try:
		sceneCache.correctCacheLib()
		
		if not c_lib.initDir:
			raise Exception("init failed, init-dir is None")
		logDir = f"{c_lib.initDir}/log"
		if not os.path.exists(logDir):
			os.mkdir(logDir)
		err = stucLib.stucBlenderInit(f"{logDir}/uv_stucco.cark".encode('utf-8'))
		if err != 1:
			raise Exception("failed to init stuc for blender")
		
		for map in bpy.context.scene.stucMaps: #type:ignore
			map.timestamp = ".0"
			map.id = 0
			map.status = '0'
			for dep in map.deps:
				dep.timestamp = ""
				dep.id = 0
				if dep.map == "":
					dep.map = dep.name
		bpy.context.scene.stucTargetIdNext = 0 #type:ignore
		props.relPathsUpdate(bpy.context.scene.stuc, bpy.context)#type:ignore
		for target in bpy.context.scene.stucTargets: #type:ignore
			target.id = bpy.context.scene.stucTargetIdNext #type:ignore
			bpy.context.scene.stucTargetIdNext += 1 #type:ignore
			target.lastObj = target.obj
		if not bpy.app.background:
			draw.reloadCoreTextures()
			
		args = client.checkForShmArg()
		if args:
			sceneCache.sceneImportToFile(args[0], args[1])
		#maps arn't loaded yet, so this is to cache targets for error mat draw
		mapping.mapToTargetsInScene(bpy.context, selOnly = False)
	except Exception as e:
		raise e

@persistent
def stucLoadPreHandler(dummy) -> None:
	stucLib.stucBlenderDestroy()
	bpy.context.scene.stucMaps.clear() #type:ignore

@persistent
def stucDepsgraphUpdatePostHandler(dummy) -> None:
	#update mat-map pair names (if blend mat name has changed)
	#this can't be caught in prop update callback, so is done here instead
	for stucMat in bpy.context.scene.stucMats:#type:ignore
		if stucMat.mat:
			stucMat.name = stucMat.mat.name
		elif len(stucMat.name):
			raise Exception("'mat' in mat-map pair empty but entry name wasn't updated?")

	utils.updateUiTargetIdx(bpy.context)
	mapping.mapToTargetsInScene(bpy.context)

@persistent
def stucSavePreHandler(dummy) -> None:
	for target in bpy.context.scene.stucTargets: #type:ignore
		target.lastObj = None
	
@persistent
def stucSavePostHandler(dummy) -> None:
	try:
		sceneCache.correctCacheLib()
		props.relPathsUpdate(bpy.context.scene.stuc, bpy.context)#type:ignore
	except Exception as e:
		raise e

def getTargetMesh(
	target: props.StucTarget
) -> list[float | stuc.StucMesh | stuc.StucAttribIndexedArr | stuc.MeshCacheType] | None:
	timestamp = ctypes.c_double()
	mesh = ctypes.POINTER(stuc.StucMesh)()
	idxAttribs = ctypes.POINTER(stuc.StucAttribIndexedArr)()
	cacheType = ctypes.c_int32()
	err = stucLib.stucBlenderTargetCacheGet(
		target.id,
		ctypes.pointer(timestamp),
		ctypes.pointer(mesh),
		ctypes.pointer(idxAttribs),
		ctypes.pointer(cacheType)
	)
	if err != 1:
		raise Exception("error getting target mesh")
	if mesh:
		return [
			timestamp.value,
			mesh.contents,
			idxAttribs.contents,
			stuc.MeshCacheType(cacheType.value)
		]
	else:
		return None

if not bpy.app.background:
	from . import draw

	def drawTarget(
		target: props.StucTarget,
		frame: int,
		matCache: dict[str, draw.MatCacheEntry]
	) -> None:
		if type(target.obj.data) != bpy.types.Mesh:
			return
		cache = getTargetMesh(target)
		if not cache:
			return
		if type(cache[0]) != float or\
		type(cache[1]) != stuc.StucMesh or\
		type(cache[3]) != stuc.MeshCacheType:
			raise Exception()
		idxAttribs = cache[2] if cache[3] == stuc.MeshCacheType.MESH_CACHE_OUT else None
		if idxAttribs != None and type(idxAttribs) != stuc.StucAttribIndexedArr:
			raise Exception()
		draw.drawMeshInViewport(
			f"{target.id}_{target.obj.name}",
			cache[0],
			frame,
			matCache,
			cache[1],
			target.obj.matrix_world,
			cache[3],
			idxAttribs = idxAttribs,
			mats = None if idxAttribs else [mat for mat in target.obj.data.materials]
		)
		if cache[3] == stuc.MeshCacheType.MESH_CACHE_IN_EDIT and target.obj.mode == 'EDIT':
			draw.drawEditOverlay(cache[1], target.obj)

	frame: int = 0

	@persistent
	def stucDrawHandler() -> None:
		try :
			if bpy.context.scene.stuc.dontDraw:#type:ignore
				return
			global frame
			frame += 1
			col = sceneCache.getCacheIfVisible(bpy.context)
			matCache = dict[str, draw.MatCacheEntry]()
			for i, target in enumerate(bpy.context.scene.stucTargets): #type:ignore
				if not target.obj or\
				   not bpy.context.view_layer.objects.get(target.obj.name, None):
					continue
				if col and sceneCache.getTargetInCacheIfVisible(col, target):
					continue
				#cProfile.runctx('drawTarget(target)', globals(), locals())
				drawTarget(target, frame, matCache)
			draw.batchCache.clean(frame)
			draw.previewArr.clear()
			#print(f"draw cache size is {len(draw.batchCache.table.keys())}")
		except Exception as e:
			raise e

def register() -> None:
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)
	bpy.app.handlers.save_post.append(stucSavePostHandler)
	bpy.app.handlers.save_pre.append(stucSavePreHandler)
	if not bpy.app.background:
		bpy.types.SpaceView3D.draw_handler_add(stucDrawHandler, (), 'WINDOW', 'POST_VIEW')

def unregister() -> None:
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)
	bpy.app.handlers.save_post.remove(stucSavePostHandler)
	bpy.app.handlers.save_pre.remove(stucSavePreHandler)
	if not bpy.app.background:
		bpy.types.SpaceView3D.draw_handler_remove(stucDrawHandler, 'WINDOW')