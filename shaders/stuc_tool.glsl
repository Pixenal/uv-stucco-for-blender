/*
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

//note, stuc_utils.glsl and stuc_pbr.glsl are included before this file in stuc_frag.glsl

mat3 fakePerpMat(vec2 viewUv, mat3 viewMat, float fov, bool refr, vec3 n) {
	vec3 v = viewMat * normalize(vec3(viewUv * 2.0f - 1.0f, -fov));
	v = refr ? refract(v, n, 1.0f / 1.125f) : v;
	vec3 side = normalize(cross(v, viewMat[1]));
	vec3 up = cross(v, side);
	return mat3(side, up, v);
}

vec4 sparklePass(
	vec3 flowVec,
	mat3 pMat,
	float perpNoise,
	vec2 viewUv,
	mat3 viewMat,
	mat3 tbn,
	float time,
	float timeOffset,
	float fov,
	float fluidExp,
	float maskMul,
	vec2 offset,
	out vec3 flowOut
	) {
	float fovAdj = addSub(fov, pow(perpNoise, fluidExp), .125f * fov * fov);
	vec3 v = viewMat * normalize(vec3(viewUv * 2.0f - 1.0f, -fovAdj));
	float planeSign = .0f;
	float macroNoise = fakeEquirect(v, vec2(.0f), macroNoiseTex, 2.0f, planeSign).x * .25f - 1.0f;
	float fluid = flowEquirect(flowVec.xy * .75f, pMat, ((time + timeOffset) / 60.0f) * 6.0f, macroNoise * .4f, flowVec.z, microNoiseTex, flowOut).x;

	vec2 scroll = offset + time / 60.0f * -.5f;
	vec4 sparkle = fakeEquirect(v, scroll, sparkleTex, 8.0f, planeSign);
	int layerIdx = abs(int((time + timeOffset) * 2.0f * macroNoise + .5f) % 4);
	float sparkleMask =
		sparkle[layerIdx] -
		pow((1.0f - clamp((fluid - .5f) * 1.0f + .5f, .0f, 1.0f)), 4.0f) * .5f * maskMul;
	sparkleMask *= sparkleMask > .95f ? 4.0f : sparkleMask > .75 ? 2.0f : 1.0f;
	return vec4(sparkle.xyz, sparkleMask);
}

vec3 makeSparkles(mat3 pMat, mat3 viewMat, vec2 viewUv, mat3 tbn, float time, float timeOffset, out vec3 flowOut) {
	float planeSign = .0f;
	vec4 flowMap = fakeEquirect(pMat[2], vec2(time / 60.0f), flowTex, 2.0f, planeSign);
	vec3 flowVec = vec3(flowMap.xy * 2.0f - 1.0f, flowMap.z);
	float macroNoise = fakeEquirect(pMat[2], vec2(.0f), macroNoiseTex, 2.0f, planeSign).x * .25f - 1.0f;
	float perpNoise = flowEquirect(flowVec.xy * .75f, pMat, ((time + timeOffset) / 60.0f) * 6.0f, macroNoise * .4f, flowVec.z, microNoiseTex, flowOut).x;

	vec4 sparkleFfg = sparklePass(flowVec, pMat, perpNoise, viewUv, viewMat, tbn, time + .0f, timeOffset, .75f, .75f, 3.0f, vec2(.0f), flowOut);
	vec4 sparkleFg = sparklePass(flowVec, pMat, perpNoise, viewUv, viewMat, tbn, time + 45.0f, timeOffset, 1.125f, .5f, 2.5f, vec2(.0f, .5f), flowOut);
	vec4 sparkleMg = sparklePass(flowVec, pMat, perpNoise, viewUv, viewMat, tbn, time + 15.0f, timeOffset, 1.5f, .25f, 2.0f, vec2(.333f), flowOut);
	vec4 sparkleBg = sparklePass(flowVec, pMat, perpNoise, viewUv, viewMat, tbn, time + 30.0f, timeOffset, 2.0f, .125f, 1.5f, vec2(.666f), flowOut);

	vec3 col = sparkleBg.xyz * sparkleBg.w * .25f;
	col = max(col, sparkleMg.xyz * sparkleMg.w * .5f);
	col = max(col, sparkleFg.xyz * sparkleFg.w * .75f);
	col = max(col, sparkleFfg.xyz * sparkleFfg.w);

	return col;
}

vec3 multipassSparkles(mat3 pMat, mat3 tbn, mat3 viewMat, vec3 v, vec2 viewUv, float time) {
	const int sparklePasses = 6;
	vec3 sparkles = vec3(.0f);
	vec3 denom = vec3(.0f);
	for (int i = 0; i < sparklePasses; ++i) {
		float weight = 1.0f - (1.0f / float(sparklePasses) * float(i));
		vec3 flowOut = vec3(.0f);
		vec3 passCol = makeSparkles(pMat, viewMat, viewUv, tbn, time, pow(float(i) * 4.0f, 1.25f), flowOut);
		float luminance = .2126f * passCol.x + .7152 * passCol.y + .0722 * passCol.z;
		passCol = mix(passCol, (-v * .5f + .5f), .75f) * luminance;

		passCol *= 255.0f;
		vec3 ypbpr = rgbToYpbpr * passCol;
		
		float hue = atan(ypbpr.z, ypbpr.y) / (2.0f * PI);
		float chroma = length(vec2(ypbpr.y, ypbpr.z));
		hue = mod(hue + weight, 1.0f) * 2.0f * PI;

		chroma *= 10.0f;

		ypbpr.y = cos(hue) * chroma;
		ypbpr.z = sin(hue) * chroma;
		passCol = ypbprToRgb * ypbpr;
		passCol /= 255.0f;

		if (i == 0) {
			weight *= 2.0f;
		}
		else {
			weight = 1.0f - (1.0f - weight) * .75f;
		}
		sparkles += passCol * weight;
		denom += weight;
	}
	sparkles /= denom;

	float luminance = .2126f * sparkles.x + .7152 * sparkles.y + .0722 * sparkles.z;
	luminance = clamp(luminance, .0f, 1.0f);
	return pow(sparkles + 1.0f, vec3(4.0f)) - 1.0f;
}

void makeErrText(
	mat3 pMat,
	mat3 viewMat,
	vec2 viewUv,
	float aspect,
	float time,
	bool selFace,
	out bool textInner,
	out bool textOuter
) {
#ifdef USE_TIME
	float timeScroll = time / 60.0f;
#else
	float timeScroll = .0f;
#endif
	vec2 vFakeViewUv = vec2(dot(pMat[2], viewMat[0]), dot(pMat[2], viewMat[1]));
	vec2 textUv = viewUv + vFakeViewUv * .0625f;
	textUv = (textUv + timeScroll) * 12.0f * vec2(aspect, 1.0f);
	float text = texture(errTex, textUv).x;
	text *= selFace ? .0f : 1.0f;
	float sinTime = sin(time / 60.0f * 3.0f * PI) * .5f + .5f;
	float timeMask = invMul(sinTime, .05f);
	float timeMaskInner = invMul(sinTime, .1f);
	textInner = text > invMul(.425f, timeMaskInner);
	textOuter = text > invMul(.35f, timeMask);
}

vec3 makeErrMat(
	vec3 pos,
	mat3 tbn,
	mat3 viewMat,
	vec3 v,
	vec2 viewUv,
	float aspect,
	float time,
	bool selFace
) {
	float triUvSign = .0f;
	vec2 triUv = triPlanarUv(pos, tbn[2], triUvSign);

	mat3 pMat = fakePerpMat(viewUv, viewMat, 1.375f, true, tbn[2]);
	vec3 sparkles = multipassSparkles(pMat, tbn, viewMat, v, viewUv, time);

	bool textInner;
	bool textOuter;
	makeErrText(
		pMat,
		viewMat,
		viewUv,
		aspect,
		time,
		selFace,
		textInner, textOuter
	);

	vec2 vFakeUv = dirToUv(pMat[2]);
	vec3 blurEnv = 
		textureLod(envTex, vFakeUv, 4.0f).xyz + 
		textureLod(envTex, vFakeUv, 5.0f).xyz +
		textureLod(envTex, vFakeUv, 6.0f).xyz;
	blurEnv /= 3.0f;
	vec3 col = sparkles + blurEnv * .01f;
	col *= textOuter ? .0f : 1.0f;
	col = mix(col, (v * .5f + .5f), textInner ? 1.0f : .0f);
	col = col / (col + vec3(1.0f));
	return clamp(col, .0, 1.0f);
}