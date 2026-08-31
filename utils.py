'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import bpy
import ctypes
import mathutils
from typing import Any, cast
import pdb

def copyString(dest: bytes, src: str, maxLen: int) -> None:
	length = len(src)
	if (length > maxLen):
		raise Exception("string length exceeds max")
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
			linearIdx = k + j * 4
			dest[linearIdx] = matWorld[j][k]
			k += 1
		j += 1

def setBlenderMatrix(dest: mathutils.Matrix, src: ctypes.Array[ctypes.c_float]) -> None:
	j = 0
	while j < 4:
		k = 0
		while k < 4:
			linearIdx = k + j * 4
			dest[j][k] = src[linearIdx]
			k += 1
		j += 1
	dest.transpose()

def findMatInCol(
	mat: bpy.types.Material,
	col: Any
) -> int | None:
	i = 0
	for item in col:
		if item.mat and item.mat.name == mat.name:
			return i
		i += 1
	return None

def findObjInCol(
	obj: bpy.types.Object,
	col: Any
) -> int | None:
	i = 0
	for item in col:
		if item.obj and item.obj.name == obj.name:
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

def updateUiTargetIdx(context: bpy.types.Context) -> int | None:
	active = context.active_object
	if (active):
		if type(active.data) == bpy.types.Mesh:
			idx = findObjInCol(active, cast(Any, context.scene).stucTargets)
			if idx != None:
				context.scene.stucTargetsIdx = idx #type:ignore
				return idx
	return None

def initActiveAttrib(
	target: Any,
	use: str,
	name: str
) -> Any:
	entry = target.activeAttribs.add()
	entry.use = use
	entry.name = name
	return entry

def makeRel(context: bpy.types.Context, dir: str) -> str | None:
	if len(bpy.data.filepath) and context.scene.stuc.relPaths: #type:ignore
		if len(dir) and dir[0] == bpy.data.filepath[0]:
			relDir = bpy.path.relpath(dir)
			if dir != relDir:
				return relDir
	return None