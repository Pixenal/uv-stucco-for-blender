/*
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

#define PI 3.14159265359

float addSub(float a, float b, float alpha) {
	return a + b * alpha - (1.0f - b) * alpha;
}

vec2 dirToUv(vec3 dir) {
	return vec2(-atan(dir.y, dir.x), asin(dir.z)) / vec2(2.0f * PI, PI) + .5f;
}

float fakeEquirectMask(vec3 a, vec3 b, float sharp, out float planeSign) {
	float aob = dot(a, b);
	planeSign = aob > .0f ? 1.0f : .0f;
	return clamp((abs(aob) - .5f) * sharp + .5f, .0f, 1.0f);
}

vec4 fakeEquirect(vec3 dir, vec2 offset, sampler2D tex, float sharp, out float planeSign) {
	vec4 xTex = texture(tex, dir.yz + offset);
	vec4 yTex = texture(tex, dir.xz + offset);
	vec4 zTex = texture(tex, dir.xy + offset);

	float mask = fakeEquirectMask(dir, vec3(1.0f, .0f, .0f), sharp, planeSign);
	vec4 col = mix(yTex, xTex, mask);
	mask = fakeEquirectMask(dir, vec3(0.0f, .0f, 1.0f), sharp, planeSign);
	return mix(col, zTex, mask);
}

vec2 triPlanarUv(vec3 pos, vec3 n, out float planeSign) {
	vec2 n2d = normalize(n.xy);
	float mask = abs(n2d.x) > .7071068f ? 1.0f : .0f;
	planeSign = mix(n2d.x > .0f ? 1.0f : -1.0f, n2d.y > .0f ? 1.0f : -1.0f, mask);
	vec2 uv = mix(vec2(pos.x, pos.z), vec2(pos.y, pos.z), mask);
	n2d = normalize(n.xz);
	mask = abs(n2d).y > .7071068f ? 1.0f : .0f;
	planeSign = mix(planeSign, n2d.y > .0f ? 1.0f : -1.0f, mask);
	return mix(uv, vec2(pos.x, pos.y), mask);
}

vec3 flowEquirect(
	vec2 flowMap,
	mat3 mat,
	float time,
	float cycleOffset,
	float mask,
	sampler2D tex,
	out vec3 flowOut
) {
	float cycleA = time + cycleOffset;
	float cycleB = mod(cycleA + .5f, 1.0f) * 2.0f - 1.0f;
	cycleA = mod(cycleA, 1.0f) * 2.0f - 1.0f;
	vec3 flowDir = mat * vec3(flowMap, .0f);
	flowOut = flowDir;
	vec3 dirA = normalize(mat[2] + cycleA * flowDir * mask);
	vec3 dirB = normalize(-mat[2] + cycleB * -flowDir * mask);
	return mix(
		texture(tex, dirToUv(dirA)).xyz,
		texture(tex, dirToUv(dirB)).xyz,
		abs(cycleA) * mask
	);
}

//https://advances.realtimerendering.com/s2010/index.html
vec3 flow(
	vec2 flowMap,
	vec2 uv,
	float time,
	float cycleOffset,
	float mask,
	sampler2D tex
) {
	float cycleA = time + cycleOffset;
	float cycleB = mod(cycleA + .5f, 1.0f) * 2.0f - 1.0f;
	cycleA = mod(cycleA, 1.0f) * 2.0f - 1.0f;
	vec2 uvA = uv + cycleA * flowMap * mask;
	vec2 uvB = uv + .5f + cycleB * flowMap * mask;
	return mix(texture(tex, uvA).xyz, texture(tex, uvB).xyz, abs(cycleA) * mask);
}

bool valToDither(float value, float mul) {
	ivec2 dither = (ivec2(gl_FragCoord.xy) + ivec2(0, 1)) % ivec2(2.0, 2.0);
	bool test = false;
	switch (int(value * mul)) {
		case 0:
			test = true;
			break;
		case 1:
			test = dither.x == 0 || dither.y == 0;
			break;
		case 2:
			test = dither.x == dither.y;
			break;
		case 3:
			test = dither.x == 0 && dither.y == 0;
			break;
		default:
			break;
	}
	return !test;
}

float fluidDither(vec2 flowUv, vec2 uv, vec3 n, float time) {
	float planeSign = .0f;
	//vec2 uv = triPlanarUv(pos * 2.0f, n, planeSign);
	uv += vec2(.0625f) * time * .5f;
	vec3 flowMap = texture(flowTex, flowUv).xyz;
	float macroNoise = texture(macroNoiseTex, uv * .25f).x;
	vec3 flowVec = vec3(flowMap.xy * 4.0f - 1.0f, 0.0f) * planeSign;
	float fluid = flow(
		flowVec.xy * .2f,
		uv * .25f,
		time / 60.0f * 4.0f,
		macroNoise * .25f - 1.0f,
		flowMap.z,
		microNoiseTex
	).x;
	vec3 col = vec3(fluid);

	return fluid;

	bool test = valToDither(fluid, 6.0f);
}

//https://jcgt.org/published/0009/03/02/paper.pdf
//'pseudo' - pcg based, but we're not strictly adhereing to the spec
uvec3 pcg3dPseudo(uvec3 value) {
	value = value * 1664525u + 1013904223u;
	value += uvec3(value.y * value.z, value.z * value.x, value.x * value.y);
	value ^= value >> 16u;
	value += uvec3(value.y * value.z, value.z * value.x, value.x * value.y);
	return value;
}

vec3 randFromVec(vec3 vec) {
	const uint iSize= 1048583u;
	const float fSize = float(iSize);
	return vec3(pcg3dPseudo(uvec3(vec * fSize)) % iSize) / fSize;
}

mat3 matrixForN(vec3 t, vec3 b, vec3 n) {
	vec3 left = cross(t == n ? b : t, n);
	vec3 right = cross(left, n);
	return mat3(right, left, n);
}

vec3 v3SwizzleChannel(vec4 vec, int channel) {
	if (channel == -1) {
		return vec.xyz;
	}
	if (channel >= 0 && channel <= 3) {
		return vec3(vec[channel]);
	}
	return vec3(1.0f, .0f, 1.0f);
}

float fSwizzleChannel(vec4 vec, int channel) {
	if (channel == -1) {
		return vec.x;
	}
	if (channel >= 0 && channel <= 3) {
		return vec[channel];
	}
	return 1.0f;
}

vec3 normalizeToRange(vec3 col, float min, float max) {
	return (col - min) / (max - min);
}

float invMul(float a, float b) {
	return 1.0f - (1.0f - a) * b;
}

#define K_R .299f
#define K_G .587f
#define K_B .114f
#define F_OF_K(K1, K2) (-.5f * (K1 / (1.0f - K2)))

const mat3 rgbToYpbpr = mat3(
    K_R, F_OF_K(K_R, K_B), .5f,
    K_G, F_OF_K(K_G, K_B), F_OF_K(K_G, K_R),
    K_B, .5f, F_OF_K(K_B, K_R)
);
const mat3 ypbprToRgb = inverse(rgbToYpbpr);

//"Photographics Tone Reproduction for Digital Images" Reinhard et al 2002
vec3 tnReinhard(vec3 col) {
	return col / (col + vec3(1.0f));
}