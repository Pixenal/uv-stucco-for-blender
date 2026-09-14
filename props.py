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

def stucDirUpdate(self, context: bpy.types.Context) -> None:
	dir = utils.makeRel(context, self.name)
	if dir:
		self.name = dir

def isMatReleventToStuc(context: bpy.types.Context, mat: bpy.types.Material) -> bool:
	matMap = context.scene.stucMats.get(mat.name, None) #type:ignore
	if matMap and matMap.map:
		return True
	return False

def matGraphSetup(nodeTree: bpy.types.NodeTree, mapName: str) -> None:
	nodeOut = None
	for node in nodeTree.nodes:
		if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
			nodeOut = node
			break
	if not nodeOut:
		return
	links = nodeTree.links
	pbrNode = utils.nodeGet(nodeTree, "Principled BSDF", 'ShaderNodeBsdfPrincipled')
	socketArr = ("Base Color", "Normal", "Roughness", "Metallic")
	imgNodeArr: list[bpy.types.Node | None] = [None, None, None, None]
	srcArr = (("albedo", -1), ("normal", -1), ("hrm", 1), ("hrm", 2))
	for i, socket in enumerate(socketArr):
		imgNode = utils.nodeGet(nodeTree, f"Tex {srcArr[i][0]}", 'ShaderNodeTexImage')
		image = bpy.data.images.get(f"{mapName}_{srcArr[i][0]}", None)
		if image and imgNode.image is not image:#type:ignore
			imgNode.image = image#type:ignore
		pbrInput = pbrNode.inputs.get(socket, None)
		if not pbrInput:
			raise Exception()
		output = imgNode.outputs[0]
		imgComp = srcArr[i][1]
		if imgComp != -1:
			nodeName = f"{imgNode.name}_break"
			breakNode = utils.nodeGet(nodeTree, nodeName, 'ShaderNodeSeparateColor')
			links.new(output, breakNode.inputs[0])
			output = breakNode.outputs[imgComp]
		if socket == "Normal":
			imgNodeArr[i] = imgNode
			normalNode = utils.nodeGet(nodeTree, "Normal Map", 'ShaderNodeNormalMap')
			links.new(imgNode.outputs[0], normalNode.inputs[1])
			output = normalNode.outputs[0]
		if socket == "Base Color":
			mulNode = utils.nodeGet(nodeTree, "Alpha Mul", 'ShaderNodeMath')
			mulNode.operation = 'MULTIPLY'#type:ignore
			mulNode.inputs[1].default_value = .0#type:ignore
			links.new(imgNode.outputs[1], mulNode.inputs[0])#plug alpha into math node
			alphaInput = pbrNode.inputs.get("Alpha", None)
			if not alphaInput:
				raise Exception()
			links.new(mulNode.outputs[0], alphaInput)
		links.new(output, pbrInput)
	links.new(pbrNode.outputs[0], nodeOut.inputs[0])

def matGraphSetupIfRelevant(
	context: bpy.types.Context,
	mat: bpy.types.Material,
	mapName: str,
	value: bool
) -> None:
	if not value and isMatReleventToStuc(context, mat):
		return
	mat.use_nodes = True
	if mat.node_tree:
		matGraphSetup(mat.node_tree, mapName)
	mat.blend_method = 'BLEND' if value else 'OPAQUE'
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
		matGraphSetupIfRelevant(context, self.matCpy, self.map, False)
	self.matCpy = self.mat
	if self.mat:
		self.name = self.mat.name
		matGraphSetupIfRelevant(context, self.mat, self.map, True)
	else:
		self.name = ""

def relPathsUpdate(self, context: bpy.types.Context) -> None:
	if not len(bpy.data.filepath):
		return
	for map in context.scene.stucMaps:#type:ignore
		if self.relPaths:
			map.dir.name = map.dir.name #update func will make relative
		else:
			map.dir.name = bpy.path.abspath(map.dir.name)
	for dir in context.scene.stucDepDirs:#type:ignore
		if self.relPaths:
			dir.name = dir.name #update func will make relative
		else:
			dir.name = bpy.path.abspath(dir.name)

def logEnabledUpdate(self, context: bpy.types.Context) -> None:
	stucLib.stucBlenderLogEnableSet(self.logEnabled)

def mapDepNameUpdate(self, context: bpy.types.Context) -> None:
	self.timestamp = ""
	self.map = self.name

def mapDepUpdate(self, context: bpy.types.Context) -> None:
	if self.timestamp != "":
		self.timestamp = ""
		bpy.ops.stuc.reload_stuc_file()#type:ignore

def dontDrawUpdate(self, context: bpy.types.Context) -> None:
	for stucMat in context.scene.stucMats:#type:ignore
		if stucMat.mat:
			utils.matAlphaSet(stucMat.mat, float(self.dontDraw))
			stucMat.mat.blend_method = 'CLIP' if self.dontDraw else 'BLEND'

class StucAttribMirror(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()#type:ignore
	use : bpy.props.IntProperty()#type:ignore

class StucPath(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(subtype = 'DIR_PATH', update = stucDirUpdate)#type:ignore

class StucMap(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()#type:ignore
	#storing as a string, value too large for Int or Float prop
	timestamp : bpy.props.StringProperty()#type:ignore
	activeAttribIdx : bpy.props.IntProperty()#type:ignore
	depsIdx : bpy.props.IntProperty()#type:ignore
	status : bpy.props.EnumProperty(default = '0', items = [#type:ignore
		('0', 'Pending Load', ""),
		('1', 'Loaded', ""),
		('2', "Error", ""),
		('3', "Missing Dep", "")
	])
	id : bpy.props.IntProperty()#type:ignore

class StucDep(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(update = mapDepNameUpdate)#type:ignore
	map : bpy.props.StringProperty(update = mapDepUpdate)#type:ignore
	timestamp : bpy.props.StringProperty()#type:ignore
	id : bpy.props.IntProperty()#type:ignore

class StucTarget(bpy.types.PropertyGroup):
	obj : bpy.props.PointerProperty(#type:ignore
		type = bpy.types.Object,#type:ignore
		update = targetObjUpdate
	)
	lastObj : bpy.props.PointerProperty( type = bpy.types.Object)#type:ignore
	activeAttribIdx : bpy.props.IntProperty()#type:ignore
	id : bpy.props.IntProperty()#type:ignore
	dirty : bpy.props.BoolProperty()#type:ignore

class StucMapActiveAttrib(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(update = mapActiveAttribUpdate)#type:ignore
	use : bpy.props.StringProperty()#type:ignore

class StucActiveAttrib(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()#type:ignore
	use : bpy.props.StringProperty()#type:ignore
	
class StucMat(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()#type:ignore
	mat : bpy.props.PointerProperty(type = bpy.types.Material, update = stucMatUpdate)#type:ignore
	#matCpy exists to allow stucMatUpdate to see the mat a material pointed to before
	#it was changed (there doesn't seem to be a pre-update callback).
	#(Map property needs to be a string it seems for the prop_search
	#  to work on custom collections?)
	matCpy : bpy.props.PointerProperty(type = bpy.types.Material)#type:ignore
	map : bpy.props.StringProperty(update = stucMatUpdate)#type:ignore

class StucCommonAttrib(bpy.types.PropertyGroup):
	domain : bpy.props.EnumProperty(items = [#type:ignore
		('NONE', "None", ""),
		('FACE', "Face", ""),
		('CORNER', "Face Corner", ""),
		('EDGE', "Edge", ""),
		('POINT', "Vertex", "")
	])
	blend : bpy.props.EnumProperty(default = '0', items = [#type:ignore
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
	opacity : bpy.props.FloatProperty(default = 1.0)#type:ignore
	order : bpy.props.EnumProperty(default = '0', items = [#type:ignore
		('0', "Map Over Mesh", ""),
		('1', "Mesh Over Map", "")
	])

class StucProperties(bpy.types.PropertyGroup):
	nextTargetId : bpy.props.IntProperty(default = 0)#type:ignore
	commonAttribDomain : bpy.props.EnumProperty(items = [#type:ignore
		('FACE', "Face", ""),
		('CORNER', "Face Corner", ""),
		('EDGE', "Edge", ""),
		('POINT', "Vertex", "")
	])
	commonAttribIdx : bpy.props.IntProperty(default = 0)#type:ignore
	wScale : bpy.props.FloatProperty(name = "w Scale", default = 1.0)#type:ignore
	relPaths : bpy.props.BoolProperty(default = True, update = relPathsUpdate)#type:ignore
	drawCacheMaxVerts : bpy.props.IntProperty(#type:ignore
		default = drawCacheMaxVerts,
		update = drawCacheSizeUpdate
	)
	dontDraw : bpy.props.BoolProperty(default = False, update = dontDrawUpdate)#type:ignore
	logEnabled : bpy.props.BoolProperty(default = False, update = logEnabledUpdate)#type:ignore
	#breakPoint : bpy.props.BoolProperty(default = False)
	
class StucCommonAttribTableEntry(bpy.types.PropertyGroup):
	mat : bpy.props.PointerProperty(type = bpy.types.Material)#type:ignore
	map : bpy.props.StringProperty()#type:ignore

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
	bpy.types.Object.stucUsgFlatCutoff = bpy.props.PointerProperty(#type:ignore
		type = bpy.types.Object,#type:ignore
		name = "Stuc USG Flatten Cut-Off",
		poll = usgFlatCutoffPoll#type:ignore
	)
	bpy.types.Scene.stuc = bpy.props.PointerProperty(type = StucProperties)#type:ignore
	bpy.types.Scene.stucTargets = bpy.props.CollectionProperty(name = "Targets", type = StucTarget)#type:ignore
	bpy.types.Scene.stucTargetsIdx = bpy.props.IntProperty(name = "Targets Index")#type:ignore
	bpy.types.Scene.stucTargetIdNext = bpy.props.IntProperty()#type:ignore
	bpy.types.Scene.stucMaps = bpy.props.CollectionProperty(name = "Maps", type = StucMap)#type:ignore
	bpy.types.Scene.stucMapsIdx = bpy.props.IntProperty(name = "Maps Index")#type:ignore
	bpy.types.Scene.stucMats = bpy.props.CollectionProperty(name = "Mats", type = StucMat)#type:ignore
	bpy.types.Scene.stucMatsIdx = bpy.props.IntProperty(name = "Mats Index")#type:ignore
	bpy.types.Scene.stucMatToRm = bpy.props.PointerProperty(type = StucMat)#type:ignore
	bpy.types.Scene.stucDepDirs = bpy.props.CollectionProperty(name = "Dep Dirs", type = StucPath)#type:ignore
	bpy.types.Scene.stucDepDirsIdx = bpy.props.IntProperty(name = "Dep Dirs Index")#type:ignore
	StucCommonAttribTableEntry.mesh = bpy.props.CollectionProperty(type = StucCommonAttrib)#type:ignore
	StucCommonAttribTableEntry.faces = bpy.props.CollectionProperty(type = StucCommonAttrib)#type:ignore
	StucCommonAttribTableEntry.corners = bpy.props.CollectionProperty(type = StucCommonAttrib)#type:ignore
	StucCommonAttribTableEntry.edges = bpy.props.CollectionProperty(type = StucCommonAttrib)#type:ignore
	StucCommonAttribTableEntry.verts = bpy.props.CollectionProperty(type = StucCommonAttrib)#type:ignore
	StucTarget.commonAttribTable = bpy.props.CollectionProperty(type = StucCommonAttribTableEntry)#type:ignore
	StucTarget.activeAttribs = bpy.props.CollectionProperty(type = StucActiveAttrib)#type:ignore
	StucMap.activeAttribs = bpy.props.CollectionProperty(type = StucMapActiveAttrib)#type:ignore
	StucMap.attribs = bpy.props.CollectionProperty(type = StucAttribMirror)#type:ignore
	StucMap.deps = bpy.props.CollectionProperty(type = StucDep)#type:ignore
	StucMap.dir = bpy.props.PointerProperty(type = StucPath)#type:ignore

#TODO don't you need to delete the other props as well?
def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
