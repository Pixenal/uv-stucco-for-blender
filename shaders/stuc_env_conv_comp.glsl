#define PI 3.14159265359
#define RING_STEPS 64
#define RING_SEGS 256

vec2 dirToUv(vec3 dir) {
	return vec2(atan(dir.y, dir.x), asin(dir.z)) / vec2(2.0f * PI, PI) + .5f;
}

vec3 uvToDir(vec2 uv) {
	uv = (uv - .5f) * vec2(2.0f * PI, PI);
	vec3 dir = vec3(.0f);
	dir.z = sin(uv.y);
	vec2 a = vec2(1.0f, .0f);
	float sinTheta = sin(uv.x);
	float cosTheta = cos(uv.x);
	dir.x = cosTheta * a.x - sinTheta * a.y;
	dir.y = sinTheta * a.x + cosTheta * a.y;
	return dir;
}

void main() {
	vec3 irr = vec3(.0f);

	vec3 normal = uvToDir(v_uv);
	vec3 up = vec3(.0f, .0f, 1.0f);
	vec3 right = normalize(cross(up, normal));
	up = normalize(cross(normal, right));
	mat3 nMat = mat3(right, up, normal);

	float ringTheta = PI / 2.0f / float(RING_STEPS);
	float sinRing = sin(ringTheta);
	float cosRing = cos(ringTheta);
	vec3 dir = vec3(1.0f, .0f, .0f);
	int total = 0;
	float segStep = 2.0f * PI / float(RING_SEGS);
	for (int ring = 0; ring < RING_STEPS; ++ring) {
		vec3 dirBuf = vec3(
			cosRing * dir.x - sinRing * dir.z,
			dir.y,
			sinRing * dir.x + cosRing * dir.z
		);
		dirBuf = normalize(dirBuf);
		dir = dirBuf;
		float circum = 2.0f * PI * dot(vec3(1.0f, .0f, .0f), dir);
		int segCount = int(circum / segStep);
		float segTheta = 2.0f * PI / float(segCount);
		float sinSeg = sin(segTheta);
		float cosSeg = cos(segTheta);
		for (int i = 0; i < segCount; ++i) {
			vec3 sampleDir = vec3(
				cosSeg * dirBuf.x - sinSeg * dirBuf.y,
				sinSeg * dirBuf.x + cosSeg * dirBuf.y,
				dirBuf.z
			);
			sampleDir = normalize(sampleDir);
			dirBuf = sampleDir;
			irr += texture(envTex, dirToUv(nMat * sampleDir)).xyz;
			++total;
		}
	}
	irr /= float(total);

	FragColor = vec4(irr, 1.0f);
}