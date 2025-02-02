import bpy
import ctypes
import sys
from . import UvStuccoB_CLib
stucLib = UvStuccoB_CLib.stucLib
import numpy
import bmesh
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from . import Utils as utils
import os
import pdb

#TODO this is in here to use clib? Is there a way to access clib it in Utils.py?
def copyStucMeshToBlenderMesh(mesh, workMesh, mats):
    if (mats):
        i = 0
        while i < mats.contents.count:
            StucString = ctypes.c_byte * 64
            matsCast = ctypes.cast(mats.contents.pData, ctypes.POINTER(StucString))
            matName = ctypes.cast(matsCast[i], ctypes.c_char_p).value.decode()
            mat = bpy.data.materials.get(matName, None)
            if not mat:
                mat = bpy.data.materials.new(name = matName)
            mesh.materials.append(mat)
            i += 1

    mesh.vertices.add(workMesh.vertCount)
    mesh.loops.add(workMesh.loopCount)
    mesh.polygons.add(workMesh.faceCount)
    createAllAttribs(mesh, workMesh)
    meshStucFormat = utils.formatAsStucMesh(mesh, False, False, None)

    stucLib.stucBlenderCopyMeshCore(ctypes.pointer(meshStucFormat[0]), ctypes.pointer(workMesh))

    matIndices = None
    i = 0
    while i < workMesh.faceAttribs.count:
        if ctypes.cast(workMesh.faceAttribs.pArr[i].name, ctypes.c_char_p).value == b"StucMaterialIndices":
            matIndices = workMesh.faceAttribs.pArr[i]
            break
        i += 1
    if matIndices:
        matIndicesNumpy = numpy.ctypeslib.as_array(ctypes.cast(matIndices.pData, ctypes.POINTER(ctypes.c_byte)),
                                                   shape = [workMesh.faceCount])
        mesh.polygons.foreach_set("material_index", matIndicesNumpy)

    #meshStuc.uv_layers.new(name="uvmap")
    #uvPtr = meshStuc.uv_layers[0].data[0].as_pointer()
    #stucMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(StucVec2))
    mesh.update()
    meshStucFormat = utils.formatAsStucMesh(mesh, False, False, None)
    stucLib.stucBlenderCopyMeshAttribs(ctypes.pointer(meshStucFormat[0]), ctypes.pointer(workMesh))
    normalsArraySize = workMesh.loopCount * 3
    normalAttrib = getNormalAttrib(workMesh)
    normalsNumpy = numpy.ctypeslib.as_array(ctypes.cast(normalAttrib.contents.pData, ctypes.POINTER(ctypes.c_float)),
                                            shape = [normalsArraySize])
    #this is necessary to set custom normals it seems
    mesh.normals_split_custom_set(tuple(zip(*(iter(normalsNumpy),) * 3)))
    mesh.use_auto_smooth = True

def blendObjFromStuc(stucObj, col, name, displayType, isUsg, mats):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    meshStuc = ctypes.cast(stucObj.pData, ctypes.POINTER(utils.StucMesh))
    copyStucMeshToBlenderMesh(mesh, meshStuc.contents, mats)
    utils.setBlenderMatrix(obj.matrix_world, stucObj.transform)
    obj.display_type = displayType
    if (isUsg):
        obj['StucUsg'] = isUsg
    return obj

#TODO calc_normals_split has been removed in 4.1, so you'll need to handle that
#TODO It seems that normals can be accessed as contiguous arrays now,
#using the polygon_normals, or vertex_normals, properties, in a mesh.
#see if you can use this.
#TODO You'll need to separetly handle seams and creases and such as well,
#these seem to have been converted to attributes in 4.0 versions.
#So probably only need to do it for pre 4.0 versions.

def getUsgCountInSelObjs(context):
    count = 0
    for obj in context.selected_objects:
        isUsg = obj.get("StucUsg", None)
        if isUsg:
            count += 1
    return count

class STUC_OT_StucSetAsUsg(bpy.types.Operator):
    bl_idname = "stuc.set_as_usg"
    bl_label = "Set As USG"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return getUsgCountInSelObjs(context) < len(context.selected_objects)

    def execute(self, context):
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
    def poll(cls, context):
        return getUsgCountInSelObjs(context) > 0

    def execute(self, context):
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
    def poll(cls, context):
        return getUsgCountInSelObjs(context) > 0

    def execute(self, context):
        activeObj = context.view_layer.objects.active
        for obj in context.selected_objects:
            if obj == activeObj:
                continue
            isUsg = obj.get("StucUsg", None)
            if isUsg:
                obj["stucUsgFlatCutoff"] = activeObj
        return {'FINISHED'}

class STUC_OT_StucExportStucFile(bpy.types.Operator, ImportHelper):
    bl_idname = "stuc.export_stuc_file"
    bl_label = "STUC Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if (len(context.selected_objects) == 0):
            print("STUC export failed, no objects selected.")
            return {'CANCELLED'}
        
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        
        depsgraph = context.evaluated_depsgraph_get()
        ObjArr = utils.StucObject * len(context.selected_objects)
        UsgArr = utils.StucUsg * len(context.selected_objects)
        objArr = ObjArr()
        usgArr = UsgArr()
        objCount = 0
        usgCount = 0
        cutoffs = {}
        mats = {}
        tuples = []
        objCount = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            isUsg = obj.get("StucUsg", None)
            if not isUsg:
                objCount += 1
        matTable = utils.StucBlenderMatTableArr()
        matTable.count = objCount
        MatTableArr = utils.StucBlenderMatTable * matTable.count
        matTable.pArr = MatTableArr()
        objIdx = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            isUsg = obj.get("StucUsg", None)
            if isUsg:
                objTuple = utils.formatAsStucObj(obj, depsgraph, None)
                usgArr[usgCount].obj = objTuple[0]
                tuples.append(objTuple)
                flatCutoff = obj.get("stucUsgFlatCutoff", None)
                if (flatCutoff):
                    if flatCutoff.type == 'MESH':
                        cutoffPtr = cutoffs.get(flatCutoff.name, None)
                        if not cutoffPtr:
                            cutoffObjTuple = utils.formatAsStucObj(flatCutoff, depsgraph, None)
                            cutoffPtr = ctypes.pointer(cutoffObjTuple[0])
                            cutoffs.update({flatCutoff.name : cutoffPtr})
                            tuples.append(cutoffObjTuple)
                        usgArr[usgCount].pFlatCutoff = cutoffPtr
                usgCount += 1
            else:
                for slot in obj.material_slots:
                    entry = mats.get(slot.name, None)
                    if not entry:
                        if len(slot.name) > 64:
                            self.report({'ERROR'}, "Export failed, mat name is over 64 characters")
                            return {'CANCELLED'}
                        mats[slot.name] = True
                objTuple = utils.formatAsStucObj(obj, depsgraph, mats, matTable.pArr[objIdx])
                objArr[objIdx] = objTuple[0]
                tuples.append(objTuple)
                objIdx += 1
        
        matCount = len(mats)
        MatArr = ctypes.c_char * 64 * matCount
        matArr = MatArr()
        i = 0
        for matName in mats.keys():
            utils.copyAttribName(matArr[i], matName)
            i += 1
        matAttrib = utils.StucAttribIndexed()
        matAttrib.pData =  ctypes.cast(matArr, ctypes.c_void_p)
        utils.copyAttribName(matAttrib.name, "StucMaterials")
        matAttrib.type = 24 #string
        matAttrib.count = matCount
        matAttrib.size = matCount
        indexedAttribs = utils.StucAttribIndexedArr()
        indexedAttribs.pArr = ctypes.pointer(matAttrib)
        indexedAttribs.count = 1
        indexedAttribs.size = 1

        #stucLib.stucBlenderMapFileExport.argtypes = (ctypes.POINTER(StucMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"))
        err = stucLib.stucBlenderMapFileExport(filePathUtf8, objCount, objArr,
                                               usgCount, usgArr, indexedAttribs,
                                               ctypes.pointer(matTable))
        if err != 1:
            self.report({'ERROR'}, "Export failed")
            return {'CANCELLED'}
        return {'FINISHED'}

class STUC_OT_StucAssign(bpy.types.Operator):
    bl_idname = "stuc.stuc_assign"
    bl_label = "STUC Assign"
    bl_options = {'REGISTER'}

    def execute(self, context):
        stuc = context.scene.stuc
        if len(context.selected_objects) == 0:
            return {'CANCELLED'}
        for obj in context.selected_objects:
            exists = False
            for target in context.scene.stucTargets:
                if target.obj == obj:
                    exists = True
                    break
            if exists:
                continue
            id = len(context.scene.stucTargets)
            newTarget = context.scene.stucTargets.add()
            newTarget.obj = obj.id_data
            newTarget.id = id
            obj["stucWScale"] = context.scene.stuc.wScale
            obj.stucTargetId = id
        return {'FINISHED'}
    
class STUC_OT_StucLoadStucFileForEdit(bpy.types.Operator, ImportHelper):
    bl_idname = "stuc.load_stuc_file_for_edit"
    bl_label = "Load STUC File For Edit"
    bl_options = {"REGISTER"}

    def execute(self, context):
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        name = os.path.basename(filepath)
        print(filepath)
        objCount = ctypes.c_int()
        usgCount = ctypes.c_int()
        flatCutoffCount = ctypes.c_int()
        objArr = ctypes.POINTER(utils.StucObject)()
        usgArr = ctypes.POINTER(utils.StucUsg)()
        flatCutoffArr = ctypes.POINTER(utils.StucObject)()
        indexedAttribs = utils.StucAttribIndexedArr()
        err = stucLib.stucBlenderMapFileLoadForEdit(filePathUtf8, ctypes.pointer(objCount), ctypes.pointer(objArr),
                                                    ctypes.pointer(usgCount), ctypes.pointer(usgArr),
                                                    ctypes.pointer(flatCutoffCount), ctypes.pointer(flatCutoffArr),
                                                    ctypes.pointer(indexedAttribs))
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        mats = None
        i = 0
        while i < indexedAttribs.count:
            if ctypes.cast(indexedAttribs.pArr[i].name, ctypes.c_char_p).value == b"StucMaterials":
                mats = ctypes.pointer(indexedAttribs.pArr[i])
                break
            i += 1

        col = bpy.data.collections.new(f"StucEdit_{name}")
        context.collection.children.link(col)
        i = 0
        while (i < objCount.value):
            blendObjFromStuc(objArr[i], col, "Stuc", 'TEXTURED', False, mats)
            i += 1
        stucLib.stucBlenderObjArrDestroy(objCount, objArr)

        usgCol = bpy.data.collections.new(f"{name}_Usg")
        col.children.link(usgCol)
        cutoffCol = bpy.data.collections.new(f"{name}_FlatCutoff")
        col.children.link(cutoffCol)
        cutoffBlend = []
        i = 0
        while (i < flatCutoffCount.value):
            cutoff = blendObjFromStuc(flatCutoffArr[i], cutoffCol,  "FlatCutoff", 'WIRE', False, None)
            cutoffBlend.append(cutoff)
            i += 1
        i = 0
        while (i < usgCount.value):
            usg = blendObjFromStuc(usgArr[i].obj, usgCol, "Usg", 'WIRE', True, None)
            if (usgArr[i].pFlatCutoff):
                j = 0
                while (j < flatCutoffCount.value):
                    cutoffPtr = ctypes.cast(ctypes.pointer(flatCutoffArr[j]), ctypes.c_void_p)
                    usgCutoffPtr = ctypes.cast(usgArr[i].pFlatCutoff, ctypes.c_void_p)
                    if cutoffPtr.value == usgCutoffPtr.value:
                        usg["stucUsgFlatCutoff"] = cutoffBlend[j]
                    j += 1
            i += 1
        stucLib.stucBlenderUsgArrDestroy(usgCount.value, usgArr)
        stucLib.stucBlenderObjArrDestroy(flatCutoffCount.value, flatCutoffArr)
        
        return {'FINISHED'}

class STUC_OT_StucLoadStucFile(bpy.types.Operator, ImportHelper):
    bl_idname = "stuc.load_stuc_file"
    bl_label = "Load STUC File"
    bl_options = {"REGISTER"}

    def execute(self, context):
        filepath = self.filepath
        for map in context.scene.stucMaps:
            if (filepath == map.filepath):
                return {'CANCELLED'}
        filePathUtf8 = filepath.encode('utf-8')
        newMap = context.scene.stucMaps.add()
        newMap.name = os.path.basename(filepath)
        print(filepath)
        newMap.filepath = filepath
        context.scene.stucMapsIndex = len(context.scene.stucMaps)
        err = stucLib.stucBlenderMapFileLoad(filePathUtf8)
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        return {'FINISHED'}

class STUC_OT_StucReloadStucFile(bpy.types.Operator):
    bl_idname = "stuc.reload_stuc_file"
    bl_label = "Reload STUC File"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
        return currentTarget.map != ""

    def execute(self, context):
        currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
        mapUtf8 = utils.getTargetMapAsUtf8(currentTarget)
        err = stucLib.stucBlenderMapFileUnload(mapUtf8)
        if err != 1:
            self.report({'ERROR'}, "Map reload failed. Couldn't unload existing map")
        mapStr = mapUtf8.decode()
        exists = False
        for map in context.scene.stucMaps:
            if (mapStr == map.filepath):
                exists = True
                break
        if not exists:
            self.report({'ERROR'}, "Cannot reload map which is not loaded. How did this get called?")
            return {'CANCELLED'}
        err = stucLib.stucBlenderMapFileLoad(mapUtf8)
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        return {'FINISHED'}

class STUC_OT_StucPreviewImage(bpy.types.Operator):
    bl_idname = "stuc.stuc_preview_image"
    bl_label = "Preview Image"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
        return currentTarget.map != ""

    def execute(self, context):
        currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
        mapUtf8 = utils.getTargetMapAsUtf8(currentTarget)
        previewRes = 512
        dataLen = previewRes * previewRes * 4
        preview = numpy.empty(dataLen, dtype = numpy.float32)
        previewCtypes = preview.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        stucLib.stucBlenderMapFileGenPreviewImage(mapUtf8, previewRes,
                                                  previewCtypes)
        previewName = "Stuc_" + currentTarget.map
        image = bpy.data.images.get(previewName, None)
        if image:
            bpy.data.images.remove(image)
        image = bpy.data.images.new(previewName, previewRes, previewRes)
        image.pixels.foreach_set(preview)
        return {'FINISHED'}

class STUC_OT_StucRemove(bpy.types.Operator):
    bl_idname = "stuc.stuc_remove"
    bl_label = "STUC Remove"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        if scene.stucTargetsIndex >= len(scene.stucTargets):
            return {'CANCELLED'}
        del scene.stucTargets[scene.stucTargetsIndex].obj["stucTargetId"]
        del scene.stucTargets[scene.stucTargetsIndex].obj["stucWScale"]
        scene.stucTargets.remove(scene.stucTargetsIndex)
        return {'FINISHED'}

def setTargetCommonAttribs(target, commonAttribs, commonAttribsCount, domain):
    i = 0
    while (i < commonAttribsCount):
        targetAttrib = target.commonAttribs.get(commonAttribs[i].name, None)
        if not(targetAttrib):
            targetAttrib = target.commonAttribs.append()
            targetAttrib.name = commonAttribs[i].name
        targetAttrib.domain = domain
        targetAttrib.blend = commonAttribs[i].blend
        targetAttrib.order = commonAttribs[i].order
        i += 1

class STUC_OT_StucQueryCommonAttribs(bpy.types.Operator):
    bl_idname = "stuc.stuc_query_common_attribs"
    bl_label = "STUC Query Common Attributes"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        target = scene.stucTargets[scene.stucTargetsIndex].obj
        depsgraph = context.evaluated_depsgraph_get()
        objEval = target.obj.evaluated_get(depsgraph)
        meshEval = objEval.mesh
        meshTuple = utils.formatAsStucMesh(meshEval, True, False, None)
        mapUtf8 = utils.getTargetMapAsUtf8(target)
        if not(mapUtf8):
            return
        commonAttribList = utils.StucCommonAttribList()
        stucLib.stucBlenderQueryCommonAttribs(meshTuple[0], mapUtf8, ctypes.pointer(commonAttribList))
        utils.setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "FACE")
        utils.setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "CORNER")
        utils.setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "EDGE")
        utils.setTargetCommonAttribs(target, commonAttribList.face,
                               commonAttribList.faceCount, "POINT")

def createSingleAttrib(mesh, attrib, domain):
    attribType = utils.getAttribBlenderType(attrib)
    name = ctypes.cast(attrib.name, ctypes.c_char_p).value
    mesh.attributes.new(name = name.decode("utf-8"), type = attribType, domain = domain)

def createAttribs(mesh, attribs, domain):
    i = 0
    while (i < attribs.count):
        createSingleAttrib(mesh, attribs.pArr[i], domain)
        i += 1

def createAllAttribs(mesh, stucMesh):
    createAttribs(mesh, stucMesh.faceAttribs, "FACE")
    createAttribs(mesh, stucMesh.loopAttribs, "CORNER")
    #createAttribs(mesh, stucMesh.pEdgeAttribs, stucMesh.edgeAttribCount, "EDGE")
    #createAttribs(mesh, stucMesh.pVertAttribs, stucMesh.vertAttribCount, "POINT")

def getNormalAttrib(mesh):
    i = 0
    while (i < mesh.loopAttribs.count):
        name = ctypes.cast(mesh.loopAttribs.pArr[i].name, ctypes.c_char_p).value
        if (name.decode("utf-8") == "normal"):
            return ctypes.pointer(mesh.loopAttribs.pArr[i])
        i += 1
    return None

@persistent
def stucDepsgraphUpdatePostHandler(dummy):
    
    scene = bpy.context.scene
    active = bpy.context.active_object
    if (active):
        if active.name in scene.stucTargets:
            target = scene.stucTargets[active.name]
            if scene.stucTargetsIndex != target.id:
                scene.stucTargetsIndex = target.id
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for target in scene.stucTargets:
        obj = target.obj
        if not(obj in bpy.context.selected_objects):
            continue
        elif obj.mode != 'OBJECT':
            continue
        
        wScale = obj.get("stucWScale", None)
        if not wScale:
            print("Target obj has no w scale. Setting to default")
            wScale = scene.stuc.wScale
            obj["stucWScale"] = wScale
        
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        meshTuple = utils.formatAsStucMesh(meshEval, False, True, None)

        workMesh = utils.StucMesh()
        mapUtf8 = utils.getTargetMapAsUtf8(target)
        if not(mapUtf8):
            continue
        print("Mapping to mesh with map ", mapUtf8)

        stucLib.stucBlenderMapToMesh.argtypes = (
            ctypes.POINTER(ctypes.c_char),
            ctypes.POINTER(utils.StucMesh),
            ctypes.POINTER(utils.StucMesh),
            ctypes.POINTER(utils.StucCommonAttribList),
            ctypes.c_float
        )
        commonAttribs = utils.StucCommonAttribList()
        stucLib.stucBlenderQueryCommonAttribs(ctypes.pointer(meshTuple[0]), mapUtf8,
                                              ctypes.pointer(commonAttribs))
        result = stucLib.stucBlenderMapToMesh(mapUtf8, ctypes.pointer(meshTuple[0]),
                                              ctypes.pointer(workMesh),
                                              ctypes.pointer(commonAttribs),
                                              wScale)
        stucLib.stucBlenderDestroyCommonAttribs(ctypes.pointer(commonAttribs))
        if result != 0:
            print("Stuc python map to mesh failed, map to mesh returned error")
            return
        
        nameStuc = obj.name + ".Stuc"
        objStuc = bpy.data.objects.get(nameStuc, None)
        if not(objStuc):
            meshStuc = bpy.data.meshes.new(nameStuc)
            objStuc = bpy.data.objects.new(nameStuc, meshStuc)
            bpy.context.scene.collection.objects.link(objStuc)
        else:
            meshStucOld = objStuc.data
            meshStucOld.name += ".Old"
            meshStuc = bpy.data.meshes.new(nameStuc)
            objStuc.data = meshStuc
            bpy.data.meshes.remove(meshStucOld)

        mats = ctypes.POINTER(utils.StucAttribIndexed)()
        stucLib.stucBlenderMapMatsGet(mapUtf8, ctypes.pointer(mats))
        
        copyStucMeshToBlenderMesh(meshStuc, workMesh, mats)
        stucLib.stucBlenderMeshDestroy(ctypes.pointer(workMesh))
        normalBlendAttrib = meshStuc.attributes.get("normal", None)
        if (normalBlendAttrib):
            meshStuc.attributes.remove(normalBlendAttrib)
        matBlendAttrib = meshStuc.attributes.get("StucMaterialIndices", None)
        if (matBlendAttrib):
            meshStuc.attributes.remove(matBlendAttrib)
        print("FinishedUpdating")
        

@persistent
def stucLoadPostHandler(dummy):
    stucLib.stucBlenderInit()
    bpy.context.scene.stucMaps.clear()

@persistent
def stucLoadPreHandler(dummy):
    stucLib.stucBlenderDestroy()

classes = [STUC_OT_StucSetAsUsg,
           STUC_OT_StucUnsetUsg,
           STUC_OT_StucSetFlatCutoff,
           STUC_OT_StucExportStucFile,
           STUC_OT_StucAssign,
           STUC_OT_StucRemove,
           STUC_OT_StucLoadStucFileForEdit,
           STUC_OT_StucLoadStucFile,
           STUC_OT_StucReloadStucFile,
           STUC_OT_StucPreviewImage]

def register():
    
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.depsgraph_update_post.append(stucDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.append(stucLoadPostHandler)
    bpy.app.handlers.load_pre.append(stucLoadPreHandler)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.app.handlers.depsgraph_update_post.remove(stucDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.remove(stucLoadPostHandler)
    bpy.app.handlers.load_pre.remove(stucLoadPreHandler)
