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

#TODO calc_normals_split has been removed in 4.1, so you'll need to handle that
#TODO It seems that normals can be accessed as contiguous arrays now,
#using the polygon_normals, or vertex_normals, properties, in a mesh.
#see if you can use this.
#TODO You'll need to separetly handle seams and creases and such as well,
#these seem to have been converted to attributes in 4.0 versions.
#So probably only need to do it for pre 4.0 versions.

class RUVM_OT_RuvmExportRuvmFile(bpy.types.Operator, ImportHelper):
    bl_idname = "ruvm.export_ruvm_file"
    bl_label = "RUVM Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        #pdb.set_trace()
        if (len(context.selected_objects) == 0):
            print("RUVM export failed, no objects selected.")
            return {'CANCELLED'}
        if (len(context.selected_objects) > 1):
            print("RUVM export failed, more than one object selected.")
            return {'CANCELLED'}
        
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        
        obj = context.selected_objects[0]
        depsgraph = context.evaluated_depsgraph_get()
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        meshTuple = utils.formatAsRuvmMesh(meshEval, False, True)

        #ruvmLib.ruvmBlenderMapFileExport.argtypes = (ctypes.POINTER(RuvmMesh),
        #    numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"))
        ruvmLib.ruvmBlenderMapFileExport(filePathUtf8, ctypes.pointer(meshTuple[0]))

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
        ruvmLib.ruvmBlenderMapFileLoad(filePathUtf8)
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
        
        print("workMesh.vertCount ", workMesh.vertCount)
        print("workMesh.loopCount ", workMesh.loopCount)
        print("workMesh.faceCount ", workMesh.faceCount)
        meshRuvm.vertices.add(workMesh.vertCount)
        meshRuvm.loops.add(workMesh.loopCount)
        meshRuvm.polygons.add(workMesh.faceCount)
        #pdb.set_trace()
        createAllAttribs(meshRuvm, workMesh)
        meshRuvmFormat = utils.formatAsRuvmMesh(meshRuvm, False, False)

        ruvmLib.ruvmBlenderCopyMeshCore(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))

        #meshRuvm.uv_layers.new(name="uvmap")
        #uvPtr = meshRuvm.uv_layers[0].data[0].as_pointer()
        #ruvmMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))
        meshRuvm.update()
        meshRuvmFormat = utils.formatAsRuvmMesh(meshRuvm, False, False)
        #pdb.set_trace()
        ruvmLib.ruvmBlenderCopyMeshAttribs(ctypes.pointer(meshRuvmFormat[0]), ctypes.pointer(workMesh))
        normalsArraySize = workMesh.loopCount * 3
        normalAttrib = getNormalAttrib(workMesh)
        normalsNumpy = numpy.ctypeslib.as_array(ctypes.cast(normalAttrib.contents.pData, ctypes.POINTER(ctypes.c_float)),
                                                shape = [normalsArraySize])
        #this is necessary to set custom normals it seems
        meshRuvm.normals_split_custom_set(tuple(zip(*(iter(normalsNumpy),) * 3)))
        meshRuvm.use_auto_smooth = True
        ruvmLib.ruvmBlenderMeshDestroy(ctypes.pointer(workMesh))
        print("FinishedUpdating")
        

@persistent
def ruvmLoadPostHandler(dummy):
    ruvmLib.ruvmBlenderInit()
    bpy.context.scene.ruvmMaps.clear()

@persistent
def ruvmLoadPreHandler(dummy):
    ruvmLib.ruvmBlenderDestroy()

classes = [RUVM_OT_RuvmExportRuvmFile,
           RUVM_OT_RuvmAssign,
           RUVM_OT_RuvmRemove,
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
