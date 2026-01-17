'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast
import ctypes
import numpy
import pdb
import cProfile

import bpy
from bpy.app.handlers import persistent
import bmesh
import mathutils

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mesh_utils as meshUtils
from . import attrib_utils as attribUtils
from . import mapping
from . import draw
from . import stuc
from . import props

@persistent
def stucLoadPostHandler(dummy) -> None:
	draw.initShaders()
	stucLib.stucBlenderInit()
	bpy.context.scene.stucAgeNext = 0 #type:ignore
	for map in bpy.context.scene.stucMaps: #type:ignore
		map.timestamp = ".0"
		map.age = 0
		map.status = '0'
	bpy.context.scene.stucTargetIdNext = 0 #type:ignore
	for target in bpy.context.scene.stucTargets: #type:ignore
		target.id = bpy.context.scene.stucTargetIdNext #type:ignore
		bpy.context.scene.stucTargetIdNext += 1 #type:ignore
		target.lastObj = target.obj

@persistent
def stucLoadPreHandler(dummy) -> None:
	stucLib.stucBlenderDestroy()
	bpy.context.scene.stucMaps.clear() #type:ignore

@persistent
def stucDepsgraphUpdatePostHandler(dummy) -> None:
	utils.updateUiTargetIdx(bpy.context)
	mapping.mapToSelTargets(bpy.context)

@persistent
def stucSavePreHandler(dummy) -> None:
	for target in bpy.context.scene.stucTargets: #type:ignore
		target.lastObj = None
		if len(target.displayType):
			if target.obj:
				target.obj.display_type = target.displayType
			target.displayType = ""
	
@persistent
def stucSavePostHandler(dummy) -> None:
	if not len(bpy.data.filepath) or not bpy.context.scene.stuc.relPaths: #type:ignore
		#this shouldn't be possible right?
		return
	for map in bpy.context.scene.stucMaps: #type:ignore
		map.dir = bpy.path.relpath(map.dir)

def getTargetMesh(
	target: props.StucTarget
) -> list[stuc.StucMesh | stuc.StucAttribIndexedArr | stuc.MeshCacheType] | None:
	mesh = ctypes.POINTER(stuc.StucMesh)()
	idxAttribs = ctypes.POINTER(stuc.StucAttribIndexedArr)()
	cacheType = ctypes.c_int32()
	err = stucLib.stucBlenderTargetCacheGet(
		target.id,
		ctypes.pointer(mesh),
		ctypes.pointer(idxAttribs),
		ctypes.pointer(cacheType)
	)
	if err != 1:
		raise Exception("error getting target mesh")
	if mesh:
		return [mesh.contents, idxAttribs.contents, stuc.MeshCacheType(cacheType.value)]
	else:
		return None

def drawTarget(target: props.StucTarget) -> None:
	if type(target.obj.data) != bpy.types.Mesh:
		return
	cache = getTargetMesh(target)
	if not cache:
		return
	if type(cache[0]) != stuc.StucMesh or type(cache[2]) != stuc.MeshCacheType:
		raise Exception()
	idxAttribs = cache[1] if cache[2] == stuc.MeshCacheType.MESH_CACHE_OUT else None
	if idxAttribs and type(idxAttribs) != stuc.StucAttribIndexedArr:
		raise Exception()
	edit = cache[2] == stuc.MeshCacheType.MESH_CACHE_IN_EDIT and target.obj.mode == 'EDIT'
	draw.drawStucMeshInViewport(
		cache[0],
		target.obj.matrix_world,
		editMode = edit,
		idxAttribs = idxAttribs,
		mats = None if idxAttribs else [mat for mat in target.obj.data.materials]
	)
	if edit:
		draw.drawEditOverlay(target.obj, cache[0])

@persistent
def stucDrawHandler() -> None:
	print("drawing targets")
	try :
		for target in bpy.context.scene.stucTargets: #type:ignore
			#cProfile.runctx('drawTarget(target)', globals(), locals())
			drawTarget(target)
			
		'''
		for obj in bpy.context.objects_in_mode:
			if type(obj.data) != bpy.types.Mesh:
				continue
			bm = bmesh.from_edit_mesh(obj.data)
			mesh = bpy.data.meshes.new("STUC_DRAW_TEMP_MESH")
			bm.to_mesh(mesh)
			draw.drawEditOverlay(mesh)
			bpy.data.meshes.remove(mesh)
		'''
	except Exception as e:
		raise e

def register() -> None:
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)
	bpy.app.handlers.save_post.append(stucSavePostHandler)
	bpy.app.handlers.save_pre.append(stucSavePreHandler)
	bpy.types.SpaceView3D.draw_handler_add(stucDrawHandler, (), 'WINDOW', 'POST_VIEW')

def unregister() -> None:
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)
	bpy.app.handlers.save_post.remove(stucSavePostHandler)
	bpy.app.handlers.save_pre.remove(stucSavePreHandler)
	bpy.types.SpaceView3D.draw_handler_remove(stucDrawHandler, 'WINDOW')