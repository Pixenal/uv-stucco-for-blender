'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
import numpy
import os
import re
from enum import Enum
from datetime import datetime
import pdb
from typing import Any
import sys
import types

import bpy
import gpu
import gpu_extras
import mathutils

from . import stuc
from . import attrib_utils as attribUtils
from . import mesh_utils as meshUtils
from . import c_lib
stucLib = c_lib.stucLib
from . import props
from . import utils

frame: int = 0

class ShaderErr(Enum):
	NONE = 0
	ERROR = 1
	NO_MAP = 2
	MAP_NOT_LOADED = 3
	NO_MAT = 4
	INVALID_SHADER = 5

class PreviewOffScreenArr():
	class Item():
		class Buf:
			def __init__(self, name: str, res: int, format: str, colorSpace: str) -> None:
				self.name = name
				self.format = format
				self.colorSpace = colorSpace
				self.buf = gpu.types.GPUOffScreen(res, res, format = format)#type:ignore
		def __init__(self) -> None:
			self.res = 2048
			self.albedo =  self.Buf("albedo", self.res, 'RGBA16F', 'sRGB')
			self.normal = self.Buf("normal", self.res, 'RGBA16F', "Non-Color")
			self.hrm = self.Buf("hrm", self.res, 'RGBA16F', "Non-Color")

	def __init__(self) -> None:
		self.arr = list[PreviewOffScreenArr.Item]()
		self.size = 0
		self.count = 0

	def append(self) -> Item:
		if self.count > self.size:
			raise Exception("preview offscreen arr state is invalid")
		if self.count == self.size:
			self.arr.append(PreviewOffScreenArr.Item())
			self.size += 1
		item = self.arr[self.count]
		self.count += 1
		return item
	
	def clear(self) -> None:
		self.count = 0
	
	def get(self, idx: int) -> Item:
		if idx < -1 or idx >= self.count:
			raise Exception("idx out of range")
		return self.arr[self.count - 1] if idx == -1 else self.arr[idx]

previewArr = PreviewOffScreenArr()

def numpyFromStucAttrib(
	mesh: stuc.StucMesh,
	use: stuc.StucAttribUse,
	size: int,
	domain: stuc.StucDomain = stuc.StucDomain.VERT,
	attribType: type = ctypes.c_float
):
	match domain:
		case stuc.StucDomain.FACE:
			attribArray = mesh.faceAttribs
			count = mesh.faceCount
		case stuc.StucDomain.CORNER:
			attribArray = mesh.cornerAttribs
			count = mesh.cornerCount
		case stuc.StucDomain.EDGE:
			attribArray = mesh.edgeAttribs
			count = mesh.edgeCount
		case stuc.StucDomain.VERT:
			attribArray = mesh.vertAttribs
			count = mesh.vertCount
		case _:
			raise Exception("invalid domain")
	attrib = attribUtils.getAttribFromUse(attribArray, use.value)
	if not attrib:
		return None
	return numpy.ctypeslib.as_array(
    	ctypes.cast(attrib.core.pData, ctypes.POINTER(attribType)),
    	shape = (count, size)
	)

parentDir = os.path.dirname(__file__)

def insertIncludes(text: str) -> str:
	newText = text
	while True:
		iter = re.finditer("#include \".+\"", newText)
		rerun = False
		for i in iter:
			path = re.search("\"(.*?)\"", i.group())
			if not path:
				continue
			file = open(f"{parentDir}/shaders/{path.group(1)}")
			newText = newText[:i.span()[0]] + file.read() + newText[i.span()[1]:]
			file.close()
			rerun = True
			break
		if not rerun:
			break
	return newText

def loadTex(name: str, colSpace: str, reload: bool = False) -> bpy.types.Image | None:
	tex = None
	if len(name):
		tex = bpy.data.images.get(f"T_{name}.png", None)
		if not tex:
			tex = bpy.data.images.load(f"{parentDir}/textures/T_{name}.png")
		elif reload:
			tex.reload()
		tex.colorspace_settings.name = colSpace #type:ignore
	return tex

coreTextures: list[gpu.types.GPUTexture] | None = None

def loadCoreTextures() -> list[gpu.types.GPUTexture] | None:
	flowTex = loadTex(f"StucNoise_Curl_A_FLOW", 'Non-Color', True)
	macroNoiseTex = loadTex(f"StucNoise_Macro_A_MASK", 'Non-Color', True)
	microNoiseTex = loadTex(f"StucNoise_Micro_A_MASK", 'Non-Color', True)
	sparkleTex = loadTex(f"StucNoise_Sparkle_A_MASK", 'Non-Color', True)
	errErrTex = loadTex(f"StucErr_Error_MASK", 'Non-Color')
	errNoMapTex = loadTex(f"StucErr_NoMap_MASK", 'Non-Color')
	errMapNotLoadedTex = loadTex(f"StucErr_MapNotLoaded_MASK", 'Non-Color')
	errNoMatTex = loadTex(f"StucErr_NoMat_MASK", 'Non-Color')
	errInvalidShaderTex = loadTex(f"StucErr_InvalidShader_MASK", 'Non-Color')
	if flowTex and macroNoiseTex and microNoiseTex and sparkleTex and errErrTex and\
	   errNoMapTex and errMapNotLoadedTex and errNoMatTex and errInvalidShaderTex:
		return [
			gpu.texture.from_image(flowTex),
			gpu.texture.from_image(macroNoiseTex),
			gpu.texture.from_image(microNoiseTex),
			gpu.texture.from_image(sparkleTex),
			gpu.texture.from_image(errErrTex),
			gpu.texture.from_image(errNoMapTex),
			gpu.texture.from_image(errMapNotLoadedTex),
			gpu.texture.from_image(errNoMatTex),
			gpu.texture.from_image(errInvalidShaderTex)
		]
	else:
		raise Exception("failed to find textures for stuc mesh shader")

vertOut = gpu.types.GPUStageInterfaceInfo("my_interface") #type:ignore
vertOut.smooth('VEC3', "v_pos")
vertOut.smooth('VEC2', "v_uv")
vertOut.smooth('MAT3', "m_tbn")
vertOut.flat('MAT3', "m_viewMat")
vertOut.flat('FLOAT', "i_select")
vertOut.smooth('FLOAT', "f_gradient")
info = gpu.types.GPUShaderCreateInfo()
info.push_constant('MAT3', "viewMat")
info.typedef_source("\
	struct MatInfo { \
		vec3 albedoUniform;\
		float metalUniform;\
		float roughUniform;\
		float albedoUseTex;\
		float normalUseTex;\
		float metalUseTex;\
		float roughUseTex;\
		float albedoChannel;\
		float metalChannel;\
		float roughChannel;\
	};\
	struct Args {\
		mat4 viewProjMat;\
		mat4 modelMat;\
		vec3 viewPos;\
		float isEditMode;\
		vec2 mapZBounds;\
		vec2 viewRes;\
		float error;\
		float time;\
		float flipY;\
		int matParam;\
	};\
")
info.uniform_buf(0, "MatInfo", "matInfo")
info.uniform_buf(1, "Args", "args")
info.sampler(0, 'FLOAT_2D', "envTex")
info.sampler(1, 'FLOAT_2D', "albedoTex")
info.sampler(2, 'FLOAT_2D', "normalTex")
info.sampler(3, 'FLOAT_2D', "metalTex")
info.sampler(4, 'FLOAT_2D', "roughTex")
info.sampler(5, 'FLOAT_2D', "errTex")
info.sampler(6, 'FLOAT_2D', "flowTex")
info.sampler(7, 'FLOAT_2D', "macroNoiseTex")
info.sampler(8, 'FLOAT_2D', "microNoiseTex")
info.sampler(9, 'FLOAT_2D', "sparkleTex")
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'VEC2', "uv")
info.vertex_in(2, 'VEC3', "normal")
info.vertex_in(3, 'VEC3', "tangent")
info.vertex_in(4, 'FLOAT', "tSign")
info.vertex_in(5, 'FLOAT', "select")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")

vertSrc = open(f"{parentDir}/shaders/stuc_vert.glsl")
info.vertex_source(vertSrc.read())
vertSrc.close()

fragSrc = open(f"{parentDir}/shaders/stuc_frag.glsl")
info.fragment_source(insertIncludes(fragSrc.read()))
fragSrc.close()
meshShader = gpu.shader.create_from_info(info)
del vertOut
del info

def reloadCoreTextures() -> None:
	global coreTextures
	coreTextures = loadCoreTextures()

def getNode(
	nodeTree: bpy.types.NodeTree,
	nodeType: str,
	parent: bpy.types.Node,
	parentSocket: str
) -> bpy.types.Node | None:
	for node in nodeTree.nodes:
		if node.type != nodeType:
			continue
		if not node.outputs:
			continue
		for out in node.outputs:
			if not out.links:
				continue
			for link in out.links:
				if link.to_node == parent and link.to_socket.name == parentSocket:
					return node
	return None

def getParentNode(node: bpy.types.Node, outSocket: str, linkIdx: int) -> bpy.types.Node | None:
	if not node.outputs:
		return None
	out = node.outputs.get(outSocket, None)
	if not out or not out.links or linkIdx >= len(out.links):
		return None
	return out.links[linkIdx].to_node
				
def getMatTex(
	nodeBsdf: bpy.types.Node,
	socket: str,
	normalMap: bool = False
) -> list[bpy.types.Image | int | bool] | None:
	if not nodeBsdf.inputs:
		raise Exception()
	inSocket = nodeBsdf.inputs.get(socket, None)
	if not inSocket:
		raise Exception()
	if not inSocket.links or not inSocket.links[0].from_node:
		return None
	flipY = False
	link = inSocket.links[0]
	node = link.from_node
	channelIdx = -1
	if node.type == 'TEX_IMAGE':
		if link.from_socket.name == "Alpha":
			channelIdx = 3
	elif normalMap and node.type == 'NORMAL_MAP':
		if not node.inputs:
			raise Exception()
		outSocket = inSocket.links[0].from_socket
		inSocket = node.inputs[1]
		if 	not inSocket.links or\
			not inSocket.links[0].from_node or\
			inSocket.links[0].from_node.type != 'TEX_IMAGE' or\
			inSocket.links[0].from_socket.name == "Alpha":
			return None
		flipY = node.label.lower() == "flip"
		node = inSocket.links[0].from_node
	elif not normalMap and\
		(node.type == 'SEPARATE_COLOR' or node.type == 'SEPARATE_XYZ'):
		
		if not node.inputs:
			raise Exception()
		outSocket = inSocket.links[0].from_socket
		inSocket = node.inputs[0]
		if 	not inSocket.links or\
			not inSocket.links[0].from_node or\
			inSocket.links[0].from_node.type != 'TEX_IMAGE':
			return None
		node = inSocket.links[0].from_node
		if inSocket.links[0].from_socket.name == "Alpha":
			channelIdx = 3
		else:
			match outSocket.name:
				case "X":
					channelIdx = 0
				case "Red":
					channelIdx = 0
				case "Y":
					channelIdx = 1
				case "Green":
					channelIdx = 1
				case "Z":
					channelIdx = 2
				case "Blue":
					channelIdx = 2
	else:
		return None
	return [node.image, channelIdx, flipY] #type:ignore

def setArrFromArr(a, b, size) -> None:
	i = 0
	while i < size:
		a[i] = b[i]
		i += 1

class MatInfo(ctypes.Structure):
	_fields_ = [
		("albedoUniform", ctypes.c_float * 3),
		("metalUniform", ctypes.c_float),
		("roughUniform", ctypes.c_float),
		("albedoUseTex", ctypes.c_float),
		("normalUseTex", ctypes.c_float),
		("metalUseTex", ctypes.c_float),
		("roughUseTex", ctypes.c_float),
		("albedoChannel", ctypes.c_float),
		("metalChannel", ctypes.c_float),
		("roughChannel", ctypes.c_float)
	]

class Args(ctypes.Structure):
	_fields_ = [
		("viewProjMat", ctypes.c_float * 16),
		("modelMat", ctypes.c_float * 16),
		("viewPos", ctypes.c_float * 3),
		("isEditMode", ctypes.c_float),
		("mapZBounds", ctypes.c_float * 2),
		("viewRes", ctypes.c_float * 2),
		("error", ctypes.c_float),
		("time", ctypes.c_float),
		("flipY", ctypes.c_float),
		("matParam", ctypes.c_int)
	]

def getMissingTex() -> gpu.types.GPUTexture:
	missingTex = bpy.data.images.get("STUC_MISSING_TEX", None)
	if not missingTex:
		missingTex = bpy.data.images.new("STUC_MISSING_TEX", 16, 16, alpha = True)
	return gpu.texture.from_image(missingTex)

def getMatParams(
	nodeTree: bpy.types.NodeTree,
	matInfo: MatInfo
) -> list[gpu.types.GPUTexture] | None:
	nodeOut = None
	for node in nodeTree.nodes:
		if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
			nodeOut = node
			break
	if not nodeOut:
		return None
	nodeBsdf = getNode(nodeTree, 'BSDF_PRINCIPLED', nodeOut, "Surface")
	if not nodeBsdf:
		return None
	
	missingTex = getMissingTex()
	texInfo = getMatTex(nodeBsdf, "Base Color")
	if texInfo:
		albedoTex = gpu.texture.from_image(texInfo[0]) #type:ignore
		matInfo.albedoChannel = texInfo[1]
		matInfo.albedoUseTex = True
	else:
		albedoTex = missingTex
		col = nodeBsdf.inputs["Base Color"].default_value #type:ignore
		setArrFromArr(matInfo.albedoUniform, col, 3)
	texInfo = getMatTex(nodeBsdf, "Normal", True)
	if texInfo:
		normalTex = gpu.texture.from_image(texInfo[0]) #type:ignore
		matInfo.normalUseTex = True
		matInfo.flipY = float(texInfo[2]) #type:ignore
	else:
		normalTex = missingTex
	texInfo = getMatTex(nodeBsdf, "Metallic")
	if texInfo:
		metalTex = gpu.texture.from_image(texInfo[0]) #type:ignore
		matInfo.metalChannel = texInfo[1]
		matInfo.metalUseTex = True
	else:
		metalTex = missingTex
		matInfo.metalUniform = nodeBsdf.inputs["Metallic"].default_value #type:ignore
	texInfo = getMatTex(nodeBsdf, "Roughness")
	if texInfo:
		roughTex = gpu.texture.from_image(texInfo[0]) #type:ignore
		matInfo.roughChannel = texInfo[1]
		matInfo.roughUseTex = True
	else:
		roughTex = missingTex
		matInfo.roughUniform = nodeBsdf.inputs["Roughness"].default_value #type:ignore

	return [albedoTex, normalTex, metalTex, roughTex]

def getErrTex(error: ShaderErr) -> gpu.types.GPUTexture | None:
	if not coreTextures:
		raise Exception()
	match error:
		case ShaderErr.ERROR:
			return coreTextures[4]
		case ShaderErr.NO_MAP:
			return coreTextures[5]
		case ShaderErr.MAP_NOT_LOADED:
			return coreTextures[6]
		case ShaderErr.NO_MAT:
			return coreTextures[7]
		case ShaderErr.INVALID_SHADER:
			return coreTextures[8]
		case _:
			return None

class BatchCache():
	class Entry():
		def __init__(self, key: str, timestamp: float, frame: int) -> None:
			self.key = key
			self.timestamp = timestamp
			self.data: gpu.types.GPUBatch | None = None
			self.vertCount: int = 0
			self.lastAccess = frame

	def __init__(self) -> None:
		self.table: dict[str, BatchCache.Entry] = {}
		self.vertCount: int = 0
		self.entryHasSetVertCount: bool = True

	def __checkEntryHasSetVertCount(self) -> None:
		if not self.entryHasSetVertCount:
			raise Exception("setVertCount must be called after adding a new entry")
		
	def __isCacheFull(self) -> bool:
		return self.vertCount > props.drawCacheMaxVerts

	def __getIntern(self, key: str, timestamp: float, frame: int) -> Entry | None:
		entry = self.table.get(key, None)
		if entry:
			entry.lastAccess = frame
			if timestamp != entry.timestamp:
				entry.timestamp = timestamp
				self.vertCount -= entry.vertCount
				if self.__isCacheFull():
					self.table.pop(key)
					return None
				entry.vertCount = 0
				entry.data = None
		else:
			if self.vertCount < 0:
				raise Exception("draw cache state is invalid")
			if self.__isCacheFull():
				return None
			entry = self.Entry(key, timestamp, frame)
			self.table[key] = entry
		return entry
	
	def __remove(self, entry: Entry) -> None:
		self.vertCount -= entry.vertCount
		self.table.pop(entry.key)

	def get(self, key: str, timestamp: float, frame: int) -> Entry | None:
		self.__checkEntryHasSetVertCount()
		entry = self.__getIntern(key, timestamp, frame)
		if entry and not entry.data:
			self.entryHasSetVertCount = False
		return entry

	def setVertCount(self, entry: Entry, vertCount: int) -> None:
		if self.entryHasSetVertCount:
			raise Exception("invalid call to func")
		entry.vertCount = vertCount
		self.vertCount += vertCount
		self.entryHasSetVertCount = True

	def remove(self, key: str) -> None:
		entry = self.table.get(key, None)
		if entry:
			self.__remove(entry)
	
	def clean(self, frame: int) -> None:
		self.__checkEntryHasSetVertCount()
		arr: list[BatchCache.Entry] = [self.table[i] for i in self.table.keys()]
		for item in arr:
			if abs(frame - item.lastAccess) > 0:
				self.__remove(item)

batchCache = BatchCache()

class MatCacheEntry():
	def __init__(
		self,
		buf: gpu.types.GPUUniformBuf,
		texArr: list[gpu.types.GPUTexture]
	) -> None:
		self.buf = buf
		self.texArr = texArr

class TexOverride():
	def __init__(self, key: str, texArr: list[gpu.types.GPUTexture]) -> None:
		self.key = key
		self.texArr = texArr

class VertBufs():
	def __init__(self) -> None:
		self.pos: numpy.ndarray | None = None
		self.uv: numpy.ndarray | None = None
		self.normal: numpy.ndarray | None = None
		self.tangent: numpy.ndarray | None = None
		self.tSign: numpy.ndarray | None = None
		self.faceSel: numpy.ndarray | None = None

class IdxBuf():
	def __init__(self) -> None:
		self.forMat: numpy.ndarray | None = None
		self.all = stuc.PixtyI32Arr()

class Bufs():
	def __init__(self) -> None:
		self.vert = VertBufs()
		self.idx = IdxBuf()

class DrawOpts():
	def __init__(
		self,
		envFileName: str = "",
		backfaceCull: bool = True,
		forceUpdate: bool = False
	) -> None:
		self.envFileName = envFileName
		self.backfaceCull = backfaceCull
		self.forceUpdate = forceUpdate

class DrawMat():
	def __init__(
		self,
		cache: dict[str, MatCacheEntry],
		mat: bpy.types.Material | None,
		param: int = -1
	) -> None:
		self.cache = cache
		self.mat = mat
		self.param = param

def drawMeshForMat(
	cacheEntry: BatchCache.Entry | None,
	mat: DrawMat,
	bufs: Bufs,
	cacheType: stuc.MeshCacheType,
	args: Args,
	texOverride: TexOverride | None = None,
	error: ShaderErr = ShaderErr.NONE,
	zBounds: stuc.StucVec2 | None = None
) -> None:
	area = utils.getArea()
	if not area:
		raise Exception()
	if area.spaces.active.overlay.show_overlays:#type:ignore
		args.isEditMode = float(cacheType == stuc.MeshCacheType.MESH_CACHE_IN_EDIT)
	else:
		args.isEditMode = False
	if zBounds:
		args.mapZBounds[0] = zBounds.x
		args.mapZBounds[1] = zBounds.y
	else:
		args.mapZBounds[0] = .0
		args.mapZBounds[1] = .0
	texArr = None
	if cacheType == stuc.MeshCacheType.MESH_CACHE_OUT:
		if not mat.mat:
			raise Exception()
		
	matCacheEntry = None
	if mat.mat or texOverride:
		key = texOverride.key if texOverride else mat.mat.name #type:ignore
		matCacheEntry = mat.cache.get(key, None)
	if matCacheEntry:
		matInfoUbo = matCacheEntry.buf
		texArr = matCacheEntry.texArr
	else:
		matInfo = MatInfo()
		if error == ShaderErr.NONE:
			if texOverride:
				if len(texOverride.texArr) != 4:
					raise Exception("tex override list is wrong size")
				texArr = texOverride.texArr
				matInfo.albedoUseTex = True
				matInfo.normalUseTex = True
				matInfo.roughUseTex = True
				matInfo.metalUseTex = True
				matInfo.albedoChannel = -1
				matInfo.roughChannel = 1
				matInfo.metalChannel = 2
			elif mat.mat:
				if mat.mat.node_tree:
					texArr = getMatParams(mat.mat.node_tree, matInfo)
				if not texArr:
					error = ShaderErr.INVALID_SHADER
		if not texArr:
			missingTex = getMissingTex()
			texArr = [missingTex, missingTex, missingTex, missingTex]
			if mat.mat:
				setArrFromArr(matInfo.albedoUniform, mat.mat.diffuse_color, 3)
				matInfo.metalUniform = mat.mat.metallic
				matInfo.roughUniform = mat.mat.roughness
		matInfoUbo = gpu.types.GPUUniformBuf(
			gpu.types.Buffer('UBYTE', ctypes.sizeof(MatInfo), matInfo) #type:ignore
		)
		if mat.mat or texOverride:
			matCacheEntry = MatCacheEntry(matInfoUbo, texArr)
			key = texOverride.key if texOverride else mat.mat.name#type:ignore
			mat.cache[key] = matCacheEntry
	meshShader.uniform_block("matInfo", matInfoUbo)

	meshShader.uniform_sampler("albedoTex", texArr[0])
	meshShader.uniform_sampler("normalTex", texArr[1])
	meshShader.uniform_sampler("metalTex", texArr[2])
	meshShader.uniform_sampler("roughTex", texArr[3])

	args.error = float(error.value)
	if error != ShaderErr.NONE:
		errTex = getErrTex(error)
		if errTex:
			meshShader.uniform_sampler("errTex", errTex)
		else:
			meshShader.uniform_sampler("errTex", getMissingTex())

	delta = (datetime.now() - datetime(1970, 1, 1))
	args.time = float(delta.seconds % 60) + delta.microseconds / 1000000.0

	if matCacheEntry:
		matInfoUbo = matCacheEntry
	
	argsUbo = gpu.types.GPUUniformBuf(
		gpu.types.Buffer('UBYTE', ctypes.sizeof(Args), args) #type:ignore
	)
	meshShader.uniform_block("args", argsUbo)

	if not coreTextures:
		raise Exception()
	meshShader.uniform_sampler("flowTex", coreTextures[0])
	meshShader.uniform_sampler("macroNoiseTex", coreTextures[1])
	meshShader.uniform_sampler("microNoiseTex", coreTextures[2])
	meshShader.uniform_sampler("sparkleTex", coreTextures[3])

	if cacheEntry and cacheEntry.data:
		batch = cacheEntry.data
	else:
		if type(bufs.idx.forMat) == types.NoneType or\
		   type(bufs.vert.pos) == types.NoneType:
			raise Exception("mesh data must be passed if batch cache is empty")
		batch = gpu_extras.batch.batch_for_shader(
			meshShader,
			'TRIS',
			{
				"position" : bufs.vert.pos, #type:ignore
				"uv" : bufs.vert.uv,
				"normal" : bufs.vert.normal,
				"tangent" : bufs.vert.tangent,
				"tSign" : bufs.vert.tSign,
				"select" : bufs.vert.faceSel if args.isEditMode else bufs.vert.tSign
			},
			indices = bufs.idx.forMat
		)
		if cacheEntry:
			cacheEntry.data = batch

	batch.draw(meshShader)

def getEnvTex(area: bpy.types.Area, name: str) -> gpu.types.GPUTexture | None:
	if len(name):
		envFile = name
	else:
		envFile = area.spaces.active.shading.studio_light #type:ignore
		if envFile == "Default":
			envFile = "city.exr"
	envTexName = f"STUC_ENV_TEX_{envFile}"
	envTex = bpy.data.images.get(envTexName, None)
	if not envTex:
		studioLights = bpy.context.preferences.studio_lights
		studioLight = studioLights.get(envFile, None)
		if not studioLight:
			return None
		envTex = bpy.data.images.load(studioLight.path)
		envTex.name = envTexName
		envTex.alpha_mode = 'NONE'
	return gpu.texture.from_image(envTex)

class DrawMeshState():
	def __init__(self, depthDestMode) -> None:
		self.valid = True
		self.depthTestMode = depthDestMode

class Camera():
	def __init__(
		self,
		perpMatrix: mathutils.Matrix | None = None,
		viewPos: mathutils.Vector = mathutils.Vector((.0, .0, .0))
	) -> None:
		if not perpMatrix:
			perpMatrix = bpy.context.region_data.perspective_matrix
		self.perpMatrix = perpMatrix
		self.viewPos = viewPos

def drawMeshStart(
	backfaceCull: bool,
	camera: Camera,
	modelMatrix: mathutils.Matrix,
	args: Args,
	matParam: int = -1,
	envFileName: str = "",
) -> DrawMeshState | None:
	area = utils.getArea()
	if not area:
		return None
	envTex = getEnvTex(area, envFileName)
	if not envTex:
		return None
	
	frameBuf: gpu.types.GPUFrameBuffer = gpu.state.active_framebuffer_get()#type:ignore
	viewRes = frameBuf.viewport_get()
	args.viewRes = (viewRes[2], viewRes[3])
	utils.setStucMatrix(args.modelMat, modelMatrix)
	utils.setStucMatrix(args.viewProjMat, camera.perpMatrix)
	viewMat = gpu.matrix.get_model_view_matrix()
	if not camera.viewPos[0] and not camera.viewPos[1] and not camera.viewPos[2]:
		camera.viewPos = viewMat.inverted().translation
	args.viewPos = (camera.viewPos[0], camera.viewPos[1], camera.viewPos[2])
	meshShader.uniform_float("viewMat", viewMat.inverted().to_3x3())#type:ignore
	args.matParam = matParam

	meshShader.uniform_sampler("envTex", envTex)

	depthTestMode = gpu.state.depth_test_get()
	gpu.state.depth_test_set('LESS_EQUAL')
	gpu.state.depth_mask_set(True)
	gpu.state.face_culling_set('BACK' if backfaceCull else 'NONE')

	return DrawMeshState(depthTestMode)

def drawMeshEnd(state: DrawMeshState) -> None:
	gpu.state.depth_mask_set(False)
	gpu.state.depth_test_set(state.depthTestMode)	
	gpu.state.face_culling_set('NONE')

def getStucCorners(
	mesh: stuc.StucMesh,
	matIdx: int,
	corners: stuc.PixtyI32Arr
) -> numpy.ndarray:
	corners.count = 0
	err = stucLib.stucBlenderCornersForMat(
		ctypes.pointer(mesh),
		matIdx,
		ctypes.pointer(corners)
	)
	if err != 1:
		raise Exception("failed to get corners for mat idx")
	return numpy.ctypeslib.as_array( 
		ctypes.cast(corners.pArr, ctypes.POINTER(ctypes.c_int32)),
		shape = (int(corners.count / 3), 3) #assumes mesh has been triangulated #type:ignore
	)

def prevSinglePass(
	key: str,
	dir: str,
	timestamp: float,
	frame: int,
	matCache: dict[str, MatCacheEntry],
	mesh: stuc.StucMesh,
	idxAttribs: stuc.StucAttribIndexedArr,
	matParam: int,
	offscreen: PreviewOffScreenArr.Item.Buf,
	zBounds: stuc.StucVec2 | None,
	forceUpdate: bool
) -> bpy.types.Image:
	name = f"{key}_{offscreen.name}"
	image = bpy.data.images.get(name, None)
	if not forceUpdate and\
	   image and\
	   image.size[0] == offscreen.buf.width and\
	   image.size[1] == offscreen.buf.height:
		return image
	with offscreen.buf.bind():
		framebuf = gpu.state.active_framebuffer_get() #type:ignore
		framebuf.clear(color = (.0, .0, .0, .0), depth = (1.0))
		scaleMatrix = mathutils.Matrix((
			(2.0, .0, .0, .0),
			(.0, 2.0, .0, .0),
			(.0, .0, -2.0, .0028),
			(.0, .0, .0, 1.0)
		))
		posMatrix = mathutils.Matrix((
			(1.0, .0, .0, -.5),
			(.0, 1.0, .0, -.5),
			(.0, .0, 1.0, .0),
			(.0, .0, .0, 1.0)
		))
		perpMatrix = scaleMatrix @ posMatrix
		viewPos = mathutils.Vector((.0, .0, .5))
		geo = DrawGeo(
			mesh,
			mathutils.Matrix.Identity(4),
			stuc.MeshCacheType.MESH_CACHE_OUT,
			idxAttribs,
			zBounds
		)
		drawMesh(
			DrawInfo(key, timestamp, frame),
			geo,
			Camera(perpMatrix, viewPos),
			DrawOpts("forest.exr", forceUpdate = forceUpdate),
			matCache,
			matParam = matParam
		)
		#now update preview texture in blender data
		width = offscreen.buf.width
		height = offscreen.buf.height
		buf = framebuf.read_color(0, 0, width, height, 4, 0, 'FLOAT')
		if image:
			bpy.data.images.remove(image)
		image = bpy.data.images.new(name, width, height, alpha = True)
		image.file_format = 'PNG'
		image.filepath = f"{bpy.path.abspath(dir)}/.preview_cache/{name}.png"
		buf.dimensions = width * height * 4
		image.colorspace_settings.name = offscreen.colorSpace#type:ignore
		image.pixels.foreach_set(buf)#type:ignore
		image.save(filepath = image.filepath)
		return image

def drawStucPreview(
	name: str,
	dir: str,
	timestamp: float,
	frame: int,
	matCache: dict[str, MatCacheEntry],
	mesh: stuc.StucMesh,
	idxAttribs: stuc.StucAttribIndexedArr,
	zBounds: stuc.StucVec2,
	forceUpdate: bool
) -> list[bpy.types.Image]:
	offscreen = previewArr.get(-1)
	albedo = prevSinglePass(
		name,
		dir,
		timestamp,
		frame,
		matCache,
		mesh,
		idxAttribs,
		0,
		offscreen.albedo,
		zBounds,
		forceUpdate
	)
	normal = prevSinglePass(
		name,
		dir,
		timestamp,
		frame,
		matCache,
		mesh,
		idxAttribs,
		1,
		offscreen.normal,
		None,
		forceUpdate
	)
	hrm = prevSinglePass(
		name,
		dir,
		timestamp,
		frame,
		matCache,
		mesh,
		idxAttribs,
		2, 
		offscreen.hrm,
		None,
		forceUpdate
	)
	return [albedo, normal, hrm]

def getMatForPrev(
	map: props.StucMap,
	mapHandle: ctypes.c_void_p,
	frame: int,
	matCache: dict[str, MatCacheEntry],
	forceUpdate: bool = False
) -> TexOverride | None:
	mapName = ctypes.c_char_p()
	err = stucLib.stucBlenderMapNameGet(
		mapHandle,
		ctypes.pointer(mapName)
	)
	if err != 1 or not mapName.value:
		raise Exception("unable to get stuc map name")
	result = meshUtils.getMapMesh(mapName.value.decode('utf-8'), True)
	if type(result[0]) != stuc.StucMesh or type(result[1]) != stuc.StucAttribIndexedArr:
		raise Exception()
	zBounds = stuc.StucVec2()
	err = stucLib.stucBlenderMapZBoundsGet(mapHandle, ctypes.pointer(zBounds))
	if err != 1:
		raise Exception("failed to get map z-bounds")
	previewArr.append()
	imageArr = drawStucPreview(
		map.name,
		map.dir.name,#type:ignore
		float(map.timestamp),
		frame,
		matCache,
		result[0],
		result[1],
		zBounds,
		forceUpdate
	)
	return TexOverride(
		map.name,
		[
			gpu.texture.from_image(imageArr[0]),
			gpu.texture.from_image(imageArr[1]),
			gpu.texture.from_image(imageArr[2]),
			gpu.texture.from_image(imageArr[2])
   		]
	)

class DrawInfo():
	def __init__(
		self,
		key: str | None,
		timestamp: float | None,
		frame: int
	) -> None:
		self.key = key
		self.timestamp = timestamp
		self.frame = frame

class DrawGeo():
	def __init__(
			self,
			mesh: stuc.StucMesh,
			modelMatrix: mathutils.Matrix,
			cacheType: stuc.MeshCacheType,
			idxAttribs: stuc.StucAttribIndexedArr | None = None,
			zBounds: stuc.StucVec2 | None = None,
		) -> None:
		self.mesh = mesh
		self.modelMatrix = modelMatrix
		self.cacheType = cacheType
		self.idxAttribs = idxAttribs
		self.zBounds = zBounds

def callDrawForMat(
	idx: int,
	info: DrawInfo,
	geo: DrawGeo,
	camera: Camera,
	opts: DrawOpts,
	mat: DrawMat,
	editMode: bool,
	bufs: Bufs
) -> None:
	texOverride = None
	error = ShaderErr.NONE
	if geo.cacheType != stuc.MeshCacheType.MESH_CACHE_OUT:
		stucMat = None
		if mat.mat:
			stucMat = bpy.context.scene.stucMats.get(mat.mat.name, None) #type:ignore
		if not stucMat:
			return
		if stucMat.mat and len(stucMat.map):
			map = bpy.context.scene.stucMaps.get(stucMat.map, None) #type:ignore
			if map:
				mapName = map.name.encode('utf-8')
				stucLib.stucBlenderMapHandleGet.restype = ctypes.c_void_p
				mapHandle = None if not map else stucLib.stucBlenderMapHandleGet(mapName)
		if not stucMat.mat:
			error = ShaderErr.NO_MAT
		elif not len(stucMat.map):
			error = ShaderErr.NO_MAP
		elif not map or not mapHandle:
			error = ShaderErr.MAP_NOT_LOADED
		elif mat.cache.get(map.name, None):
			texOverride = TexOverride(key = map.name, texArr = [])
		else:
			texOverride = getMatForPrev(
				map,
				ctypes.cast(mapHandle, ctypes.c_void_p),
				frame,
				mat.cache
			)
	args = Args()
	drawState = drawMeshStart(
		opts.backfaceCull,
		camera,
		geo.modelMatrix,
		args,
		matParam = mat.param,
		envFileName = opts.envFileName,
	)
	if not drawState:
		return
	
	cacheEntry = None
	if info.key:
		if not info.timestamp:
			raise Exception("timestamp is required if key is passed")
		keyWithMat = f"{info.key}_{mat.mat.name if mat.mat else 'None'}"
		if opts.forceUpdate:
			batchCache.remove(keyWithMat)
		cacheEntry = batchCache.get(keyWithMat, info.timestamp, frame)
		if not cacheEntry:
			return
		
	if not cacheEntry or not cacheEntry.data:
		bufs.idx.forMat = getStucCorners(geo.mesh, idx, bufs.idx.all)
		if cacheEntry:
			batchCache.setVertCount(cacheEntry, bufs.idx.all.count)
	else:
		bufs.idx.forMat = None
	if type(bufs.vert.pos) == types.NoneType and (not cacheEntry or not cacheEntry.data):
		bufs.vert.pos = numpyFromStucAttrib(geo.mesh, stuc.StucAttribUse.POS, 3)
		bufs.vert.uv = numpyFromStucAttrib(geo.mesh, stuc.StucAttribUse.UV, 2)
		bufs.vert.normal = numpyFromStucAttrib(geo.mesh, stuc.StucAttribUse.NORMAL, 3)
		bufs.vert.tangent = numpyFromStucAttrib(geo.mesh, stuc.StucAttribUse.TANGENT, 3)
		bufs.vert.tSign = numpyFromStucAttrib(geo.mesh, stuc.StucAttribUse.TSIGN, 1)
		if editMode:
			bufs.vert.faceSel = numpyFromStucAttrib(geo.mesh, stuc.StucAttribUse.MISC, 1)
	drawMeshForMat(
		cacheEntry,
		mat,
		bufs,
		geo.cacheType,
		args,
		texOverride = texOverride,
		error = error,
		zBounds = geo.zBounds
	)
	drawMeshEnd(drawState)

def drawMesh(
	info: DrawInfo,
	geo: DrawGeo,
	camera: Camera,
	opts: DrawOpts,
	matCache: dict[str, MatCacheEntry],
	matParam: int = -1,
	mats: list[bpy.types.Material | None] | None = None
) -> None:
	area = utils.getArea()
	if not area:
		return
	editMode = geo.cacheType == stuc.MeshCacheType.MESH_CACHE_IN_EDIT

	if not mats:
		if not geo.idxAttribs:
			raise Exception("'idxAttribs' must be passed if 'mats' is None")
		mats = []
		attrib = attribUtils.getAttribFromUse(
			geo.mesh.faceAttribs,
			stuc.StucAttribUse.IDX.value
		)
		attribName = attribUtils.pyStrFromC(attrib.core.name) #type:ignore
		attrib = attribUtils.getIdxAttrib(geo.idxAttribs, attribName.encode('utf-8'))
		StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
		matsByteStr = ctypes.cast(attrib.core.pData, ctypes.POINTER(StucString))
		i = 0
		while i < attrib.count:
			matName = ctypes.cast(matsByteStr[i], ctypes.c_char_p).value.decode('utf-8')#type:ignore
			mat = bpy.data.materials.get(matName, None)
			if not mat:
				mat = bpy.data.materials.new(name = matName)
				mat.use_fake_user = True
			mats.append(mat)
			i += 1

	bufs = Bufs()
	for i, mat in enumerate(mats):
		drawMat = DrawMat(matCache, mat, matParam)
		callDrawForMat(i, info, geo, camera, opts, drawMat, editMode, bufs)
	stucLib.stucBlenderCallFree(bufs.idx.all.pArr)

def drawMeshInViewport(
	drawInfo: DrawInfo,
	geo: DrawGeo,
	matCache: dict[str, MatCacheEntry],
	mapArr: stuc.StucMapArr | None = None,
	mats: list[bpy.types.Material | None] | None = None
) -> None:
	opts = DrawOpts("", mapArr == None)
	drawMesh(drawInfo, geo, Camera(), opts, matCache, mats = mats)

editShader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')

def drawEditOverlay(
	mesh: stuc.StucMesh,
	obj: bpy.types.Object
) -> None:
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	edges = numpyFromStucAttrib(
		mesh,
		stuc.StucAttribUse.EDGE_CORNERS,
		2,
		stuc.StucDomain.EDGE,
		ctypes.c_int32
	)
	if type(pos) == types.NoneType or type(edges) == types.NoneType:
		raise Exception("unable to get mesh attribs")

	vertMode = bpy.context.tool_settings.mesh_select_mode[0]
	vertCount = mesh.vertCount if vertMode else mesh.edgeCount * 2
	color = (ctypes.c_float * 4 * vertCount)()
	if vertMode:
		vertsSel = numpyFromStucAttrib(
			mesh,
			stuc.StucAttribUse.MASK,
			1,
			stuc.StucDomain.VERT,
			ctypes.c_int8
		)
		if type(vertsSel) == types.NoneType:
			return
		err = stucLib.stucBlenderEditOverlayColVert(
			mesh.vertCount,
			numpy.ctypeslib.as_ctypes(vertsSel), #type:ignore
			color
		)
	else:
		edgesSel = numpyFromStucAttrib(
			mesh,
			stuc.StucAttribUse.MASK,
			1,
			stuc.StucDomain.EDGE,
			ctypes.c_int8
		)
		if type(edgesSel) == types.NoneType:
			return
		preserve = numpyFromStucAttrib(
			mesh,
			stuc.StucAttribUse.PRESERVE_EDGE,
			1,
			stuc.StucDomain.EDGE,
			ctypes.c_int8
		)
		posSplit = (ctypes.c_float * 3 * vertCount)()
		edgesSplit = (ctypes.c_int32 * 2 * mesh.edgeCount)()
		err = stucLib.stucBlenderEditOverlayColEdge(
			mesh.edgeCount,
			numpy.ctypeslib.as_ctypes(edges), #type:ignore
			edgesSplit,
			numpy.ctypeslib.as_ctypes(edgesSel), #type:ignore
			ctypes.c_void_p(0) if preserve is None else numpy.ctypeslib.as_ctypes(preserve),
			mesh.vertCount,
			numpy.ctypeslib.as_ctypes(pos),
			posSplit,
			color
		)
		pos = numpy.ctypeslib.as_array(posSplit, shape = (vertCount, 3))
		edges = numpy.ctypeslib.as_array(edgesSplit, shape = (mesh.edgeCount, 2))
	if err != 1:
		raise Exception("error while making colors for edit overlay")
	colorNumpy = numpy.ctypeslib.as_array(color, shape = (vertCount, 4))
	editBatch = gpu_extras.batch.batch_for_shader(
		editShader,
		'LINES',
		{
			"pos" : pos, #type:ignore
			"color" : colorNumpy
   		},
		indices = edges
	)
	with gpu.matrix.push_pop():
		perpMatrix = bpy.context.region_data.perspective_matrix
		gpu.matrix.load_projection_matrix(perpMatrix)

		gpu.matrix.load_matrix(obj.matrix_world)
		editShader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
		editShader.uniform_float("lineWidth", 1.0)
		depthTestMode = gpu.state.depth_test_get()
		gpu.state.depth_test_set('LESS_EQUAL')
		gpu.state.depth_mask_set(True)
		editBatch.draw(editShader)
		gpu.state.depth_mask_set(False)
		gpu.state.depth_test_set(depthTestMode)

#TODO return lists should probably be dicts