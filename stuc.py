'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
from enum import Enum

STUC_ATTRIB_NAME_MAX_LEN = 96
STUC_ATTRIB_STRING_MAX_LEN = 64

class StucAttribType(Enum):
	I8 = 0
	I16 = 1
	I32 = 2
	I64 = 3
	F32 = 4
	F64 = 5
	V2_I8 = 6
	V2_I16 = 7
	V2_I32 = 8
	V2_I64 = 9
	V2_F32 = 10
	V2_F64 = 11
	V3_I8 = 12
	V3_I16 = 13
	V3_I32 = 14
	V3_I64 = 15
	V3_F32 = 16
	V3_F64 = 17
	V4_I8 = 18
	V4_I16 = 19
	V4_I32 = 20
	V4_I64 = 21
	V4_F32 = 22
	V4_F64 = 23
	STRING = 24
	NONE = 25
	ENUM_COUNT = 26

class StucObjectType(Enum):
	NULL = 0
	MESH = 1
	MESH_INTERN = 2
	MESH_BUF = 3

class StucAttribUse(Enum):
	NONE = 0
	POS = 1
	UV = 2
	NORMAL = 3
	PRESERVE_EDGE = 4
	RECEIVE = 5
	PRESERVE_VERT = 6
	USG = 7
	TANGENT = 8
	TSIGN = 9
	WSCALE = 10
	IDX = 11
	EDGE_LEN = 12
	SEAM_EDGE = 13
	SEAM_VERT = 14
	NUM_ADJ_PRESERVE = 15
	EDGE_FACES = 16
	EDGE_CORNERS = 17
	NORMALS_VERT = 18
	SP_ENUM_COUNT = 19
	COLOR = 20
	MASK = 21
	SCALAR = 22
	MISC = 23
	ENUM_COUNT = 24

class StucBlendMode(Enum):
	REPLACE = 0
	MULTIPLY = 1
	DIVIDE = 2
	ADD = 3
	SUBTRACT = 4
	ADD_SUB = 5
	LIGHTEN = 6
	DARKEN = 7
	OVERLAY = 8
	SOFT_LIGHT = 9
	COLOR_DODGE = 10
	APPEND = 11

class StucDomain(Enum):
	NONE = 0
	FACE = 1
	CORNER = 2
	EDGE = 3
	VERT = 4

class StucAttribCopyOpt(Enum):
	COPY = 0
	DONT_COPY = 1

class StucVec2(ctypes.Structure):
	_fields_ = [
		("x", ctypes.c_float),
		("y", ctypes.c_float)
	]

class StucVec3(ctypes.Structure):
	_fields_ = [
		("x", ctypes.c_float),
		("y", ctypes.c_float),
		("z", ctypes.c_float)
	]
	
Stuc_M4x4_F32 = ctypes.c_float * 16

class StucAttribCore(ctypes.Structure):
	_fields_ = [
		("pData", ctypes.c_void_p),
		#use c_byte instead of c_char, as the latter is immutable
		("name", ctypes.c_byte * STUC_ATTRIB_NAME_MAX_LEN),
		("type", ctypes.c_int32),
		("use", ctypes.c_int32)
	]

class StucAttrib(ctypes.Structure):
	_fields_ = [
		("core", StucAttribCore),
		("origin", ctypes.c_int32),
		("copyOpt", ctypes.c_int32),
		("interpolate", ctypes.c_int32)
	]
	
class StucAttribIndexed(ctypes.Structure):
	_fields_ = [
		("core", StucAttribCore),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]
	
class StucAttribIndexedArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucAttribIndexed)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

class StucAttribArray(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucAttrib)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]
	
class StucObjectData(ctypes.Structure):
	_fields_ = [
		("type", ctypes.c_int32)
	]
	
class StucAttribActive(ctypes.Structure):
	_fields_ = [
		("domain", ctypes.c_int32),
		("idx", ctypes.c_int16),
		("active", ctypes.c_bool)
	]

class StucMesh(ctypes.Structure):
	_fields_ = [
		("type", StucObjectData),
		("activeAttribs", StucAttribActive * StucAttribUse.ENUM_COUNT.value),
		("pFaces", ctypes.POINTER(ctypes.c_int32)),
		("pCorners", ctypes.POINTER(ctypes.c_int32)),
		("pEdges", ctypes.POINTER(ctypes.c_int32)),
		("meshAttribs", StucAttribArray),
		("faceAttribs", StucAttribArray),
		("cornerAttribs", StucAttribArray),
		("edgeAttribs", StucAttribArray),
		("vertAttribs", StucAttribArray),
		("faceCount", ctypes.c_int32),
		("cornerCount", ctypes.c_int32),
		("edgeCount", ctypes.c_int32),
		("vertCount", ctypes.c_int32)
	]
	
class StucObject(ctypes.Structure):
	_fields_ = [
		("pData", ctypes.POINTER(StucObjectData)),
		("transform", Stuc_M4x4_F32)
	]

class StucBlendConfig(ctypes.Structure):
	_fields_ = [
		("fMin", ctypes.c_double),
		("fMax", ctypes.c_double),
		("iMin", ctypes.c_int64),
		("iMax", ctypes.c_int64),
		("blend", ctypes.c_int32),
		("opacity", ctypes.c_float),
		("clamp", ctypes.c_bool),
		("order", ctypes.c_bool)
	]

class StucCommonAttrib(ctypes.Structure):
	#use c_byte instead of c_char, as the latter is immutable
	_fields_ = [
		("name", ctypes.c_byte * STUC_ATTRIB_NAME_MAX_LEN),
		("blendConfig", StucBlendConfig)
	]

class StucCommonAttribArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucCommonAttrib)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

class StucCommonAttribList(ctypes.Structure):
	_fields_ = [
		("mesh", StucCommonAttribArr),
		("face", StucCommonAttribArr),
		("corner", StucCommonAttribArr),
		("edge", StucCommonAttribArr),
		("vert", StucCommonAttribArr),
	]

class StucMapArrEntry(ctypes.Structure):
	_fields_ = [
		("pMap", ctypes.c_void_p),
		("matIdx", ctypes.c_byte)
	]

class StucMapArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucMapArrEntry)),
		("pCommonAttribArr", ctypes.POINTER(StucCommonAttribList)),
		("count", ctypes.c_int32)
	]

class StucFlatCutoffIdx(ctypes.Structure):
	_fields_ = [
		("idx", ctypes.c_int32),
		("enabled", ctypes.c_bool)
	]
	
class StucUsg(ctypes.Structure):
	_fields_ = [
		("obj", StucObject),
		("flatCutoff", StucFlatCutoffIdx)
	]
	
class StucBlenderMatTable(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(ctypes.c_byte)),
		("count", ctypes.c_byte)
	]
	
class StucBlenderMatTableArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucBlenderMatTable)),
		("count", ctypes.c_int32)
	]