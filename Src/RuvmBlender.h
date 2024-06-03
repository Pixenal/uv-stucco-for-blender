#pragma once
#include <stdint.h>

#include <RUVM.h>

#ifdef PLATFORM_LINUX
    #define RUVM_BLENDER_EXPORT
#endif
#ifdef PLATFORM_WINDOWS
	#define RUVM_BLENDER_EXPORT __declspec(dllexport)
#endif

RUVM_BLENDER_EXPORT
void ruvmBlenderInit();
RUVM_BLENDER_EXPORT
void ruvmBlenderMapFileExport(const char *pName, RuvmMesh *pMesh);
RUVM_BLENDER_EXPORT
void ruvmBlenderMapFileLoad(char *pFilePath);
//RUVM_BLENDER_EXPORT void ruvmBlenderMapFileUnload(char *pFilePath);
RUVM_BLENDER_EXPORT
int32_t ruvmBlenderMapToMesh(char *pFilePath,
                             RuvmMesh *pMesh,
                             RuvmMesh *pWorkMesh,
							 RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void ruvmBlenderQueryCommonAttribs(RuvmMesh *pMesh,
								   char *pMapName,
								   RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void ruvmBlenderDestroyCommonAttribs(RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void ruvmBlenderCopyMeshCore(RuvmMesh *ruvmMesh,
                             RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT
void ruvmBlenderCopyMeshAttribs(RuvmMesh *ruvmMesh,
                                RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT 
void ruvmBlenderMeshDestroy(RuvmMesh *pWorkMesh);
RUVM_BLENDER_EXPORT
int32_t ruvmBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res,
                                          float *pImage);
