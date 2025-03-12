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
	context = bpy.context
	try:
		utils.updateUiTargetIdx(context)
		mapping.mapToSelTargets(context)
	except:
		print("STUC PYTHON ERROR in update post handler")
	

def register() -> None:
	bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.append(stucLoadPostHandler)
	bpy.app.handlers.load_pre.append(stucLoadPreHandler)

def unregister() -> None:
	bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
	bpy.app.handlers.load_post.remove(stucLoadPostHandler)
	bpy.app.handlers.load_pre.remove(stucLoadPreHandler)