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

#TODO calc_normals_split has been removed in 4.1, so you'll need to handle that
#TODO It seems that normals can be accessed as contiguous arrays now,
#using the polygon_normals, or vertex_normals, properties, in a mesh.
#see if you can use this.
#TODO You'll need to separetly handle seams and creases and such as well,
#these seem to have been converted to attributes in 4.0 versions.
#So probably only need to do it for pre 4.0 versions.

class STUC_OT_StucSetAsUsg(bpy.types.Operator):
	bl_idname = "stuc.set_as_usg"
	bl_label = "Set As USG"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
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
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
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
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
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

class STUC_OT_StucAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_assign"
	bl_label = "STUC Assign"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			if len(context.selected_objects) == 0:
				return {'CANCELLED'}
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
				newTarget.obj = obj.id_data
				obj["stucWScale"] = context.scene.stuc.wScale #type:ignore
				obj["stucReceiveLen"] = -1.0

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
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			scene = context.scene
			if scene.stucTargetsIdx >= len(scene.stucTargets): #type:ignore
				return {'CANCELLED'}
			target: props.StucTarget = scene.stucTargets[scene.stucTargetsIdx] #type:ignore
			if target.obj:
				objProp = target.obj.get("stucWScale", None)
				if objProp:
					del objProp
				objProp = target.obj.get("stucReceiveLen", None)
				if objProp:
					del objProp
			scene.stucTargets.remove(scene.stucTargetsIdx) #type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to remove target")
			raise e
		return {'FINISHED'}

class STUC_OT_StucMatAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_assign"
	bl_label = "STUC Mat Assign"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			item = context.scene.stucMats.add() #type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to add material target")
			raise e
		return {'FINISHED'}

class STUC_OT_StucMatRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_remove"
	bl_label = "STUC Mat Remove"
	bl_options = {"REGISTER"}

	itemIdx : bpy.props.IntProperty() #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			context.scene.stucMats.remove(self.itemIdx) #type:ignore
		except Exception as e:
			self.report({'ERROR'}, "Failed to remove mat")
			raise e
		return {'FINISHED'}
	
class STUC_OT_StucMapRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_map_unload"
	bl_label = "Unload Map"
	bl_options = {'REGISTER'}

	itemIdx : bpy.props.IntProperty() #type:ignore

	def execute(self, context: bpy.types.Context) -> set[str]:
		try:
			pdb.set_trace()
			if self.itemIdx >= len(context.scene.stucMaps): #type:ignore
				raise Exception("specificed index out of range")
			map = context.scene.stucMaps[self.itemIdx] #type:ignore
			name = map.name.encode('utf-8')
			context.scene.stucMaps.remove(self.itemIdx) #type:ignore
			if stucLib.stucBlenderMapFileUnload(name) != 1:
				raise Exception()
		except Exception as e:
			self.report({'ERROR'}, "Failed to unload map")
			raise e
		return {'FINISHED'}

classes = [
	STUC_OT_StucSetAsUsg,
	STUC_OT_StucUnsetUsg,
	STUC_OT_StucSetFlatCutoff,
	STUC_OT_StucAssign,
	STUC_OT_StucRemove,
	STUC_OT_StucMatAssign,
	STUC_OT_StucMatRemove,
	STUC_OT_StucMapRemove
]

def register() -> None:
	
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
