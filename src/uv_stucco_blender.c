/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#define HANDLE_TABLE_SIZE 64

#include <string.h>

#include <pixenals_io_utils.h>
#include <pixenals_structs.h>

#include <uv_stucco_blender.h>

#include <pixenals_math_utils.h>

typedef int8_t I8;
typedef int16_t I16;
typedef int32_t I32;
typedef int64_t I64;

typedef uint8_t U8;
typedef uint16_t U16;
typedef uint32_t U32;
typedef uint64_t U64;

typedef float F32;
typedef double F64;

typedef struct MapEntry {
	PixuctHTableEntryCore core;
	StucMap pMap;
	StucMesh meshRender;
} MapEntry;

typedef struct TargetEntry {
	PixuctHTableEntryCore core;
	F64 timestamp;
	StucMesh mesh;
	StucAttribIndexedArr idxAttribs;
	I32 id;
	TargetCacheType type;
} TargetEntry;

static PixalcFPtrs allocPtrs = {
	.fpCalloc = calloc,
	.fpMalloc = malloc,
	.fpRealloc = realloc,
	.fpFree = free
};
static StucContextInternal stucCtx = {0};
static PixErr tableErr = PIX_ERR_SUCCESS;
static PixuctHTable mapTable = {0};
static PixuctHTable targetCache = {0};

static
void clearMapEntry(void *pUserData, PixuctHTableEntryCore *pCore, const void *pKeyData) {
	MapEntry *pEntry = (MapEntry *)pCore;
	if (pEntry->pMap) {
		*(PixErr *)pUserData = stucMapFileUnload(&stucCtx, pEntry->pMap);
		pEntry->pMap = NULL;
	}
	*(PixErr *)pUserData = PIX_ERR_SUCCESS == stucMeshDestroy(&stucCtx, &pEntry->meshRender);
	pEntry->meshRender = (StucMesh){0};
}

static
void clearTargetEntry(void *pUserData, PixuctHTableEntryCore *pCore, const void *pKeyData) {
	TargetEntry *pEntry = (TargetEntry *)pCore;
	if (pEntry->mesh.faceCount) {
		*(PixErr *)pUserData = stucMeshDestroy(&stucCtx, &pEntry->mesh);
	}
}

PixErr stucBlenderMapNameGet(StucMap pMap, const char **ppName) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, pMap, "");
	const char *pName = NULL;
	err = stucMapNameGet(&stucCtx, pMap, ppName);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

static
bool cmpMap(
	const PixuctHTableEntryCore *pCore,
	const void *pKeyData,
	const void *pInitInfo
) {
	const char *pName = NULL;
	//TODO v pass userdata to cmp fp in htable get func, so error can be passed out here v
	stucMapNameGet(&stucCtx, ((MapEntry *)pCore)->pMap, &pName);
	if (pName) {
		return !strncmp(pKeyData, pName, PIXIO_PATH_MAX);
	}
	return false;
}

static
bool cmpTarget(
	const PixuctHTableEntryCore *pCore,
	const void *pKeyData,
	const void *pInitInfo
) {
	return *(I32 *)pKeyData == ((TargetEntry *)pCore)->id;
}

static
void initMapEntry(
	void *pUserData,
	PixuctHTableEntryCore *pCore,
	const void *pKeyData,
	void *pInitInfo,
	I32 idx
) {
	((MapEntry *)pCore)->pMap = pInitInfo;
}

static
void initTargetEntry(
	void *pUserData,
	PixuctHTableEntryCore *pCore,
	const void *pKeyData,
	void *pInitInfo,
	I32 idx
) {
	void **ppInitArr = pInitInfo;
	TargetEntry *pEntry = (TargetEntry *)pCore;
	pEntry->id = *(I32 *)pKeyData;
	pEntry->timestamp = *(double *)ppInitArr[0];
	pEntry->mesh = *(StucMesh *)ppInitArr[1];
	pEntry->type = *(TargetCacheType *)ppInitArr[3];
	if (pEntry->type == MESH_CACHE_OUT) {
		PIX_ERR_ASSERT("", ppInitArr[1]);
		pEntry->idxAttribs = *(StucAttribIndexedArr *)ppInitArr[2];
	}
}

static
PixuctKey keyFromPath(const void *pKeyData) {
	I32 len = (I32)strnlen(pKeyData, pixioPathMaxGet());
	return (PixuctKey){.pKey = pKeyData, .size = len};
}

static
PixErr mapEntryGet(const char *pName, MapEntry **ppEntry, StucMap pMap) {
	PixErr err = PIX_ERR_SUCCESS;
	pixuctHTableGet(
		&mapTable,
		0,
		pName,
		ppEntry,
		!!pMap,
		pMap,
		keyFromPath,
		NULL,
		pMap ? initMapEntry : NULL,
		cmpMap
	);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	return err;
}

static
PixErr targetEntryGet(
	I32 id,
	F64 *pTimestamp,
	TargetEntry **ppEntry,
	StucMesh *pMesh,
	StucAttribIndexedArr *pIdxAttribs,
	TargetCacheType type
) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, !(!pMesh ^ !pIdxAttribs) || type != MESH_CACHE_OUT, "");
	void *init[] = {pTimestamp, pMesh, pIdxAttribs, &type};
	SearchResult result = pixuctHTableGet(
		&targetCache,
		0,
		&id,
		ppEntry,
		!!pMesh,
		init,
		pixuctKeyFromI32,
		NULL,
		pMesh ? initTargetEntry : NULL,
		cmpTarget
	);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	if (result == PIX_SEARCH_FOUND) {
		//update entry
		PIX_ERR_ASSERT("", *ppEntry);
		if (pMesh) {
			if ((*ppEntry)->mesh.faceCount) {
				err = stucMeshDestroy(&stucCtx, &(*ppEntry)->mesh);
				PIX_ERR_RETURN_IFNOT(err, "");
			}
			PIX_ERR_ASSERT("", type != MESH_CACHE_NONE);
			(*ppEntry)->type = type;
			(*ppEntry)->mesh = *pMesh;
		}
		if (pIdxAttribs) {
			if ((*ppEntry)->idxAttribs.count) {
				err = stucAttribIndexedArrDestroy(&stucCtx, &(*ppEntry)->idxAttribs);
				PIX_ERR_RETURN_IFNOT(err, "");
			}
			(*ppEntry)->idxAttribs = *pIdxAttribs;
		}
		if (pTimestamp) {
			(*ppEntry)->timestamp = *pTimestamp;
		}
	}	
	return err;
}

static
PixErr mapEntryDestroy(const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	pixuctHTableRemove(&mapTable, 0, pName, keyFromPath, cmpMap, clearMapEntry);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	return err;
}

static
PixErr targetEntryDestroy(I32 id) {
	PixErr err = PIX_ERR_SUCCESS;
	pixuctHTableRemove(&targetCache, 0, &id, pixuctKeyFromI32, cmpTarget, clearTargetEntry);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	return err;
}

PixErr stucBlenderInit() {
	PixErr err = PIX_ERR_SUCCESS;
#ifdef STUC_DEBUG_UTILS
	bool threadLogging = true;
#else
	bool threadLogging = false;
#endif
	err = stucContextInit(&stucCtx, NULL, NULL, NULL, NULL, NULL, threadLogging);
	PIX_ERR_RETURN_IFNOT(err, "");
	pixuctHTableInit(
		&allocPtrs,
		&mapTable,
		HANDLE_TABLE_SIZE,
		(PixtyI32Arr){.pArr = (I32[]){sizeof(MapEntry)}, .count = 1},
		NULL,
		&tableErr,
		true
	);
	pixuctHTableInit(
		&allocPtrs,
		&targetCache,
		HANDLE_TABLE_SIZE,
		(PixtyI32Arr){.pArr = (I32[]){sizeof(TargetEntry)}, .count = 1},
		NULL,
		&tableErr,
		true
	);
	return err;
}

StucErr stucBlenderMapExportInit(
	void **ppHandle,
	const char *pPath,
	bool compress
) {
	return stucMapExportInit(&stucCtx, (StucMapExport **)ppHandle, pPath, compress);
}

StucErr stucBlenderMapExportEnd(void **ppHandle) {
	return stucMapExportEnd((StucMapExport **)ppHandle);
}

StucErr stucBlenderMapExportTargetAdd(
	void *pHandle,
	StucMapArr *pMapArr,
	const StucObject *pObj,
	const StucAttribIndexedArr *pIndexedAttribs,
	float wScale,
	float receiveLen
) {
	PixErr err = PIX_ERR_SUCCESS;
	err = stucMapExportTargetAdd(
		pHandle,
		pMapArr,
		pObj,
		pIndexedAttribs,
		wScale,
		receiveLen
	);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

StucErr stucBlenderMapExportObjAdd(
	void *pHandle,
	const StucObject *pObj,
	const StucAttribIndexedArr *pIndexedAttribs
) {
	return stucMapExportObjAdd(pHandle, pObj, pIndexedAttribs);
}

StucErr stucBlenderMapExportUsgAdd(void *pHandle, StucUsg *pUsg) {
	return stucMapExportUsgAdd(pHandle, pUsg);
}

StucErr stucBlenderMapExportUsgCutoffAdd(void *pHandle, StucObject *pFlatCutoff) {
	return stucMapExportUsgCutoffAdd(pHandle, pFlatCutoff);
}

//TODO get this working again
PixErr stucBlenderMapFileLoadForEdit(
	const char *pName,
	I32 *pObjCount,
	StucObject **ppObjArr,
	I32 *pUsgCount,
	StucUsg **ppUsgArr,
	I32 *pFlatCutoffCount,
	StucObject **ppFlatCutoffArr,
	StucAttribIndexedArr *pIndexedAttribs
) {
	PixErr err = stucMapFileLoadForEdit(
		&stucCtx,
		pName,
		pObjCount,
		ppObjArr,
		pUsgCount,
		ppUsgArr,
		pFlatCutoffCount,
		ppFlatCutoffArr,
		pIndexedAttribs
	);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderMapFileUnload(const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;

	MapEntry *pEntry = NULL;
	err = mapEntryGet(pName, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (!pEntry) {
		return err;
	}

	err = mapEntryDestroy(pName);
	PIX_ERR_RETURN_IFNOT(err, "")
	return err;
}

typedef struct LoadState {
	PixtyStrArr *pDepDirs;
	StrWithLen pathBuf;
	I32 (* fpGetMapPath)(const char *, const PixtyStrArr *Dirs, char *, double *);
	void (* fpStoreMap)(
		const char *,
		const char *,
		double,
		StucMapStatus,
		const PixtyStrArr *
	);
} LoadState;

static
PixErr mapGet(
	void *pUserData,
	const char *pName,
	const char **ppFilepath,
	double *pTimestamp,
	StucMap * const ppMap
) {
	PixErr err = PIX_ERR_SUCCESS;
	LoadState *pState = pUserData;
	I32 len = (I32)strnlen(pState->pathBuf.pStr, PIXIO_PATH_MAX);
	memset(pState->pathBuf.pStr, 0, len);
	double timestamp = .0;
	I32 ret = pState->fpGetMapPath(pName, pState->pDepDirs, pState->pathBuf.pStr, pTimestamp);
	PIX_ERR_RETURN_IFNOT_COND(err, !ret, "unable to find map in provided directories");

	bool noPath = !pState->pathBuf.pStr[0];
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pName, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (pEntry && pEntry->pMap) {
		if (noPath) {
			//loaded map is up to date
			*ppMap = pEntry->pMap;
			return err;
		}
		else {
			err = stucMapFileUnload(&stucCtx, pEntry->pMap);
			pEntry->pMap = NULL;
			PIX_ERR_RETURN_IFNOT(err, "");
		}
	}
	PIX_ERR_ASSERT("", !noPath);
	*ppFilepath = pState->pathBuf.pStr;
	return err;
}

static
PixErr mapStore(
	void *pUserData,
	const char *pName,
	const char *pFilepath,
	double timestamp,
	StucMap pMap,
	StucMapStatus status,
	const PixtyStrArr *pDeps
) {
	PixErr err = PIX_ERR_SUCCESS;
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pName, &pEntry, pMap);
	PIX_ERR_RETURN_IFNOT(err, "");
	((LoadState *)pUserData)->fpStoreMap(pName, pFilepath, timestamp, status, pDeps);
	return err;
}

PixErr stucBlenderMapFileLoad(
	const char *pFilepath,
	const char *pName,
	F64 timestamp,
	PixtyStrArr *pDepDirs,
	I32 (* fpGetMapPath)(const char *, const PixtyStrArr *Dirs, char *, double *),
	void (* fpStoreMap)(
		const char *,
		const char *,
		double,
		StucMapStatus,
		const PixtyStrArr *
	),
	bool dirty 
) {
	PixErr err = PIX_ERR_SUCCESS;
	LoadState state = {
		.pDepDirs = pDepDirs,
		.fpGetMapPath = fpGetMapPath,
		.fpStoreMap = fpStoreMap,
		.pathBuf.pStr = calloc(PIXIO_PATH_MAX, 1)
	};
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pName, &pEntry, NULL);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	if (pEntry) {
		err = stucMapFileUnload(&stucCtx, pEntry->pMap);
		pEntry->pMap = NULL;
		PIX_ERR_THROW_IFNOT(err, "", 0);
	}
	StucMapLoad *pHandle = NULL;
	err = stucMapFileLoadInit(
		&stucCtx,
		&pHandle,
		pFilepath,
		timestamp,
		&state,
		mapGet, mapStore
	);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	err = stucMapFileLoadDeps(pHandle);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	StucMapStatus status = 0;
	err = stucMapFileLoadGetDepStatus(pHandle, &status);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	switch (status) {
		case STUC_MAP_LOADED:
			if (!dirty) {
				break; //file is already up to date
			}
			//v otherwise fallthrough v
		case STUC_MAP_PENDING_LOAD:
			err = stucMapFileLoad(pHandle);
			PIX_ERR_THROW_IFNOT(err, "", 0);
			break;
		case STUC_MAP_ERROR:
		case STUC_MAP_MISSING_DEP:
			PIX_ERR_THROW(err, "unable to load one or more dependencies", 0);
	}
	PIX_ERR_CATCH(0, err,
		stucBlenderMapFileUnload(pName);
	);
	if (state.pathBuf.pStr) {
		free(state.pathBuf.pStr);
	}
	return err;
}

PixErr stucBlenderMapMeshGet(
	const char *pMap,
	StucMesh **ppMesh,
	StucAttribIndexedArr **ppIdxAttribs,
	bool forRender
) {
	PixErr err = PIX_ERR_SUCCESS;
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pMap, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	PIX_ERR_RETURN_IFNOT_COND(err, pEntry, "");
	if (forRender) {
		PIX_ERR_RETURN_IFNOT_COND(err, pEntry->meshRender.faceCount, "");
		*ppMesh = &pEntry->meshRender;
		err = stucMapFileMeshGet(&stucCtx, pEntry->pMap, NULL, ppIdxAttribs);
		PIX_ERR_THROW_IFNOT(err, "", 0);
	}
	else {
		err = stucMapFileMeshGet(&stucCtx, pEntry->pMap, ppMesh, ppIdxAttribs);
		PIX_ERR_THROW_IFNOT(err, "", 0);
	}
	PIX_ERR_CATCH(0, err,
		*ppMesh = NULL;
		*ppIdxAttribs = NULL;
	);
	return err;
}

PixErr stucBlenderMeshPrepForRender(StucMesh *pMesh, bool triangulate) {
	PixErr err = PIX_ERR_SUCCESS;
	if (triangulate) {
		err = stucMeshTriangulate(&stucCtx, pMesh);
		PIX_ERR_RETURN_IFNOT(err, "");
	}
	//else assume already triangulated
	PIX_ERR_ASSERT(
		"tangent and tsign attribs must be mutually inclusive",
		!(
			pMesh->activeAttribs[STUC_ATTRIB_USE_TANGENT].active ^
			pMesh->activeAttribs[STUC_ATTRIB_USE_TSIGN].active
		)
	);
	if (!pMesh->activeAttribs[STUC_ATTRIB_USE_TANGENT].active) {
		err = stucMeshBuildTangentsForTris(&stucCtx, pMesh);
		PIX_ERR_RETURN_IFNOT(err, "");
	}
	err = stucMeshAttribsCornerToVert(&stucCtx, pMesh);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderMeshCpy(StucMesh *pDest, const StucMesh *pSrc) {
	StucErr err = PIX_ERR_SUCCESS;
	err = stucMeshAllocCopy(&stucCtx, pDest, pSrc, true);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	PIX_ERR_CATCH(0, err,
		stucMeshDestroy(&stucCtx, pDest);
	);
	return err;
}

PixErr stucBlenderMapMeshRenderGet(
	const char *pMap,
	StucMesh **ppMesh,
	StucAttribIndexedArr **ppIdxAttribs
) {
	PixErr err = PIX_ERR_SUCCESS;
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pMap, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	PIX_ERR_RETURN_IFNOT_COND(err, pEntry, "");
	return err;
}

PixErr stucBlenderMapMeshRenderUpdate(const char *pMap) {
	PixErr err = PIX_ERR_SUCCESS;
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pMap, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	PIX_ERR_RETURN_IFNOT_COND(err, pEntry, "");

	stucMeshDestroy(&stucCtx, &pEntry->meshRender);
	pEntry->meshRender = (StucMesh){0};

	const StucMesh *pMesh = NULL;
	err = stucMapFileMeshGet(&stucCtx, pEntry->pMap, &pMesh, NULL);
	PIX_ERR_RETURN_IFNOT_COND(err, pMesh, "");
	err = stucBlenderMeshCpy(&pEntry->meshRender, pMesh);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	err = stucBlenderMeshPrepForRender(&pEntry->meshRender, true);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	PIX_ERR_CATCH(0, err,
		stucMeshDestroy(&stucCtx, &pEntry->meshRender);
		pEntry->meshRender = (StucMesh){0};
	);
	return err;
}

PixErr stucBlenderQueryCommonAttribs(
	const StucMesh *pMesh,
	const StucMap pMap,
	StucBlendOptArr *pBlendOptArr
) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, pMesh && pMap && pBlendOptArr, "");
	err = stucQueryCommonAttribs(&stucCtx, pMap, pMesh, pBlendOptArr);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderMapToMesh(
	PixthJob *pJobHandle,
	StucMapArr *pMapArr,
	StucMesh *pMesh,
	StucAttribIndexedArr *pInIndexedAttribs,
	StucMesh *pOutMesh,
	StucAttribIndexedArr *pOutIndexedAttribs,
	float wScale,
	float receiveLen,
	I32 *pPushedJobs,
	bool triangulate
) {
	PixErr err = PIX_ERR_SUCCESS;
	err = stucQueueMapToMesh(
		&stucCtx,
		pJobHandle,
		pMapArr,
		pMesh, pInIndexedAttribs,
		pOutMesh, pOutIndexedAttribs,
		wScale,
		receiveLen,
		triangulate
	);
	PIX_ERR_RETURN_IFNOT(err, "");
	*pPushedJobs = true;
	return err;
}

PixErr stucBlenderDestroyBlendOptArr(StucBlendOptArr *pBlendOptArr) {
	PixErr err = stucDestroyBlendOptArr(&stucCtx, pBlendOptArr);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

void stucBlenderCopyMeshCore(StucMesh *pDest, StucMesh *pSrc) {
	memcpy(
		pDest->pFaces,
		pSrc->pFaces,
		sizeof(I32) * (pDest->faceCount + 1)
	);
	memcpy(
		pDest->pCorners,
		pSrc->pCorners,
		sizeof(I32) * pDest->cornerCount
	);
	StucAttrib *pSrcPos =
		pSrc->vertAttribs.pArr +
		pSrc->activeAttribs[STUC_ATTRIB_USE_POS].idx;
	StucAttrib *pDestPos= 
		pDest->vertAttribs.pArr +
		pDest->activeAttribs[STUC_ATTRIB_USE_POS].idx;
	memcpy(
		pDestPos->core.pData,
		pSrcPos->core.pData,
		sizeof(Stuc_V3_F32) * pDest->vertCount
	);
}

static
PixErr copyAttribs(StucAttribArray *pA, StucAttribArray *pB, I32 dataLen) {
	PixErr err = PIX_ERR_SUCCESS;
	if (!pA || !pB) {
		return err;
	}
	for (I32 i = 0; i < pA->count; ++i) {
		StucAttrib* pBEntry;
		stucGetAttrib(pA->pArr[i].core.name, pB, &pBEntry);
		PIX_ERR_RETURN_IFNOT_COND(err, pBEntry, "missing attrib");
		I32 attribSize = 0;
		stucGetAttribSize(&pA->pArr[i].core, &attribSize);
		memcpy(pBEntry->core.pData, pA->pArr[i].core.pData, attribSize * dataLen);
	}
	return err;
}

PixErr stucBlenderCopyMeshAttribs(StucMesh *pDest, StucMesh *pSrc) {
	PixErr err = PIX_ERR_SUCCESS;
	err = copyAttribs(
		&pSrc->faceAttribs,
		&pDest->faceAttribs,
		pSrc->faceCount
	);
	PIX_ERR_RETURN_IFNOT(err, "");
	err = copyAttribs(
		&pSrc->cornerAttribs,
		&pDest->cornerAttribs,
		pSrc->cornerCount
	);
	PIX_ERR_RETURN_IFNOT(err, "");
	//TODO re-add copying of vert attribs
	return err;
}

PixErr stucBlenderObjArrDestroy(StucObjArr *pObjArr) {
	return stucObjArrDestroy(&stucCtx, pObjArr);
}

PixErr stucBlenderUsgArrDestroy(I32 count, StucUsg *pUsgArr) {
	PixErr err = stucUsgArrDestroy(&stucCtx, count, pUsgArr);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderMeshDestroy(StucMesh *pMesh) {
	PixErr err = stucMeshDestroy(&stucCtx, pMesh);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderWaitForJobs(
	I32 count,
	PixthJob *pJobHandles,
	bool wait,
	bool *pDone
) {
	PixErr err = stucWaitForJobs(&stucCtx, count, pJobHandles, wait, pDone);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (wait || *pDone) {
		err = stucJobGetErrs(&stucCtx, count, pJobHandles);
		PIX_ERR_RETURN_IFNOT(err, "");
	}
	return err;
}

void stucBlenderDestroy() {
	if (mapTable.pTable) {
		pixuctHTableDestroy(&mapTable);
	}
	if (targetCache.pTable) {
		pixuctHTableDestroy(&targetCache);
	}
	stucContextDestroy(&stucCtx);
	return;
}

void stucBlenderCallFree(void *pData) {
	if (pData) {
		free(pData);
	}
}

//TODO why isn't this returning an error?
void *stucBlenderMapHandleGet(const char *pName) {
	MapEntry *pEntry = NULL;
	mapEntryGet(pName, &pEntry, NULL);
	return pEntry ? pEntry->pMap : NULL;
}

PixErr stucBlenderAttribGet(
	StucMesh *pMesh,
	const char *pName,
	StucAttrib **ppAttrib,
	int32_t *pIdx,
	StucDomain *pDomain
) {
	return stucAttribGetAllDomains(&stucCtx, pMesh, pName, ppAttrib, pIdx, pDomain);
}

PixErr stucBlenderTargetCacheRemove(I32 id) {
	PixErr err = PIX_ERR_SUCCESS;

	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, NULL, &pEntry, NULL, NULL, MESH_CACHE_NONE);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (!pEntry) {
		return err;
	}

	err = targetEntryDestroy(id);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderTargetCacheAdd(
	I32 id,
	F64 timestamp,
	StucMesh *pMesh,
	StucAttribIndexedArr *pIdxAttribs,
	TargetCacheType type
) {
	PixErr err = PIX_ERR_SUCCESS;
	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, &timestamp, &pEntry, pMesh, pIdxAttribs, type);
	PIX_ERR_RETURN_IFNOT(err, "");

	*pMesh = (StucMesh){0};
	if (pIdxAttribs) {
		*pIdxAttribs = (StucAttribIndexedArr){0};
	}
	return err;
}

PixErr stucBlenderTargetCacheGet(
	I32 id,
	F64 *pTimestamp,
	StucMesh **ppMesh,
	StucAttribIndexedArr **ppIdxAttribs,
	TargetCacheType *pType
) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, ppMesh || ppIdxAttribs, "");
	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, NULL, &pEntry, NULL, NULL, MESH_CACHE_NONE);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (pEntry && pEntry->type != MESH_CACHE_NONE) {
		PIX_ERR_ASSERT("", pEntry->mesh.faceCount);
		if (ppMesh) {
			*ppMesh = &pEntry->mesh;
		}
		if (ppIdxAttribs) {
			*ppIdxAttribs = &pEntry->idxAttribs;
		}
		if (pTimestamp) {
			*pTimestamp = pEntry->timestamp;
		}
		*pType = pEntry->type;
	}
	return err;
}

PixErr stucBlenderTargetCacheClear(I32 id) {
	PixErr err = PIX_ERR_SUCCESS;
	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, NULL, &pEntry, NULL, NULL, MESH_CACHE_NONE);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (pEntry && pEntry->mesh.faceCount) {
		err = stucMeshDestroy(&stucCtx, &pEntry->mesh);
		PIX_ERR_RETURN_IFNOT(err, "");
		pEntry->mesh = (StucMesh){0};
		err = stucAttribIndexedArrDestroy(&stucCtx, &pEntry->idxAttribs);
		PIX_ERR_RETURN_IFNOT(err, "");
		pEntry->idxAttribs = (StucAttribIndexedArr){0};
		pEntry->type = MESH_CACHE_NONE;
	}
	return err;
}

static
void copyCorners(const StucMesh *pMesh, PixtyI32Arr *pCorners, I32 start, I32 toCpy) {
	I32 newCount = pCorners->count + toCpy;
	PIXALC_DYN_ARR_RESIZE(I32, &allocPtrs, pCorners, newCount);
	memcpy(
		pCorners->pArr + pCorners->count,
		pMesh->pCorners + start,
		sizeof(I32) * toCpy
	);
	pCorners->count = newCount;
}

PixErr stucBlenderCornersForMat(StucMesh *pMesh, I32 mat, PixtyI32Arr *pCorners) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, pMesh && pCorners && mat >= 0, "");
	PIX_ERR_ASSERT("mesh must be triangulated", !pMesh->pFaces);

	StucAttrib *pAttrib = NULL;
	err = stucAttribActiveGet(&stucCtx, pMesh, STUC_ATTRIB_USE_IDX, &pAttrib);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	I8 *pMat = pAttrib->core.pData;
	I32 start = -1;
	for (I32 i = 0; i < pMesh->cornerCount; ++i) {
		I32 tri = i / 3;
		if (pMat[tri] == mat) {
			if (start < 0) {
				start = i;
			}
		}
		else if (start >= 0) {
			copyCorners(pMesh, pCorners, start, i - start);
			start = -1;
		}
	}
	if (start >= 0) {
		copyCorners(pMesh, pCorners, start, pMesh->cornerCount - start);
	}
	PIX_ERR_CATCH(0, err,
		if (pCorners->pArr) {
			free(pCorners->pArr);
			*pCorners = (PixtyI32Arr){0};
		}
	);
	return err;
}

PixErr stucBlenderEditOverlayCol(
	I32 edgeCount,
	const PixtyV2_I32 *pEdges,
	const float *pSelect,
	I32 vertCount,
	PixtyV4_F32 *pCol
) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, pCol && pEdges && pSelect, "");
	PIX_ERR_RETURN_IFNOT_COND(err, edgeCount > 0 && vertCount >= 2, "");
	const PixtyV4_F32 col =
		pixmV4F32DivideScalar((PixtyV4_F32){.d = {.0f, .0f, .0f, 255.0f}}, 255.0f);
	const PixtyV4_F32 colSelect =
		pixmV4F32DivideScalar((PixtyV4_F32){.d = {227.0f, 62.0f, 191.0f, 255.0f}}, 255.0f);
	for (I32 i = 0; i < edgeCount; ++i) {
		for (I32 j = 0; j < 2; ++j) {
			I32 vert = pEdges[i].d[j];
			PIX_ERR_ASSERT("", vert < vertCount);
			if (pCol[vert].d[0] != colSelect.d[0]) {
				pCol[vert] = pSelect[i] ? colSelect : col;
			}
		}
	}
	return err;
}

PixErr stucBlenderMeshCastSel(
	const StucMesh *pMesh,
	F32 *pSelCorners,
	const I8 *pSelFaces,
	F32 *pfSelEdges,
	const I8 *piSelEdges
) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(
		err,
		pMesh && pSelCorners && pSelFaces && pfSelEdges && piSelEdges,
		""
	);
	for (I32 i = 0; i < pMesh->faceCount; ++i) {
		I32 faceStart = pMesh->pFaces[i];
		PIX_ERR_ASSERT("", faceStart >= 0);
		I32 faceSize = pMesh->pFaces[i + 1] - faceStart;
		PIX_ERR_ASSERT("", faceSize >= 3 && faceStart + faceSize <= pMesh->cornerCount);
		for (I32 j = 0; j < faceSize; ++j) {
			pSelCorners[faceStart + j] = (F32)pSelFaces[i];
		}
	}
	for (I32 i = 0; i < pMesh->edgeCount; ++i) {
		pfSelEdges[i] = (F32)piSelEdges[i];
	}
	return err;
}

void stucBlenderArrayCast(
	void *pDest, I32 sizeDest,
	void *pSrc, I32 sizeSrc,
	I32 len
) {
	PIX_ERR_ASSERT("", sizeDest < sizeSrc && sizeDest > 0);
	for (I32 i = 0; i < len; ++i) {
		memcpy(
			(U8 *)pDest + i * sizeDest,
			(U8 *)pSrc + i * sizeSrc,
			sizeDest
		);
	}
}

I32 stucBlenderShmNameMaxLen() {
	return PIXIO_SHM_NAME_MAX_LEN;
}

PixErr stucBlenderSceneExportInit(PixioShmCtx *pShmCtx, char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmOpenServer(pShmCtx, "STUC", pName);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneImportInit(PixioShmCtx *pShmCtx, char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmOpenClient(pShmCtx, pName);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneExportStr(PixioShmCtx *pShmCtx, ShmDesc desc, const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmSend(pShmCtx, (I32)strnlen(pName, pixioPathMaxGet()), desc, pName);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneExportMesh(PixioShmCtx *pShmCtx, const StucMesh *pMesh) {
	PixErr err = PIX_ERR_SUCCESS;
	StucMesh buf = *pMesh;
	buf.pFaces = NULL;
	buf.pCorners = NULL;
	buf.pEdges = NULL;
	for (StucDomain domain = STUC_DOMAIN_FACE; domain <= STUC_DOMAIN_VERT; ++domain) {
		StucAttribArray *pArr = NULL;
		err = stucAttribArrGet(&stucCtx, &buf, domain, &pArr);
		PIX_ERR_RETURN_IFNOT(err, "");
		pArr->pArr = NULL;
	}
	I32 size = sizeof(StucMesh);
	err = pixioShmSend(pShmCtx, size, STUCB_SHM_MESH, &buf);
	PIX_ERR_RETURN_IFNOT(err, "");
	size = sizeof(I32) * (pMesh->faceCount + 1);
	err = pixioShmSend(pShmCtx, size, STUCB_SHM_FACES, pMesh->pFaces);
	PIX_ERR_RETURN_IFNOT(err, "");
	size = sizeof(I32) * pMesh->cornerCount;
	err = pixioShmSend(pShmCtx, size, STUCB_SHM_CORNERS, pMesh->pCorners);
	PIX_ERR_RETURN_IFNOT(err, "");
	size = sizeof(I32) * pMesh->cornerCount;
	err = pixioShmSend(pShmCtx, size, STUCB_SHM_EDGES, pMesh->pEdges);
	PIX_ERR_RETURN_IFNOT(err, "");
	for (StucDomain domain = STUC_DOMAIN_FACE; domain <= STUC_DOMAIN_VERT; ++domain) {
		const StucAttribArray *pArr = NULL;
		err = stucAttribArrGetConst(&stucCtx, pMesh, domain, &pArr);
		PIX_ERR_RETURN_IFNOT(err, "");
		for (I32 i = 0; i < pArr->count; ++i) {
			size = sizeof(StucAttrib);
			{
				StucAttrib cpy = pArr->pArr[i];
				cpy.core.pData = NULL;
				err = pixioShmSend(pShmCtx, size, STUCB_SHM_ATTRIB, &cpy);
				PIX_ERR_RETURN_IFNOT(err, "");
			}
			I32 typeSize = 0;
			I32 domainCount = 0;
			err = stucGetAttribSize(&pArr->pArr[i].core, &typeSize);
			PIX_ERR_RETURN_IFNOT(err, "");
			err = stucDomainCountGet(&stucCtx, pMesh, domain, &domainCount);
			PIX_ERR_RETURN_IFNOT(err, "");
			size = typeSize * domainCount;
			err = pixioShmSend(
				pShmCtx,
				size,
				STUCB_SHM_ATTRIB_DATA,
				pArr->pArr[i].core.pData
			);
			PIX_ERR_RETURN_IFNOT(err, "");
		}
	}
	return err;
}

PixErr stucBlenderSceneExportObj(
	PixioShmCtx *pShmCtx,
	const char *pName,
	const StucObject *pObj
) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, pObj->pData->type == STUC_OBJECT_DATA_MESH, "");
	//max len of blend obj name is 64 as of writing (afaik
	I32 nameLen = (I32)strnlen(pName, 64);
	err = pixioShmSend(pShmCtx, nameLen, STUCB_SHM_OBJ, pName);
	PIX_ERR_RETURN_IFNOT(err, "");
	err = pixioShmSend(pShmCtx, sizeof(PixtyM4x4), STUCB_SHM_XFORM, pObj->transform.d);
	PIX_ERR_RETURN_IFNOT(err, "");
	err = stucBlenderSceneExportMesh(pShmCtx, (StucMesh *)pObj->pData);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneExportIdxAttribs(
	PixioShmCtx *pShmCtx,
	const StucAttribIndexedArr *pArr
) {
	PixErr err = PIX_ERR_SUCCESS;
	I32 size = sizeof(StucAttribIndexedArr);
	err = pixioShmSend(pShmCtx, size, STUCB_SHM_IDX_ATTRIB_ARR, pArr);
	PIX_ERR_RETURN_IFNOT(err, "");
	for (I32 i = 0; i < pArr->count; ++i) {
		{
			StucAttribIndexed cpy = pArr->pArr[i];
			cpy.core.pData = NULL;
			size = sizeof(cpy);
			err = pixioShmSend(pShmCtx, size, STUCB_SHM_IDX_ATTRIB, &cpy);
			PIX_ERR_RETURN_IFNOT(err, "");
		}
		err = stucGetAttribSize(&pArr->pArr[i].core, &size);
		PIX_ERR_RETURN_IFNOT(err, "");
		size *= pArr->pArr[i].count;
		err = pixioShmSend(
			pShmCtx,
			size,
			STUCB_SHM_IDX_ATTRIB_DATA,
			pArr->pArr[i].core.pData
		);
		PIX_ERR_RETURN_IFNOT(err, "");
	}
	return err;
}

PixErr stucBlenderSceneImportStr(PixioShmCtx *pShmCtx, char *pStr) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmReceive(pShmCtx, pStr);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

static
PixErr sceneImport4ByteList(
	PixioShmCtx *pShmCtx,
	ShmDesc expectDesc,
	I32 count,
	void **ppDest
) {
	PixErr err = PIX_ERR_SUCCESS;
	I32 size = 0;
	ShmDesc desc = STUCB_SHM_NONE;
	err = pixioShmReceiveInit(pShmCtx, &size, (I32 *)&desc, NULL);
	PIX_ERR_RETURN_IFNOT_COND(err, desc == expectDesc && size == 4 * count, "");
	*ppDest = malloc(size);
	err = pixioShmReceive(pShmCtx, *ppDest);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneImportMesh(PixioShmCtx *pShmCtx, StucMesh *pMesh) {
	PixErr err = PIX_ERR_SUCCESS;
	I32 size = 0;
	ShmDesc desc = STUCB_SHM_NONE;
	err = pixioShmReceiveInit(pShmCtx, &size, (I32 *)&desc, NULL);
	PIX_ERR_RETURN_IFNOT_COND(err, desc == STUCB_SHM_MESH && size == sizeof(StucMesh), "");
	err = pixioShmReceive(pShmCtx, pMesh);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	err =
		sceneImport4ByteList(pShmCtx, STUCB_SHM_FACES, pMesh->faceCount + 1, &pMesh->pFaces);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	err =
		sceneImport4ByteList(pShmCtx, STUCB_SHM_CORNERS, pMesh->cornerCount, &pMesh->pCorners);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	err =
		sceneImport4ByteList(pShmCtx, STUCB_SHM_EDGES, pMesh->cornerCount, &pMesh->pEdges);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	for (StucDomain domain = STUC_DOMAIN_FACE; domain <= STUC_DOMAIN_VERT; ++domain) {
		StucAttribArray *pArr = NULL;
		err = stucAttribArrGet(&stucCtx, pMesh, domain, &pArr);
		PIX_ERR_THROW_IFNOT(err, "", 0);
		pArr->size = pArr->count;
		if (pArr->size) {
			pArr->pArr = malloc(sizeof(StucAttrib) * pArr->size);
		}
		for (I32 i = 0; i < pArr->count; ++i) {
			err = pixioShmReceiveInit(pShmCtx, &size, (I32 *)&desc, NULL);
			PIX_ERR_THROW_IFNOT_COND(err, desc == STUCB_SHM_ATTRIB && size == sizeof(StucAttrib), "", 0);
			err = pixioShmReceive(pShmCtx, pArr->pArr + i);
			PIX_ERR_THROW_IFNOT(err, "", 0);
			err = pixioShmReceiveInit(pShmCtx, &size, (I32 *)&desc, NULL);
			PIX_ERR_THROW_IFNOT_COND(err, desc == STUCB_SHM_ATTRIB_DATA && size > 0, "", 0);
			pArr->pArr[i].core.pData = malloc(size);
			err = pixioShmReceive(pShmCtx, pArr->pArr[i].core.pData);
			PIX_ERR_THROW_IFNOT(err, "", 0);
		}
	}
	PIX_ERR_CATCH(0, err,
		stucMeshDestroy(&stucCtx, pMesh);
	);
	return err;
}

PixErr stucBlenderSceneImportObj(PixioShmCtx *pShmCtx, StucObject *pObj) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmReceive(pShmCtx, pObj->transform.d);
	PIX_ERR_RETURN_IFNOT(err, "");
	err = stucBlenderSceneImportMesh(pShmCtx, (StucMesh *)pObj->pData);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneImportIdxAttribs(PixioShmCtx *pShmCtx, StucAttribIndexedArr *pArr) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmReceive(pShmCtx, pArr);
	pArr->size = pArr->count;
	if (!pArr->size) {
		return err;
	}
	pArr->pArr = malloc(sizeof(StucAttribIndexed) * pArr->size);
	for (I32 i = 0; i < pArr->count; ++i) {
		I32 size = 0;
		ShmDesc desc = STUCB_SHM_NONE;
		err = pixioShmReceiveInit(pShmCtx, &size, (I32 *)&desc, NULL);
		PIX_ERR_RETURN_IFNOT_COND(err,
			desc == STUCB_SHM_IDX_ATTRIB && size == sizeof(StucAttribIndexed),
			""
		);
		err = pixioShmReceive(pShmCtx, pArr->pArr + i);
		PIX_ERR_THROW_IFNOT(err, "", 0);
		err = pixioShmReceiveInit(pShmCtx, &size, (I32 *)&desc, NULL);
		PIX_ERR_RETURN_IFNOT_COND(err,
			desc == STUCB_SHM_IDX_ATTRIB_DATA && size > 0,
			""
		);
		pArr->pArr[i].core.pData = malloc(size);
		err = pixioShmReceive(pShmCtx, pArr->pArr[i].core.pData);
		PIX_ERR_THROW_IFNOT(err, "", 0);
	}
	PIX_ERR_CATCH(0, err,
		stucAttribIndexedArrDestroy(&stucCtx, pArr);
	);
	return err;
}


PixErr stucBlenderSceneImportQuery(
	PixioShmCtx *pShmCtx,
	I32 *pSize,
	ShmDesc *pDesc,
	bool *pClose
) {
	return pixioShmReceiveInit(pShmCtx, pSize, (I32 *)pDesc, pClose);
}

PixErr stucBlenderSceneExportDestroy(PixioShmCtx *pShmCtx) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmCloseServer(pShmCtx);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderSceneImportDestroy(PixioShmCtx *pShmCtx) {
	PixErr err = PIX_ERR_SUCCESS;
	err = pixioShmCloseClient(pShmCtx);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderThreadPoolLogDump(const char *pPath) {
	PixErr err = PIX_ERR_SUCCESS;
#ifdef STUC_DEBUG_UTILS
	err = stucThreadPoolLogDump(&stucCtx, pPath);
	PIX_ERR_RETURN_IFNOT(err, "");
#else
	PIX_ERR_RETURN(err, "logging disabled");
#endif
	return err;
}
