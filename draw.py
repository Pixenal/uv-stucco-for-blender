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

from . import stuc
from . import attrib_utils as attribUtils
from . import c_lib
stucLib = c_lib.stucLib

offscreen = gpu.types.GPUOffScreen(64, 32) #type:ignore

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
vertOut.smooth('VEC2', "v_uv")

info = gpu.types.GPUShaderCreateInfo()
info.sampler(0, 'FLOAT_2D', "envTex")
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'VEC2', "uv")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")
info.vertex_source("\
	void main() {\
		v_pos = position;\
		v_uv = uv;\
		gl_Position = vec4(position, 1.0f);\
	}\
")
compSrc = open(f"{parentDir}/shaders/stuc_env_conv_comp.glsl")
info.fragment_source(compSrc.read())
compSrc.close()
compShader = gpu.shader.create_from_info(info)
del vertOut
del info

def getEnvTexConv(
	envTex: gpu.types.GPUTexture
) -> None:
	with offscreen.bind():
		framebuf = gpu.state.active_framebuffer_get() #type:ignore
		framebuf.clear(color = (.0, .0, .0, .0))
		with gpu.matrix.push_pop():
			gpu.matrix.load_matrix(mathutils.Matrix.Identity(4))
			gpu.matrix.load_projection_matrix(mathutils.Matrix.Identity(4))

			batch = gpu_extras.batch.batch_for_shader(
				compShader,
				'TRI_FAN',
				{
					"position" : [(-1.0, -1.0, .0), (1.0, -1.0, .0), (1.0, 1.0, .0), (-1.0, 1.0, .0)], #type:ignore
					"uv" : [(.0, .0), (1.0, .0), (1.0, 1.0), (.0, 1.0)],
				}
			)
			compShader.uniform_sampler("envTex", envTex)
			batch.draw(compShader)
			

vertOut = gpu.types.GPUStageInterfaceInfo("my_interface") #type:ignore
vertOut.smooth('VEC3', "v_pos")
vertOut.smooth('VEC2', "v_uv")
vertOut.smooth('MAT3', "m_tbn")
vertOut.smooth('VEC3', "v_viewPos")

info = gpu.types.GPUShaderCreateInfo()
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('MAT4', "modelMatrix")
info.push_constant('VEC3', "viewPos")
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
")
info.uniform_buf(0, "MatInfo", "matInfo")
info.sampler(0, 'FLOAT_2D', "envTex")
info.sampler(1, 'FLOAT_2D', "envTexConv")
info.sampler(2, 'FLOAT_2D', "albedoTex")
info.sampler(3, 'FLOAT_2D', "normalTex")
info.sampler(4, 'FLOAT_2D', "metalTex")
info.sampler(5, 'FLOAT_2D', "roughTex")
#info.sampler(6, 'FLOAT_3D', "tmLut")
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'VEC2', "uv")
info.vertex_in(2, 'VEC3', "normal")
info.vertex_in(3, 'VEC3', "tangent")
info.vertex_in(4, 'FLOAT', "tSign")
info.vertex_out(vertOut)
info.fragment_out(0, 'VEC4', "FragColor")

vertSrc = open(f"{parentDir}/shaders/stuc_vert.glsl")
fragSrc = open(f"{parentDir}/shaders/stuc_frag.glsl")
info.vertex_source(vertSrc.read())
info.fragment_source(fragSrc.read())
vertSrc.close()
fragSrc.close()
shader = gpu.shader.create_from_info(info)
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
		("roughChannel", ctypes.c_float)
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
	mesh: stuc.StucMesh,
	pos, uv, normal, tangent, tSign,
	corners: stuc.PixtyI32Arr,
	matIdx: int,
	matName: str
) -> None:
	mat = bpy.data.materials.get(matName, None)
	if not mat:
		mat = bpy.data.materials.new(name = matName)
		mat.use_fake_user = True
	
	corners.count = 0
	err = stucLib.stucBlenderCornersForMat(
		ctypes.pointer(mesh),
		matIdx,
		ctypes.pointer(corners)
	)
	if err != 1:
		raise Exception("failed to get corners for mat idx")
	cornerNumpy = numpy.ctypeslib.as_array( 
		ctypes.cast(corners.pArr, ctypes.POINTER(ctypes.c_int32)),
		shape = (int(corners.count / 3), 3) #assumes mesh has been triangulated #type:ignore
	)

	matInfo = MatInfo()
	texArr = None
	if mat.node_tree:
		texArr = getMatParams(mat.node_tree, matInfo)
	if not texArr:
		texArr = []
		texArr[2] = texArr[1] = texArr[0] = getMissingTex()
		setArrFromArr(matInfo.albedoUniform, mat.diffuse_color, 3)
		matInfo.metalUniform = mat.metallic
		matInfo.roughUniform = mat.roughness
	shader.uniform_sampler("albedoTex", texArr[0])
	shader.uniform_sampler("normalTex", texArr[1])
	shader.uniform_sampler("metalTex", texArr[2])
	shader.uniform_sampler("roughTex", texArr[3])
	matInfoUbo = gpu.types.GPUUniformBuf(
		gpu.types.Buffer('UBYTE', ctypes.sizeof(MatInfo), matInfo) #type:ignore
	)
	shader.uniform_block("matInfo", matInfoUbo)

	batch = gpu_extras.batch.batch_for_shader(
		shader,
		'TRIS',
		{
			"position" : pos, #type:ignore
			"uv" : uv,
			"normal" : normal,
			"tangent" : tangent,
			"tSign" : tSign,
		},
		indices = cornerNumpy
	)
	batch.draw(shader)

def drawStucMesh(
	mesh: stuc.StucMesh,
	idxAttribs: stuc.StucAttribIndexedArr,
	modelMatrix: mathutils.Matrix
) -> None:
	area = getArea()
	if not area:
		return
	
	envFile = area.spaces.active.shading.studio_light #type:ignore
	if envFile == "Default":
		envFile = "studio.exr"
	envTexName = f"STUC_ENV_TEX_{envFile}"
	envTex = bpy.data.images.get(envTexName, None)
	if not envTex:
		studioLights = bpy.context.preferences.studio_lights
		studioLight = studioLights.get(envFile, None)
		if not studioLight:
			return
		envTex = bpy.data.images.load(studioLight.path)
		envTex.name = envTexName
		envTex.alpha_mode = 'NONE'
	
	envTexGl = gpu.texture.from_image(envTex)
	getEnvTexConv(envTexGl)
	
	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	uv = numpyFromStucAttrib(mesh, stuc.StucAttribUse.UV, 2)
	normal = numpyFromStucAttrib(mesh, stuc.StucAttribUse.NORMAL, 3)
	tangent = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TANGENT, 3)
	tSign = numpyFromStucAttrib(mesh, stuc.StucAttribUse.TSIGN, 1)
	
	shader.bind()
	perpMat = bpy.context.region_data.perspective_matrix
	shader.uniform_float("viewProjectionMatrix", perpMat) #type:ignore
	shader.uniform_float("modelMatrix", modelMatrix) #type:ignore
	viewPos = area.spaces.active.region_3d.view_matrix.inverted().translation #type:ignore
	shader.uniform_float("viewPos", viewPos)
	shader.uniform_sampler("envTex", envTexGl)
	shader.uniform_sampler("envTexConv", offscreen.texture_color)

	#shader.uniform_sampler("tmLut", tmLut)

	gpu.state.depth_test_set('LESS_EQUAL')
	gpu.state.depth_mask_set(True)

	attrib = attribUtils.getAttribFromUse(mesh.faceAttribs, stuc.StucAttribUse.IDX.value)
	attribName = attribUtils.pyStrFromC(attrib.core.name) #type:ignore
	outMats = attribUtils.getIdxAttrib(idxAttribs, attribName.encode('utf-8'))
	StucString = ctypes.c_byte * stuc.STUC_ATTRIB_STRING_MAX_LEN
	outMatsCast = ctypes.cast(outMats.core.pData, ctypes.POINTER(StucString))

	corners = stuc.PixtyI32Arr()
	i = 0
	while i < outMats.count:
		matName = attribUtils.pyStrFromC(outMatsCast[i])
		print(f"drawing for mat {matName}")
		drawMeshForMat(mesh, pos, uv, normal, tangent, tSign, corners, i, matName)
		i += 1
	stucLib.stucBlenderCallFree(corners.pArr)
	gpu.state.depth_mask_set(False)

editShader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

def drawEditOverlay(mesh: bpy.types.Mesh) -> None:
	area = getArea()
	if not area:
		return
	edgeCount = len(mesh.edges)
	edges = ctypes.c_void_p(mesh.edges[0].as_pointer())
	verts = ctypes.c_void_p(mesh.vertices[0].as_pointer())
	vertsNumpy = numpy.ctypeslib.as_array(
		ctypes.cast(verts, ctypes.POINTER(ctypes.c_float)),
		shape = (len(mesh.vertices), 3)
	)
	edges = numpy.ctypeslib.as_array(
		ctypes.cast(edges, ctypes.POINTER(ctypes.c_int32)),
		shape = (edgeCount, 2)
	)
	editBatch = gpu_extras.batch.batch_for_shader(
		editShader,
		'LINES',
		{"pos": vertsNumpy}, #type:ignore
		indices = edges
	)
	editShader.bind()
	editShader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
	editShader.uniform_float("lineWidth", 1.0)
	theme = bpy.context.preferences.themes[0]
	colWire = theme.view_3d.wire_edit
	editShader.uniform_float("color", (colWire.r, colWire.g, colWire.b))
	editBatch.draw(editShader)