/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#pragma once
#include <uv_stucco.h>

#ifdef WIN32 
	#define STUC_BLENDER_EXPORT __declspec(dllexport)
#else
	#define STUC_BLENDER_EXPORT __attribute__((visibility("default")))
#endif

typedef struct StucBlenderMatTable{
	int8_t *pArr;
	int32_t count;
} StucBlenderMatTable;

typedef struct StucBlenderMatTableArr{
	StucBlenderMatTable *pArr;
	int32_t count;
} StucBlenderMatTableArr;

typedef struct StrWithLen {
	char *pStr;
	int32_t len;
} StrWithLen;

STUC_BLENDER_EXPORT
void stucBlenderInit();
STUC_BLENDER_EXPORT
StucErr stucBlenderMapExportInit(
	void **ppHandle,
	const char *pPath,
	bool compress
);
STUC_BLENDER_EXPORT
StucErr stucBlenderMapExportEnd(void **ppHandle);
STUC_BLENDER_EXPORT
StucErr stucBlenderMapExportTargetAdd(
	void *pHandle,
	StucMapArr *pMapArr,
	const StucObject *pObj,
	const StucAttribIndexedArr *pIndexedAttribs,
	float wScale,
	float receiveLen
);
STUC_BLENDER_EXPORT
StucErr stucBlenderMapExportObjAdd(
	void *pHandle,
	const StucObject *pObj,
	const StucAttribIndexedArr *pIndexedAttribs
);
STUC_BLENDER_EXPORT
StucErr stucBlenderMapExportUsgAdd(void *pHandle, StucUsg *pUsg);
STUC_BLENDER_EXPORT
StucErr stucBlenderMapExportUsgCutoffAdd(void *pHandle, StucObject *pFlatCutoff);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapFileLoadForEdit(
	const char *pFilepath,
	int32_t *pObjCount,
	StucObject **ppObjArr,
	int32_t *pUsgCount,
	StucUsg **ppUsgArr,
	int32_t *pFlatCutoffCount,
	StucObject **ppFlatCutoffArr,
	StucAttribIndexedArr *pIndexedAttribs
);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapFileLoad(
	const char *pFilepath,
	const char *pName,
	PixtyStrArr *pDepDirs,
	int32_t (* getDepDirs)(const char *, const PixtyStrArr *Dirs, const char *)
);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapFileUnload(const char *pName);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapToMesh(
	void **ppJobHandle,
	StucMapArr *pMapArr,
	StucMesh *pMesh,
	StucAttribIndexedArr *pInIndexedAttribs,
	StucMesh *pOutMesh,
	StucAttribIndexedArr *pOutIndexedAttribs,
	float wScale,
	float receiveLen,
	int32_t *pPushedJobs
);
STUC_BLENDER_EXPORT
PixErr stucBlenderQueryCommonAttribs(
	StucMesh *pMesh,
	const char *pMapName,
	StucBlendOptArr *pBlendOptArr
);
STUC_BLENDER_EXPORT
PixErr stucBlenderDestroyBlendOptArr(StucBlendOptArr *pBlendOptArr);
STUC_BLENDER_EXPORT
void stucBlenderCopyMeshCore(StucMesh *pDest, StucMesh *pSrc);
STUC_BLENDER_EXPORT
PixErr stucBlenderCopyMeshAttribs(StucMesh *pDest, StucMesh *pSrc);
STUC_BLENDER_EXPORT
PixErr stucBlenderObjArrDestroy(StucObjArr *pObjArr);
STUC_BLENDER_EXPORT
PixErr stucBlenderUsgArrDestroy(int32_t count, StucUsg *pUsgArr);
STUC_BLENDER_EXPORT
PixErr stucBlenderMeshDestroy(StucMesh *pMesh);
STUC_BLENDER_EXPORT
PixErr stucBlenderWaitForJobs(
	int32_t count,
	void **ppJobHandles,
	bool wait,
	bool *pDone
);
STUC_BLENDER_EXPORT
void stucBlenderDestroy();
STUC_BLENDER_EXPORT
void stucBlenderCallFree(void *pData);
STUC_BLENDER_EXPORT
void *stucBlenderMapHandleGet(const char *pName);
