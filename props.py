'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

drawCacheMaxVerts: int = 25000000

import pdb
import ctypes

import bpy

from . import c_lib
stucLib = c_lib.stucLib
from . import stuc
from . import mesh_utils as meshUtils
from . import utils

def drawCacheSizeUpdate(self, context: bpy.types.Context) -> None:
	global drawCacheMaxVerts
	drawCacheMaxVerts = self.drawCacheMaxVerts

def stucMapDirUpdate(self, context: bpy.types.Context) -> None:
	dir = utils.makeRel(context, self.dir)
	if dir:
		self.dir = dir

def isMatReleventToStuc(context: bpy.types.Context, mat: bpy.types.Material) -> bool:
	matMap = context.scene.stucMats.get(mat.name, None) #type:ignore
	if matMap and matMap.map:
		return True
	return False

def matSetInvisible(context: bpy.types.Context, mat: bpy.types.Material, value: bool) -> None:
	if not value and isMatReleventToStuc(context, mat):
		return
	mat.use_nodes = True
	if mat.node_tree:
		nodeOut = None
		for node in mat.node_tree.nodes:
			if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
				nodeOut = node
				break
		if nodeOut:
			emisNode = mat.node_tree.nodes.new('ShaderNodeBsdfTransparent')
			emisNode.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0) #type:ignore
			links = mat.node_tree.links
			links.new(emisNode.outputs[0], nodeOut.inputs[0])
	mat.blend_method = 'HASHED' if value else 'OPAQUE'
	mat.shadow_method = 'NONE' if value else 'OPAQUE' #type:ignore
	if value:
		mat["StucMat"] = True
	else:
		del mat["StucMat"]

def targetObjUpdate(self, context: bpy.types.Context) -> None:
	try:
		if self.obj != self.lastObj:
			if self.obj:
				self.name = self.obj.name
			else:
				self.name = ""
			if self.lastObj:
				err = stucLib.stucBlenderTargetCacheClear(self.id)
				if err != 1:
					raise Exception("error clearing target mesh cache")
			self.lastObj = self.obj
	except Exception as e:
		raise e

def mapActiveAttribUpdate(self, context: bpy.types.Context) -> None:
	if not len(self.name) or not len(context.scene.stucMaps):#type:ignore
		return
	map = context.scene.stucMaps[context.scene.stucMapsIdx]#type:ignore
	mapInfo = meshUtils.getMapMesh(map.name)
	if type(mapInfo[0]) != stuc.StucMesh:
		raise Exception()
	mesh = mapInfo[0]
	attrib = ctypes.POINTER(stuc.StucAttrib)()
	idx = ctypes.c_int32()
	domain = ctypes.c_int32()
	stucLib.stucBlenderAttribGet(
		ctypes.pointer(mesh),
		self.name.encode('utf-8'),
		ctypes.pointer(attrib),
		ctypes.pointer(idx),
		ctypes.pointer(domain)
	)
	entry = mesh.activeAttribs[attrib.contents.core.use]
	entry.active = True
	entry.idx = idx.value
	entry.domain = domain.value

def usgFlatCutoffPoll(self, obj: bpy.types.Object) -> bool | None:
	return self != obj and not obj.get("StucUsg", None)

def stucMatUpdate(self, context: bpy.types.Context) -> None:
	if self.matCpy and self.mat != self.matCpy:
		matSetInvisible(context, self.matCpy, False)
	self.matCpy = self.mat
	if self.mat:
		self.name = self.mat.name
		matSetInvisible(context, self.mat, True)
	else:
		self.name = ""

def relPathsUpdate(self, context: bpy.types.Context) -> None:
	if not bpy.data.filepath:
		return
	for map in context.scene.stucMaps:#type:ignore
		if self.relPaths:
			map.dir = map.dir #update func will make relative
		else:
			map.dir = bpy.path.abspath(map.dir)
	for dir in context.scene.stucDepDirs:#type:ignore
		if self.relPaths:
			dir.name = bpy.path.relpath(dir.name)
		else:
			dir.name = bpy.path.abspath(dir.name)
			

class StucAttribMirror(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	use : bpy.props.IntProperty()

class StucMap(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	dir : bpy.props.StringProperty(subtype = 'DIR_PATH', update = stucMapDirUpdate)
	#storing as a string, value too large for Int or Float prop
	timestamp : bpy.props.StringProperty()
	activeAttribIdx : bpy.props.IntProperty()
	depsIdx : bpy.props.IntProperty()
	status : bpy.props.EnumProperty(default = '0', items = [
		('0', 'Pending Load', ""),
		('1', 'Loaded', ""),
		('2', "Error", ""),
		('3', "Missing Dep", "")
	])
	age : bpy.props.IntProperty()

class StucDep(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()

class StucTarget(bpy.types.PropertyGroup):
	obj : bpy.props.PointerProperty(
		type = bpy.types.Object,
		update = targetObjUpdate
	)
	lastObj : bpy.props.PointerProperty( type = bpy.types.Object)
	activeAttribIdx : bpy.props.IntProperty()
	id : bpy.props.IntProperty()
	dirty : bpy.props.BoolProperty()

class StucMapActiveAttrib(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(update = mapActiveAttribUpdate)
	use : bpy.props.StringProperty()

class StucActiveAttrib(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	use : bpy.props.StringProperty()
	
class StucMat(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	mat : bpy.props.PointerProperty(type = bpy.types.Material, update = stucMatUpdate)
	#matCpy exists to allow stucMatUpdate to see the mat a material pointed to before
	#it was changed (there doesn't seem to be a pre-update callback).
	#(Map property needs to be a string it seems for the prop_search
	#  to work on custom collections?)
	matCpy : bpy.props.PointerProperty(type = bpy.types.Material)
	map : bpy.props.StringProperty()

class StucCommonAttrib(bpy.types.PropertyGroup):
	domain : bpy.props.EnumProperty(items = [
		('NONE', "None", ""),
		('FACE', "Face", ""),
		('CORNER', "Face Corner", ""),
		('EDGE', "Edge", ""),
		('POINT', "Vertex", "")
	])
	blend : bpy.props.EnumProperty(default = '0', items = [
		('0', "Replace", ""),
		('1', "Multiply", ""),
		('2', "Divide", ""),
		('3', "Add", ""), 
		('4', "Subtract", ""),
		('5', "Add Sub", ""),
		('6', "Lighten", ""),
		('7', "Darken", ""),
		('8', "Overlay", ""),
		('9', "Soft Light", ""),
		('10', "Color Dodge", "")
	])
	opacity : bpy.props.FloatProperty(default = 1.0)
	order : bpy.props.EnumProperty(default = '0', items = [
		('0', "Map Over Mesh", ""),
		('1', "Mesh Over Map", "")
	])

class StucProperties(bpy.types.PropertyGroup):
	nextTargetId : bpy.props.IntProperty(default = 0)
	commonAttribDomain : bpy.props.EnumProperty(items = [
		('FACE', "Face", ""),
		('CORNER', "Face Corner", ""),
		('EDGE', "Edge", ""),
		('POINT', "Vertex", "")
	])
	commonAttribIdx : bpy.props.IntProperty(default = 0)
	wScale : bpy.props.FloatProperty(name = "w Scale", default = 1.0)
	relPaths : bpy.props.BoolProperty(default = True, update = relPathsUpdate)
	drawCacheMaxVerts : bpy.props.IntProperty(
		default = drawCacheMaxVerts,
		update = drawCacheSizeUpdate
	)
	#breakPoint : bpy.props.BoolProperty(default = False)
	
class StucCommonAttribTableEntry(bpy.types.PropertyGroup):
	mat : bpy.props.PointerProperty(type = bpy.types.Material)
	map : bpy.props.StringProperty()

class StucPath(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(subtype = 'DIR_PATH')

classes = [
	StucProperties,
	StucTarget,
	StucAttribMirror,
	StucActiveAttrib,
	StucMapActiveAttrib,
	StucCommonAttrib,
	StucCommonAttribTableEntry,
	StucPath,
	StucMap,
	StucDep,
	StucMat
]

def register() -> None:
	for cls in classes:
		bpy.utils.register_class(cls)
	#TODO add these as needed, rather than adding it to every object like this
	bpy.types.Object.stucUsgFlatCutoff = bpy.props.PointerProperty(
		type = bpy.types.Object,
		name = "Stuc USG Flatten Cut-Off",
		poll = usgFlatCutoffPoll
	)
	bpy.types.Scene.stuc = bpy.props.PointerProperty(type = StucProperties)
	bpy.types.Scene.stucTargets = bpy.props.CollectionProperty(name = "Targets", type = StucTarget)
	bpy.types.Scene.stucTargetsIdx = bpy.props.IntProperty(name = "Targets Index")
	bpy.types.Scene.stucTargetIdNext = bpy.props.IntProperty()
	bpy.types.Scene.stucMaps = bpy.props.CollectionProperty(name = "Maps", type = StucMap)
	bpy.types.Scene.stucMapsIdx = bpy.props.IntProperty(name = "Maps Index")
	bpy.types.Scene.stucMats = bpy.props.CollectionProperty(name = "Mats", type = StucMat)
	bpy.types.Scene.stucMatsIdx = bpy.props.IntProperty(name = "Mats Index")
	bpy.types.Scene.stucMatToRm = bpy.props.PointerProperty(type = StucMat)
	bpy.types.Scene.stucDepDirs = bpy.props.CollectionProperty(name = "Dep Dirs", type = StucPath)
	bpy.types.Scene.stucDepDirsIdx = bpy.props.IntProperty(name = "Dep Dirs Index")
	bpy.types.Scene.stucAgeNext = bpy.props.IntProperty()
	StucCommonAttribTableEntry.mesh = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.faces = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.corners = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.edges = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.verts = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucTarget.commonAttribTable = bpy.props.CollectionProperty(type = StucCommonAttribTableEntry)
	StucTarget.activeAttribs = bpy.props.CollectionProperty(type = StucActiveAttrib)
	StucMap.activeAttribs = bpy.props.CollectionProperty(type = StucMapActiveAttrib)
	StucMap.attribs = bpy.props.CollectionProperty(type = StucAttribMirror)
	StucMap.deps = bpy.props.CollectionProperty(type = StucDep)

#TODO don't you need to delete the other props as well?
def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
