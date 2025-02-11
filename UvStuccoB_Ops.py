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

#TODO these funcs are in here to use clib? Is there a way to access clib it in Utils.py?
def updateCommonAttribs(context, target, depsgraph):
	objEval = target.obj.evaluated_get(depsgraph)
	meshEval = objEval.data
	#clean common attrib entries for mat's no longer assigned to obj
	for entry in target.commonAttribTable:
		mat = meshEval.materials.get(entry.mat.name, None)
		if not mat:
			target.commonAttribTable.remove(entry)
            
	targetMats = utils.getMatsInStucMats(context, meshEval)
	targetMatCount = len(targetMats)
	if targetMatCount == 0:
		return None
	CommonAttribList = utils.StucCommonAttribList * targetMatCount
	commonAttribList = CommonAttribList()
	meshTuple = utils.formatAsStucMesh(meshEval, True, False, True)
	i = 0
	for mat in targetMats:
		if not len(mat.map):
			continue
		idx = utils.findMatInCol(mat.mat, target.commonAttribTable)
		if idx != None:
			entry = target.commonAttribTable[idx]
		else:
			entry = target.commonAttribTable.add()
			entry.mat = mat.mat
		mapUtf8 = mat.map.encode('utf-8')
		stucLib.stucBlenderQueryCommonAttribs(meshTuple[0], mapUtf8, ctypes.pointer(commonAttribList[i]))
		utils.setTargetCommonAttribs(entry.faces, commonAttribList[i].faceCount,
									commonAttribList[i].pFace)
		utils.setTargetCommonAttribs(entry.corners, commonAttribList[i].cornerCount,
									commonAttribList[i].pCorner)
		utils.setTargetCommonAttribs(entry.edges, commonAttribList[i].edgeCount,
									commonAttribList[i].pEdge)
		utils.setTargetCommonAttribs(entry.verts, commonAttribList[i].vertCount,
									commonAttribList[i].pVert)
		i += 1
	return commonAttribList

def copyStucMeshToBlenderMesh(mesh, workMesh, outIndexedAttribs, commonAttribs = None):
    if (outIndexedAttribs):
        #TODO this should be done on the c side, in uv-stucco, not uv-stucco-blender.
        #this will make it easier to merge duplicate materials.
        #pass inMesh materials to stucMapToMesh, and it will pass back
        #an outMesh mat arr (in a separate out param), which contains
        #the final material slots, and their mat names.
        outMats = utils.getAttrib(outIndexedAttribs, "StucMaterials")
        StucString = ctypes.c_byte * 64
        outMatsCast = ctypes.cast(outMats.core.pData, ctypes.POINTER(StucString))
        i = 0
        while i < outMats.count:
            matName = ctypes.cast(outMatsCast[i], ctypes.c_char_p).value.decode()
            mat = bpy.data.materials.get(matName, None)
            if not mat:
                #this should throw an error of some kind, or a warning
                #there shouldn't be any dups
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
        if ctypes.cast(workMesh.faceAttribs.pArr[i].core.name, ctypes.c_char_p).value == b"StucMaterialIndices":
            matIndices = workMesh.faceAttribs.pArr[i]
            break
        i += 1
    if matIndices:
        matIndicesNumpy = numpy.ctypeslib.as_array(ctypes.cast(matIndices.core.pData, ctypes.POINTER(ctypes.c_byte)),
                                                   shape = [workMesh.faceCount])
        print(f"matIndicesNumpy[0] = {matIndicesNumpy[0]}")
        mesh.polygons.foreach_set("material_index", matIndicesNumpy)

    #meshStuc.uv_layers.new(name="uvmap")
    #uvPtr = meshStuc.uv_layers[0].data[0].as_pointer()
    #stucMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(StucVec2))
    mesh.update()
    meshStucFormat = utils.formatAsStucMesh(mesh, False, False, None)
    stucLib.stucBlenderCopyMeshAttribs(ctypes.pointer(meshStucFormat[0]), ctypes.pointer(workMesh))
    normalsArraySize = workMesh.loopCount * 3
    normalAttrib = getNormalAttrib(workMesh)
    normalsNumpy = numpy.ctypeslib.as_array(ctypes.cast(normalAttrib.contents.core.pData, ctypes.POINTER(ctypes.c_float)),
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
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            isUsg = obj.get("StucUsg", None)
            if not isUsg:
                for slot in obj.material_slots:
                    entry = mats.get(slot.name, None)
                    if not entry:
                        mats[slot.name] = True
        matCount = len(mats)
        if not matCount:
            mats = None
                        
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
                objTuple = utils.formatAsStucObj(obj, depsgraph, mats, matTable.pArr[objIdx])
                objArr[objIdx] = objTuple[0]
                tuples.append(objTuple)
                objIdx += 1
        
        indexedAttribCount = 0
        indexedAttribs = utils.StucAttribIndexedArr()
        if matCount:
            MatArr = ctypes.c_byte * 64 * matCount
            matArr = MatArr()
            i = 0
            for matName in mats.keys():
                utils.copyString(matArr[i], matName, 96)
                i += 1
            matAttrib = utils.StucAttribIndexed()
            matAttrib.core.pData =  ctypes.cast(matArr, ctypes.c_void_p)
            utils.copyString(matAttrib.core.name, "StucMaterials", 96)
            matAttrib.core.type = 24 #string
            matAttrib.count = matCount
            matAttrib.size = matCount
            indexedAttribCount = 1
            indexedAttribs.pArr = ctypes.pointer(matAttrib)
        indexedAttribs.count = indexedAttribCount
        indexedAttribs.size = indexedAttribCount
        
        err = stucLib.stucBlenderMapFileExport(filePathUtf8, objCount, objArr,
                                               usgCount, usgArr, ctypes.pointer(indexedAttribs),
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
            newTarget = context.scene.stucTargets.add()
            newTarget.obj = obj.id_data
            obj["stucWScale"] = context.scene.stuc.wScale
        return {'FINISHED'}
    
class STUC_OT_StucMatAssign(bpy.types.Operator):
    bl_idname = "stuc.stuc_mat_assign"
    bl_label = "STUC Mat Assign"
    bl_options = {'REGISTER'}

    def execute(self, context):
        item = context.scene.stucMats.add()
        return {'FINISHED'}
    
class STUC_OT_StucLoadStucFileForEdit(bpy.types.Operator, ImportHelper):
    bl_idname = "stuc.load_stuc_file_for_edit"
    bl_label = "Load STUC File For Edit"
    bl_options = {"REGISTER"}

    def execute(self, context):
        filepathUtf8 = self.filepath.encode('utf-8')
        name = os.path.basename(self.filepath)
        objCount = ctypes.c_int()
        usgCount = ctypes.c_int()
        flatCutoffCount = ctypes.c_int()
        objArr = ctypes.POINTER(utils.StucObject)()
        usgArr = ctypes.POINTER(utils.StucUsg)()
        flatCutoffArr = ctypes.POINTER(utils.StucObject)()
        indexedAttribs = utils.StucAttribIndexedArr()
        err = stucLib.stucBlenderMapFileLoadForEdit(filepathUtf8, ctypes.pointer(objCount), ctypes.pointer(objArr),
                                                    ctypes.pointer(usgCount), ctypes.pointer(usgArr),
                                                    ctypes.pointer(flatCutoffCount), ctypes.pointer(flatCutoffArr),
                                                    ctypes.pointer(indexedAttribs))
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        mats = None
        i = 0
        while i < indexedAttribs.count:
            if ctypes.cast(indexedAttribs.pArr[i].core.name, ctypes.c_char_p).value == b"StucMaterials":
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
        name = os.path.basename(self.filepath)
        for map in context.scene.stucMaps:
            if (name == map.name):
                return {'CANCELLED'}
        filepathUtf8 = self.filepath.encode('utf-8')
        newMap = context.scene.stucMaps.add()
        newMap.name = name
        nameUtf8 = newMap.name.encode('utf-8')
        context.scene.stucMapsIndex = len(context.scene.stucMaps)
        err = stucLib.stucBlenderMapFileLoad(filepathUtf8, nameUtf8)
        if err != 1:
            self.report({'ERROR'}, "Load failed")
            return {'CANCELLED'}
        return {'FINISHED'}

#fix this
class STUC_OT_StucReloadStucFile(bpy.types.Operator):
    bl_idname = "stuc.reload_stuc_file"
    bl_label = "Reload STUC File"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return False

    def execute(self, context):
        currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
        mapUtf8 = ""
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
        return False

    def execute(self, context):
        currentTarget = context.scene.stucTargets[context.scene.stucTargetsIndex]
        mapUtf8 = ""
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
        del scene.stucTargets[scene.stucTargetsIndex].obj["stucWScale"]
        scene.stucTargets.remove(scene.stucTargetsIndex)
        return {'FINISHED'}

class STUC_OT_StucMatRemove(bpy.types.Operator):
    bl_idname = "stuc.stuc_mat_remove"
    bl_label = "STUC Mat Remove"
    bl_options = {"REGISTER"}

    def execute(self, context):
        pdb.set_trace()
        print("hi")
        return {'FINISHED'}

def createSingleAttrib(mesh, attrib, domain):
    attribType = utils.getAttribBlenderType(attrib)
    name = ctypes.cast(attrib.core.name, ctypes.c_char_p).value
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
        name = ctypes.cast(mesh.loopAttribs.pArr[i].core.name, ctypes.c_char_p).value
        if (name.decode("utf-8") == "normal"):
            return ctypes.pointer(mesh.loopAttribs.pArr[i])
        i += 1
    return None

@persistent
def stucDepsgraphUpdatePostHandler(dummy):
    scene = bpy.context.scene
    active = bpy.context.active_object
    if (active):
        idx = utils.findObjInCol(active, scene.stucTargets)
        if idx != None:
            scene.stucTargetsIndex = idx
    depsgraph = bpy.context.evaluated_depsgraph_get()
    class TargetCache:
        def __init__(self, obj, jobHandle, mapArr, inMeshTuple, inIndexedAttribs, outMesh,
                     outIndexedAttribs, commonAttribs, matCount):
            self.obj = obj
            self.jobHandle = jobHandle
            self.mapArr = mapArr
            self.inMeshTuple = inMeshTuple
            self.inIndexedAttribs = inIndexedAttribs
            self.outMesh = outMesh
            self.outIndexedAttribs = outIndexedAttribs
            self.commonAttribs = commonAttribs
            self.matCount = matCount
    targetCache = []
    for target in scene.stucTargets:
        obj = target.obj
        if obj not in bpy.context.selected_objects and not obj == active:
            continue
        elif obj.mode != 'OBJECT':
            continue
        commonAttribs = updateCommonAttribs(bpy.context, target, depsgraph)
        #hide_viewport is the moniter icon, and hide_get is the eye
        if not commonAttribs or obj.hide_viewport or obj.hide_get():
            continue
        wScale = obj.get("stucWScale", None)
        if not wScale:
            print("Target obj has no w scale. Setting to default")
            wScale = scene.stuc.wScale
            obj["stucWScale"] = wScale
        
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data
        
        targetMats = utils.getMatsInStucMats(bpy.context, meshEval)
        matCount = len(targetMats)
        if not matCount:
            continue
        mapArr = utils.StucBlenderMapArr()
        mapArr.ppArr = (ctypes.POINTER(ctypes.c_byte) * matCount)()
        mapArr.pMatIdxArr = (ctypes.c_byte * matCount)()
        mapArr.count = matCount
        mapStrs = []
        
        inIndexedAttribs = utils.StucAttribIndexedArr()
        inIndexedAttribs.count = 1
        inIndexedAttribs.pArr = ctypes.pointer(utils.StucAttribIndexed())
        inMats = inIndexedAttribs.pArr.contents
        inMats.count = matCount
        inMats.core.type = 24 #string
        utils.copyString(inMats.core.name, "StucMaterials", 96)
        StucString = ctypes.c_byte * 64
        inMatsArr = (StucString * inMats.count)()
        inMats.core.pData = ctypes.cast(inMatsArr, ctypes.c_void_p)
        
        i = 0
        for mat in targetMats:
            utils.copyString(inMatsArr[i], mat.mat.name, 64)
            mapStrs.append(mat.map.encode('utf-8'))
            mapArr.ppArr[i] = ctypes.cast(mapStrs[i], ctypes.POINTER(ctypes.c_byte))
            mapArr.pMatIdxArr[i] = objEval.material_slots.find(mat.mat.name)
            i += 1
        
        meshTuple = utils.formatAsStucMesh(meshEval, False, True, True)
        workMesh = utils.StucMesh()
        stucLib.stucBlenderMapToMesh.argtypes = (
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(utils.StucBlenderMapArr),
            ctypes.POINTER(utils.StucMesh), ctypes.POINTER(utils.StucAttribIndexedArr),
            ctypes.POINTER(utils.StucMesh), ctypes.POINTER(utils.StucAttribIndexedArr),
            ctypes.POINTER(utils.StucCommonAttribList),
            ctypes.c_float
        )
        i = 0
        while i < meshTuple[0].faceAttribs.count:
            StucName = ctypes.c_byte * 96
            nameCast = ctypes.cast(meshTuple[0].faceAttribs.pArr[i].core.name, ctypes.POINTER(StucName))
            attribName = ctypes.cast(nameCast, ctypes.c_char_p).value.decode()
            if attribName == "StucMaterialIndices":
                matIdxArr = ctypes.cast(meshTuple[0].faceAttribs.pArr[i].core.pData, ctypes.POINTER(ctypes.c_byte))
                print(f"face mat indices 5 on the python side is {matIdxArr[5]}")
            i += 1
        outIndexedAttribs = utils.StucAttribIndexedArr()
        jobHandle = ctypes.c_void_p()
        result = stucLib.stucBlenderMapToMesh(ctypes.pointer(jobHandle),
                                              ctypes.pointer(mapArr),
                                              ctypes.pointer(meshTuple[0]),
                                              ctypes.pointer(inIndexedAttribs),
                                              ctypes.pointer(workMesh),
                                              ctypes.pointer(outIndexedAttribs),
                                              commonAttribs,
											  wScale)
        if result != 0:
            print("Stuc python map to mesh failed, error pushing job to queue")
            return
        targetCache.append(TargetCache(objEval,
                                       jobHandle,
                                       mapArr,
                                       meshTuple,
                                       inIndexedAttribs,
                                       workMesh,
                                       outIndexedAttribs,
                                       commonAttribs,
                                       matCount))
    if not len(targetCache):
        return
    cacheCount = len(targetCache)
    jobHandleArr = (ctypes.c_void_p * cacheCount)()
    i = 0
    for item in targetCache:
        jobHandleArr[i] = item.jobHandle
        i += 1
    result = stucLib.stucBlenderWaitForJobs(cacheCount, jobHandleArr)
    if result != 0:
        print("Stuc python map to mesh failed, map to mesh returned error")
        return
    print("all mapping jobs returned success")
    for item in targetCache:
        nameStuc = item.obj.name + ".Stuc"
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

        copyStucMeshToBlenderMesh(meshStuc, item.outMesh, outIndexedAttribs, item.commonAttribs)
        stucLib.stucBlenderMeshDestroy(item.outMesh)
        normalBlendAttrib = meshStuc.attributes.get("normal", None)
        if (normalBlendAttrib):
            meshStuc.attributes.remove(normalBlendAttrib)
        matBlendAttrib = meshStuc.attributes.get("StucMaterialIndices", None)
        if (matBlendAttrib):
            meshStuc.attributes.remove(matBlendAttrib)
            
        i = 0
        while i < item.matCount:
            stucLib.stucBlenderDestroyCommonAttribs(ctypes.pointer(item.commonAttribs[i]))
            i += 1
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
           STUC_OT_StucMatAssign,
           STUC_OT_StucRemove,
           STUC_OT_StucMatRemove,
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
