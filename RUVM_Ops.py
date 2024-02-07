import bpy
import ctypes
import numpy
import bmesh
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
import os

#ruvmLib = ctypes.cdll.LoadLibrary("T:/workshop_folders/RUVM/Win64/RUVM.dll")
ruvmLibPath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM_Blender/Build/Debug/libRUVMBlender.so"
ruvmLib = ctypes.cdll.LoadLibrary(ruvmLibPath)
#ruvmLib = ctypes.cdll.LoadLibrary("T:\workshop_folders/RUVMWin/RUVM/x64/Debug/RUVM.dll")

class RuvmVec2(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float),
                ("y", ctypes.c_float)]

class RuvmVec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float),
                ("y", ctypes.c_float),
                ("z", ctypes.c_float)]

#class Vert(ctypes.Structure):
#    _fields_ = [("pos", Vec3)] 
#
#class Loop(ctypes.Structure):
#    _fields_ = [("vert", ctypes.c_int),
#                ("normal", Vec3)]
#
#class Face(ctypes.Structure):
#    _fields_ = [("loopSize", ctypes.c_int),
#                ("loops", Loop * 4)]

class RuvmMesh(ctypes.Structure):
    _fields_ = [("faceCount", ctypes.c_int),
                ("pFaces", ctypes.POINTER(ctypes.c_int)),
                ("loopCount", ctypes.c_int),
                ("pLoops", ctypes.POINTER(ctypes.c_int)),
                ("pNormals", ctypes.POINTER(RuvmVec3)),
                ("pUvs", ctypes.POINTER(RuvmVec2)),
                ("vertCount", ctypes.c_int),
                ("pVerts", ctypes.POINTER(RuvmVec3))]

class RUVM_OT_RUVMDumpMesh(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_dump_mesh"
    bl_label = "RUVM Dump Mesh"
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj = context.selected_objects[0]
        depsgraph = context.evaluated_depsgraph_get()
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data

        bMeshEval = bmesh.new()
        bMeshEval.from_mesh(meshEval)

        mesh = RuvmMesh()
        mesh.faceCount = len(meshEval.polygons)
        mesh.loopCount = len(meshEval.loops)
        mesh.vertCount = len(meshEval.vertices)

        normals = numpy.zeros(mesh.loopCount * 3, dtype = numpy.float32)
        meshEval.calc_normals_split()
        meshEval.loops.foreach_get("normal", normals)

        vertsPtr = meshEval.vertices[0].as_pointer()
        mesh.pVerts = ctypes.cast(vertsPtr, ctypes.POINTER(RuvmVec3))
        loopsPtr = meshEval.loops[0].as_pointer()
        mesh.pLoops = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int))
        facesPtr = meshEval.polygons[0].as_pointer()
        mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int))
        uvPtr = meshEval.uv_layers[0].data[0].as_pointer()
        mesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))

        ruvmLib.ruvmBlenderDumpMesh.argtypes = (ctypes.POINTER(RuvmMesh),
            numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),
                                                ctypes.POINTER(ctypes.c_char))
        filepath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM_CallTest/TestOutputDir/MeshDump"
        filePathUtf8 = filepath.encode('utf-8')
        ruvmLib.ruvmBlenderDumpMesh(mesh, normals, filePathUtf8)

        return {'FINISHED'}


class RUVM_OT_RuvmExportRuvmFile(bpy.types.Operator):
    bl_idname = "ruvm.ruvm_export_ruvm_file"
    bl_label = "RUVM Export"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if (len(context.selected_objects) == 0):
            print("RUVM export failed, no objects selected.")
            return {'CANCELLED'}
        if (len(context.selected_objects) > 1):
            print("RUVM export failed, more than one object selected.")
            return {'CANCELLED'}
        obj = context.selected_objects[0]
        depsgraph = context.evaluated_depsgraph_get()
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data

        bMeshEval = bmesh.new()
        bMeshEval.from_mesh(meshEval)

        mesh = RuvmMesh()
        mesh.faceCount = len(meshEval.polygons)
        mesh.loopCount = len(meshEval.loops)
        mesh.vertCount = len(meshEval.vertices)

        normals = numpy.zeros(mesh.loopCount * 3, dtype = numpy.float32)
        meshEval.calc_normals_split()
        meshEval.loops.foreach_get("normal", normals)

        vertsPtr = meshEval.vertices[0].as_pointer()
        mesh.pVerts = ctypes.cast(vertsPtr, ctypes.POINTER(RuvmVec3))
        loopsPtr = meshEval.loops[0].as_pointer()
        mesh.pLoops = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int))
        facesPtr = meshEval.polygons[0].as_pointer()
        mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int))
        uvPtr = meshEval.uv_layers[0].data[0].as_pointer()
        mesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))

        ruvmLib.ruvmBlenderMapFileExport.argtypes = (ctypes.POINTER(RuvmMesh),
            numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"))
        ruvmLib.ruvmBlenderMapFileExport(mesh, normals)

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
        #filePath = "/run/media/calebdawson/Tuna/workshop_folders/RUVM/TestOutputDir/File_Misc_F.ruvm"
        filepath = self.filepath
        filePathUtf8 = filepath.encode('utf-8')
        newMap = context.scene.ruvmMaps.add()
        newMap.name = os.path.basename(filepath)
        newMap.filepath = filepath
        context.scene.ruvmMapsIndex = len(context.scene.ruvmMaps)
        ruvmLib.ruvmBlenderMapFileLoad(filePathUtf8)
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

@persistent
def ruvmDepsgraphUpdatePostHandler(dummy):
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for target in scene.ruvmTargets:
        obj = target.obj;
        if not(obj in bpy.context.selected_objects):
            continue
        elif obj.mode != 'OBJECT':
            continue
        mesh = obj.data
        objEval = obj.evaluated_get(depsgraph)
        meshEval = objEval.data

        mesh = RuvmMesh()
        mesh.faceCount = len(meshEval.polygons)
        mesh.loopCount = len(meshEval.loops)
        mesh.vertCount = len(meshEval.vertices)

        normals = numpy.zeros(mesh.loopCount * 3, dtype = numpy.float32)
        meshEval.calc_normals_split()
        meshEval.loops.foreach_get("normal", normals)

        vertsPtr = meshEval.vertices[0].as_pointer()
        mesh.pVerts = ctypes.cast(vertsPtr, ctypes.POINTER(RuvmVec3))
        loopsPtr = meshEval.loops[0].as_pointer()
        mesh.pLoops = ctypes.cast(loopsPtr, ctypes.POINTER(ctypes.c_int))
        facesPtr = meshEval.polygons[0].as_pointer()
        mesh.pFaces = ctypes.cast(facesPtr, ctypes.POINTER(ctypes.c_int))
        uvPtr = meshEval.uv_layers[0].data[0].as_pointer()
        mesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))

        workMesh = RuvmMesh()

        map = bpy.context.scene.ruvmMaps.get(target.map, None)
        if map == None:
            print("Target has no map")
            continue
        filepath = map.filepath
        filePathUtf8 = filepath.encode('utf-8')
        print("Mapping to mesh with map ", filepath)

        ruvmLib.ruvmBlenderMapToMesh.argtypes = (
            ctypes.POINTER(ctypes.c_char),
            ctypes.POINTER(RuvmMesh),
            numpy.ctypeslib.ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),
            ctypes.POINTER(RuvmMesh)
        )
        ruvmLib.ruvmBlenderMapToMesh(filePathUtf8, ctypes.pointer(mesh), normals, ctypes.pointer(workMesh))

        nameRuvm = obj.name + ".Ruvm"
        print(nameRuvm)

        objRuvm = bpy.data.objects.get(nameRuvm, None)
        if not(objRuvm):
            print("Not objRuvm")
            meshRuvm = bpy.data.meshes.new(nameRuvm)
            objRuvm = bpy.data.objects.new(nameRuvm, meshRuvm)
            scene.collection.objects.link(objRuvm)
        else:
            print("Yes objRuvm")
            meshRuvmOld = objRuvm.data
            meshRuvmOld.name += ".Old"
            meshRuvm = bpy.data.meshes.new(nameRuvm)
            objRuvm.data = meshRuvm
            bpy.data.meshes.remove(meshRuvmOld)

        ruvmMesh = RuvmMesh()
        print("workMesh.vertCount ", workMesh.vertCount)
        print("workMesh.loopCount ", workMesh.loopCount)
        print("workMesh.faceCount ", workMesh.faceCount)
        meshRuvm.vertices.add(workMesh.vertCount)
        meshRuvm.loops.add(workMesh.loopCount)
        meshRuvm.polygons.add(workMesh.faceCount)
        ruvmMesh.vertCount = len(meshRuvm.vertices)
        ruvmMesh.loopCount = len(meshRuvm.loops)
        ruvmMesh.faceCount = len(meshRuvm.polygons)
        vertsRuvmPtr = meshRuvm.vertices[0].as_pointer()
        ruvmMesh.pVerts = ctypes.cast(vertsRuvmPtr, ctypes.POINTER(RuvmVec3))
        loopsRuvmPtr = meshRuvm.loops[0].as_pointer()
        ruvmMesh.pLoops = ctypes.cast(loopsRuvmPtr, ctypes.POINTER(ctypes.c_int))
        facesRuvmPtr = meshRuvm.polygons[0].as_pointer()
        ruvmMesh.pFaces = ctypes.cast(facesRuvmPtr, ctypes.POINTER(ctypes.c_int))

        ruvmLib.ruvmBlenderUpdateMesh(ctypes.pointer(ruvmMesh), ctypes.pointer(workMesh))

        meshRuvm.uv_layers.new(name="uvmap")
        uvPtr = meshRuvm.uv_layers[0].data[0].as_pointer()
        ruvmMesh.pUvs = ctypes.cast(uvPtr, ctypes.POINTER(RuvmVec2))
        ruvmLib.ruvmBlenderUpdateMeshUv(ctypes.pointer(ruvmMesh), ctypes.pointer(workMesh))
        ruvmLib.ruvmBlenderMeshDestroy(ctypes.pointer(workMesh))
        print("FinishedUpdating")
        meshRuvm.update()

@persistent
def ruvmLoadPostHandler(dummy):
    ruvmLib.ruvmBlenderInit()

@persistent
def ruvmLoadPreHandler(dummy):
    ruvmLib.ruvmBlenderDestroy()

classes = [RUVM_OT_RuvmExportRuvmFile,
           RUVM_OT_RuvmAssign,
           RUVM_OT_RuvmRemove,
           RUVM_OT_RuvmLoadRuvmFile,
           RUVM_OT_RUVMDumpMesh]

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
