import bpy
import ctypes
import mathutils
from typing import Any, cast
import pdb

def copyString(dest: bytes, src: str, maxLen: int) -> None:
	length = len(src)
	if (length > maxLen):
		#TODO add proper exception handling in general
		print("string length exceeds max")
		return
	srcUtf8 = src.encode('utf-8')
	i = 0
	while (i < length):
		cast(Any, dest)[i] = srcUtf8[i]
		i += 1

def setStucMatrix(dest: ctypes.Array[ctypes.c_float], src: mathutils.Matrix) -> None:
	matWorld = src.copy()
	matWorld.transpose()
	j = 0
	while j < 4:
		k = 0
		while k < 4:
			linearIndex = k + j * 4
			dest[linearIndex] = matWorld[j][k]
			k += 1
		j += 1

def setBlenderMatrix(dest: mathutils.Matrix, src: ctypes.Array[ctypes.c_float]) -> None:
	j = 0
	while j < 4:
		k = 0
		while k < 4:
			linearIndex = k + j * 4
			dest[j][k] = src[linearIndex]
			k += 1
		j += 1
	dest.transpose()

def findMatInCol(
	mat: bpy.types.Material,
	col: bpy.types.Collection
) -> int | None:
	i = 0
	for item in col:
		if item.mat and item.mat.name == mat.name:
			return i
		i += 1
	return None

def findObjInCol(
	obj: bpy.types.Object,
	col: bpy.types.Collection
) -> int | None:
	i = 0
	for item in col:
		if item.obj.name == obj.name:
			return i
		i += 1
	return None

def getMatsInStucMats(context: bpy.types.Context, mesh: bpy.types.Mesh) -> list[Any]:
	targetMats = []
	for mat in mesh.materials:
		idx = findMatInCol(mat, cast(Any, context.scene).stucMats)
		if idx != None:
			targetMats.append(cast(Any, context.scene).stucMats[idx])
	return targetMats