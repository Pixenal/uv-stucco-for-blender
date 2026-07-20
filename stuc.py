'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import ctypes
import enum
import inspect
import sys

from . import c_lib
stucLib = c_lib.stucLib

STUC_ATTRIB_NAME_MAX_LEN = 96
STUC_ATTRIB_STRING_MAX_LEN = 64

class MeshCacheType(enum.Enum):
	MESH_CACHE_NONE = 0
	MESH_CACHE_IN = 1
	MESH_CACHE_IN_EDIT = 2
	MESH_CACHE_OUT = 3

class StucAttribType(enum.Enum):
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

class StucObjectType(enum.Enum):
	NULL = 0
	MESH = 1
	MESH_INTERN = 2
	MESH_BUF = 3

class StucAttribUse(enum.Enum):
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

class StucBlendMode(enum.Enum):
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

class StucDomain(enum.Enum):
	NONE = 0
	FACE = 1
	CORNER = 2
	EDGE = 3
	VERT = 4
	MESH = 5

class StucAttribCopyOpt(enum.Enum):
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

class StucBlendOpt(ctypes.Structure):
	_fields_ = [
		("blendConfig", StucBlendConfig),
		("attrib", ctypes.c_int32)
	]

class StucBlendOptArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucBlendOpt)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

StucBlendOptDomainArrs = StucBlendOptArr * StucDomain.MESH.value

class StucMapOrIdx(ctypes.Union):
    _fields_ = [
        ("ptr", ctypes.c_void_p),
        ("idx", ctypes.c_int64)
    ]

class StucMapArrEntry(ctypes.Structure):
	_fields_ = [
		("map", StucMapOrIdx),
		("blendOptArr", StucBlendOptDomainArrs),
		("wScale", ctypes.c_float),
		("receiveLen", ctypes.c_float),
		("matIdx", ctypes.c_byte)
	]

class StucMapArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(StucMapArrEntry)),
		("size", ctypes.c_int32),
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

class StucMapExport(ctypes.Structure):
	_fields_ = [
		("data", ctypes.c_byte * 320)#members aren't accessed in python
	]

class PixtyStrArr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(ctypes.c_char_p)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

class PixtyI32Arr(ctypes.Structure):
	_fields_ = [
		("pArr", ctypes.POINTER(ctypes.c_int32)),
		("size", ctypes.c_int32),
		("count", ctypes.c_int32)
	]

class PixioShmCtx(ctypes.Structure):
	_fields_ = [
		("pFile", ctypes.c_void_p),
		("pBuf", ctypes.c_void_p),
		("name", ctypes.c_byte * 40),
		("blockSize", ctypes.c_int32)
	]

class ShmDesc(enum.Enum):
	STUCB_SHM_NONE = 0
	STUCB_SHM_DIR = 1
	STUCB_SHM_NAME = 2
	STUCB_SHM_OBJ = 3
	STUCB_SHM_XFORM = 4
	STUCB_SHM_MESH = 5
	STUCB_SHM_FACES = 6
	STUCB_SHM_CORNERS = 7
	STUCB_SHM_EDGES = 8
	STUCB_SHM_ATTRIB = 9
	STUCB_SHM_ATTRIB_DATA = 10
	STUCB_SHM_IDX_ATTRIB_ARR = 11
	STUCB_SHM_IDX_ATTRIB = 12
	STUCB_SHM_IDX_ATTRIB_DATA = 13

class PixthJobInfo(ctypes.Structure):
	_fields_ = [
		("pJob", ctypes.c_void_p),
		("pArgs", ctypes.c_void_p),
		("hash", ctypes.c_uint64)
	]

class PixthJob(ctypes.Structure):
	_fields_ = [
		("info", PixthJobInfo),
		("err", ctypes.c_int32),
		("padding", ctypes.c_char * 40)
	]

#verify py classes mirrored from c lib
def stucStructVerify():
	try:
		for item in inspect.getmembers(sys.modules[__name__], inspect.isclass):
			if issubclass(item[1], enum.Enum) or item[0] == "StucBlendOptDomainArrs":
				continue
			verifyFunc = f"stucBlenderVerify{item[0]}"
			if not eval(f"stucLib.{verifyFunc}({ctypes.sizeof(item[1])})"):
				errStr = f"mirrored c-struct {item[0]} does not match library's"
				raise Exception(errStr)
	except Exception as e:
		raise e
