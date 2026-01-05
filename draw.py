import ctypes
import numpy
import pdb
import os

import bpy
import gpu
import gpu_extras
from gpu_extras.presets import draw_circle_2d
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
vertOut.smooth('VEC3', "v_normal")
vertOut.smooth('VEC3', "v_viewPos")

info = gpu.types.GPUShaderCreateInfo()
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('VEC3', "viewPos")
info.typedef_source("\
	struct MatInfo { \
		vec3 albedoUniform;\
		float metalUniform;\
		float roughUniform;\
		float albedoUseTex;\
		float metalUseTex;\
		float roughUseTex;\
	};\
")
info.uniform_buf(0, "MatInfo", "matInfo")
info.sampler(0, 'FLOAT_2D', "envTex")
info.sampler(1, 'FLOAT_2D', "envTexConv")
info.sampler(2, 'UINT_2D', "albedoTex")
info.sampler(3, 'UINT_2D', "metalTex")
info.sampler(4, 'UINT_2D', "roughTex")
info.vertex_in(0, 'VEC3', "position")
info.vertex_in(1, 'VEC2', "uv")
info.vertex_in(2, 'VEC3', "normal")
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
				
def getMatTex(
	nodeTree: bpy.types.NodeTree,
	nodeBsdf: bpy.types.Node,
	socket: str
) -> bpy.types.Image | None:
	tex = None
	nodeTex = getNode(nodeTree, 'TEX_IMAGE', nodeBsdf, socket)
	if nodeTex:
		tex = nodeTex.image #type:ignore
	return tex

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
		("metalUseTex", ctypes.c_float),
		("roughUseTex", ctypes.c_float)
	]

def getMissingTex() -> gpu.types.GPUTexture:
	missingTex = bpy.data.images.get("STUC_MISSING_TEX", None)
	if not missingTex:
		missingTex = bpy.data.images.new("STUC_MISSING_TEX", 16, 16, alpha = True)
	return gpu.texture.from_image(missingTex)

def getMatParams(
	nodeTree: bpy.types.NodeTree,
	matInfo: MatInfo,
	albedoTex: bpy.types.Image | gpu.types.GPUTexture | None,
	metalTex: bpy.types.Image | gpu.types.GPUTexture | None,
	roughTex: bpy.types.Image | gpu.types.GPUTexture | None
) -> None:
	nodeOut = None
	for node in nodeTree.nodes:
		if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
			nodeOut = node
			break
	if not nodeOut:
		return
	nodeBsdf = getNode(nodeTree, 'BSDF_PRINCIPLED', nodeOut, "Surface")
	if not nodeBsdf:
		return
	
	missingTex = getMissingTex()

	albedoTex = getMatTex(nodeTree, nodeBsdf, "Base Color")
	if albedoTex:
		albedoTex = gpu.texture.from_image(albedoTex)
		matInfo.albedoUseTex = True
	else:
		albedoTex = missingTex
		col = nodeBsdf.inputs["Base Color"].default_value #type:ignore
		setArrFromArr(matInfo.albedoUniform, col, 3)
	metalTex = getMatTex(nodeTree, nodeBsdf, "Metallic")
	if metalTex:
		metalTex = gpu.texture.from_image(metalTex)
		matInfo.metalUseTex = True
	else:
		metalTex = missingTex
		matInfo.metalUniform = nodeBsdf.inputs["Metallic"].default_value #type:ignore
	roughTex = getMatTex(nodeTree, nodeBsdf, "Roughness")
	if roughTex:
		roughTex = gpu.texture.from_image(roughTex)
		matInfo.roughUseTex = True
	else:
		roughTex = missingTex
		matInfo.roughUniform = nodeBsdf.inputs["Roughness"].default_value #type:ignore

def arrPow(arr, exp: float, size: int) -> None:
	i = 0
	while i < size:
		arr[i] = pow(arr[i], exp)
		i += 1

def drawMeshForMat(
	mesh: stuc.StucMesh,
	pos, uv, normal,
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
	albedoTex = None
	metalTex = None
	roughTex = None
	if mat.node_tree:
		getMatParams(mat.node_tree, matInfo, albedoTex, metalTex, roughTex)
	if not albedoTex or not metalTex or not roughTex:
		albedoTex = metalTex = roughTex = getMissingTex()
		setArrFromArr(matInfo.albedoUniform, mat.diffuse_color, 3)
		matInfo.metalUniform = mat.metallic
		matInfo.roughUniform = mat.roughness
	shader.uniform_sampler("albedoTex", albedoTex)
	shader.uniform_sampler("metalTex", metalTex)
	shader.uniform_sampler("roughTex", roughTex)
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
		},
		indices = cornerNumpy
	)
	batch.draw(shader)

def drawStucMesh(mesh, idxAttribs) -> None:
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
	
	shader.bind()
	perpMat = bpy.context.region_data.perspective_matrix
	shader.uniform_float("viewProjectionMatrix", perpMat) #type:ignore
	viewPos = area.spaces.active.region_3d.view_matrix.inverted().translation #type:ignore
	shader.uniform_float("viewPos", viewPos)
	shader.uniform_sampler("envTex", envTexGl)
	shader.uniform_sampler("envTexConv", offscreen.texture_color)

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
		drawMeshForMat(mesh, pos, uv, normal, corners, i, matName)
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