'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast

import bpy
from bpy.app.handlers import persistent

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mapping

@persistent
def stucLoadPostHandler(dummy) -> None:
	stucLib.stucBlenderInit()
	bpy.context.scene.stucMaps.clear() #type:ignore

@persistent
def stucLoadPreHandler(dummy) -> None:
	stucLib.stucBlenderDestroy()

@persistent
def stucDepsgraphUpdatePostHandler(dummy) -> None:
	utils.updateUiTargetIdx(bpy.context)
	mapping.mapToSelTargets(bpy.context)
	
@persistent
def stucSavePostHandler(dummy) -> None:
	if not len(bpy.data.filepath) or not bpy.context.scene.stuc.relPaths: #type:ignore
		#this shouldn't be possible right?
		return
	for map in bpy.context.scene.stucMaps: #type:ignore
		map.dir = bpy.path.relpath(map.dir)

def register() -> None:
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)
	bpy.app.handlers.save_post.append(stucSavePostHandler)

def unregister() -> None:
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)
	bpy.app.handlers.save_post.remove(stucSavePostHandler)