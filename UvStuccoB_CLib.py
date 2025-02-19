import ctypes
import sys

if sys.platform == "win32":
	stucLibPath = "T:/workshop_folders/RUVM_Blender/Build/WinMdNew/Release/UvStuccoBlender.dll"
elif sys.platform == "darwin":
	stucLibPath = "/Users/calebdawson/Repos/UvStuccoB_Blender/build/macosShared/libUvStuccoBBlender.dylib"
elif sys.platform == "linux" or "linux2":
	stucLibPath = "/run/media/calebdawson/Tuna/workshop_folders/UvStuccoB_Blender/Build/Debug/libStucBlender.so"
stucLib = ctypes.cdll.LoadLibrary(stucLibPath)
