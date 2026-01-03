#define PI 3.14159265359
#define FLT_MIN 1.175494351e-38

float trowbridgeReitzGgx(float a, vec3 n, vec3 h) {
	float a2 = a * a;
	float noh = max(dot(n, h), .0f);
	float base = noh * noh * (a2 - 1.0f) + 1.0f;
	float denom = PI * base * base;
	return a2 / denom;
}

float geoSchlickGgx(float nov, float a) {
	float aP1 = a + 1.0f;
	float a2 = (aP1 * aP1) / 8.0f;
	return nov / (nov * (1.0f - a2) + a2);
}

float geoSmith(float nol, float nov, float a) {
	return geoSchlickGgx(nov, a) * geoSchlickGgx(nol, a);
}

vec3 fresnelSchlick(vec3 refl, float voh) {
	return refl + (1.0f - refl) * pow(clamp(1.0f - voh, .0f, 1.0f), 5.0f);
}

vec3 singleLight(
	vec3 viewDir,
	vec3 lightDir,
	vec3 radiance,
	vec3 normal,
	vec3 albedo,
	float metal,
	float rough
) {
	vec3 h = normalize(lightDir + viewDir);
	float nol = max(dot(normal, lightDir), .0f);
	float nov = max(dot(normal, viewDir), .0f);

	float ndf = trowbridgeReitzGgx(rough, normal, h);
	vec3 f0 = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		max(dot(h, viewDir), .0f)
	);
	float geo = geoSmith(nol, nov, rough);

	float denom = 4.0f * nol * nov + FLT_MIN; //<-avoids div by 0
	vec3 spec = ndf * f0 * geo / denom;
	vec3 diffuse = (vec3(1.0f) - spec) * (1.0f - metal);

	vec3 result = (diffuse * (albedo / PI) + spec) * radiance * nol;
	return result;
}

vec2 dirToUv(vec3 dir) {
	return vec2(atan(dir.y, dir.x), asin(dir.z)) / vec2(2.0f * PI, PI) + .5f;
}

vec3 calcAmbient(vec3 v, vec3 normal, vec3 albedo, float metal, float rough) {
	vec3 spec = fresnelSchlick(
		mix(vec3(.04f), albedo, metal),
		max(dot(normal, v), .0f)
	);
	vec3 irr = texture(envTexConv, dirToUv(normal)).xyz;
	return (1.0f - spec) * irr * albedo;
}

void main() {
	vec3 viewDir = normalize(v_viewPos - v_pos);
	
	vec3 light = singleLight(
		viewDir,
		v_lightDir,
		vec3(1.0f, 1.0f, .9f) * 10.0f,
		v_normal,
		v_albedo,
		s_metal,
		s_rough
	);

	vec3 ambient = calcAmbient(viewDir, v_normal, v_albedo, s_metal, s_rough);

	FragColor = vec4(v_uv, .0f, 1.0f) * .000001f + vec4(light + ambient, 1.0f);
}