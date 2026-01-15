#include "stuc_utils.glsl"

#define MIN 1.0e-6
#define SPEC_SAMPLE_COUNT 64
#define DIFF_SAMPLE_COUNT 128

float geoSchlickGgx(float nov, float a) {
	float a2 = (a * a) / 2.0f;
	return nov / (nov * (1.0f - a2) + a2);
}

float geoSmith(float nov, float nol, float a) {
	return geoSchlickGgx(nov, a) * geoSchlickGgx(nol, a);
}

vec3 fresnelSchlick(vec3 refl, float voh) {
	return refl + (1.0f - refl) * pow(clamp(1.0f - voh, .0f, 1.0f), 5.0f);
}

vec3 sampleEnvSpec(
	vec3 h,
	vec3 v,
	vec3 l,
	vec3 n,
	vec3 albedo,
	float metal,
	float a2,
	float mip
) {
	float hov = max(dot(h, v), .0f);
	float nol = max(dot(n, l), .0f);
	float nov = max(dot(n, v), .0f);
	float noh = max(dot(n, h), .0f);

	vec3 f0 = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		hov
	);
	float g = geoSmith(nov, nol, a2);
	float denom = 4.0f * noh * nov + MIN;
	vec3 brdf = f0 * g / denom;

	vec3 light = textureLod(envTex, dirToUv(l), mip).xyz * 4.0f;
	return brdf * light * nol;
}

float radicalInvVdc(uint i) {
	i = (i << 16u) | (i >> 16u);
	i = ((i & 0x55555555u) << 1u) | ((i & 0xAAAAAAAAu) >> 1u);
	i = ((i & 0x33333333u) << 2u) | ((i & 0xCCCCCCCCu) >> 2u);
	i = ((i & 0x0F0F0F0Fu) << 4u) | ((i & 0xF0F0F0F0u) >> 4u);
	i = ((i & 0x00FF00FFu) << 8u) | ((i & 0xFF00FF00u) >> 8u);
	return float(i) * 2.3283064365386963e-10;
}

//hammersley set, see https://holger.dammertz.org/stuff/notes_HammersleyOnHemisphere.html
vec2 hammersley2d(uint i, uint num) {
	return vec2(float(i) / float(num), radicalInvVdc(i));
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

const float mipTable[11] = float[11](
	0.0f,
	1.0f,
	3.0f,
	4.0f,
	4.0f,
	4.0f,
	5.0f,
	5.0f,
	6.0f,
	6.0f,
	6.0f
);

vec3 calcLights(vec3 viewUvw, vec3 v, mat3 tbn, vec3 n, vec3 albedo, float metal, float a) {
	mat3 nMat = matrixForN(tbn[0], tbn[1], n);
	vec3 light = vec3(.0f);
	vec3 rand = randFromVec(abs(viewUvw + v));
	a = clamp(a, .01f, .99f);
	float a2 = a * a;

	const int ia = int(a * 10.0f);
	const float mip = mix(mipTable[ia], mipTable[ia + 1], a * 10.0f - float(ia));

	//float mip = a >= 1.0f ? 100.0f : -2.0f / log(a);
	//mip = clamp(mip, .0f, 6.0f);
    
	vec3 specSum = vec3(.0f);
    vec3 diffSum = vec3(.0f);
	for (int i = 0; i < SPEC_SAMPLE_COUNT; ++i) {
		vec2 xi = hammersley2d(uint(i + 1), uint(SPEC_SAMPLE_COUNT + 1));
		xi += vec2(rand.x * -.125f, rand.y);
		float phi = (xi.y) * 2.0f * PI;
		const float cosTheta = sqrt((1.0f - xi.x) / (1.0f + (a2 * a2 - 1.0f) * xi.x));
		const float sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 h = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		h = nMat * normalize(h);
		const vec3 lSpec = reflect(-v, h);
		specSum += sampleEnvSpec(h, v, lSpec, n, albedo, metal, a2, mip);
	}
	for (int i = 0; i < DIFF_SAMPLE_COUNT; ++i) {
		vec2 xi = hammersley2d(uint(i + 1), uint(DIFF_SAMPLE_COUNT + 1));
		xi += vec2(rand.z * -.125f, rand.x);
		const float phi = (xi.y) * 2.0f * PI;
		const float cosTheta = 1.0f - xi.x;
		const float sinTheta = sqrt(1.0f - cosTheta * cosTheta);
		vec3 lDiff = vec3(cos(phi) * sinTheta, sin(phi) * sinTheta, cosTheta);
		lDiff = nMat * lDiff;
		const float nol = max(dot(n, lDiff), .0f);
		diffSum += textureLod(envTex, dirToUv(lDiff), 5.0f).xyz * 2.5f * nol;
	}
	return
        diffSum / float(DIFF_SAMPLE_COUNT) * albedo * (1.0f - metal) +
        specSum / float(SPEC_SAMPLE_COUNT);
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

void main() {
	vec3 v = normalize(v_viewPos - v_pos);
	vec3 viewUvw = vec3(gl_FragCoord.xy / v_viewRes, 1.0f);
	float aspect = v_viewRes.x / v_viewRes.y;
	
	vec4 v4Albedo = texture(albedoTex, v_uv);
	vec3 albedo = v3SwizzleChannel(v4Albedo, int(matInfo.albedoChannel));
	albedo = mix(matInfo.albedoUniform, albedo, matInfo.albedoUseTex);
	vec3 normal = texture(normalTex, v_uv).xyz;
	//normal.y = 1.0f - normal.y;
	normal = mix(vec3(.5f, .5f, 1.0f), normal, matInfo.normalUseTex);
	normal = m_tbn * (normal * 2.0f - 1.0f);
	normal *= float(gl_FrontFacing) * 2.0f - 1.0f;
	float metal = fSwizzleChannel(texture(metalTex, v_uv), int(matInfo.metalChannel));
	metal = mix(matInfo.metalUniform, metal, matInfo.metalUseTex);
	float rough = fSwizzleChannel(texture(roughTex, v_uv), int(matInfo.roughChannel));
	rough = mix(matInfo.roughUniform, rough, matInfo.roughUseTex);

	vec3 col = .000000001f * (albedo + normal + vec3(metal, rough, .0f) + v);

	bool selFace = matInfo.isEditMode == 1.0f && i_select == 1;

	bool textOuter = false;
	bool textInner = false;
	vec3 errCol = vec3(.0f);
	vec3 crystal = vec3(.0f);
	float sinTimeSlow = sin(matInfo.time / 45.0f * PI);
	{
		crystal = mod(v_pos + sinTimeSlow, vec3(1.0f));
		vec3 crystalRefl = mod(reflect(normalize(-v), crystal), vec3(.5f)) * 2.0f;
		crystal = normalize(cross(crystal, crystalRefl));
	}

	albedo = vec3(.25f);
	rough = .25f;

	vec3 sparkles = vec3(.0f);
	vec3 selCol = vec3(227.0f, 62.0f, 191.0f) / vec3(255.0f);
	if (matInfo.error != .0f) {
		float triUvSign = .0f;
		vec2 triUv = triPlanarUv(v_pos, m_tbn[2], triUvSign);

		mat3 pMat = fakePerpMat(viewUvw.xy, m_viewMat, 1.375f, true, m_tbn[2]);
		const int sparklePasses = 6;
		vec3 denom = vec3(.0f);
		for (int i = 0; i < sparklePasses; ++i) {
			float weight = 1.0f - (1.0f / float(sparklePasses) * float(i));
			vec3 flowOut = vec3(.0f);
			vec3 passCol = makeSparkles(pMat, m_viewMat, viewUvw.xy, m_tbn, matInfo.time, pow(float(i) * 4.0f, 1.25f), flowOut);
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
		sparkles = pow(sparkles + 1.0f, vec3(4.0f)) - 1.0f;

		float timeScroll = matInfo.time / 60.0f;
		vec2 vFakeViewUv = vec2(dot(pMat[2], viewMat[0]), dot(pMat[2], viewMat[1]));
		vec2 textUv = viewUvw.xy + vFakeViewUv * .0625f;
		textUv = (textUv + timeScroll) * 12.0f * vec2(aspect, 1.0f);
		float text = texture(errTex, textUv).x;
		text *= selFace ? .0f : 1.0f;
		float sinTime = sin(matInfo.time / 60.0f * 24.0f * PI) * .5f + .5f;
		float timeMask = invMul(sinTime, .05f);
		float timeMaskInner = invMul(sinTime, .1f);
		bool textInner = text > invMul(.425f, timeMaskInner);
		bool textOuter = text > invMul(.35f, timeMask);

		vec2 vFakeUv = dirToUv(pMat[2]);
		vec3 blurEnv = 
			textureLod(envTex, vFakeUv, 4.0f).xyz + 
			textureLod(envTex, vFakeUv, 5.0f).xyz +
			textureLod(envTex, vFakeUv, 6.0f).xyz;
		blurEnv /= 3.0f;
		sparkles = sparkles + blurEnv * .01f;
		sparkles *= textOuter ? .0f : 1.0f;
		sparkles = mix(sparkles, (v * .5f + .5f), textInner ? 1.0f : .0f);
		sparkles = sparkles / (sparkles + vec3(1.0f));
		sparkles = clamp(sparkles, .0, 1.0f);

		ivec2 checker = (ivec2(gl_FragCoord.xy) + ivec2(0, 1)) % ivec2(2.0, 2.0);
		//FragColor = vec4(vec3(pow(luminance * 8.0f, .125f)), 1.0f);
		//return;
		if (!textOuter && (checker.x == 0 && checker.y == 0)) {
			//discard;
		}

		/*
		checker = (ivec2(gl_FragCoord.xy + ivec2(vec2(matInfo.time / 60.0f) * v_viewRes.xy)) / 18 + ivec2(0, 1)) % ivec2(2.0, 2.0);
		
		errCol = textOuter ? normalize(m_tbn[2] + vec3(.0f, .0f, sinTimeSlow)) : crystal * .5f + .5f;
		errCol = pow(errCol, vec3(2.0f));
		errCol = !textInner && textOuter ? vec3(.0f) : errCol;
		errCol = !selFace && !textOuter && checker.x == checker.y ? vec3(.0f, .0f, .0f) : errCol;
		
		ivec2 colChecker = ((ivec2(gl_FragCoord.xy + ivec2(vec2(matInfo.time / 60.0f) * v_viewRes.xy))) / 32 + ivec2(0, 1)) % ivec2(2.0, 2.0);
		errCol = mix(
			errCol,
			clamp(errCol * 2.0f, .0f, 1.0f),
			!textOuter && colChecker.x == colChecker.y
		);
		*/
		//float luminance = .2126f * albedo.x + .7152 * albedo.y + .0722 * albedo.z;
		albedo = vec3(.0f);
		//albedo = (albedo / luminance) * (albedo / luminance) * luminance;
		metal = 1.0f;
		//rough = mix(.2f, .6f, luminance) - (textInner ? .2f : .0f);
		rough = .0f;
	}
	switch (i_matParam) {
		case 0:
			col += albedo;
			break;
		case 1:
			normal.y = -normal.y;
			normal = normal * .5f + .5f;
			col += normal;
			break;
		case 2:
			col += vec3(.0f, rough, metal);
			break;
		default:
			if (v4Albedo.w < .5) {
				discard;
			}
			col = calcLights(viewUvw, v, m_tbn, normal, albedo, metal, rough);

			//col = normalizeToRange(log2(col / .18), -10, 15);
			//col = texture(tmLut, col).xyz;
			//col = pow(col, vec3(2.4f));
			col = col / (col + vec3(1.0f));
	}

	if (matInfo.error != 0.0f) {
		/*
		ivec2 dither = (ivec2(gl_FragCoord.xy + ivec2(vec2(matInfo.time / 60.0f) * v_viewRes.xy)) + ivec2(0, 1)) % ivec2(2.0, 2.0);
		float envDither = (textOuter ? dither.x == .0f || dither.y == .0f : dither.x == dither.y) ? 1.0f : .0f;
		float envDitherFresnel = (textOuter ? dither.x == .0f && dither.y == .0f : false) ? 1.0f : .0f;
		float luminance = .2126f * col.x + .7152 * col.y + .0722 * col.z;
		float fresnelMask = pow(abs(dot(v, m_tbn[2])), 2.0f);
		//col = vec3(fresnelMask);
		col = mix((col / luminance) * (col / luminance) * luminance, col, fresnelMask);
		col = mix(col, errCol, selFace ? .0f : mix(envDitherFresnel, envDither, fresnelMask));

		col *= 255.0f;
		vec3 ypbpr = rgbToYpbpr * col;
		
		float hue = atan(ypbpr.z, ypbpr.y) / (2.0f * PI);
		float chroma = length(vec2(ypbpr.y, ypbpr.z));
		const float hueScale = .33f;
		const float hueShift = 1.0f;
		hue = hue * hueScale + hueShift;
		hue = mod(hue, 1.0f);

		const float desatPos = .7f;
		const float desatRange = .35f;
		
		if (hue > desatPos && hue < desatPos + desatRange) {
			chroma *= .0f;
		}
		hue *= 2.0f * PI;
		ypbpr.y = cos(hue) * chroma;
		ypbpr.z = sin(hue) * chroma;

		col = ypbprToRgb * ypbpr;
		col /= 255.0f;
		*/
		col += sparkles;
	}

	float luminance = .2126f * sparkles.x + .7152 * sparkles.y + .0722 * sparkles.z;
	col = mix(mix(selCol * .5f, selCol, pow(luminance, .25f)), col, selFace ? .5f : 1.0f);

	//col = mix(col, selCol, selFace ? 1.0f : .0f);
	//col = col * .000001f + texture(flowTex, viewUvw.xy).xyz;
	FragColor = vec4(col, 1.0f);
}