import bpy
import ctypes
import sys
from . import RUVM_CLib
ruvmLib = RUVM_CLib.ruvmLib
import numpy
import bmesh
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from . import Utils as utils
import os
import pdb

def copyRuvmMeshToBlenderMesh(mesh, workMesh, mats):
    if (mats):
        i = 0
        while i < mats.contents.count:
            RuvmString = ctypes.c_byte * 64
            matsCast = ctypes.cast(mats.contents.pData, ctypes.POINTER(RuvmString))
            matName = ctypes.cast(matsCast[i], ctypes.c_char_p).value.decode()
            mat = bpy.data.materials.get(matName, None)
            if not mat:
                mat = bpy.data.materials.new(name = matName)
            mesh.materials.append(mat)
            i += 1

    mesh.vertices.add(workMesh.vertCount)
    mesh.loops.add(workMesh.loopCount)
    mesh.polygons.add(workMesh.faceCount)
    #pdb.set_trace()
    createAllAttribs(mesh, workMesh)
    meshRuvmFormat = utils.formatAsRuvmMesh(mesh, False, False, False)

    ruvmLib.ruvmBlenderCopyMeshCore(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))

    """
    matIndices = None
    i = 0
    while i < workMesh.faceAttribs.count:
        if ctypes.cast(workMesh.faceAttribs.pArr[i].name, ctypes.c_char_p).value == b"material_index":
            matIndices = workMesh.faceAttribs.pArr[i]
            break
        i += 1
    if matIndices:
        matIndicesNumpy = numpy.ctypeslib.as_array(ctypes.cast(matIndices.pData, ctypes.POINTER(ctypes.c_int32)),
                                                   shape = [workMesh.faceCount])
        mesh.polygons.foreach_set("material_index", matIndicesNumpy)
    """

    #meshRuvm.uv_layers.new(name="uvmap")
    #uvPtr = meshRuvm.uv_layers[0].data[0].as_pointer()
    #ruvmMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))
    mesh.update()
    meshRuvmFormat = utils.formatAsRuvmMesh(mesh, False, False, False)
    #pdb.set_trace()
    ruvmLib.ruvmBlenderCopyMeshAttribs(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))
    normalsArraySize = workMesh.loopCount * 3
    normalAttrib = getNormalAttrib(workMesh)
    normalsNumpy = numpy.ctypeslib.as_array(ctypes.cast(normalAttrib.contents.pData, ctypes.POINTER(ctypes.c_float)),
                                            shape = [normalsArraySize])
    #this is necessary to set custom normals it seems
    mesh.normals_split_custom_set(tuple(zip(*(iter(normalsNumpy),) * 3)))
    mesh.use_auto_smooth = True

def blendObjFromRuvm(ruvmObj, col, name, displayType, isUsg, mats):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    meshRuvm = ctypes.cast(ruvmObj.pData, ctypes.POINTER(utils.RuvmMesh))
    copyRuvmMeshToBlenderMesh(mesh, meshRuvm.contents, mats)
    utils.setBlenderMatrix(obj.matrix_world, ruvmObj.transform)
    obj.display_type = displayType
    if (isUsg):
        obj['RuvmUsg'] = isUsg
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
        isUsg = obj.get("RuvmUsg", None)
        if isUsg:
            count += 1
    return count

class RUVM_OT_RuvmSetAsUsg(bpy.types.Operator):
    bl_idname = "ruvm.set_as_usg"
    bl_label = "Set As USG"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return getUsgCountInSelObjs(context) < len(context.selected_objects)

    def execute(self, context):
        for obj in context.selected_objects:
            isUsg = obj.get("RuvmUsg", None)
            if isUsg:
                continue
            obj["RuvmUsg"] = True
            obj.display_type = 'WIRE'
        return {'FINISHED'}
    
class RUVM_OT_RuvmUnsetUsg(bpy.types.Operator):
    bl_idname = "ruvm.unset_usg"
    bl_label = "Unset USG"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return getUsgCountInSelObjs(context) > 0

    def execute(self, context):
        for obj in context.selected_objects:
            isUsg = obj.get("RuvmUsg", None)
            if isUsg:
                del obj["RuvmUsg"]
                obj["ruvmUsgFlatCutoff"] = None
                obj.display_type = 'TEXTURED'
        return {'FINISHED'}
    
class RUVM_OT_RuvmSetFlatCutoff(bpy.types.Operator):
    bl_idname = "ruvm.set_flat_cutoff"
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
            isUsg = obj.get("RuvmUsg", None)
            if isUsg:
                obj["ruvmUsgFlatCutoff"] = activeObj
        return {'FINISHED'}

class RUVM_OT_RuvmExportRuvmFile(bpy.types.Operator, ImportHelper):
    bl_idname = "ruvm.export_ruvm_file"
    bl_label = "RUVM Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        #pdb.set_trace()
        if (len(context.selected_objects) == 0):
            print("RUVM export failed, no objects selected.")
            return {'CANCELLED'}
        
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        
        depsgraph = context.evaluated_depsgraph_get()
        ObjArr = utils.RuvmObject * len(context.selected_objects)
        UsgArr = utils.RuvmUsg * len(context.selected_objects)
        objArr = ObjArr()
        usgArr = UsgArr()
        objCount = 0
        usgCount = 0
        cutoffs = {}
        #pdb.set_trace()
        mats = {}
        tuples = []
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            isUsg = obj.get("RuvmUsg", None)
            if isUsg:
                objTuple = utils.formatAsRuvmObj(obj, depsgraph, False)
                usgArr[usgCount].obj = objTuple[0]
                tuples.append(objTuple)
                flatCutoff = obj.get("ruvmUsgFlatCutoff", None)
                if (flatCutoff):
                    if flatCutoff.type == 'MESH':
                        cutoffPtr = cutoffs.get(flatCutoff.name, None)
                        if not cutoffPtr:
                            cutoffObjTuple = utils.formatAsRuvmObj(flatCutoff, depsgraph, False)
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
                objTuple = utils.formatAsRuvmObj(obj, depsgraph, True)
                objArr[objCount] = objTuple[0]
                tuples.append(objTuple)
                objCount += 1  
        
        #pdb.set_trace()
        matCount = len(mats)
        MatArr = ctypes.c_char * 64 * matCount
        matArr = MatArr()
        i = 0
        for matName in mats.keys():
            utils.copyAttribName(matArr[i], matName)
            i += 1
        matAttrib = utils.RuvmAttribIndexed()
        matAttrib.pData =  ctypes.cast(matArr, ctypes.c_void_p)
        utils.copyAttribName(matAttrib.name, "RuvmMaterials")
        matAttrib.type = 24 #string
        matAttrib.count = matCount
        matAttrib.size = matCount
        indexedAttribs = utils.RuvmAttribIndexedArr()
        indexedAttribs.pArr = ctypes.pointer(matAttrib)
        indexedAttribs.count = 1
        indexedAttribs.size = 1

        #ruvmLib.ruvmBlenderMapFileExport.argtypes = (ctypes.POINTER(RuvmMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"))
        err = ruvmLib.ruvmBlenderMapFileExport(filePathUtf8, objCount, objArr,
                                               usgCount, usgArr, indexedAttribs)
        if err != 1:
            self.report({'ERROR'}, "Export failed")
            return {'CANCELLED'}
        return {'FINISHED'}

class RUVM_OT_RuvmAssign(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_assign"
    bl_label = "RUVM Assign"
    bl_options = {'REGISTER'}

    def execute(self, context):
        ruvm = context.scene.ruvm
        if len(context.selected_objects) == 0:
            return {'CANCELLED'}
        for obj in context.selected_objects:
            exists = False
            for target in context.scene.ruvmTargets:
                if target.obj == obj:
                    exists = True
                    break
            if exists:
                continue
            id = len(context.scene.ruvmTargets)
            newTarget = context.scene.ruvmTargets.add()
            newTarget.obj = obj.id_data
            newTarget.id = id
            obj["ruvmWScale"] = context.scene.ruvm.wScale
            obj.ruvmTargetId = id
        return {'FINISHED'}
    
class RUVM_OT_RuvmLoadRuvmFileForEdit(bpy.types.Operator, ImportHelper):
    bl_idname = "ruvm.load_ruvm_file_for_edit"
    bl_label = "Load RUVM File For Edit"
    bl_options = {"REGISTER"}

    def execute(self, context):
        #pdb.set_trace()
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        name = os.path.basename(filepath)
        print(filepath)
        objCount = ctypes.c_int()
        usgCount = ctypes.c_int()
        flatCutoffCount = ctypes.c_int()
        objArr = ctypes.POINTER(utils.RuvmObject)()
        usgArr = ctypes.POINTER(utils.RuvmUsg)()
        flatCutoffArr = ctypes.POINTER(utils.RuvmObject)()
        indexedAttribs = utils.RuvmAttribIndexedArr()
        err = ruvmLib.ruvmBlenderMapFileLoadForEdit(filePathUtf8, ctypes.pointer(objCount), ctypes.pointer(objArr),
                                                    ctypes.pointer(usgCount), ctypes.pointer(usgArr),
                                                    ctypes.pointer(flatCutoffCount), ctypes.pointer(flatCutoffArr),
                                                    ctypes.pointer(indexedAttribs))
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        pdb.set_trace()
        mats = None
        i = 0
        while i < indexedAttribs.count:
            if ctypes.cast(indexedAttribs.pArr[i].name, ctypes.c_char_p).value == b"RuvmMaterials":
                mats = ctypes.pointer(indexedAttribs.pArr[i])
                break
            i += 1

        col = bpy.data.collections.new(f"RuvmEdit_{name}")
        context.collection.children.link(col)
        i = 0
        while (i < objCount.value):
            blendObjFromRuvm(objArr[i], col, "Ruvm", 'TEXTURED', False, mats)
            i += 1
        ruvmLib.ruvmBlenderObjArrDestroy(objCount, objArr)

        usgCol = bpy.data.collections.new(f"{name}_Usg")
        col.children.link(usgCol)
        cutoffCol = bpy.data.collections.new(f"{name}_FlatCutoff")
        col.children.link(cutoffCol)
        cutoffBlend = []
        i = 0
        while (i < flatCutoffCount.value):
            cutoff = blendObjFromRuvm(flatCutoffArr[i], cutoffCol,  "FlatCutoff", 'WIRE', False, None)
            cutoffBlend.append(cutoff)
            i += 1
        i = 0
        while (i < usgCount.value):
            usg = blendObjFromRuvm(usgArr[i].obj, usgCol, "Usg", 'WIRE', True, None)
            if (usgArr[i].pFlatCutoff):
                j = 0
                while (j < flatCutoffCount.value):
                    cutoffPtr = ctypes.cast(ctypes.pointer(flatCutoffArr[j]), ctypes.c_void_p)
                    usgCutoffPtr = ctypes.cast(usgArr[i].pFlatCutoff, ctypes.c_void_p)
                    if cutoffPtr.value == usgCutoffPtr.value:
                        usg["ruvmUsgFlatCutoff"] = cutoffBlend[j]
                    j += 1
            i += 1
        ruvmLib.ruvmBlenderUsgArrDestroy(usgCount.value, usgArr)
        ruvmLib.ruvmBlenderObjArrDestroy(flatCutoffCount.value, flatCutoffArr)
        
        return {'FINISHED'}

class RUVM_OT_RuvmLoadRuvmFile(bpy.types.Operator, ImportHelper):
    bl_idname = "ruvm.load_ruvm_file"
    bl_label = "Load RUVM File"
    bl_options = {"REGISTER"}

    def execute(self, context):
        #pdb.set_trace()
        filepath = self.filepath
        for map in context.scene.ruvmMaps:
            if (filepath == map.filepath):
                return {'CANCELLED'}
        filePathUtf8 = filepath.encode('utf-8')
        newMap = context.scene.ruvmMaps.add()
        newMap.name = os.path.basename(filepath)
        print(filepath)
        newMap.filepath = filepath
        context.scene.ruvmMapsIndex = len(context.scene.ruvmMaps)
        err = ruvmLib.ruvmBlenderMapFileLoad(filePathUtf8)
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        return {'FINISHED'}

class RUVM_OT_RuvmReloadRuvmFile(bpy.types.Operator):
    bl_idname = "ruvm.reload_ruvm_file"
    bl_label = "Reload RUVM File"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        currentTarget = context.scene.ruvmTargets[context.scene.ruvmTargetsIndex]
        return currentTarget.map != ""

    def execute(self, context):
        pdb.set_trace()
        currentTarget = context.scene.ruvmTargets[context.scene.ruvmTargetsIndex]
        mapUtf8 = utils.getTargetMapAsUtf8(currentTarget)
        err = ruvmLib.ruvmBlenderMapFileUnload(mapUtf8)
        if err != 1:
            self.report({'ERROR'}, "Map reload failed. Couldn't unload existing map")
        mapStr = mapUtf8.decode()
        exists = False
        for map in context.scene.ruvmMaps:
            if (mapStr == map.filepath):
                exists = True
                break
        if not exists:
            self.report({'ERROR'}, "Cannot reload map which is not loaded. How did this get called?")
            return {'CANCELLED'}
        err = ruvmLib.ruvmBlenderMapFileLoad(mapUtf8)
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        return {'FINISHED'}

class RUVM_OT_RuvmPreviewImage(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_preview_image"
    bl_label = "Preview Image"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        currentTarget = context.scene.ruvmTargets[context.scene.ruvmTargetsIndex]
        return currentTarget.map != ""

    def execute(self, context):
        currentTarget = context.scene.ruvmTargets[context.scene.ruvmTargetsIndex]
        mapUtf8 = utils.getTargetMapAsUtf8(currentTarget)
        previewRes = 512
        dataLen = previewRes * previewRes * 4
        preview = numpy.empty(dataLen, dtype = numpy.float32)
        previewCtypes = preview.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ruvmLib.ruvmBlenderMapFileGenPreviewImage(mapUtf8, previewRes,
                                                  previewCtypes)
        previewName = "Ruvm_" + currentTarget.map
        image = bpy.data.images.get(previewName, None)
        if image:
            bpy.data.images.remove(image)
        image = bpy.data.images.new(previewName, previewRes, previewRes)
        image.pixels.foreach_set(preview)
        return {'FINISHED'}

class RUVM_OT_RuvmRemove(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_remove"
    bl_label = "RUVM Remove"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        if scene.ruvmTargetsIndex >= len(scene.ruvmTargets):
            return {'CANCELLED'}
        del scene.ruvmTargets[scene.ruvmTargetsIndex].obj["ruvmTargetId"]
        del scene.ruvmTargets[scene.ruvmTargetsIndex].obj["ruvmWScale"]
        scene.ruvmTargets.remove(scene.ruvmTargetsIndex)
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

class RUVM_OT_RuvmQueryCommonAttribs(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_query_common_attribs"
    bl_label = "RUVM Query Common Attributes"
    bl_options = {'REGISTER'}

    def execute(self, context):
        pdb.set_trace()
        scene = context.scene
        target = scene.ruvmTargets[scene.ruvmTargetsIndex].obj
        depsgraph = context.evaluated_depsgraph_get()
        objEval = target.obj.evaluated_get(depsgraph)
        meshEval = objEval.mesh
        meshTuple = utils.formatAsRuvmMesh(meshEval, True, False, False)
        mapUtf8 = utils.getTargetMapAsUtf8(target)
        if not(mapUtf8):
            return
        commonAttribList = utils.RuvmCommonAttribList()
        ruvmLib.ruvmBlenderQueryCommonAttribs(meshTuple[0], mapUtf8, ctypes.pointer(commonAttribList))
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

def createAllAttribs(mesh, ruvmMesh):
    createAttribs(mesh, ruvmMesh.faceAttribs, "FACE")
    createAttribs(mesh, ruvmMesh.loopAttribs, "CORNER")
    #createAttribs(mesh, ruvmMesh.pEdgeAttribs, ruvmMesh.edgeAttribCount, "EDGE")
    #createAttribs(mesh, ruvmMesh.pVertAttribs, ruvmMesh.vertAttribCount, "POINT")

def getNormalAttrib(mesh):
    i = 0
    while (i < mesh.loopAttribs.count):
        name = ctypes.cast(mesh.loopAttribs.pArr[i].name, ctypes.c_char_p).value
        if (name.decode("utf-8") == "normal"):
            return ctypes.pointer(mesh.loopAttribs.pArr[i])
        i += 1
    return None

@persistent
def ruvmDepsgraphUpdatePostHandler(dummy):
    
    scene = bpy.context.scene
    active = bpy.context.active_object
    if (active):
        if active.name in scene.ruvmTargets:
            target = scene.ruvmTargets[active.name]
            if scene.ruvmTargetsIndex != target.id:
                scene.ruvmTargetsIndex = target.id
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for target in scene.ruvmTargets:
        obj = target.obj
        if not(obj in bpy.context.selected_objects):
            continue
        elif obj.mode != 'OBJECT':
            continue
        
        wScale = obj.get("ruvmWScale", None)
        if not wScale:
            print("Target obj has no w scale. Skipping")
            continue
        
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        meshTuple = utils.formatAsRuvmMesh(meshEval, False, False, True)

        workMesh = utils.RuvmMesh()
        mapUtf8 = utils.getTargetMapAsUtf8(target)
        if not(mapUtf8):
            continue
        print("Mapping to mesh with map ", mapUtf8)

        ruvmLib.ruvmBlenderMapToMesh.argtypes = (
            ctypes.POINTER(ctypes.c_char),
            ctypes.POINTER(utils.RuvmMesh),
            ctypes.POINTER(utils.RuvmMesh),
            ctypes.POINTER(utils.RuvmCommonAttribList),
            ctypes.c_float
        )
        commonAttribs = utils.RuvmCommonAttribList()
        ruvmLib.ruvmBlenderQueryCommonAttribs(ctypes.pointer(meshTuple[0]), mapUtf8,
                                              ctypes.pointer(commonAttribs))
        result = ruvmLib.ruvmBlenderMapToMesh(mapUtf8, ctypes.pointer(meshTuple[0]),
                                              ctypes.pointer(workMesh),
                                              ctypes.pointer(commonAttribs),
                                              wScale)
        ruvmLib.ruvmBlenderDestroyCommonAttribs(ctypes.pointer(commonAttribs))
        if result != 0:
            print("Ruvm python map to mesh failed, map to mesh returned error")
            return
        
        nameRuvm = obj.name + ".Ruvm"
        objRuvm = bpy.data.objects.get(nameRuvm, None)
        if not(objRuvm):
            meshRuvm = bpy.data.meshes.new(nameRuvm)
            objRuvm = bpy.data.objects.new(nameRuvm, meshRuvm)
            bpy.context.scene.collection.objects.link(objRuvm)
        else:
            meshRuvmOld = objRuvm.data
            meshRuvmOld.name += ".Old"
            meshRuvm = bpy.data.meshes.new(nameRuvm)
            objRuvm.data = meshRuvm
            bpy.data.meshes.remove(meshRuvmOld)

        mats = ctypes.POINTER(utils.RuvmAttribIndexed)()
        ruvmLib.ruvmBlenderMapMatsGet(mapUtf8, ctypes.pointer(mats))
        
        #pdb.set_trace()
        copyRuvmMeshToBlenderMesh(meshRuvm, workMesh, mats)
        ruvmLib.ruvmBlenderMeshDestroy(ctypes.pointer(workMesh))
        print("FinishedUpdating")
        

@persistent
def ruvmLoadPostHandler(dummy):
    ruvmLib.ruvmBlenderInit()
    bpy.context.scene.ruvmMaps.clear()

@persistent
def ruvmLoadPreHandler(dummy):
    ruvmLib.ruvmBlenderDestroy()

classes = [RUVM_OT_RuvmSetAsUsg,
           RUVM_OT_RuvmUnsetUsg,
           RUVM_OT_RuvmSetFlatCutoff,
           RUVM_OT_RuvmExportRuvmFile,
           RUVM_OT_RuvmAssign,
           RUVM_OT_RuvmRemove,
           RUVM_OT_RuvmLoadRuvmFileForEdit,
           RUVM_OT_RuvmLoadRuvmFile,
           RUVM_OT_RuvmReloadRuvmFile,
           RUVM_OT_RuvmPreviewImage]

def register():
    
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.depsgraph_update_post.append(ruvmDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.append(ruvmLoadPostHandler)
    bpy.app.handlers.load_pre.append(ruvmLoadPreHandler)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.app.handlers.depsgraph_update_post.remove(ruvmDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.remove(ruvmLoadPostHandler)
    bpy.app.handlers.load_pre.remove(ruvmLoadPreHandler)
