'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast
import ctypes
import pdb

import bpy
from bpy.app.handlers import persistent
import bmesh

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mapping
from . import draw
from . import stuc
from . import props

@persistent
def stucLoadPostHandler(dummy) -> None:
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

def getTargetMesh(target: props.StucTarget) -> stuc.StucMesh | None:
	mesh = ctypes.POINTER(stuc.StucMesh)()
	err = stucLib.stucBlenderTargetCacheGet(target.id, ctypes.pointer(mesh))
	if err != 1:
		raise Exception("error getting target mesh")
	if mesh:
		return mesh.contents
	else:
		return None

@persistent
def stucDrawHandler() -> None:
	try :
		for target in bpy.context.scene.stucTargets: #type:ignore
			mesh = getTargetMesh(target)
			if mesh:
				draw.drawStucMesh(mesh)
		for obj in bpy.context.objects_in_mode:
			if type(obj.data) != bpy.types.Mesh:
				continue
			bm = bmesh.from_edit_mesh(obj.data)
			mesh = bpy.data.meshes.new("STUC_DRAW_TEMP_MESH")
			bm.to_mesh(mesh)
			draw.drawEditOverlay(mesh)
			bpy.data.meshes.remove(mesh)
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