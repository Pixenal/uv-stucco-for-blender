#define PI 3.14159265359
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

vec2 dirToUv(vec3 dir) {
	return vec2(-atan(dir.y, dir.x), asin(dir.z)) / vec2(2.0f * PI, PI) + .5f;
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

void main() {
	vec3 v = normalize(v_viewPos - v_pos);
	vec3 viewUvw = vec3(gl_FragCoord.xy / v_viewRes, 1.0f);
	
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
	float opac = 1.0f;
	if (matInfo.noCache > .5f) {
		ivec2 dither = (ivec2(gl_FragCoord.xy) / 4 + ivec2(0, 1)) % ivec2(2.0, 2.0);
		if (dither.x == dither.y) {
			discard;
		}
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
			//col = v_pos;
			//vec4 edit = texture(editTex, viewUvw.xy);
			//float mask = edit.x > .4f ? edit.w : .0f;
			//col = edit.xyz;
			//edit = edit * 2.0f - 1.0f;
			//col = mix(col, edit.xyz, mask * matInfo.isEditMode);

			//col = normalizeToRange(log2(col / .18), -10, 15);
			//col = texture(tmLut, col).xyz;
			//col = pow(col, vec3(2.4f));
			col = col / (col + vec3(1.0f));
			break;
	}
	FragColor = vec4(col, opac);
}