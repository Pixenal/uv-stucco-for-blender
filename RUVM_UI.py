import bpy

def RuvmExport(self, context):
    self.layout.operator("ruvm.export_ruvm_file")

def RuvmLoadForEdit(self, context):
    self.layout.operator("ruvm.load_ruvm_file_for_edit")

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
        ruvm = context.scene.ruvm
        layout = self.layout
        col0 = layout.column()
        col0.prop(context.scene.ruvm, "wScale")
        col0.label(text = "")
        col0.label(text = "Targets")
        row0 = col0.row()
        row0.template_list("RUVM_UL_RuvmTargets", "", context.scene, "ruvmTargets",
                           context.scene, "ruvmTargetsIndex")
        col1 = row0.column(align = True)
        col1.scale_x = .35
        col1.operator("ruvm.ruvm_assign", icon = "ADD")
        col1.operator("ruvm.ruvm_remove", icon = "REMOVE")
        row1 = col0.row()
        row1.operator("ruvm.load_ruvm_file", text = "Open Map")
        if (len(context.scene.ruvmTargets)):
            currentTarget = context.scene.ruvmTargets[context.scene.ruvmTargetsIndex]
            col0.prop_search(currentTarget, "map", context.scene, "ruvmMaps",
                             text = "", icon = 'MESH_PLANE')
            col0.operator("ruvm.ruvm_preview_image", text = "Preview Map")
            col0.label(text = "")
            col0.label(text = "Common Attribs")
            col0.prop(ruvm, "commonAttribDomain", text = "")
            match (ruvm.commonAttribDomain):
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
                               ruvm, "commonAttribIndex")
            if len(commonAttrib):
                match (ruvm.commonAttribDomain):
                    case "FACE":
                        commonAttribEntry =\
                            currentTarget.commonFaceAttribs[ruvm.commonAttribIndex]
                    case "CORNER":
                        commonAttribEntry =\
                            currentTarget.commonCornerAttribs[ruvm.commonAttribIndex]
                    case "EDGE":
                        commonAttribEntry =\
                            currentTarget.commonEdgeAttribs[ruvm.commonAttribIndex]
                    case "POINT":
                        commonAttribEntry =\
                            currentTarget.commonVertAttribs[ruvm.commonAttribIndex]
                col0.prop(commonAttribEntry, "blend")
                col0.prop(commonAttribEntry, "order")
        col0.label(text = "")
        col0.label(text = "Export Options")
        col0.operator("ruvm.set_as_usg", icon = "NORMALS_FACE")
        col0.operator("ruvm.unset_usg", icon = "X")
        col0.label(text = "Flatten Cut-Off")
        if (context.view_layer.objects.active.get("RuvmUsg")):
            col0.prop_search(context.view_layer.objects.active, "ruvmUsgFlatCutoff", context.view_layer, "objects", text = "")
        col0.operator("ruvm.set_flat_cutoff", text = "Set Sel To Active")
        #print("currentTarget.map: ", currentTarget.map)
        #targetsMap = context.scene.ruvmMaps.get(currentTarget.map, None)
        #col0.prop(targetsMap, "filepath", text = "", emboss = False);

classes = [RUVM_PT_Ruvm,
           RUVM_UL_RuvmTargets,
           RUVM_UL_RuvmCommonAttribs]

#Register
def register():
    print("Registering RUVM_UI")
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(RuvmExport)
    bpy.types.TOPBAR_MT_file_import.append(RuvmLoadForEdit)

#Unregister
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_export.remove(RuvmExport)
    bpy.types.TOPBAR_MT_file_import.remove(RuvmLoadForEdit)

