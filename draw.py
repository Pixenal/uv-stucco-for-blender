import ctypes
import numpy
import pdb
import os
import re
import io

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


vertOut = gpu.types.GPUStageInterfaceInfo("comp_interface") #type:ignore
vertOut.smooth('VEC3', "v_pos")
vertOut.flat('FLOAT', "i_select")
info = gpu.types.GPUShaderCreateInfo()
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'FLOAT', "select")
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('MAT4', "modelMatrix")
info.push_constant('VEC3', "viewPos")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")
info.vertex_source("\
	void main() {\
		v_pos = (modelMatrix * vec4(position, 1.0f)).xyz;\
		i_select = select;\
		\
		vec3 v = normalize(viewPos - v_pos);\
		v_pos -= v * .001f;\
		\
		gl_Position = viewProjectionMatrix * vec4(v_pos, 1.0f);\
	}\
")
info.fragment_source("\
	void main() {\
		if (i_select != 1) {\
			discard;\
		}\
		ivec2 dither = (ivec2(gl_FragCoord.xy) + ivec2(0, 1)) % ivec2(2.0, 2.0);\
		if (dither.x == dither.y) {\
			discard;\
		}\
		vec3 col = vec3(227.0f, 62.0f, 191.0f) / vec3(255.0f);\
		FragColor = vec4(col, 1.0f);\
	}\
")
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
vertOut.flat('VEC3', "v_viewPos")
vertOut.flat('INT', "i_matParam")
vertOut.flat('VEC2', "v_viewRes")

info = gpu.types.GPUShaderCreateInfo()
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('MAT4', "modelMatrix")
info.push_constant('VEC3', "viewPos")
info.push_constant('INT', "matParam")
info.push_constant('VEC2', "viewRes")
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
		float noCache;\
		vec2 padding;\
	};\
")
info.uniform_buf(0, "MatInfo", "matInfo")
info.sampler(0, 'FLOAT_2D', "envTex")
info.sampler(1, 'FLOAT_2D', "albedoTex")
info.sampler(2, 'FLOAT_2D', "normalTex")
info.sampler(3, 'FLOAT_2D', "metalTex")
info.sampler(4, 'FLOAT_2D', "roughTex")
#info.sampler(5, 'FLOAT_3D', "tmLut")
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'VEC2', "uv")
info.vertex_in(2, 'VEC3', "normal")
info.vertex_in(3, 'VEC3', "tangent")
info.vertex_in(4, 'FLOAT', "tSign")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")

vertSrc = open(f"{parentDir}/shaders/stuc_vert.glsl")
info.vertex_source(vertSrc.read())
vertSrc.close()

fragSrc = open(f"{parentDir}/shaders/stuc_frag.glsl")
info.fragment_source(fragSrc.read())
fragSrc.close()
meshShader = gpu.shader.create_from_info(info)
del vertOut
del info

'''
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
'''

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
		("noCache", ctypes.c_float),
		("padding", ctypes.c_float * 2)
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

def drawMeshForMat(
	pos, uv, normal, tangent, tSign,
	corners: numpy.ndarray,
	matName: str,
	isEditMode: bool = False,
	texOverride: list[gpu.types.GPUTexture] | None = None,
	noCache: bool = False
) -> None:
	matInfo = MatInfo()
	matInfo.isEditMode = float(isEditMode)
	matInfo.noCache = float(noCache)
	texArr = None
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
	else:
		mat = bpy.data.materials.get(matName, None)
		if not mat:
			mat = bpy.data.materials.new(name = matName)
			mat.use_fake_user = True
		if mat.node_tree:
			texArr = getMatParams(mat.node_tree, matInfo)
		if not texArr:
			missingTex = getMissingTex()
			texArr = [missingTex, missingTex, missingTex, missingTex]
			setArrFromArr(matInfo.albedoUniform, mat.diffuse_color, 3)
			matInfo.metalUniform = mat.metallic
			matInfo.roughUniform = mat.roughness
	meshShader.uniform_sampler("albedoTex", texArr[0])
	meshShader.uniform_sampler("normalTex", texArr[1])
	meshShader.uniform_sampler("metalTex", texArr[2])
	meshShader.uniform_sampler("roughTex", texArr[3])
	matInfoUbo = gpu.types.GPUUniformBuf(
		gpu.types.Buffer('UBYTE', ctypes.sizeof(MatInfo), matInfo) #type:ignore
	)
	meshShader.uniform_block("matInfo", matInfoUbo)

	batch = gpu_extras.batch.batch_for_shader(
		meshShader,
		'TRIS',
		{
			"position" : pos, #type:ignore
			"uv" : uv,
			"normal" : normal,
			"tangent" : tangent,
			"tSign" : tSign,
		},
		indices = corners
	)
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
	mesh: stuc.StucMesh,
	backfaceCull: bool,
	idxAttribs: stuc.StucAttribIndexedArr,
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
	if not viewPos[0] and not viewPos[1] and not viewPos[2]:
		viewPos = gpu.matrix.get_model_view_matrix().inverted().translation
	meshShader.uniform_float("viewPos", viewPos) #type:ignore
	meshShader.uniform_sampler("envTex", envTex)
	meshShader.uniform_int("matParam", matParam) #type:ignore
	#shader.uniform_sampler("tmLut", tmLut)

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
	idxAttribs: stuc.StucAttribIndexedArr,
	modelMatrix: mathutils.Matrix,
	mapArr: stuc.StucMapArr | None = None, #<- enables preview
	editTex: gpu.types.GPUTexture | None = None,
	noCache: bool = False
) -> None:
	perpMatrix = bpy.context.region_data.perspective_matrix
	drawStucMesh(
		mesh,
		mapArr == None,
		idxAttribs,
		perpMatrix,
		modelMatrix,
		mapArr = mapArr,
		noCache = noCache
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

def drawStucMesh(
	mesh: stuc.StucMesh,
	backfaceCull: bool,
	idxAttribs: stuc.StucAttribIndexedArr,
	modelMatrix: mathutils.Matrix,
	perpMatrix: mathutils.Matrix,
	mapArr: stuc.StucMapArr | None = None, #<- enables preview
	matParam: int = -1,
	envFileName: str = "",
	viewPos: mathutils.Vector = mathutils.Vector((.0, .0, .0)),
	noCache: bool = False
) -> None:
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	uv = numpyFromStucAttrib(mesh, stuc.StucAttribUse.UV, 2)
	normal = numpyFromStucAttrib(mesh, stuc.StucAttribUse.NORMAL, 3)
	tangent = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TANGENT, 3)
	tSign = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TSIGN, 1)

	attrib = attribUtils.getAttribFromUse(mesh.faceAttribs, stuc.StucAttribUse.IDX.value)
	attribName = attribUtils.pyStrFromC(attrib.core.name) #type:ignore
	outMats = attribUtils.getIdxAttrib(idxAttribs, attribName.encode('utf-8'))
	if mapArr and outMats.count != mapArr.count:
		raise Exception()
	StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
	outMatsCast = ctypes.cast(outMats.core.pData, ctypes.POINTER(StucString))

	corners = stuc.PixtyI32Arr()
	i = 0
	while i < outMats.count:
		cornerNumpy = getStucCorners(mesh, i, corners)
		if mapArr:
			matName = ""
			map = mapArr.pArr[i].map.ptr
			mapName = ctypes.c_char_p()
			err = stucLib.stucBlenderMapNameGet(
				ctypes.cast(map, ctypes.c_void_p),
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
		else:
			matName = attribUtils.pyStrFromC(outMatsCast[i])
			texOverride = None

		drawState = drawMeshInit(
			mesh,
			backfaceCull,
			idxAttribs,
			perpMatrix,
			modelMatrix, 
			matParam = matParam,
			envFileName = envFileName,
			viewPos = viewPos
		)
		if not drawState:
			continue
		drawMeshForMat(
			pos, uv, normal, tangent, tSign,
			cornerNumpy,
			matName,
			texOverride = texOverride,
			noCache = noCache
		)
		drawMeshEnd(drawState)
		i += 1
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
			"select" : faceSel
   		},
		indices = stucCorner
	)
	with gpu.matrix.push_pop():
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
		compBatch.draw(compShader)
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
			idxAttribs,
			perpMatrix,
			mathutils.Matrix.Identity(4),
			matParam = matParam,
			envFileName = "forest.exr",
			viewPos = viewPos
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