'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

import os
import sys
import ctypes
import addon_utils

import pdb
initPath = None
for module in addon_utils.modules():
	if module.bl_info['name'] == "UV Stucco":
		initPath = module.__file__
stucLib = None
if initPath:
	initDir = os.path.dirname(initPath)
	if sys.platform == "win32":
		stucLibPath = f"{initDir}\\lib\\win\\UvStuccoBlender.dll"
	elif sys.platform == "darwin":
		stucLibPath = f"{initDir}/lib/macos/libUvStuccoBlender.dylib"
	elif sys.platform == "linux" or sys.platform == "linux2":
		stucLibPath = f"{initDir}/lib/linux/libUvStuccoBlender.so"
	stucLib = ctypes.cdll.LoadLibrary(stucLibPath)
