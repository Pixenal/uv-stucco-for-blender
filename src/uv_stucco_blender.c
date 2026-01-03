/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#define HANDLE_TABLE_SIZE 64

#include <string.h>

#include <pixenals_io_utils.h>
#include <pixenals_structs.h>

#include <uv_stucco_blender.h>

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
} MapEntry;

typedef struct TargetEntry {
	PixuctHTableEntryCore core;
	StucMesh mesh;
	I32 id;
} TargetEntry;

static PixalcFPtrs allocPtrs = {
	.fpCalloc = calloc,
	.fpMalloc = malloc,
	.fpRealloc = realloc,
	.fpFree = free
};
static StucContext pStucCtx = NULL;
static PixErr tableErr = PIX_ERR_SUCCESS;
static PixuctHTable mapTable = {0};
static PixuctHTable targetCache = {0};

static
void clearMapEntry(void *pUserData, PixuctHTableEntryCore *pCore, const void *pKeyData) {
	MapEntry *pEntry = (MapEntry *)pCore;
	if (pEntry->pMap) {
		*(PixErr *)pUserData = stucMapFileUnload(pStucCtx, pEntry->pMap);
		pEntry->pMap = NULL;
	}
}

static
void clearTargetEntry(void *pUserData, PixuctHTableEntryCore *pCore, const void *pKeyData) {
	TargetEntry *pEntry = (TargetEntry *)pCore;
	if (pEntry->mesh.faceCount) {
		*(PixErr *)pUserData = stucMeshDestroy(pStucCtx, &pEntry->mesh);
	}
}

static
bool cmpMap(
	const PixuctHTableEntryCore *pCore,
	const void *pKeyData,
	const void *pInitInfo
) {
	const char *pName = NULL;
	//TODO v pass userdata to cmp fp in htable get func, so error can be passed out here v
	stucMapNameGet(pStucCtx, ((MapEntry *)pCore)->pMap, &pName);
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
	((TargetEntry *)pCore)->id = *(I32 *)pKeyData;
	((TargetEntry *)pCore)->mesh = *(StucMesh *)pInitInfo;
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
		stucKeyFromPath,
		NULL,
		pMap ? initMapEntry : NULL,
		cmpMap
	);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	return err;
}

static
PixErr targetEntryGet(I32 id, TargetEntry **ppEntry, StucMesh *pMesh) {
	PixErr err = PIX_ERR_SUCCESS;
	SearchResult result = pixuctHTableGet(
		&targetCache,
		0,
		&id,
		ppEntry,
		!!pMesh,
		pMesh,
		stucKeyFromI32,
		NULL,
		pMesh ? initTargetEntry : NULL,
		cmpTarget
	);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	if (result == PIX_SEARCH_FOUND && pMesh) {
		PIX_ERR_ASSERT("", *ppEntry);
		if ((*ppEntry)->mesh.faceCount) {
			err = stucMeshDestroy(pStucCtx, &(*ppEntry)->mesh);
			PIX_ERR_RETURN_IFNOT(err, "");
		}
		(*ppEntry)->mesh = *pMesh;
	}	
	return err;
}

static
PixErr mapEntryDestroy(const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	pixuctHTableRemove(&mapTable, 0, pName, stucKeyFromPath, cmpMap, clearMapEntry);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	return err;
}

static
PixErr targetEntryDestroy(I32 id) {
	PixErr err = PIX_ERR_SUCCESS;
	pixuctHTableRemove(&targetCache, 0, &id, stucKeyFromI32, cmpTarget, clearTargetEntry);
	PIX_ERR_RETURN_IFNOT_COND(err, tableErr == PIX_ERR_SUCCESS, "");
	return err;
}

void stucBlenderInit() {
	stucContextInit(&pStucCtx, NULL, NULL, NULL, NULL, NULL);
	pixuctHTableInit(
		&allocPtrs,
		&mapTable,
		HANDLE_TABLE_SIZE,
		(PixtyI32Arr){.pArr = (I32[]){sizeof(MapEntry)}, .count = 1},
		&tableErr
	);
	pixuctHTableInit(
		&allocPtrs,
		&targetCache,
		HANDLE_TABLE_SIZE,
		(PixtyI32Arr){.pArr = (I32[]){sizeof(TargetEntry)}, .count = 1},
		&tableErr
	);
}

StucErr stucBlenderMapExportInit(
	void **ppHandle,
	const char *pPath,
	bool compress
) {
	return stucMapExportInit(pStucCtx, (StucMapExport **)ppHandle, pPath, compress);
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
		pStucCtx,
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
	I32 len = strnlen(pState->pathBuf.pStr, PIXIO_PATH_MAX);
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
			err = stucMapFileUnload(pStucCtx, pEntry->pMap);
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
		err = stucMapFileUnload(pStucCtx, pEntry->pMap);
		pEntry->pMap = NULL;
		PIX_ERR_THROW_IFNOT(err, "", 0);
	}
	StucMapLoad *pHandle = NULL;
	err = stucMapFileLoadInit(
		pStucCtx,
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

PixErr stucBlenderMapMeshGet(const char *pMap, StucMesh **ppMesh) {
	PixErr err = PIX_ERR_SUCCESS;
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pMap, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	PIX_ERR_RETURN_IFNOT_COND(err, pEntry, "");
	return stucMapFileMeshGet(pStucCtx, pEntry->pMap, ppMesh);
}

PixErr stucBlenderQueryCommonAttribs(
	StucMesh *pMesh,
	const char *pMap,
	StucBlendOptArr *pBlendOptArr
) {
	PixErr err = PIX_ERR_SUCCESS;
	MapEntry *pEntry = NULL;
	err = mapEntryGet(pMap, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (!pEntry) {
		return err;
	}
	err = stucQueryCommonAttribs(pStucCtx, pEntry->pMap, pMesh, pBlendOptArr);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderMapToMesh(
	void **ppJobHandle,
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
		pStucCtx,
		ppJobHandle,
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
	PixErr err = stucDestroyBlendOptArr(pStucCtx, pBlendOptArr);
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
	return stucObjArrDestroy(pStucCtx, pObjArr);
}

PixErr stucBlenderUsgArrDestroy(I32 count, StucUsg *pUsgArr) {
	PixErr err = stucUsgArrDestroy(pStucCtx, count, pUsgArr);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderMeshDestroy(StucMesh *pMesh) {
	PixErr err = stucMeshDestroy(pStucCtx, pMesh);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderWaitForJobs(
	I32 count,
	void **ppJobHandles,
	bool wait,
	bool *pDone
) {
	PixErr err = stucWaitForJobs(pStucCtx, count, ppJobHandles, wait, pDone);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (wait || *pDone) {
		err = stucJobGetErrs(pStucCtx, count, &ppJobHandles);
		stucJobDestroyHandles(pStucCtx, count, ppJobHandles);
		PIX_ERR_RETURN_IFNOT(err, "");
	}
	return err;
}

void stucBlenderDestroy() {
	pixuctHTableDestroy(&mapTable);
	pixuctHTableDestroy(&targetCache);
	stucContextDestroy(pStucCtx);
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
	return stucAttribGetAllDomains(pStucCtx, pMesh, pName, ppAttrib, pIdx, pDomain);
}

PixErr stucBlenderTargetCacheRemove(I32 id) {
	PixErr err = PIX_ERR_SUCCESS;
	err = targetEntryDestroy(id);
	PIX_ERR_RETURN_IFNOT(err, "");
	return err;
}

PixErr stucBlenderTargetCacheAdd(I32 id, StucMesh *pMesh) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_ASSERT("", pMesh->faceCount);
	err = stucMeshAttribsCornerToVert(pStucCtx, pMesh);
	PIX_ERR_RETURN_IFNOT(err, "");

	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, &pEntry, pMesh);
	PIX_ERR_RETURN_IFNOT(err, "");

	*pMesh = (StucMesh){0};
	return err;
}

PixErr stucBlenderTargetCacheGet(I32 id, StucMesh **ppMesh) {
	PixErr err = PIX_ERR_SUCCESS;
	PIX_ERR_RETURN_IFNOT_COND(err, ppMesh, "");
	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (pEntry && pEntry->mesh.faceCount) {
		*ppMesh = &pEntry->mesh;
	}
	return err;
}

PixErr stucBlenderTargetCacheClear(I32 id) {
	PixErr err = PIX_ERR_SUCCESS;
	TargetEntry *pEntry = NULL;
	err = targetEntryGet(id, &pEntry, NULL);
	PIX_ERR_RETURN_IFNOT(err, "");
	if (pEntry && pEntry->mesh.faceCount) {
		err = stucMeshDestroy(pStucCtx, &pEntry->mesh);
		pEntry->mesh = (StucMesh){0};
		PIX_ERR_RETURN_IFNOT(err, "");
	}
	return err;
}
