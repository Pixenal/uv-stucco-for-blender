/* 
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#define HANDLE_TABLE_SIZE 64

#include <string.h>

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
	char *pName;
} HandleEntry;

typedef struct HandleBucket {
	HandleEntry *pList;
} HandleBucket;

static StucContext pStucCtx;
static HandleBucket handleTable[HANDLE_TABLE_SIZE];

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
		if (!pEntry->pName) {
			break;
		}
		if (!strcmp(pName, pEntry->pName)) {
			return pEntry;
		}
		pEntry = pEntry->pNext;
	}
	return NULL;
}

static
void handleDestroy(HandleEntry *pEntry) {
	if (pEntry->pName) {
		free(pEntry->pName);
	}
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

PixErr stucBlenderMapFileLoad(const char *pFilepath, const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	HandleEntry *pEntry = handleAdd(pName);
	if (!pEntry) {
		stucBlenderMapFileReload(pFilepath, pName);
		return err;
	}
	//TODO add callback funcs to call
	err = stucMapFileLoad(pStucCtx, pFilepath, NULL, NULL);
	PIX_ERR_THROW_IFNOT(err, "", 0);
	I32 nameLength = (I32)strlen(pName) + 1;
	pEntry->pName = calloc(nameLength, 1);
	memcpy(pEntry->pName, pName, nameLength);
	PIX_ERR_CATCH(0, err,
		stucBlenderMapFileUnload(pName);
	);
	return err;
}

PixErr stucBlenderMapFileReload(const char *pFilepath, const char *pName) {
	PixErr err = PIX_ERR_SUCCESS;
	if (getHandle(NULL, pName)) {
		stucBlenderMapFileUnload(pName);
	}
	stucBlenderMapFileLoad(pFilepath, pName);
	return err;
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
	return getHandle(NULL, pName);
}
