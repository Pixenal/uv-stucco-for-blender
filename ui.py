'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

from typing import Any, cast
import pdb

import bpy

from . import utils

def StucExport(self, context) -> None:
	self.layout.operator("stuc.export_stuc_file")

def StucLoadForEdit(self, context) -> None:
	self.layout.operator("stuc.load_stuc_file_for_edit")

class StucParentPanel(bpy.types.Panel):
	bl_space_type = 'VIEW_3D'
	bl_region_type = "UI"
	bl_category = "UV Stucco"

class STUC_UL_StucTargets(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			row0.prop(item, "obj", text = "", emboss = False, icon = 'CUBE')

class STUC_UL_StucMaps(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			if item.status == '1':
				mapIcon = "MESH_PLANE"
			else:
				mapIcon = "ERROR"
			row0.prop(item, "name", text = "", emboss = False, icon = mapIcon)
			remove = row0.operator("stuc.stuc_map_unload", text = "", icon = 'REMOVE')
			remove.itemIdx = index

class STUC_UL_StucActiveAttribs(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not data.obj:
				return
			row0 = layout.row(align = True)
			row0.prop_search(item, "name", data.obj.data, "attributes", text = item.use, icon = 'SOLO_OFF')

class STUC_UL_StucMapActiveAttribs(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			row0.prop_search(item, "name", data, "attribs", text = item.use, icon = 'SOLO_OFF')

class STUC_UL_StucMapDeps(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			row0.prop_search(item, "name", context.scene, "stucMaps", text = "", icon = 'MESH_PLANE')

class STUC_UL_StucCommonAttribs(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			row0.prop(item, "name", text = "", emboss = False, icon = 'CUBE')
			
class STUC_UL_StucMats(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			row0.prop_search(item, "mat", bpy.data, "materials", text = "")
			row0.prop_search(item, "map", context.scene, "stucMaps", text = "", icon = 'MESH_PLANE')
			layout.context_pointer_set(name = "stucMatToRm", data = item)
			remove = row0.operator("stuc.stuc_mat_remove", text = "", icon = 'REMOVE')
			remove.itemIdx = index

class STUC_UL_StucDepDirs(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index) -> None:
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			row0 = layout.row(align = True)
			row0.prop(item, "name", text = "")
			remove = row0.operator("stuc.extra_dep_dir_remove", text = "", icon = 'REMOVE')
			remove.itemIdx = index


class STUC_PT_Stuc(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_Stuc"
	bl_label = "STUC"

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		col0.operator("stuc.scene_export", text = "Export Scene", icon = 'EXPORT')
		col0.label(text = "")
		col0.operator("stuc.load_stuc_file", text = "Load Map", icon = "MESH_PLANE")
		col0.operator("stuc.reload_stuc_file", text = "Refresh Maps", icon = 'FILE_REFRESH')

class STUC_PT_StucDepDirs(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucDepDirs"
	bl_label = "Extra Dep Dirs"
	bl_parent_id = "STUC_PT_Stuc"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		row0 = col0.row()
		row0.template_list(
			"STUC_UL_StucDepDirs",
			"",
			context.scene, "stucDepDirs",
			context.scene, "stucDepDirsIdx"
		)
		col1 = row0.column(align = True)
		col1.scale_x = .35
		col1.operator("stuc.extra_dep_dir_add", text = " ", icon = "ADD")

class STUC_PT_StucMaps(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucMaps"
	bl_label = "Maps"
	bl_parent_id = "STUC_PT_Stuc"

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		col0.template_list(
			"STUC_UL_StucMaps",
			"",
			context.scene, "stucMaps",
			context.scene, "stucMapsIdx",
			rows = 4, maxrows = 6
		)

class STUC_PT_StucMapDeps(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucMapDeps"
	bl_label = "Map Deps"
	bl_parent_id = "STUC_PT_StucMaps"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		if len(context.scene.stucMaps): #type:ignore
			map = context.scene.stucMaps[context.scene.stucMapsIdx] #type:ignore
			col0.template_list(
				"STUC_UL_StucMapDeps",
				"",
				map, "deps",
				map, "depsIdx",
				rows = 1, maxrows = 8
			)

class STUC_PT_StucMapActive(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucMapActive"
	bl_label = "Map Active Attribs"
	bl_parent_id = "STUC_PT_StucMaps"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		if len(context.scene.stucMaps): #type:ignore
			map = context.scene.stucMaps[context.scene.stucMapsIdx] #type:ignore
			col0.template_list(
				"STUC_UL_StucMapActiveAttribs",
				"",
				map, "activeAttribs",
				map, "activeAttribIdx",
				rows = 4, maxrows = 4
			)

class STUC_PT_StucMats(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucMats"
	bl_label = "Materials"
	bl_parent_id = "STUC_PT_Stuc"

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		row0 = col0.row()
		row0.template_list(
			"STUC_UL_StucMats",
			"",
			context.scene, "stucMats",
			context.scene, "stucMatsIdx",
			rows = 4, maxrows = 6
			)
		col1 = row0.column(align = True)
		col1.scale_x = .35
		col1.operator("stuc.stuc_mat_assign", text = " ", icon = "ADD")

class STUC_PT_StucTargets(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucTargets"
	bl_label = "Targets"
	bl_parent_id = "STUC_PT_Stuc"

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		row0 = col0.row()
		row0.template_list(
			"STUC_UL_StucTargets",
			"",
			context.scene, "stucTargets",
			context.scene, "stucTargetsIdx",
			rows = 4, maxrows = 6
		)
		col2 = row0.column(align = True)
		col2.scale_x = .35
		col2.operator("stuc.stuc_assign", text = " ", icon = "ADD")
		col2.operator("stuc.stuc_remove", text = " ", icon = "REMOVE")
		
		if (len(context.scene.stucTargets)): #type:ignore
			target = context.scene.stucTargets[context.scene.stucTargetsIdx] #type:ignore
			col0.template_list(
				"STUC_UL_StucActiveAttribs",
				"",
				target, "activeAttribs",
				target, "activeAttribIdx",
				rows = 8, maxrows = 8
			)

class STUC_PT_StucCommonAttribs(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucCommonAttribs"
	bl_label = "Common Attribs"
	bl_parent_id = "STUC_PT_StucTargets"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		stuc = context.scene.stuc #type:ignore
		col0 = self.layout.column()
		target = context.scene.stucTargets[context.scene.stucTargetsIdx] #type:ignore
		idx = None
		if len(target.obj.material_slots):
			matSlotIdx = target.obj.active_material_index
			mat = target.obj.material_slots[matSlotIdx]
			idx = utils.findMatInCol(mat, target.commonAttribTable)
		if idx != None:
			commonAttribs = target.commonAttribTable[idx]
			col0.prop(stuc, "commonAttribDomain", text = "")
			match (stuc.commonAttribDomain):
				case "FACE":
					domain = "faces"
					commonAttrib = commonAttribs.faces
				case "CORNER":
					domain = "corners" 
					commonAttrib = commonAttribs.corners
				case "EDGE":
					domain = "edges"
					commonAttrib = commonAttribs.edges
				case "POINT":
					domain = "verts"
					commonAttrib = commonAttribs.verts
			col0.template_list(
				"STUC_UL_StucCommonAttribs",
				"",
				commonAttribs, domain,
				stuc, "commonAttribIdx"
			)
			if len(commonAttrib):
				match (stuc.commonAttribDomain):
					case "FACE":
						commonAttribEntry =\
							commonAttribs.faces[stuc.commonAttribIdx]
					case "CORNER":
						commonAttribEntry =\
							commonAttribs.corners[stuc.commonAttribIdx]
					case "EDGE":
						commonAttribEntry =\
							commonAttribs.edges[stuc.commonAttribIdx]
					case "POINT":
						commonAttribEntry =\
							commonAttribs.verts[stuc.commonAttribIdx]
				col0.prop(commonAttribEntry, "opacity")
				col0.prop(commonAttribEntry, "blend")
				col0.prop(commonAttribEntry, "order")

class STUC_PT_StucUsg(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucUsg"
	bl_label = "USG"
	bl_parent_id = "STUC_PT_Stuc"

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		col0.operator("stuc.set_as_usg", icon = "NORMALS_FACE")
		col0.operator("stuc.unset_usg", icon = "X")
		col0.label(text = "Flatten Cut-Off")
		if context.view_layer.objects.active and\
			context.view_layer.objects.active.get("StucUsg", None):
			col0.prop_search(
				context.view_layer.objects.active,
				"stucUsgFlatCutoff",
				context.view_layer,
				"objects",
				text = ""
			)
		col0.operator("stuc.set_flat_cutoff", text = "Set Sel To Active")

class STUC_PT_StucOpts(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucOpts"
	bl_label = "Options"
	bl_parent_id = "STUC_PT_Stuc"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		col0.prop(cast(Any, context.scene).stuc, "wScale", text = "Default W Scale")
		col0.prop(context.scene.stuc, "relPaths", text = "Relative paths") #type:ignore
		col0.prop(context.scene.stuc, "drawCacheMaxVerts", text = "Draw Cache Size")#type:ignore
		#col0.prop(context.scene.stuc, "breakPoint", text = "Enable Break Points")#type:ignore

class STUC_PT_StucDev(StucParentPanel, bpy.types.Panel):
	bl_idname = "STUC_PT_StucDev"
	bl_label = "Dev"
	bl_parent_id = "STUC_PT_Stuc"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context: bpy.types.Context) -> None:
		col0 = self.layout.column()
		col0.operator("stuc.stuc_force_update_targets", icon = 'CUBE')
		col0.prop(context.scene.stuc, "dontDraw", text = "Don't Draw")#type:ignore
		col0.label(text = "")
		col0.prop(context.scene.stuc, "logEnabled", text = "Log")#type:ignore
		#col0.label(text = "^ Unrelated v")
		#col0.operator("stuc.thread_pool_log_dump", icon = "FILE_BLANK")

classes = [
	STUC_PT_Stuc,
	STUC_PT_StucDepDirs,
	STUC_PT_StucMaps,
	STUC_PT_StucMapDeps,
	STUC_PT_StucMapActive,
	STUC_PT_StucMats,
	STUC_PT_StucTargets,
	STUC_PT_StucCommonAttribs,
	STUC_PT_StucUsg,
	STUC_PT_StucOpts,
	STUC_PT_StucDev,
	STUC_UL_StucTargets,
	STUC_UL_StucMaps,
	STUC_UL_StucActiveAttribs,
	STUC_UL_StucMapDeps,
	STUC_UL_StucMapActiveAttribs,
	STUC_UL_StucCommonAttribs,
	STUC_UL_StucMats,
	STUC_UL_StucDepDirs
]

def register() -> None:
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.TOPBAR_MT_file_export.append(StucExport)
	bpy.types.TOPBAR_MT_file_import.append(StucLoadForEdit)

def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
	bpy.types.TOPBAR_MT_file_export.remove(StucExport)
	bpy.types.TOPBAR_MT_file_import.remove(StucLoadForEdit)

