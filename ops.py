'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
from typing import Any, cast
import numpy
import pdb

import bpy

from . import c_lib
stucLib = c_lib.stucLib
from . import utils
from . import mesh_utils as meshUtils
if not bpy.app.background:
	from . import draw
from . import mapping
from . import props

#TODO uncomment when usg are reimplemented
'''
class STUC_OT_StucSetAsUsg(bpy.types.Operator):
	bl_idname = "stuc.set_as_usg"
	bl_label = "Set As USG"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		return meshUtils.getUsgCountInSelObjs(context) < len(context.selected_objects)

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			for obj in context.selected_objects:
				isUsg = obj.get("StucUsg", None)
				if isUsg:
					continue
				obj["StucUsg"] = True
				obj.display_type = 'WIRE'
		except Exception as e:
			self.report({'ERROR'}, "Failed to set as USG")
			raise e
		return {'FINISHED'}
	
class STUC_OT_StucUnsetUsg(bpy.types.Operator):
	bl_idname = "stuc.unset_usg"
	bl_label = "Unset USG"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		return meshUtils.getUsgCountInSelObjs(context) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			for obj in context.selected_objects:
				isUsg = obj.get("StucUsg", None)
				if isUsg:
					del obj["StucUsg"]
					obj["stucUsgFlatCutoff"] = None
					obj.display_type = 'TEXTURED'
		except Exception as e:
			self.report({'ERROR'}, "Failed to unset USG")
			raise e
		return {'FINISHED'}
	
class STUC_OT_StucSetFlatCutoff(bpy.types.Operator):
	bl_idname = "stuc.set_flat_cutoff"
	bl_label = "Set Flatten Cut-Off"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		return meshUtils.getUsgCountInSelObjs(context) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			activeObj = context.view_layer.objects.active
			for obj in context.selected_objects:
				if obj == activeObj:
					continue
				isUsg = obj.get("StucUsg", None)
				if isUsg:
					obj["stucUsgFlatCutoff"] = activeObj
		except Exception as e:
			self.report({'ERROR'}, "Failed to set USG flat cutoff")
			raise e
		return {'FINISHED'}
'''

class STUC_OT_StucAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_assign"
	bl_label = "STUC Assign"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		return len(context.selected_objects) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			for obj in context.selected_objects:
				if type(obj.data) != bpy.types.Mesh:
					continue
				exists = False
				for target in context.scene.stucTargets: #type:ignore
					if target.obj == obj:
						exists = True
						break
				if exists:
					continue
				newTarget = context.scene.stucTargets.add() #type:ignore
				newTarget.id = context.scene.stucTargetIdNext #type:ignore
				context.scene.stucTargetIdNext += 1 #type:ignore
				newTarget.obj = obj.id_data
				newTarget.wScale = context.scene.stuc.wScale#type:ignore

				utils.initActiveAttrib(newTarget, "position", "position")
				utils.initActiveAttrib(newTarget, "normal", "")
				uvEntry = utils.initActiveAttrib(newTarget, "UV", "")
				for uv in obj.data.uv_layers:
					if uv.active:
						uvEntry.name = uv.name
						break
				colEntry = utils.initActiveAttrib(newTarget, "Color", "")
				activeColIdx = obj.data.attributes.active_color_index
				if activeColIdx and activeColIdx >= 0:
					colEntry.name = obj.data.color_attributes[activeColIdx].name
				utils.initActiveAttrib(newTarget, "Preserve Edge", "")
				utils.initActiveAttrib(newTarget, "Preserve Vert", "")
				utils.initActiveAttrib(newTarget, "Receive Edge", "")
				utils.initActiveAttrib(newTarget, "WScale", "")
		except Exception as e:
			self.report({'ERROR'}, "Failed to add target")
			raise e
		return {'FINISHED'}
	
class STUC_OT_StucRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_remove"
	bl_label = "STUC Remove"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		return len(context.scene.stucTargets) and len(context.selected_objects)#type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			for obj in context.selected_objects:
				targetIdx = context.scene.stucTargets.find(obj.name)#type:ignore
				if targetIdx == -1:
					continue
				target = context.scene.stucTargets[targetIdx]#type:ignore
				stucLib.stucBlenderTargetCacheRemove(target.id)
				context.scene.stucTargets.remove(targetIdx)#type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to remove target")
			raise e
		return {'FINISHED'}

class STUC_OT_StucMatAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_assign"
	bl_label = "STUC Mat Assign"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			context.scene.stucMats.add()#type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to add material target")
			raise e
		return {'FINISHED'}

class STUC_OT_StucMatRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_remove"
	bl_label = "STUC Mat Remove"
	bl_options = {'REGISTER', 'UNDO'}

	itemIdx : bpy.props.IntProperty() #type:ignore

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		return context.scene.stucMatsIdx < len(context.scene.stucMats)#type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			context.scene.stucMats.remove(self.itemIdx) #type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to remove mat")
			raise e
		return {'FINISHED'}

class STUC_OT_StucForceUpdateTargets(bpy.types.Operator):
	bl_idname = "stuc.stuc_force_update_targets"
	bl_label = "Force Update Targets"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		mapping.mapToTargetsInScene(context, selOnly = True, force = True)
		return {'FINISHED'}

def mapPreviewImgGet(map: props.StucMap) -> bpy.types.Image | None:
	return bpy.data.images.get(f"{map.name}_albedo", None)

class STUC_OT_StucMapViewPreview(bpy.types.Operator):
	bl_idname = "stuc.stuc_map_view_preview"
	bl_label = "View Map Preview"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context: bpy.types.Context) -> bool:
		if context.scene.stucMapsIdx >= len(context.scene.stucMaps):#type:ignore
			return False
		map = context.scene.stucMaps[context.scene.stucMapsIdx]#type:ignore
		return bool(mapPreviewImgGet(map) and utils.getArea('IMAGE_EDITOR'))

	def execute(self, context: bpy.types.Context) -> set[str]:
		map = context.scene.stucMaps[context.scene.stucMapsIdx]#type:ignore
		image = mapPreviewImgGet(map)
		if not image:
			return {'CANCELLED'}
		for area in bpy.context.window.screen.areas:
			if area.type == 'IMAGE_EDITOR':
				area.spaces.active.image = image#type:ignore
		return {'FINISHED'}

classes = [
	#STUC_OT_StucSetAsUsg,
	#STUC_OT_StucUnsetUsg,
	#STUC_OT_StucSetFlatCutoff,
	STUC_OT_StucAssign,
	STUC_OT_StucRemove,
	STUC_OT_StucMatAssign,
	STUC_OT_StucMatRemove,
	STUC_OT_StucForceUpdateTargets,
	STUC_OT_StucMapViewPreview
]

def register() -> None:
	
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
