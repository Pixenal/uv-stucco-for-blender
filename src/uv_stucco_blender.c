/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#define HANDLE_TABLE_SIZE 64

#include <string.h>

#include <pixenals_io_utils.h>

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

typedef struct HandleEntry {
	struct HandleEntry *pNext;
	struct HandleEntry *pPrev;
	StucMap pHandle;
} HandleEntry;

typedef struct HandleBucket {
	HandleEntry *pList;
} HandleBucket;

static StucContext pStucCtx = NULL;
static HandleBucket handleTable[HANDLE_TABLE_SIZE] = {0};

static
U32 fnvHash(unsigned char *value, I32 valueSize, U32 size) {
	U32 hash = 2166136261;
	for (I32 i = 0; i < valueSize; ++i) {
		hash ^= value[i];
		hash *= 16777619;
	}
	hash %= size;
	return hash;
}

//returns null if doesn't exist
static
HandleEntry *getHandle(HandleBucket **pOutBucket, const char *pName) {
	I32 pathLength = (I32)strlen(pName);
	I32 hash = fnvHash((unsigned char *)pName, pathLength, HANDLE_TABLE_SIZE);
	HandleBucket *pBucket = handleTable + hash;
	if (pOutBucket) {
		*pOutBucket = pBucket;
	}
	HandleEntry *pEntry = pBucket->pList;
	while (pEntry) {
		if (!pEntry->pHandle) {
			break;
		}
		const char *pMapName = NULL;
		stucMapNameGet(pStucCtx, pEntry->pHandle, &pMapName);
		if (!strcmp(pName, pMapName)) {
			return pEntry;
		}
		pEntry = pEntry->pNext;
	}
	return NULL;
}

static
void handleDestroy(HandleEntry *pEntry) {
	if (pEntry->pHandle) {
		stucMapFileUnload(pStucCtx, pEntry->pHandle);
	}
	*pEntry = (HandleEntry) {0};
}

static
void handleTableDestroy() {
	for (I32 i = 0; i < HANDLE_TABLE_SIZE; ++i) {
		HandleEntry *pEntry = handleTable[i].pList;
		while (pEntry) {
			HandleEntry *pNext = pEntry->pNext;
			handleDestroy(pEntry);
			free(pEntry);
			pEntry = pNext;
		};
		handleTable[i].pList = NULL;
	}
}

void stucBlenderInit() {
	stucContextInit(&pStucCtx, NULL, NULL, NULL, NULL, NULL);
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

//returns null if handle already exists for this map
static
HandleEntry *handleAdd(const char *pName) {
	HandleBucket *pBucket = NULL;
	HandleEntry *pEntry = getHandle(&pBucket, pName);
	if (pEntry) {
		return NULL;
	}
	pEntry = pBucket->pList;
	if (!pEntry) {
		pBucket->pList = calloc(1, sizeof(HandleEntry));
		return pBucket->pList;
	}
	while (pEntry->pNext) {
		pEntry = pEntry->pNext;
	}
	pEntry->pNext = calloc(1, sizeof(HandleEntry));
	pEntry->pNext->pPrev = pEntry;
	return pEntry->pNext;
}

PixErr stucBlenderMapFileUnload(const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	HandleBucket *pBucket = NULL;
	HandleEntry *pEntry = getHandle(&pBucket, pName);
	if (!pEntry) {
		return err;
	}
	HandleEntry *pNext = pEntry->pNext;
	HandleEntry *pPrev = pEntry->pPrev;
	handleDestroy(pEntry);
	if (pPrev) {
		pPrev->pNext = pNext;
		pNext->pPrev = pPrev;
	}
	else {
		pBucket->pList = pNext;
		if (pNext) {
			pNext->pPrev = NULL;
		}
	}
	free(pEntry);
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
	HandleEntry *pEntry = getHandle(NULL, pName);
	if (pEntry && pEntry->pHandle) {
		if (noPath) {
			//loaded map is up to date
			*ppMap = pEntry->pHandle;
			return err;
		}
		else {
			err = stucMapFileUnload(pStucCtx, pEntry->pHandle);
			pEntry->pHandle = NULL;
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
	HandleEntry *pEntry = getHandle(NULL, pName);
	if (!pEntry) {
		pEntry = handleAdd(pName);
	}
	PIX_ERR_ASSERT("", !pEntry->pHandle);
	pEntry->pHandle = pMap;
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
	HandleEntry *pEntry = getHandle(NULL, pName);
	if (pEntry) {
		err = stucBlenderMapFileUnload(pName);
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
	HandleEntry *pEntry = getHandle(NULL, pMap);
	PIX_ERR_RETURN_IFNOT_COND(err, pEntry, "");
	return stucMapFileMeshGet(pStucCtx, pEntry->pHandle, ppMesh);
}

PixErr stucBlenderQueryCommonAttribs(
	StucMesh *pMesh,
	const char *pMap,
	StucBlendOptArr *pBlendOptArr
) {
	PixErr err = PIX_ERR_SUCCESS;
	HandleEntry *pEntry = getHandle(NULL, pMap);
	if (!pEntry) {
		return err;
	}
	err = stucQueryCommonAttribs(pStucCtx, pEntry->pHandle, pMesh, pBlendOptArr);
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
	I32 *pPushedJobs

) {
	PixErr err = PIX_ERR_SUCCESS;
	err = stucQueueMapToMesh(
		pStucCtx,
		ppJobHandle,
		pMapArr,
		pMesh, pInIndexedAttribs,
		pOutMesh, pOutIndexedAttribs,
		wScale,
		receiveLen
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
	handleTableDestroy();
	stucContextDestroy(pStucCtx);
	return;
}

void stucBlenderCallFree(void *pData) {
	if (pData) {
		free(pData);
	}
}

void *stucBlenderMapHandleGet(const char *pName) {
	HandleEntry *pEntry = getHandle(NULL, pName);
	return pEntry ? pEntry->pHandle : NULL;
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
