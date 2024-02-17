#pragma once
#include <stdint.h>

#include <RUVM.h>

#define RUVM_BLENDER_EXPORT
#ifdef PLATFORM_WIN
	#define RUVM_BLENDER_EXPORT __declspec(dllexport)
#endif

RUVM_BLENDER_EXPORT void ruvmBlenderInit();
RUVM_BLENDER_EXPORT void ruvmBlenderMapFileExport(RuvmMesh *pMesh,
                                                  float *pNormals);
RUVM_BLENDER_EXPORT void ruvmBlenderMapFileLoad(char *pFilePath);
RUVM_BLENDER_EXPORT void ruvmBlenderMapFileUnload(char *pFilePath);
RUVM_BLENDER_EXPORT void ruvmBlenderMapToMesh(char *pFilePath,
                                              RuvmMesh *pMesh,
											  int32_t *pEdges,
											  float *pNormals,
                                              RuvmMesh *pWorkMesh);
RUVM_BLENDER_EXPORT void ruvmBlenderUpdateMesh(RuvmMesh *ruvmMesh,
                                               RuvmMesh *workMesh,
                                               float **ppOutNormals);
RUVM_BLENDER_EXPORT void ruvmBlenderUpdateMeshUv(RuvmMesh *ruvmMesh,
                                                 RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT void ruvmBlenderDestroy(RuvmMesh *pWorkMesh);
