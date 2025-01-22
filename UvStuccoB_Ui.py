import bpy

def RuvmExport(self, context):
    self.layout.operator("uvs.export_uvs_file")

def RuvmLoadForEdit(self, context):
    self.layout.operator("uvs.load_uvs_file_for_edit")

class RuvmParentPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = "UI"
    bl_category = "RUVM"

class RUVM_UL_RuvmTargets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row0 = layout.row(align = True)
            row0.prop(item, "obj", text = "", emboss = False, icon = 'MESH_CUBE')

class RUVM_UL_RuvmCommonAttribs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row0 = layout.row(align = True)
            row0.prop(item, "name", text = "", emboss = False, icon = 'MESH_CUBE')

class RUVM_PT_Ruvm(RuvmParentPanel, bpy.types.Panel):
    bl_idname = "RUVM_PT_Ruvm"
    bl_label = "RUVM"

    def draw(self, context):
        uvs = context.scene.uvs
        layout = self.layout
        col0 = layout.column()
        col0.label(text = "Targets")
        row0 = col0.row()
        row0.template_list("RUVM_UL_RuvmTargets", "", context.scene, "uvsTargets",
                           context.scene, "uvsTargetsIndex")
        col1 = row0.column(align = True)
        col1.scale_x = .35
        col1.operator("uvs.uvs_assign", icon = "ADD")
        col1.operator("uvs.uvs_remove", icon = "REMOVE")
        row1 = col0.row()
        row1.operator("uvs.load_uvs_file", text = "Open Map")
        if (len(context.scene.uvsTargets)):
            currentTarget = context.scene.uvsTargets[context.scene.uvsTargetsIndex]
            col0.prop_search(currentTarget, "map", context.scene, "uvsMaps",
                             text = "", icon = 'MESH_PLANE')
            col0.operator("uvs.reload_uvs_file", text = "Reload Map")
            col0.operator("uvs.uvs_preview_image", text = "Preview Map")
            col0.label(text = "")
            col0.label(text = "Common Attribs")
            col0.prop(uvs, "commonAttribDomain", text = "")
            match (uvs.commonAttribDomain):
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
            col0.template_list("RUVM_UL_RuvmCommonAttribs", "", currentTarget, domain,
                               uvs, "commonAttribIndex")
            if len(commonAttrib):
                match (uvs.commonAttribDomain):
                    case "FACE":
                        commonAttribEntry =\
                            currentTarget.commonFaceAttribs[uvs.commonAttribIndex]
                    case "CORNER":
                        commonAttribEntry =\
                            currentTarget.commonCornerAttribs[uvs.commonAttribIndex]
                    case "EDGE":
                        commonAttribEntry =\
                            currentTarget.commonEdgeAttribs[uvs.commonAttribIndex]
                    case "POINT":
                        commonAttribEntry =\
                            currentTarget.commonVertAttribs[uvs.commonAttribIndex]
                col0.prop(commonAttribEntry, "blend")
                col0.prop(commonAttribEntry, "order")
        col0.label(text = "")
        col0.label(text = "Export Options")
        col0.operator("uvs.set_as_usg", icon = "NORMALS_FACE")
        col0.operator("uvs.unset_usg", icon = "X")
        col0.label(text = "Flatten Cut-Off")
        if (context.view_layer.objects.active.get("RuvmUsg")):
            col0.prop_search(context.view_layer.objects.active, "uvsUsgFlatCutoff", context.view_layer, "objects", text = "")
        col0.operator("uvs.set_flat_cutoff", text = "Set Sel To Active")
        col0.label(text = "")
        col0.prop(context.scene.uvs, "wScale", text = "Default W Scale")
        #print("currentTarget.map: ", currentTarget.map)
        #targetsMap = context.scene.uvsMaps.get(currentTarget.map, None)
        #col0.prop(targetsMap, "filepath", text = "", emboss = False);

classes = [RUVM_PT_Ruvm,
           RUVM_UL_RuvmTargets,
           RUVM_UL_RuvmCommonAttribs]

def register():
    print("Registering RUVM_UI")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(RuvmExport)
    bpy.types.TOPBAR_MT_file_import.append(RuvmLoadForEdit)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_export.remove(RuvmExport)
    bpy.types.TOPBAR_MT_file_import.remove(RuvmLoadForEdit)

