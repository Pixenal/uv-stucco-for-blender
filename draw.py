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

class ShaderErr(Enum):
	NONE = 0
	ERROR = 1
	NO_MAP = 2
	MAP_NOT_LOADED = 3
	NO_MAT = 4
	INVALID_SHADER = 5

offscreenAlbedo = gpu.types.GPUOffScreen(2048, 2048, format = 'RGBA8') #type:ignore
offscreenNormal = gpu.types.GPUOffScreen(2048, 2048, format = 'RGBA16F') #type:ignore
offscreenHrm = gpu.types.GPUOffScreen(2048, 2048, format = 'RGBA8') #type:ignore

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

def getArea() -> bpy.types.Area | None:
	for area in bpy.context.window.screen.areas:
		if area.type == 'VIEW_3D':
			return area
	return None

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
vertOut.flat('FLOAT', "i_select")
vertOut.flat('VEC3', "v_viewPos")
vertOut.flat('INT', "i_matParam")
vertOut.flat('VEC2', "v_viewRes")
vertOut.flat('MAT3', "m_viewMat")
info = gpu.types.GPUShaderCreateInfo()
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('MAT4', "modelMatrix")
info.push_constant('VEC3', "viewPos")
info.push_constant('INT', "matParam")
info.push_constant('VEC2', "viewRes")
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
		float isEditMode;\
		float error;\
		float time;\
		float flipY;\
	};\
")
info.uniform_buf(0, "MatInfo", "matInfo")
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
		("roughChannel", ctypes.c_float),
		("isEditMode", ctypes.c_float),
		("error", ctypes.c_float),
		("time", ctypes.c_float),
		("flipY", ctypes.c_float)
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
		def __init__(self, key: str, timestamp: float, vertCount: int) -> None:
			self.key = key
			self.timestamp = timestamp
			self.data: gpu.types.GPUBatch | None = None
			self.vertCount = vertCount

	def __init__(self, size: int) -> None:
		if size <= 0:
			raise Exception("cache size must be > 0")
		self.size = size
		self.table: dict[str, BatchCache.Entry] = {}
		self.arr: list[BatchCache.Entry] = []

	def get(self, key: str, timestamp: float, vertCount: int) -> Entry:
		entry = self.table.get(key, None)
		if entry:
			if timestamp != entry.timestamp:
				entry.data = None
				entry.timestamp = timestamp
				entry.vertCount = vertCount
			return entry
		arrSize = len(self.arr)
		if arrSize > self.size:
			raise Exception("invalid state")
		if arrSize == self.size:
			def sortKey(entry: BatchCache.Entry) -> int:
				return entry.vertCount
			self.arr.sort(key = sortKey)
			if vertCount <= self.arr[0].vertCount:
				#rejected from cache, returning dummy
				return self.Entry(key, timestamp, vertCount)
			self.table.pop(self.arr[0].key)
			self.arr.pop(0)
		self.arr.append(self.Entry(key, timestamp, vertCount))
		entry = self.arr[-1]
		if not entry:
			raise Exception()
		self.table[key] = entry
		return entry
	
batchCache = BatchCache(32)

def drawMeshForMat(
	cacheEntry: BatchCache.Entry | None,
	pos, uv, normal, tangent, tSign, faceSel,
	corners: numpy.ndarray | None,
	mat: bpy.types.Material | None,
	cacheType: stuc.MeshCacheType,
	texOverride: list[gpu.types.GPUTexture] | None = None,
	error: ShaderErr = ShaderErr.NONE
) -> None:
	area = getArea()
	if not area:
		return None
	matInfo = MatInfo()
	matInfo.isEditMode = float(cacheType == stuc.MeshCacheType.MESH_CACHE_IN_EDIT)
	texArr = None
	if cacheType == stuc.MeshCacheType.MESH_CACHE_OUT:
		if not mat:
			raise Exception()
	
	if error == ShaderErr.NONE:
		if texOverride:
			if len(texOverride) != 4:
				raise Exception("tex override list is wrong size")
			texArr = texOverride
			matInfo.albedoUseTex = True
			matInfo.normalUseTex = True
			matInfo.roughUseTex = True
			matInfo.metalUseTex = True
			matInfo.albedoChannel = -1
			matInfo.roughChannel = 1
			matInfo.metalChannel = 2
		elif mat:
			if mat.node_tree:
				texArr = getMatParams(mat.node_tree, matInfo)
			if not texArr:
				error = ShaderErr.INVALID_SHADER
	matInfo.error = float(error.value)
	if not texArr:
		missingTex = getMissingTex()
		texArr = [missingTex, missingTex, missingTex, missingTex]
		if mat:
			setArrFromArr(matInfo.albedoUniform, mat.diffuse_color, 3)
			matInfo.metalUniform = mat.metallic
			matInfo.roughUniform = mat.roughness
	meshShader.uniform_sampler("albedoTex", texArr[0])
	meshShader.uniform_sampler("normalTex", texArr[1])
	meshShader.uniform_sampler("metalTex", texArr[2])
	meshShader.uniform_sampler("roughTex", texArr[3])
	
	if error != ShaderErr.NONE:
		errTex = getErrTex(error)
		if errTex:
			meshShader.uniform_sampler("errTex", errTex)
		else:
			meshShader.uniform_sampler("errTex", getMissingTex())

	delta = (datetime.now() - datetime(1970, 1, 1))
	matInfo.time = float(delta.seconds % 60) + delta.microseconds / 1000000.0

	matInfoUbo = gpu.types.GPUUniformBuf(
		gpu.types.Buffer('UBYTE', ctypes.sizeof(MatInfo), matInfo) #type:ignore
	)
	meshShader.uniform_block("matInfo", matInfoUbo)

	if not coreTextures:
		raise Exception()
	meshShader.uniform_sampler("flowTex", coreTextures[0])
	meshShader.uniform_sampler("macroNoiseTex", coreTextures[1])
	meshShader.uniform_sampler("microNoiseTex", coreTextures[2])
	meshShader.uniform_sampler("sparkleTex", coreTextures[3])

	if cacheEntry and cacheEntry.data:
		batch = cacheEntry.data
	else:
		if type(corners) == None:
			raise Exception("corners must be passed if batch cache is empty")
		batch = gpu_extras.batch.batch_for_shader(
			meshShader,
			'TRIS',
			{
				"position" : pos, #type:ignore
				"uv" : uv,
				"normal" : normal,
				"tangent" : tangent,
				"tSign" : tSign,
				"select" : faceSel if matInfo.isEditMode else tSign
			},
			indices = corners
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

def drawMeshInit(
	backfaceCull: bool,
	perpMatrix: mathutils.Matrix,
	modelMatrix: mathutils.Matrix,
	matParam: int = -1,
	envFileName: str = "",
	viewPos: mathutils.Vector = mathutils.Vector((.0, .0, .0))
) -> DrawMeshState | None:
	
	area = getArea()
	if not area:
		return None
	envTex = getEnvTex(area, envFileName)
	if not envTex:
		return None
	
	frameBuf: gpu.types.GPUFrameBuffer = gpu.state.active_framebuffer_get()  #type:ignore
	viewRes = frameBuf.viewport_get()
	meshShader.uniform_float("viewRes", (viewRes[2], viewRes[3]))
	meshShader.uniform_float("modelMatrix", modelMatrix) #type:ignore
	meshShader.uniform_float("viewProjectionMatrix", perpMatrix) #type:ignore

	viewMat = gpu.matrix.get_model_view_matrix()
	if not viewPos[0] and not viewPos[1] and not viewPos[2]:
		viewPos = viewMat.inverted().translation
	meshShader.uniform_float("viewPos", viewPos) #type:ignore
	meshShader.uniform_float("viewMat", viewMat.inverted().to_3x3()) #type:ignore

	meshShader.uniform_sampler("envTex", envTex)
	meshShader.uniform_int("matParam", matParam) #type:ignore

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
	matIdx: int, corners:
	stuc.PixtyI32Arr
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
	timestamp: float,
	mesh: stuc.StucMesh,
	idxAttribs: stuc.StucAttribIndexedArr,
	matParam: int,
	offscreen: gpu.types.GPUOffScreen
) -> None:
	with offscreen.bind():
		framebuf = gpu.state.active_framebuffer_get() #type:ignore
		framebuf.clear(color = (.0, .0, .0, .0), depth = (1.0))
		scaleMatrix = mathutils.Matrix((
			(2.0, .0, .0, .0),
			(.0, 2.0, .0, .0),
			(.0, .0, 2.0, .0028),
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
		drawStucMesh(
			key,
			timestamp,
			mesh,
			True,
			perpMatrix,
			mathutils.Matrix.Identity(4),
			stuc.MeshCacheType.MESH_CACHE_OUT,
			matParam = matParam,
			envFileName = "forest.exr",
			viewPos = viewPos,
			idxAttribs = idxAttribs,
		)

def drawStucPreview(
	name: str,
	timestamp: float,
	mesh: stuc.StucMesh,
	idxAttribs: stuc.StucAttribIndexedArr
) -> None:
	prevSinglePass(name, timestamp, mesh, idxAttribs, 0, offscreenAlbedo)
	prevSinglePass(name, timestamp, mesh, idxAttribs, 1, offscreenNormal)
	prevSinglePass(name, timestamp, mesh, idxAttribs, 2, offscreenHrm)

def getMatForPrev(
	map: props.StucMap,
	mapHandle: ctypes.c_void_p
) -> list[gpu.types.GPUTexture] | None:
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
	drawStucPreview(map.name, float(map.timestamp), result[0], result[1])
	return [
		offscreenAlbedo.texture_color,
		offscreenNormal.texture_color,
		offscreenHrm.texture_color,
		offscreenHrm.texture_color
	]

def drawStucMesh(
	key: str | None,
	timestamp: float | None,
	mesh: stuc.StucMesh,
	backfaceCull: bool,
	perpMatrix: mathutils.Matrix,
	modelMatrix: mathutils.Matrix,
	cacheType: stuc.MeshCacheType,
	mapArr: stuc.StucMapArr | None = None,
	matParam: int = -1,
	envFileName: str = "",
	viewPos: mathutils.Vector = mathutils.Vector((.0, .0, .0)),
	mats: list[bpy.types.Material | None] | None = None,
	idxAttribs: stuc.StucAttribIndexedArr | None = None,
) -> None:
	area = getArea()
	if not area:
		return
	shadingType = area.spaces.active.shading.type #type:ignore
	isCycles = bpy.context.scene.render.engine == 'CYCLES'
	if shadingType != 'MATERIAL' and (shadingType != 'RENDERED' or isCycles):
		return
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	uv = numpyFromStucAttrib(mesh, stuc.StucAttribUse.UV, 2)
	normal = numpyFromStucAttrib(mesh, stuc.StucAttribUse.NORMAL, 3)
	tangent = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TANGENT, 3)
	tSign = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TSIGN, 1)
	faceSel = None
	editMode = cacheType == stuc.MeshCacheType.MESH_CACHE_IN_EDIT
	if editMode:
		faceSel = numpyFromStucAttrib(mesh, stuc.StucAttribUse.MISC, 1)

	if not mats:
		if not idxAttribs:
			raise Exception("'idxAttribs' must be passed if 'mats' is None")
		mats = []
		attrib = attribUtils.getAttribFromUse(mesh.faceAttribs, stuc.StucAttribUse.IDX.value)
		attribName = attribUtils.pyStrFromC(attrib.core.name) #type:ignore
		attrib = attribUtils.getIdxAttrib(idxAttribs, attribName.encode('utf-8'))
		StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
		matsByteStr = ctypes.cast(attrib.core.pData, ctypes.POINTER(StucString))
		i = 0
		while i < attrib.count:
			matName = ctypes.cast(matsByteStr[i], ctypes.c_char_p).value.decode('utf-8') #type:ignore
			mat = bpy.data.materials.get(matName, None)
			if not mat:
				mat = bpy.data.materials.new(name = matName)
				mat.use_fake_user = True
			mats.append(mat)
			i += 1

	corners = stuc.PixtyI32Arr()
	for i, mat in enumerate(mats):
		texOverride = None
		error = ShaderErr.NONE
		if cacheType != stuc.MeshCacheType.MESH_CACHE_OUT:
			stucMat = None
			if mat:
				stucMat = bpy.context.scene.stucMats.get(mat.name, None) #type:ignore
				if stucMat and stucMat.mat and len(stucMat.map):
					map = bpy.context.scene.stucMaps.get(stucMat.map, None) #type:ignore
					if map:
						mapName = map.name.encode('utf-8')
						stucLib.stucBlenderMapHandleGet.restype = ctypes.c_void_p
						mapHandle = None if not map else stucLib.stucBlenderMapHandleGet(mapName)
			if not stucMat:
				continue
			if not stucMat.mat:
				error = ShaderErr.NO_MAT
			elif not len(stucMat.map):
				error = ShaderErr.NO_MAP
			elif not map or not mapHandle:
				error = ShaderErr.MAP_NOT_LOADED
			else:
				texOverride = getMatForPrev(map, ctypes.cast(mapHandle, ctypes.c_void_p))

		drawState = drawMeshInit(
			backfaceCull,
			perpMatrix,
			modelMatrix, 
			matParam = matParam,
			envFileName = envFileName,
			viewPos = viewPos
		)
		if not drawState:
			continue
		cacheEntry = None
		if key:
			if not timestamp:
				raise Exception("timestamp is required if key is passed")
			cacheEntry = batchCache.get(
				f"{key}_{mat.name if mat else 'None'}",
				timestamp,
				mesh.vertCount
			)
		drawMeshForMat(
			cacheEntry,
			pos, uv, normal, tangent, tSign, faceSel,
			getStucCorners(mesh, i, corners) if not cacheEntry or not cacheEntry.data else None,
			mat,
			cacheType,
			texOverride = texOverride,
			error = error
		)
		drawMeshEnd(drawState)
	stucLib.stucBlenderCallFree(corners.pArr)

def drawStucMeshInViewport(
	key: str,
	timestamp: float,
	mesh: stuc.StucMesh,
	modelMatrix: mathutils.Matrix,
	cacheType: stuc.MeshCacheType,
	mapArr: stuc.StucMapArr | None = None,
	mats: list[bpy.types.Material | None] | None = None,
	idxAttribs: stuc.StucAttribIndexedArr | None = None
) -> None:
	perpMatrix = bpy.context.region_data.perspective_matrix
	drawStucMesh(
		key,
		timestamp,
		mesh,
		mapArr == None,
		perpMatrix,
		modelMatrix,
		cacheType,
		mapArr = mapArr,
		mats = mats,
		idxAttribs = idxAttribs
	)

editShader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')

def drawEditOverlay(
	mesh: stuc.StucMesh,
	obj: bpy.types.Object
) -> None:
	area = getArea()
	if not area:
		return
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	edgeSel = numpyFromStucAttrib(mesh, stuc.StucAttribUse.MASK, 1, stuc.StucDomain.EDGE)
	edges = numpyFromStucAttrib(
		mesh,
		stuc.StucAttribUse.EDGE_CORNERS,
		2,
		stuc.StucDomain.EDGE,
		ctypes.c_int32
	)
	if type(pos) == None or type(edgeSel) == None or type(edges) == None:
		raise Exception("unable to get mesh attribs")

	color = (ctypes.c_float * 4 * mesh.vertCount)()
	err = stucLib.stucBlenderEditOverlayCol(
		mesh.edgeCount,
		numpy.ctypeslib.as_ctypes(edges), #type:ignore
		numpy.ctypeslib.as_ctypes(edgeSel), #type:ignore
		mesh.vertCount,
		color
	)
	if err != 1:
		raise Exception("error while making colors for edit overlay")
	colorNumpy = numpy.ctypeslib.as_array(color, shape = (mesh.vertCount, 4))
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