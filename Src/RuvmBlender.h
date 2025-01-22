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
void uvsBlenderInit();
RUVM_BLENDER_EXPORT
RuvmResult uvsBlenderMapFileExport(const char *pName, int32_t objCount,
                                    RuvmObject* pObjArr, int32_t usgCount,
                                    RuvmUsg* pUsgArr,
                                    RuvmAttribIndexedArr indexedAttribs);
RUVM_BLENDER_EXPORT
RuvmResult uvsBlenderMapFileLoadForEdit(char *pFilePath,
                                         int32_t *pObjCount, RuvmObject **ppObjArr,
                                         int32_t *pUsgCount, RuvmUsg **ppUsgArr,
                                         int32_t *pFlatCutoffCount, RuvmObject **ppFlatCutoffArr,
                                         RuvmAttribIndexedArr *pIndexedAttribs);
RUVM_BLENDER_EXPORT
RuvmResult uvsBlenderMapFileLoad(char *pFilePath);
RUVM_BLENDER_EXPORT
RuvmResult uvsBlenderMapFileUnload(char *pFilePath);
RUVM_BLENDER_EXPORT
int32_t uvsBlenderMapToMesh(char *pFilePath,
                             RuvmMesh *pMesh,
                             RuvmMesh *pWorkMesh,
							 RuvmCommonAttribList *pCommonAttribs, float wScale);
RUVM_BLENDER_EXPORT
void uvsBlenderQueryCommonAttribs(RuvmMesh *pMesh,
								   char *pMapName,
								   RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void uvsBlenderDestroyCommonAttribs(RuvmCommonAttribList *pCommonAttribs);
RUVM_BLENDER_EXPORT
void uvsBlenderCopyMeshCore(RuvmMesh *uvsMesh,
                             RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT
void uvsBlenderCopyMeshAttribs(RuvmMesh *uvsMesh,
                                RuvmMesh *workMesh);
RUVM_BLENDER_EXPORT
RuvmResult uvsBlenderObjArrDestroy(int32_t objCount, RuvmObject *pObjArr);
RUVM_BLENDER_EXPORT
RuvmResult uvsBlenderUsgArrDestroy(int32_t count, RuvmUsg *pUsgArr);
RUVM_BLENDER_EXPORT 
void uvsBlenderMeshDestroy(RuvmMesh *pWorkMesh);
RUVM_BLENDER_EXPORT
int32_t uvsBlenderMapFileGenPreviewImage(char *pFilePath, int32_t res,
                                          float *pImage);
RUVM_BLENDER_EXPORT
void uvsBlenderMapMatsGet(char *pFilePath,
                           RuvmAttribIndexed **ppMats);
RUVM_BLENDER_EXPORT
void uvsBlenderDestroy();