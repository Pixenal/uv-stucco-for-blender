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

def copyRuvmMeshToBlenderMesh(mesh, workMesh):
    mesh.vertices.add(workMesh.vertCount)
    mesh.loops.add(workMesh.loopCount)
    mesh.polygons.add(workMesh.faceCount)
    #pdb.set_trace()
    createAllAttribs(mesh, workMesh)
    meshRuvmFormat = utils.formatAsRuvmMesh(mesh, False, False)

    ruvmLib.ruvmBlenderCopyMeshCore(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))

    #meshRuvm.uv_layers.new(name="uvmap")
    #uvPtr = meshRuvm.uv_layers[0].data[0].as_pointer()
    #ruvmMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))
    mesh.update()
    meshRuvmFormat = utils.formatAsRuvmMesh(mesh, False, False)
    #pdb.set_trace()
    ruvmLib.ruvmBlenderCopyMeshAttribs(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))
    normalsArraySize = workMesh.loopCount * 3
    normalAttrib = getNormalAttrib(workMesh)
    normalsNumpy = numpy.ctypeslib.as_array(ctypes.cast(normalAttrib.contents.pData, ctypes.POINTER(ctypes.c_float)),
                                            shape = [normalsArraySize])
    #this is necessary to set custom normals it seems
    mesh.normals_split_custom_set(tuple(zip(*(iter(normalsNumpy),) * 3)))
    mesh.use_auto_smooth = True

#TODO calc_normals_split has been removed in 4.1, so you'll need to handle that
#TODO It seems that normals can be accessed as contiguous arrays now,
#using the polygon_normals, or vertex_normals, properties, in a mesh.
#see if you can use this.
#TODO You'll need to separetly handle seams and creases and such as well,
#these seem to have been converted to attributes in 4.0 versions.
#So probably only need to do it for pre 4.0 versions.

class RUVM_OT_RuvmSetAsUsg(bpy.types.Operator):
    bl_idname = "ruvm.set_as_usg"
    bl_label = "Set As USG"
    bl_options = {'REGISTER'}

    def execute(self, context):
        for obj in context.selected_objects:
            isUsg = obj.get("RuvmUsg", None)
            if isUsg:
                continue
            obj["RuvmUsg"] = True
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
        #pdb.set_trace()
        objArr = ObjArr()
        usgArr = ObjArr()
        objCount = 0
        usgCount = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            isUsg = obj.get("RuvmUsg", None)
            if isUsg:
                arr = usgArr
                i = usgCount
            else:
                arr = objArr
                i = objCount
            objEval = obj.evaluated_get(depsgraph)
            meshEval = objEval.data
            meshTuple = utils.formatAsRuvmMesh(meshEval, False, True)
            arr[i].pData = ctypes.cast(ctypes.pointer(meshTuple[0]), ctypes.POINTER(utils.RuvmObjectData))
            matWorld = obj.matrix_world.copy()
            matWorld.transpose()
            j = 0
            while j < 4:
                k = 0
                while k < 4:
                    linearIndex = k + j * 4
                    arr[i].transform[linearIndex] = matWorld[j][k]
                    k += 1
                j += 1
            if isUsg:
                usgCount += 1
            else:
                objCount += 1

        #ruvmLib.ruvmBlenderMapFileExport.argtypes = (ctypes.POINTER(RuvmMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"))
        err = ruvmLib.ruvmBlenderMapFileExport(filePathUtf8, objCount, objArr,
                                               usgCount, usgArr)
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
            newTarget = context.scene.ruvmTargets.add()
            newTarget.obj = obj.id_data
            newTarget.id = ruvm.nextTargetId
            obj.ruvmTargetId = ruvm.nextTargetId
            ruvm.nextTargetId += 1
        return {'FINISHED'}
    
def setBlenderMatrix(blenderMatrix, ruvmMatrix):
    j = 0
    while j < 4:
        k = 0
        while k < 4:
            linearIndex = k + j * 4
            blenderMatrix[j][k] = ruvmMatrix[linearIndex]
            k += 1
        j += 1
    blenderMatrix.transpose()
    
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
        objArr = ctypes.POINTER(utils.RuvmObject)()
        usgArr = ctypes.POINTER(utils.RuvmObject)()
        #pdb.set_trace()
        err = ruvmLib.ruvmBlenderMapFileLoadForEdit(filePathUtf8, ctypes.pointer(objCount), ctypes.pointer(objArr),
                                                    ctypes.pointer(usgCount), ctypes.pointer(usgArr))
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        
        col = bpy.data.collections.new(f"RuvmEdit_{name}")
        context.collection.children.link(col)
        i = 0
        while (i < objCount.value):
            mesh = bpy.data.meshes.new("RuvmMesh")
            obj = bpy.data.objects.new("RuvmObj", mesh)
            col.objects.link(obj)
            meshRuvm = ctypes.cast(objArr[i].pData, ctypes.POINTER(utils.RuvmMesh))
            copyRuvmMeshToBlenderMesh(mesh, meshRuvm.contents)
            setBlenderMatrix(obj.matrix_world, objArr[i].transform)
            i += 1
        ruvmLib.ruvmBlenderObjArrDestroy(objCount, objArr)

        usgCol = bpy.data.collections.new(f"{name}_Usg")
        col.children.link(usgCol)
        i = 0
        while (i < usgCount.value):
            mesh = bpy.data.meshes.new("RuvmUsgMesh")
            obj = bpy.data.objects.new("RuvmUsg", mesh)
            usgCol.objects.link(obj)
            meshRuvm = ctypes.cast(usgArr[i].pData, ctypes.POINTER(utils.RuvmMesh))
            copyRuvmMeshToBlenderMesh(mesh, meshRuvm.contents)
            setBlenderMatrix(obj.matrix_world, usgArr[i].transform)
            obj.display_type = 'WIRE'
            obj['RuvmUsg'] = True
            i += 1
        ruvmLib.ruvmBlenderObjArrDestroy(usgCount, usgArr)
        
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
        meshTuple = utils.formatAsRuvmMesh(meshEval, True, False)
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
    #createAttribs(mesh, ruvmMesh.pFaceAttribs, ruvmMesh.faceAttribCount, "FACE")
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
            target = scene.ruvmTargets[active.name];
            if scene.ruvmTargetsIndex != target.id:
                scene.ruvmTargetsIndex = target.id
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for target in scene.ruvmTargets:
        obj = target.obj
        if not(obj in bpy.context.selected_objects):
            continue
        elif obj.mode != 'OBJECT':
            continue
        
        mesh = obj.data
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        meshTuple = utils.formatAsRuvmMesh(meshEval, False, True)

        workMesh = utils.RuvmMesh()
        mapUtf8 = utils.getTargetMapAsUtf8(target)
        if not(mapUtf8):
            continue
        print("Mapping to mesh with map ", mapUtf8)

        #ruvmLib.ruvmBlenderMapToMesh.argtypes = (
        #    ctypes.POINTER(ctypes.c_char),
        #    ctypes.POINTER(RuvmMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_int32, flags="C_CONTIGUOUS"),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),
        #    ctypes.POINTER(RuvmMesh)
        #)
        commonAttribs = utils.RuvmCommonAttribList()
        ruvmLib.ruvmBlenderQueryCommonAttribs(ctypes.pointer(meshTuple[0]), mapUtf8,
                                              ctypes.pointer(commonAttribs))
        result = ruvmLib.ruvmBlenderMapToMesh(mapUtf8, ctypes.pointer(meshTuple[0]),
                                              ctypes.pointer(workMesh),
                                              ctypes.pointer(commonAttribs))
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
        
        copyRuvmMeshToBlenderMesh(meshRuvm, workMesh)
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
           RUVM_OT_RuvmExportRuvmFile,
           RUVM_OT_RuvmAssign,
           RUVM_OT_RuvmRemove,
           RUVM_OT_RuvmLoadRuvmFileForEdit,
           RUVM_OT_RuvmLoadRuvmFile,
           RUVM_OT_RuvmPreviewImage]

#Register
def register():
    
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.depsgraph_update_post.append(ruvmDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.append(ruvmLoadPostHandler)
    bpy.app.handlers.load_pre.append(ruvmLoadPreHandler)

#Unregister
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.app.handlers.depsgraph_update_post.remove(ruvmDepsgraphUpdatePostHandler)
    bpy.app.handlers.load_post.remove(ruvmLoadPostHandler)
    bpy.app.handlers.load_pre.remove(ruvmLoadPreHandler)
