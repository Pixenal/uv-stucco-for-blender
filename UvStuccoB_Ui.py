import bpy

def StucExport(self, context):
    self.layout.operator("stuc.export_stuc_file")

def StucLoadForEdit(self, context):
    self.layout.operator("stuc.load_stuc_file_for_edit")

class StucParentPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = "UI"
    bl_category = "UV Stucco"

class STUC_UL_StucTargets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row0 = layout.row(align = True)
            row0.prop(item, "obj", text = "", emboss = False, icon = 'MESH_CUBE')

class STUC_UL_StucCommonAttribs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row0 = layout.row(align = True)
            row0.prop(item, "name", text = "", emboss = False, icon = 'MESH_CUBE')

class STUC_PT_Stuc(StucParentPanel, bpy.types.Panel):
    bl_idname = "STUC_PT_Stuc"
    bl_label = "STUC"

    def draw(self, context):
        stuc = context.scene.stuc
        layout = self.layout
        col0 = layout.column()
        col0.label(text = "Targets")
        row0 = col0.row()
        row0.template_list("STUC_UL_StucTargets", "", context.scene, "stucTargets",
                           context.scene, "stucTargetsIndex")
        col1 = row0.column(align = True)
        col1.scale_x = .35
        col1.operator("stuc.stuc_assign", icon = "ADD")
        col1.operator("stuc.stuc_remove", icon = "REMOVE")
        row1 = col0.row()
        row1.operator("stuc.load_stuc_file", text = "Open Map")
        if (len(context.scene.stucTargets)):
            currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
            col0.prop_search(currentTarget, "map", context.scene, "stucMaps",
                             text = "", icon = 'MESH_PLANE')
            col0.operator("stuc.reload_stuc_file", text = "Reload Map")
            col0.operator("stuc.stuc_preview_image", text = "Preview Map")
            col0.label(text = "")
            col0.label(text = "Common Attribs")
            col0.prop(stuc, "commonAttribDomain", text = "")
            match (stuc.commonAttribDomain):
                case "FACE":
                    domain = "commonFaceAttribs"
                    commonAttrib = currentTarget.commonFaceAttribs
                case "CORNER":
                    domain = "commonCornerAttribs" 
                    commonAttrib = currentTarget.commonCornerAttribs
                case "EDGE":
                    domain = "commonEdgeAttribs"
                    commonAttrib = currentTarget.commonEdgeAttribs
                case "POINT":
                    domain = "commonVertAttribs"
                    commonAttrib = currentTarget.commonVertAttribs
            col0.template_list("STUC_UL_StucCommonAttribs", "", currentTarget, domain,
                               stuc, "commonAttribIndex")
            if len(commonAttrib):
                match (stuc.commonAttribDomain):
                    case "FACE":
                        commonAttribEntry =\
                            currentTarget.commonFaceAttribs[stuc.commonAttribIndex]
                    case "CORNER":
                        commonAttribEntry =\
                            currentTarget.commonCornerAttribs[stuc.commonAttribIndex]
                    case "EDGE":
                        commonAttribEntry =\
                            currentTarget.commonEdgeAttribs[stuc.commonAttribIndex]
                    case "POINT":
                        commonAttribEntry =\
                            currentTarget.commonVertAttribs[stuc.commonAttribIndex]
                col0.prop(commonAttribEntry, "opacity")
                col0.prop(commonAttribEntry, "blend")
                col0.prop(commonAttribEntry, "order")
        col0.label(text = "")
        col0.label(text = "Export Options")
        col0.operator("stuc.set_as_usg", icon = "NORMALS_FACE")
        col0.operator("stuc.unset_usg", icon = "X")
        col0.label(text = "Flatten Cut-Off")
        if (context.view_layer.objects.active.get("StucUsg")):
            col0.prop_search(context.view_layer.objects.active, "stucUsgFlatCutoff", context.view_layer, "objects", text = "")
        col0.operator("stuc.set_flat_cutoff", text = "Set Sel To Active")
        col0.label(text = "")
        col0.prop(context.scene.stuc, "wScale", text = "Default W Scale")
        #print("currentTarget.map: ", currentTarget.map)
        #targetsMap = context.scene.stucMaps.get(currentTarget.map, None)
        #col0.prop(targetsMap, "filepath", text = "", emboss = False);

classes = [STUC_PT_Stuc,
           STUC_UL_StucTargets,
           STUC_UL_StucCommonAttribs]

def register():
    print("Registering STUC_UI")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(StucExport)
    bpy.types.TOPBAR_MT_file_import.append(StucLoadForEdit)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_export.remove(StucExport)
    bpy.types.TOPBAR_MT_file_import.remove(StucLoadForEdit)

