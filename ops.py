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
		for obj in context.selected_objects:
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				continue
			obj["StucUsg"] = True
			obj.display_type = 'WIRE'
		return {'FINISHED'}
	
class STUC_OT_StucUnsetUsg(bpy.types.Operator):
	bl_idname = "stuc.unset_usg"
	bl_label = "Unset USG"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
		return meshUtils.getUsgCountInSelObjs(context) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		for obj in context.selected_objects:
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				del obj["StucUsg"]
				obj["stucUsgFlatCutoff"] = None
				obj.display_type = 'TEXTURED'
		return {'FINISHED'}
	
class STUC_OT_StucSetFlatCutoff(bpy.types.Operator):
	bl_idname = "stuc.set_flat_cutoff"
	bl_label = "Set Flatten Cut-Off"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context) -> bool:
		return meshUtils.getUsgCountInSelObjs(context) > 0

	def execute(self, context: bpy.types.Context) -> set[str]:
		activeObj = context.view_layer.objects.active
		for obj in context.selected_objects:
			if obj == activeObj:
				continue
			isUsg = obj.get("StucUsg", None)
			if isUsg:
				obj["stucUsgFlatCutoff"] = activeObj
		return {'FINISHED'}

class STUC_OT_StucAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_assign"
	bl_label = "STUC Assign"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
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
			newTarget.activeAttribs.add().name = "position"
			newTarget.activeAttribs.add().name = ""
			uvEntry = newTarget.activeAttribs.add()
			for uv in obj.data.uv_layers:
				if uv.active:
					uvEntry.name = uv.name
					break
			colEntry = newTarget.activeAttribs.add()
			activeColIdx = obj.data.attributes.active_color_index
			if activeColIdx and activeColIdx >= 0:
				colEntry.name = obj.data.color_attributes[activeColIdx].name

		return {'FINISHED'}
	
class STUC_OT_StucMatAssign(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_assign"
	bl_label = "STUC Mat Assign"
	bl_options = {'REGISTER'}

	def execute(self, context: bpy.types.Context) -> set[str]:
		item = context.scene.stucMats.add() #type:ignore
		return {'FINISHED'}

class STUC_OT_StucPreviewImage(bpy.types.Operator):
	bl_idname = "stuc.stuc_preview_image"
	bl_label = "Preview Image"
	bl_options = {"REGISTER"}

	@classmethod
	def poll(cls, context) -> bool:
		#currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
		return False

	def execute(self, context: bpy.types.Context) -> set[str]:
		currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex] #type:ignore
		mapUtf8 = ""
		previewRes = 512
		dataLen = previewRes * previewRes * 4
		preview = numpy.empty(dataLen, dtype = numpy.float32)
		previewCtypes = preview.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
		stucLib.stucBlenderMapFileGenPreviewImage(
			mapUtf8,
			previewRes,
			previewCtypes
		)
		previewName = "Stuc_" + currentTarget.map
		image = bpy.data.images.get(previewName, None)
		if image:
			bpy.data.images.remove(image)
		image = bpy.data.images.new(previewName, previewRes, previewRes)
		image.pixels.foreach_set(preview) #type:ignore
		return {'FINISHED'}

class STUC_OT_StucRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_remove"
	bl_label = "STUC Remove"
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		scene = context.scene
		if scene.stucTargetsIndex >= len(scene.stucTargets): #type:ignore
			return {'CANCELLED'}
		del scene.stucTargets[scene.stucTargetsIndex].obj["stucWScale"] #type:ignore
		scene.stucTargets.remove(scene.stucTargetsIndex) #type:ignore
		return {'FINISHED'}

class STUC_OT_StucMatRemove(bpy.types.Operator):
	bl_idname = "stuc.stuc_mat_remove"
	bl_label = "STUC Mat Remove"
	bl_options = {"REGISTER"}

	def execute(self, context: bpy.types.Context) -> set[str]:
		pdb.set_trace()
		print("hi")
		return {'FINISHED'}

classes = [
	STUC_OT_StucSetAsUsg,
	STUC_OT_StucUnsetUsg,
	STUC_OT_StucSetFlatCutoff,
	STUC_OT_StucAssign,
	STUC_OT_StucMatAssign,
	STUC_OT_StucRemove,
	STUC_OT_StucMatRemove,
	STUC_OT_StucPreviewImage
]

def register() -> None:
	
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
