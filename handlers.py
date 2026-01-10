'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast
import ctypes
import numpy
import pdb

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
) -> list[stuc.StucMesh | stuc.StucAttribIndexedArr] | None:
	mesh = ctypes.POINTER(stuc.StucMesh)()
	idxAttribs = ctypes.POINTER(stuc.StucAttribIndexedArr)()
	err = stucLib.stucBlenderTargetCacheGet(
		target.id,
		ctypes.pointer(mesh),
		ctypes.pointer(idxAttribs)
	)
	if err != 1:
		raise Exception("error getting target mesh")
	if mesh:
		return [mesh.contents, idxAttribs.contents]
	else:
		return None

def drawFallback(
	target: props.StucTarget,
	objOverride: bpy.types.Object | None = None,
	edit: bool = False
) -> None:
	obj = objOverride if objOverride else target.obj
	if not obj:
		return
	stucObj = meshUtils.formatAsStucObj(
		obj,
		True,
		None,
		True,
		target.activeAttribs #type:ignore
	)
	if edit:
		appendSelAttrib(obj, stucObj.meshData.mesh)
	mesh = stucObj.meshData.mesh
	meshRender = meshUtils.cpyStucMeshForRender(mesh)
	draw.drawNoCache(meshRender, obj.matrix_world)
	if edit:
		draw.drawEditOverlay(obj, meshRender)
	stucLib.stucBlenderMeshDestroy(ctypes.pointer(meshRender))

def appendSelAttrib(obj: bpy.types.Object, mesh: stuc.StucMesh):
	selFlag = (ctypes.c_float * mesh.cornerCount)()
	attribUtils.appendAttrib(
		mesh.cornerAttribs,
		"select",
		stuc.StucAttribType.F32.value,
		stuc.StucAttribUse.MISC.value,
		ctypes.cast(selFlag, ctypes.c_void_p)
	)
	selFaces = numpy.empty(mesh.faceCount, dtype = numpy.int8)
	obj.data.polygons.foreach_get("select", selFaces) #type:ignore
	stucLib.stucBlenderSelCornersFromFaces(
		ctypes.pointer(mesh),
		selFlag,
		numpy.ctypeslib.as_ctypes(selFaces)
	)

def drawTargetInEditMode(info: tuple[mapping.MappingInfo, int]) -> None:
	mesh = info[0].stucObj.meshData.mesh
	appendSelAttrib(info[0].objEval, mesh)
	meshRender = meshUtils.cpyStucMeshForRender(mesh)
	draw.drawStucMeshInViewport(
		meshRender,
		info[0].inIndexedArr,
		info[0].objEval.matrix_world,
		info[0].mapArr
	)
	draw.drawEditOverlay(info[0].objEval, meshRender)
	stucLib.stucBlenderMeshDestroy(ctypes.pointer(meshRender))

def drawTarget(target: props.StucTarget) -> None:
	if type(target.obj.data) != bpy.types.Mesh:
		return
	match target.obj.mode:
		case 'OBJECT':
			cache = getTargetMesh(target)
			if cache:
				if not cache[1]:
					raise Exception("idx attribs missing from target cache")
				draw.drawStucMeshInViewport(cache[0], cache[1], target.obj.matrix_world) #type:ignore
			else:
				drawFallback(target)
		case 'EDIT':
			info = mapping.prepTargetForMapping(bpy.context, None, target)
			if info[0]:
				drawTargetInEditMode(info) #type:ignore
			elif info[2]:
				drawFallback(target, objOverride = info[2], edit = True)
			else:
				drawFallback(target)
		case _:
			drawFallback(target)
	

@persistent
def stucDrawHandler() -> None:
	try :
		for target in bpy.context.scene.stucTargets: #type:ignore
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