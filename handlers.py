'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast
import pdb

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
	context = bpy.context
	#pdb.set_trace()
	utils.updateUiTargetIdx(context)
	mapping.mapToSelTargets(context)
	

def register() -> None:
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)

def unregister() -> None:
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)