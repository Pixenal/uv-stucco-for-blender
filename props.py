'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import pdb
import ctypes

import bpy

from . import c_lib
stucLib = c_lib.stucLib
from . import stuc
from . import mesh_utils as meshUtils

def targetObjUpdate(self, context) -> None:
	self.name = self.obj.name

def mapActiveAttribUpdate(self, context) -> None:
	if not len(self.name):
		return
	map = context.scene.stucMaps[context.scene.stucMapsIdx]
	mesh = meshUtils.getMapMesh(map.name.encode('utf-8'))
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

def stucMatUpdate(self, context) -> None:
	if self.matCpy and self.mat != self.matCpy:
		del self.matCpy["StucMat"]
	self.matCpy = self.mat
	if self.mat:
		self.mat["StucMat"] = True

def relPathsUpdate(self, context) -> None:
	if not bpy.data.filepath:
		return
	if self.relPaths:
		for map in context.scene.stucMaps:
			map.dir = bpy.path.relpath(map.dir)
	else:
		for map in context.scene.stucMaps:
			map.dir = bpy.path.abspath(map.dir)

class StucAttribMirror(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	use : bpy.props.IntProperty()

class StucMap(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	dir : bpy.props.StringProperty(subtype = 'DIR_PATH')
	#storing as a string, value too large for Int or Float prop
	timestamp : bpy.props.StringProperty()
	activeAttribIdx : bpy.props.IntProperty()

class StucTarget(bpy.types.PropertyGroup):
	obj : bpy.props.PointerProperty(type = bpy.types.Object,
									update = targetObjUpdate)
	activeAttribIdx : bpy.props.IntProperty()

class StucMapActiveAttrib(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty(update = mapActiveAttribUpdate)
	use : bpy.props.StringProperty()

class StucActiveAttrib(bpy.types.PropertyGroup):
	name : bpy.props.StringProperty()
	use : bpy.props.StringProperty()
	
class StucMat(bpy.types.PropertyGroup):
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
	
class StucCommonAttribTableEntry(bpy.types.PropertyGroup):
	mat : bpy.props.PointerProperty(type = bpy.types.Material)
	map : bpy.props.StringProperty()

class StucPath(bpy.types.PropertyGroup):
	path : bpy.props.StringProperty(subtype = 'DIR_PATH')

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
	bpy.types.Scene.stucMaps = bpy.props.CollectionProperty(name = "Maps", type = StucMap)
	bpy.types.Scene.stucMapsIdx = bpy.props.IntProperty(name = "Maps Index")
	bpy.types.Scene.stucMats = bpy.props.CollectionProperty(name = "Mats", type = StucMat)
	bpy.types.Scene.stucMatsIdx = bpy.props.IntProperty(name = "Mats Index")
	bpy.types.Scene.stucDepDirs = bpy.props.CollectionProperty(name = "Dep Dirs", type = StucPath)
	bpy.types.Scene.stucDepDirsIdx = bpy.props.IntProperty(name = "Dep Dirs Index")
	StucCommonAttribTableEntry.mesh = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.faces = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.corners = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.edges = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucCommonAttribTableEntry.verts = bpy.props.CollectionProperty(type = StucCommonAttrib)
	StucTarget.commonAttribTable = bpy.props.CollectionProperty(type = StucCommonAttribTableEntry)
	StucTarget.activeAttribs = bpy.props.CollectionProperty(type = StucActiveAttrib)
	StucMap.activeAttribs = bpy.props.CollectionProperty(type = StucMapActiveAttrib)
	StucMap.attribs = bpy.props.CollectionProperty(type = StucAttribMirror)

#TODO don't you need to delete the other props as well?
def unregister() -> None:
	for cls in classes:
		bpy.utils.unregister_class(cls)
