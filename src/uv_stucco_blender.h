/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#pragma once


//#define STUC_DEBUG_UTILS
#include <uv_stucco.h>

#ifdef WIN32 
	#define STUC_BLENDER_EXPORT __declspec(dllexport)
#else
	#define STUC_BLENDER_EXPORT __attribute__((visibility("default")))
#endif

typedef enum TargetCacheType {
	MESH_CACHE_NONE,
	MESH_CACHE_IN,
	MESH_CACHE_IN_EDIT,
	MESH_CACHE_OUT
} TargetCacheType;

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
PixErr stucBlenderInit();
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
	double timestamp,
	PixtyStrArr *pDepDirs,
	int32_t (* fpGetMapPath)(const char *, const PixtyStrArr *Dirs, char *, double *),
	void (* fpStoreMap)(
		const char *,
		const char *,
		double,
		StucMapStatus,
		const PixtyStrArr *
	),
	bool dirty
);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapMeshGet(
	const char *pMap,
	const StucMesh **ppMesh,
	StucAttribIndexedArr **ppIdxAttribs,
	bool forRender
);
STUC_BLENDER_EXPORT
PixErr stucBlenderMeshPrepForRender(StucMesh *pMesh, bool triangulate);
STUC_BLENDER_EXPORT
PixErr stucBlenderMeshCpy(StucMesh *pDest, const StucMesh *pSrc);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapMeshRenderUpdate(const char *pMap);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapFileUnload(const char *pName);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapToMesh(
	PixthJob *pJobHandle,
	StucMapArr *pMapArr,
	StucMesh *pMesh,
	StucAttribIndexedArr *pInIndexedAttribs,
	StucMesh *pOutMesh,
	StucAttribIndexedArr *pOutIndexedAttribs,
	float wScale,
	float receiveLen,
	int32_t *pPushedJobs,
	bool triangulate
);
STUC_BLENDER_EXPORT
PixErr stucBlenderQueryCommonAttribs(
	const StucMesh *pMesh,
	const StucMap pMap,
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
	PixthJob *pJobsHandles,
	bool wait,
	bool *pDone
);
STUC_BLENDER_EXPORT
void stucBlenderDestroy();
STUC_BLENDER_EXPORT
void stucBlenderCallFree(void *pData);
STUC_BLENDER_EXPORT
void *stucBlenderMapHandleGet(const char *pName);
STUC_BLENDER_EXPORT
PixErr stucBlenderAttribGet(
	StucMesh *pMesh,
	const char *pName,
	StucAttrib **ppAttrib,
	int32_t *pIdx,
	StucDomain *pDomain
);
STUC_BLENDER_EXPORT
PixErr stucBlenderTargetCacheRemove(int32_t id);
STUC_BLENDER_EXPORT
PixErr stucBlenderTargetCacheAdd(
	int32_t id,
	double timestamp,
	StucMesh *pMesh,
	StucAttribIndexedArr *pIdxAttribs,
	TargetCacheType type,
	uint64_t crc
);
STUC_BLENDER_EXPORT
PixErr stucBlenderCrcFromTarget(
	const StucMesh *pMesh,
	const StucAttribIndexedArr *pIdxAttribArr,
	const StucMapArr *pMapArr,
	uint64_t *pCrc
);
STUC_BLENDER_EXPORT
PixErr stucBlenderTargetCrc(int32_t id, uint64_t *pCrc);
STUC_BLENDER_EXPORT
PixErr stucBlenderTargetCacheGet(
	int32_t id,
	double *pTimestamp,
	StucMesh **ppMesh,
	StucAttribIndexedArr **ppIdxAttribs,
	TargetCacheType *pType
);
STUC_BLENDER_EXPORT
PixErr stucBlenderTargetCacheClear(int32_t id);
STUC_BLENDER_EXPORT
PixErr stucBlenderCornersForMat(StucMesh *pMesh, I32 mat, PixtyI32Arr *pCorners);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapNameGet(StucMap pMap, const char **ppName);
STUC_BLENDER_EXPORT
PixErr stucBlenderEditOverlayCol(
	I32 edgeCount,
	const PixtyV2_I32 *pEdges,
	const float *pSelect,
	I32 vertCount,
	PixtyV4_F32 *pCol
);
STUC_BLENDER_EXPORT
PixErr stucBlenderMeshCastSel(
	const StucMesh *pMesh,
	float *pSelCorners,
	const int8_t *pSelFaces,
	float *pfSelEdges,
	const int8_t *piSelEdges
);
STUC_BLENDER_EXPORT
void stucBlenderArrayCast(
	void *pDest, int32_t sizeDest,
	void *pSrc, int32_t sizeSrc,
	int32_t len
);

typedef enum ShmDesc {
	STUCB_SHM_NONE,
	STUCB_SHM_DIR,
	STUCB_SHM_NAME,
	STUCB_SHM_OBJ,
	STUCB_SHM_XFORM,
	STUCB_SHM_MESH,
	STUCB_SHM_FACES,
	STUCB_SHM_CORNERS,
	STUCB_SHM_EDGES,
	STUCB_SHM_ATTRIB,
	STUCB_SHM_ATTRIB_DATA,
	STUCB_SHM_IDX_ATTRIB_ARR,
	STUCB_SHM_IDX_ATTRIB,
	STUCB_SHM_IDX_ATTRIB_DATA 
} ShmDesc;

STUC_BLENDER_EXPORT
I32 stucBlenderShmNameMaxLen();
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneExportInit(PixioShmCtx *pShmCtx, char *pName);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportInit(PixioShmCtx *pShmCtx, char *pName);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneExportStr(PixioShmCtx *pShmCtx, ShmDesc desc, const char *pName);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneExportMesh(PixioShmCtx *pShmCtx, const StucMesh *pMesh);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneExportObj(
	PixioShmCtx *pShmCtx,
	const char *pName,
	const StucObject *pObj
);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneExportIdxAttribs(
	PixioShmCtx *pShmCtx,
	const StucAttribIndexedArr *pArr
);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportStr(PixioShmCtx *pShmCtx, char *pStr);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportMesh(PixioShmCtx *pShmCtx, StucMesh *pMesh);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportObj(PixioShmCtx *pShmCtx, StucObject *pObj);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportIdxAttribs(PixioShmCtx *pShmCtx, StucAttribIndexedArr *pArr);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportQuery(
	PixioShmCtx *pShmCtx,
	int32_t *pSize,
	ShmDesc *pDesc,
	bool *pClose
);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneExportDestroy(PixioShmCtx *pShmCtx);
STUC_BLENDER_EXPORT
PixErr stucBlenderSceneImportDestroy(PixioShmCtx *pShmCtx);
STUC_BLENDER_EXPORT
PixErr stucBlenderThreadPoolLogDump(const char *pPath);
STUC_BLENDER_EXPORT
PixErr stucBlenderMapZBoundsGet(const StucMap pMap, PixtyV2_F32 *pZBounds);


//funcs for verifying c structs mirrored in python are correct size
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucVec2(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucVec3(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStuc_M4x4_F32(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucAttribCore(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucAttrib(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucAttribIndexed(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucAttribIndexedArr(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucAttribArray(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucObjectData(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucAttribActive(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucMesh(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucObject(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucBlendConfig(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucBlendOpt(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucBlendOptArr(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucMapOrIdx(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucMapArrEntry(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucMapArr(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucFlatCutoffIdx(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucUsg(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucBlenderMatTable(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyStucBlenderMatTableArr(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyPixtyStrArr(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyPixtyI32Arr(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyPixioShmCtx(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyShmDesc(I32 size);
STUC_BLENDER_EXPORT
bool stucBlenderVerifyPixthJob(I32 size);
