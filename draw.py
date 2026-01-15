import ctypes
import numpy
import pdb
import os
import re
import io
from enum import Enum
from datetime import datetime

import bpy
import gpu
import gpu_extras
import mathutils
import bmesh

from . import stuc
from . import attrib_utils as attribUtils
from . import mesh_utils as meshUtils
from . import c_lib
stucLib = c_lib.stucLib

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
	size: int
):
	attrib = attribUtils.getAttribFromUse(mesh.vertAttribs, use.value)
	if not attrib:
		return None
	return numpy.ctypeslib.as_array(
    	ctypes.cast(attrib.core.pData, ctypes.POINTER(ctypes.c_float)),
    	shape = (mesh.vertCount, size)
	)

def getArea() -> bpy.types.Area | None:
	for area in bpy.context.window.screen.areas:
		if area.type == 'VIEW_3D':
			return area
	return None

parentDir = os.path.dirname(__file__)

def insertIncludes(text: str) -> str:
	newText = text
	iter = re.finditer("#include \".+\"", newText)
	for i in iter:
		path = re.search("\"(.*?)\"", i.group())
		if not path:
			continue
		file = open(f"{parentDir}/shaders/{path.group(1)}")
		newText = newText[:i.span()[0]] + file.read() + newText[i.span()[1]:]
		file.close()
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

fluidTextures: list[gpu.types.GPUTexture] | None = None

def loadFluidTextures() -> list[gpu.types.GPUTexture] | None:
	flowTex = loadTex(f"StucNoise_Curl_A_FLOW", 'Non-Color', True)
	macroNoiseTex = loadTex(f"StucNoise_Macro_A_MASK", 'Non-Color', True)
	microNoiseTex = loadTex(f"StucNoise_Micro_A_MASK", 'Non-Color', True)
	sparkleTex = loadTex(f"StucNoise_Sparkle_A_MASK", 'Non-Color', True)
	crystalTex = loadTex(f"StucNoise_Crystal_A_N", 'Non-Color', True)
	if flowTex and macroNoiseTex and microNoiseTex and sparkleTex and crystalTex:
		return [
			gpu.texture.from_image(flowTex),
			gpu.texture.from_image(macroNoiseTex),
			gpu.texture.from_image(microNoiseTex),
			gpu.texture.from_image(sparkleTex),
			gpu.texture.from_image(crystalTex)
		]
	else:
		raise Exception("failed to find textures for stuc mesh shader")
		'''
		missingTex = getMissingTex()
		shader.uniform_sampler("flowTex", missingTex)
		shader.uniform_sampler("macroNoiseTex", missingTex)
		shader.uniform_sampler("microNoiseTex", missingTex)
		shader.uniform_sampler("sparkleTex", missingTex)
		shader.uniform_sampler("crystalTex", missingTex)
		'''
		return None

vertOut = gpu.types.GPUStageInterfaceInfo("comp_interface") #type:ignore
vertOut.smooth('VEC3', "v_pos")
vertOut.smooth('VEC3', "v_normal")
vertOut.flat('FLOAT', "i_select")
vertOut.flat('FLOAT', "f_time")
vertOut.flat('VEC2', "v_viewRes")
info = gpu.types.GPUShaderCreateInfo()
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'VEC3', "normal")
info.vertex_in(2, 'FLOAT', "select")
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('MAT4', "modelMatrix")
info.push_constant('VEC3', "viewPos")
info.push_constant('FLOAT', "time")
info.push_constant('VEC2', "viewRes")
info.sampler(0, 'FLOAT_2D', "flowTex")
info.sampler(1, 'FLOAT_2D', "macroNoiseTex")
info.sampler(2, 'FLOAT_2D', "microNoiseTex")
info.sampler(3, 'FLOAT_2D', "sparkleTex")
info.sampler(4, 'FLOAT_2D', "crystalTex")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")
info.vertex_source("\
	void main() {\
		v_pos = (modelMatrix * vec4(position, 1.0f)).xyz;\
		mat3 normalMatrix = transpose(inverse(mat3(modelMatrix)));\
		v_normal = normalMatrix * normal;\
		\
		i_select = select;\
		f_time = time;\
		v_viewRes = viewRes;\
		\
		vec3 v = normalize(viewPos - v_pos);\
		v_pos -= v * .001f;\
		\
		gl_Position = viewProjectionMatrix * vec4(v_pos, 1.0f);\
	}\
")
fragSrc = open(f"{parentDir}/shaders/stuc_edit_frag.glsl")
info.fragment_source(insertIncludes(fragSrc.read()))
fragSrc.close()
compShader = gpu.shader.create_from_info(info)
del vertOut
del info

vertOut = gpu.types.GPUStageInterfaceInfo("noCache_interface") #type:ignore
vertOut.smooth('VEC3', "v_pos")
info = gpu.types.GPUShaderCreateInfo()
info.vertex_in(0, 'VEC3', "position")
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('MAT4', "modelMatrix")
info.push_constant('VEC3', "viewPos")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")
info.vertex_source("\
	void main() {\
		v_pos = (modelMatrix * vec4(position, 1.0f)).xyz;\
		\
		vec3 v = normalize(viewPos - v_pos);\
		v_pos -= v * .001f;\
		\
		gl_Position = viewProjectionMatrix * vec4(v_pos, 1.0f);\
	}\
")
info.fragment_source("\
	void main() {\
		ivec2 dither = (ivec2(gl_FragCoord.xy) / 4 + ivec2(0, 1)) % ivec2(2.0, 2.0);\
		if (dither.x == dither.y) {\
			discard;\
		}\
		vec3 col = vec3(18.0f, 119.0f, 106.0f) / vec3(255.0f);\
		FragColor = vec4(col, 1.0f);\
	}\
")
noCacheShader = gpu.shader.create_from_info(info)
del vertOut
del info


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
		float padding;\
	};\
")
info.uniform_buf(0, "MatInfo", "matInfo")
info.sampler(0, 'FLOAT_2D', "envTex")
info.sampler(1, 'FLOAT_2D', "albedoTex")
info.sampler(2, 'FLOAT_2D', "normalTex")
info.sampler(3, 'FLOAT_2D', "metalTex")
info.sampler(4, 'FLOAT_2D', "roughTex")
info.sampler(5, 'FLOAT_2D', "errTex")
#info.sampler(6, 'FLOAT_3D', "tmLut")
info.sampler(6, 'FLOAT_2D', "flowTex")
info.sampler(7, 'FLOAT_2D', "macroNoiseTex")
info.sampler(8, 'FLOAT_2D', "microNoiseTex")
info.sampler(9, 'FLOAT_2D', "sparkleTex")
info.sampler(10, 'FLOAT_2D', "crystalTex")
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

def initShaders() -> None:
	global fluidTextures
	fluidTextures = loadFluidTextures()

def readCubeLutFile(file: io.TextIOWrapper) -> numpy.ndarray | None:
	while True:
		line = file.readline()
		if "LUT_3D_SIZE" in line:
			break
	sizeStr = re.findall("(?<= )[0-9]*$", line)#find digits after a space
	if not len(sizeStr):
		return None
	size = int(sizeStr[0])
	if size < 2 or size > 256:
		return None
	sizeLin = size * size * size
	data = numpy.empty(shape = (sizeLin, 4), dtype = numpy.float32)
	i = 0
	while i < sizeLin:
		line = file.readline()
		if not len(line):
			break
		colStr = re.findall("[0-9,.]+", line)
		if len(colStr) != 3:
			return None
		col = [float(i) for i in colStr]
		data[i][0] = col[0]
		data[i][1] = col[1]
		data[i][2] = col[2]
		data[i][3] = 1.0
		i += 1
	if i == sizeLin:
		return data
	else:
		return None

def loadCubeLut(filepath: str) -> numpy.ndarray | None:
	file = open(filepath, encoding = 'utf-8')
	data = readCubeLutFile(file)
	file.close()
	return data

tmLutData = loadCubeLut(
	"E:/blender/4.3.2/4.3/datafiles/colormanagement/luts/AgX_Base_sRGB.cube"
)
if tmLutData is None:
	raise Exception()
tmLutBuf = gpu.types.Buffer('FLOAT', tmLutData.size, tmLutData) #type:ignore
tmLut = gpu.types.GPUTexture(
	size = (57, 57, 57), #type:ignore
	format = 'RGBA32F',	#type:ignore
	data = tmLutBuf	#type:ignore
)


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
) -> list[bpy.types.Image | int] | None:
	if not nodeBsdf.inputs:
		raise Exception()
	inSocket = nodeBsdf.inputs.get(socket, None)
	if not inSocket:
		raise Exception()
	if not inSocket.links or not inSocket.links[0].from_node:
		return None
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
	return [node.image, channelIdx] #type:ignore

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
		("padding", ctypes.c_float)
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

def arrPow(arr, exp: float, size: int) -> None:
	i = 0
	while i < size:
		arr[i] = pow(arr[i], exp)
		i += 1

def getErrTex(error: ShaderErr) -> bpy.types.Image | None:
	texName = None
	match error:
		case ShaderErr.ERROR:
			texName = "Error"
		case ShaderErr.NO_MAP:
			texName = "NoMap"
		case ShaderErr.MAP_NOT_LOADED:
			texName = "MapNotLoaded"
		case ShaderErr.NO_MAT:
			texName = "NoMat"
		case ShaderErr.INVALID_SHADER:
			texName = "InvalidShader"
	return loadTex(f"StucErr_{texName}_MASK", 'Non-Color')

def drawMeshForMat(
	pos, uv, normal, tangent, tSign, faceSel,
	corners: numpy.ndarray,
	mat: bpy.types.Material | None,
	isEditMode: bool = False,
	texOverride: list[gpu.types.GPUTexture] | None = None,
	errorParam: ShaderErr = ShaderErr.NONE
) -> None:
	matInfo = MatInfo()
	matInfo.isEditMode = float(isEditMode)
	texArr = None
	error = errorParam
	map = None
	if mat:
		stucMat = bpy.context.scene.stucMats.get(mat.name, None) #type:ignore
		if stucMat and len(stucMat.map):
			map = bpy.context.scene.stucMaps.get(stucMat.map, None) #type:ignore
			mapHandle = None if not map else stucLib.stucBlenderMapHandleGet(map.name)
	else:
		stucMat = None
	if error != ShaderErr.NONE:
		pass
	if not mat:
		error = ShaderErr.NO_MAT
	elif not stucMat:
		return
	elif not len(stucMat.map):
		error = ShaderErr.NO_MAP
	elif not map or not mapHandle:
		error = ShaderErr.MAP_NOT_LOADED
	elif texOverride:
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
	else:
		newMat: bool = False
		if not mat:
			newMat = True
			mat = bpy.data.materials.new(name = matName)
			mat.use_fake_user = True
		if mat.node_tree:
			texArr = getMatParams(mat.node_tree, matInfo)
		if not texArr:
			if newMat:
				raise Exception()
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
	errTex = getErrTex(error)
	if errTex:
		meshShader.uniform_sampler("errTex", gpu.texture.from_image(errTex))
	else:
		meshShader.uniform_sampler("errTex", getMissingTex())

	delta = (datetime.now() - datetime(1970, 1, 1))
	matInfo.time = float(delta.seconds % 60) + delta.microseconds / 1000000.0

	matInfoUbo = gpu.types.GPUUniformBuf(
		gpu.types.Buffer('UBYTE', ctypes.sizeof(MatInfo), matInfo) #type:ignore
	)
	meshShader.uniform_block("matInfo", matInfoUbo)

	if not fluidTextures:
		raise Exception()
	meshShader.uniform_sampler("flowTex", fluidTextures[0])
	meshShader.uniform_sampler("macroNoiseTex", fluidTextures[1])
	meshShader.uniform_sampler("microNoiseTex", fluidTextures[2])
	meshShader.uniform_sampler("sparkleTex", fluidTextures[3])
	meshShader.uniform_sampler("crystalTex", fluidTextures[4])

	batch = gpu_extras.batch.batch_for_shader(
		meshShader,
		'TRIS',
		{
			"position" : pos, #type:ignore
			"uv" : uv,
			"normal" : normal,
			"tangent" : tangent,
			"tSign" : tSign,
			"select" : faceSel if isEditMode else tSign
		},
		indices = corners
	)
	batch.draw(meshShader)
	if errTex:
		bpy.data.images.remove(errTex, do_unlink = True)

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
	modelMatrix: mathutils.Matrix,
	perpMatrix: mathutils.Matrix,
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
	#meshShader.uniform_sampler("tmLut", tmLut)

	depthTestMode = gpu.state.depth_test_get()
	gpu.state.depth_test_set('LESS_EQUAL')
	gpu.state.depth_mask_set(True)
	gpu.state.face_culling_set('BACK' if backfaceCull else 'NONE')

	return DrawMeshState(depthTestMode)

def drawMeshEnd(state: DrawMeshState) -> None:
	gpu.state.depth_mask_set(False)
	gpu.state.depth_test_set(state.depthTestMode)	
	gpu.state.face_culling_set('NONE')

def drawStucMeshInViewport(
	mesh: stuc.StucMesh,
	modelMatrix: mathutils.Matrix,
	editMode: bool,
	mapArr: stuc.StucMapArr | None = None,
	mats: list[bpy.types.Material | None] | None = None,
	idxAttribs: stuc.StucAttribIndexedArr | None = None

) -> None:
	perpMatrix = bpy.context.region_data.perspective_matrix
	drawStucMesh(
		mesh,
		mapArr == None,
		perpMatrix,
		modelMatrix,
		editMode = editMode,
		mapArr = mapArr,
		mats = mats,
		idxAttribs = idxAttribs
	)

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

def getMatForPrev(
	map: ctypes.c_void_p,
	texOverride: list[gpu.types.GPUTexture] | None
) -> None:
	mapName = ctypes.c_char_p()
	err = stucLib.stucBlenderMapNameGet(
		map,
		ctypes.pointer(mapName)
	)
	if err != 1 or not mapName.value:
		raise Exception("unable to get stuc map name")
	result = meshUtils.getMapMesh(mapName.value.decode('utf-8'), True)
	if type(result[0]) != stuc.StucMesh or type(result[1]) != stuc.StucAttribIndexedArr:
		raise Exception()
	drawStucPreview(result[0], result[1])
	texOverride = [
		offscreenAlbedo.texture_color,
		offscreenNormal.texture_color,
		offscreenHrm.texture_color,
		offscreenHrm.texture_color
	]

def drawStucMesh(
	mesh: stuc.StucMesh,
	backfaceCull: bool,
	modelMatrix: mathutils.Matrix,
	perpMatrix: mathutils.Matrix,
	editMode: bool = False,
	mapArr: stuc.StucMapArr | None = None,
	matParam: int = -1,
	envFileName: str = "",
	viewPos: mathutils.Vector = mathutils.Vector((.0, .0, .0)),
	mats: list[bpy.types.Material | None] | None = None,
	idxAttribs: stuc.StucAttribIndexedArr | None = None,
) -> None:
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	uv = numpyFromStucAttrib(mesh, stuc.StucAttribUse.UV, 2)
	normal = numpyFromStucAttrib(mesh, stuc.StucAttribUse.NORMAL, 3)
	tangent = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TANGENT, 3)
	tSign = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TSIGN, 1)
	faceSel = None
	if editMode:
		selAttrib = ctypes.POINTER(stuc.StucAttrib)()
		err = stucLib.stucBlenderAttribGet(
			ctypes.pointer(mesh),
			b"select",
			ctypes.pointer(selAttrib),
			None, None
		)
		if err != 1:
			raise Exception("error while getting sel attrib")
		faceSel = numpy.ctypeslib.as_array(
			ctypes.cast(selAttrib.contents.core.pData, ctypes.POINTER(ctypes.c_float)),
			shape = (mesh.vertCount, 1)
		)

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
			mats.append(bpy.data.materials.get(matsByteStr[i].decode('utf-8'), None))
			i += 1

	corners = stuc.PixtyI32Arr()
	for i, mat in enumerate(mats):
		cornerNumpy = getStucCorners(mesh, i, corners)
		texOverride = None
		if editMode and mapArr:
			map = None
			j = 0
			while j < mapArr.count:
				if mapArr.pArr[j].matIdx:
					map = mapArr.pArr[j].map.ptr
					break
				j += 1
			if map:
				getMatForPrev(map, texOverride)

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
		drawMeshForMat(
			pos, uv, normal, tangent, tSign, faceSel,
			cornerNumpy,
			mat,
			texOverride = texOverride,
			isEditMode = editMode
		)
		drawMeshEnd(drawState)
	stucLib.stucBlenderCallFree(corners.pArr)

editShader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')

def drawEditOverlay(
	obj: bpy.types.Object,
	stucMesh: stuc.StucMesh
) -> None:
	area = getArea()
	if not area:
		return

	mesh = obj.data
	if type(mesh) != bpy.types.Mesh:
		raise Exception()
	
	stucPos = numpyFromStucAttrib(stucMesh, stuc.StucAttribUse.POS, 3)
	stucNormal = numpyFromStucAttrib(stucMesh, stuc.StucAttribUse.NORMAL, 3)
	stucCorner = numpy.ctypeslib.as_array(
    	ctypes.cast(stucMesh.pCorners, ctypes.POINTER(ctypes.c_int32)),
    	shape = (stucMesh.faceCount, 3)
	)
	selAttrib = ctypes.POINTER(stuc.StucAttrib)()
	err = stucLib.stucBlenderAttribGet(
		ctypes.pointer(stucMesh),
		b"select",
		ctypes.pointer(selAttrib),
		None, None
	)
	if err != 1:
		raise Exception("error while getting sel attrib")
	faceSel = numpy.ctypeslib.as_array(
		ctypes.cast(selAttrib.contents.core.pData, ctypes.POINTER(ctypes.c_float)),
		shape = (stucMesh.vertCount, 1)
	)

	edgeCount = len(mesh.edges)
	vertCount = len(mesh.vertices)
	edges = ctypes.c_void_p(mesh.edges[0].as_pointer())
	pos = ctypes.c_void_p(mesh.vertices[0].as_pointer())
	posNumpy = numpy.ctypeslib.as_array(
		ctypes.cast(pos, ctypes.POINTER(ctypes.c_float)),
		shape = (vertCount, 3)
	)
	edgesNumpy = numpy.ctypeslib.as_array(
		ctypes.cast(edges, ctypes.POINTER(ctypes.c_int32)),
		shape = (edgeCount, 2)
	)
	select = numpy.empty(edgeCount, dtype = numpy.bool)
	mesh.edges.foreach_get("select", select) #type:ignore
	color = (ctypes.c_float * 4 * vertCount)()
	err = stucLib.stucBlenderEditOverlayCol(
		edgeCount,
		edges,
		numpy.ctypeslib.as_ctypes(select),
		vertCount,
		color
	)
	if err != 1:
		raise Exception("error while making colors for edit overlay")
	colorNumpy = numpy.ctypeslib.as_array(color, shape = (vertCount, 4))

	#vertSelIsOn = bpy.context.tool_settings.mesh_select_mode[0]
	#shaderType = 'POLYLINE_SMOOTH_COLOR' if vertSelIsOn else 'POLYLINE_FLAT_COLOR'
	#editShader = gpu.shader.from_builtin(shaderType)
	editBatch = gpu_extras.batch.batch_for_shader(
		editShader,
		'LINES',
		{
			"pos" : posNumpy, #type:ignore
			"color" : colorNumpy
   		},
		indices = edgesNumpy
	)

	compBatch = gpu_extras.batch.batch_for_shader(
		compShader,
		'TRIS',
		{
			"position" : stucPos, #type:ignore
			"normal" : stucNormal,
			"select" : faceSel
   		},
		indices = stucCorner
	)

	if not fluidTextures:
		raise Exception()
	compShader.uniform_sampler("flowTex", fluidTextures[0])
	compShader.uniform_sampler("macroNoiseTex", fluidTextures[1])
	compShader.uniform_sampler("microNoiseTex", fluidTextures[2])
	compShader.uniform_sampler("sparkleTex", fluidTextures[3])
	meshShader.uniform_sampler("crystalTex", fluidTextures[4])

	with gpu.matrix.push_pop():
		delta = (datetime.now() - datetime(1970, 1, 1))
		time = float(delta.seconds % 60) + delta.microseconds / 1000000.0
		compShader.uniform_float("time", time)
		frameBuf = gpu.state.active_framebuffer_get() #type:ignore
		compShader.uniform_float("viewRes", frameBuf.viewport_get())

		perpMatrix = bpy.context.region_data.perspective_matrix
		gpu.matrix.load_projection_matrix(perpMatrix)
		compShader.uniform_float("viewProjectionMatrix", perpMatrix) #type:ignore
		compShader.uniform_float("modelMatrix", obj.matrix_world) #type:ignore
		viewPos = gpu.matrix.get_model_view_matrix().inverted().translation
		compShader.uniform_float("viewPos", viewPos) #type:ignore

		gpu.matrix.load_matrix(obj.matrix_world)
		editShader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
		editShader.uniform_float("lineWidth", 1.0)
		#col = mathutils.Vector((127.0, 127.0, 127.0)) / 225.0
		#colSelect = mathutils.Vector((227.0, 62.0, 191.0)) / 225.0
		#editShader.uniform_float("color", (col.x, col.y, col.z, 1.0))
		depthTestMode = gpu.state.depth_test_get()
		gpu.state.depth_test_set('LESS_EQUAL')
		gpu.state.depth_mask_set(True)
		#compBatch.draw(compShader)
		editBatch.draw(editShader)
		gpu.state.depth_mask_set(False)
		gpu.state.depth_test_set(depthTestMode)

def drawNoCache(
	mesh: stuc.StucMesh,
	modelMatrix: mathutils.Matrix
) -> None:
	area = getArea()
	if not area:
		return
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	corner = numpy.ctypeslib.as_array(
    	ctypes.cast(mesh.pCorners, ctypes.POINTER(ctypes.c_int32)),
    	shape = (mesh.faceCount, 3)
	)
	batch = gpu_extras.batch.batch_for_shader(
		noCacheShader,
		'TRIS',
		{
			"position" : pos, #type:ignore
   		},
		indices = corner
	)
	perpMatrix = bpy.context.region_data.perspective_matrix
	noCacheShader.uniform_float("viewProjectionMatrix", perpMatrix) #type:ignore
	noCacheShader.uniform_float("modelMatrix", modelMatrix) #type:ignore
	viewPos = gpu.matrix.get_model_view_matrix().inverted().translation
	noCacheShader.uniform_float("viewPos", viewPos) #type:ignore

	depthTestMode = gpu.state.depth_test_get()
	gpu.state.depth_test_set('LESS_EQUAL')
	gpu.state.depth_mask_set(True)
	batch.draw(noCacheShader)
	gpu.state.depth_mask_set(False)
	gpu.state.depth_test_set(depthTestMode)

def imageFromFrame(name: str, offscreen: gpu.types.GPUOffScreen) -> None:
	prevImage = bpy.data.images.get(name, None)
	if not prevImage:
		prevImage = bpy.data.images.new(name, offscreen.width, offscreen.height)
	prevImage.scale(offscreen.width, offscreen.height)
	data = offscreen.texture_color.read()
	bufSize = (data.dimensions[0] * data.dimensions[1] * data.dimensions[2])
	buf = gpu.types.Buffer('FLOAT', bufSize, data) #type:ignore
	prevImage.pixels.foreach_set(buf) #type:ignore

def prevSinglePass(
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
			mesh,
			True,
			perpMatrix,
			mathutils.Matrix.Identity(4),
			matParam = matParam,
			envFileName = "forest.exr",
			viewPos = viewPos,
			idxAttribs = idxAttribs,
		)

def drawStucPreview(
	#name: str,
	mesh: stuc.StucMesh,
	idxAttribs: stuc.StucAttribIndexedArr
) -> None:
	#namePrefix = "STUC_PREV"

	prevSinglePass(mesh, idxAttribs, 0, offscreenAlbedo)
	#imageFromFrame(f"{namePrefix}_CURRENT_ALBEDO", offscreenAlbedo)
	prevSinglePass(mesh, idxAttribs, 1, offscreenNormal)
	#imageFromFrame(f"{namePrefix}_{name}_NORMAL", offscreen)
	prevSinglePass(mesh, idxAttribs, 2, offscreenHrm)
	#imageFromFrame(f"{namePrefix}_{name}_HRM", offscreen)


#TODO return lists like this should probably be dicts