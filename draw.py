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
vertOut.smooth('VEC3', "v_albedo")
vertOut.smooth('FLOAT', "s_metal")
vertOut.smooth('FLOAT', "s_rough")
vertOut.smooth('VEC3', "v_lightDir")
vertOut.smooth('VEC3', "v_viewPos")

info = gpu.types.GPUShaderCreateInfo()
info.push_constant('MAT4', "viewProjectionMatrix")
info.push_constant('VEC3', "lightDir")
info.push_constant('VEC3', "viewPos")
info.sampler(0, 'FLOAT_2D', "envTex")
info.sampler(1, 'FLOAT_2D', "envTexConv")
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

def drawStucMesh(mesh) -> None:
	area = getArea()
	if not area:
		return
	
	envTex = bpy.data.images.get("STUC_ENV_TEX", None)
	if not envTex:
		studioLights = bpy.context.preferences.studio_lights
		studioLight = studioLights.get("forest.exr", None)
		if not studioLight:
			return
		envTex = bpy.data.images.load(studioLight.path)
		envTex.name = "STUC_ENV_TEX"
		envTex.alpha_mode = 'NONE'
	
	envTexGl = gpu.texture.from_image(envTex)
	getEnvTexConv(envTexGl)


	pos = numpyFromStucAttrib(mesh, stuc.StucAttribUse.POS, 3)
	uv = numpyFromStucAttrib(mesh, stuc.StucAttribUse.UV, 2)
	normal = numpyFromStucAttrib(mesh, stuc.StucAttribUse.NORMAL, 3)
	corners = numpy.ctypeslib.as_array(
		ctypes.cast(mesh.pCorners, ctypes.POINTER(ctypes.c_int32)),
		shape = (mesh.faceCount, 3) #assumes mesh has been triangulated
	)
	batch = gpu_extras.batch.batch_for_shader(
		shader,
		'TRIS',
		{
			"position" : pos, #type:ignore
			"uv" : uv,
			"normal" : normal,
		},
		indices = corners
	)
	shader.bind()
	perpMat = bpy.context.region_data.perspective_matrix
	shader.uniform_float("viewProjectionMatrix", perpMat) #type:ignore
	viewPos = area.spaces.active.region_3d.view_matrix.inverted().translation #type:ignore
	shader.uniform_float("viewPos", viewPos)
	shader.uniform_float("lightDir", (.0, .0, 1.0))
	shader.uniform_sampler("envTex", envTexGl)
	shader.uniform_sampler("envTexConv", offscreen.texture_color)

	gpu.state.depth_test_set('LESS_EQUAL')
	gpu.state.depth_mask_set(True)
	batch.draw(shader)
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