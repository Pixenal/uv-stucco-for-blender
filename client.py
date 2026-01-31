'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import sys
import pdb
import os

import bpy

def checkForShmArg() -> list[str] | None:
	shmName = ""
	serverPath = ""
	stucArgs = 0
	for arg in sys.argv:
		if arg == "--stuc-scene-cache":
			stucArgs = 1
			continue
		elif arg == "--stuc-scene-cache-server":
			stucArgs = 2
			continue
		match stucArgs:
			case 1:
				if "STUC_" in arg:
					shmName = arg
			case 2:
				if ".blend" in arg:
					serverPath = arg
	if len(shmName) and len(serverPath):
		return [shmName, serverPath]
	return None

def createCachePath(shmServer: str)-> str:
	cacheDir = f"{os.path.dirname(shmServer)}/_STUC_CACHE"
	os.makedirs(cacheDir, exist_ok = True)
	return f"{cacheDir}/_STUC_CACHE_{bpy.path.basename(shmServer)}"

if __name__ == "__main__":
	try:
		args = checkForShmArg()
		if args:
			path = createCachePath(args[1])
			if not os.path.isfile(path):
				bpy.ops.wm.save_mainfile(filepath = path)
			bpy.ops.wm.open_mainfile(filepath = path)
	except Exception:
		pass