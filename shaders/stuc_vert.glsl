void main() {
	v_pos = vec3(modelMatrix * vec4(position, 1.0f));
	mat3 normalMatrix = transpose(inverse(mat3(modelMatrix)));
	m_tbn = mat3(
		normalize(tangent),
		vec3(.0f),
		normalize(normal)
	);
	m_tbn[1] = normalize(cross(m_tbn[0], m_tbn[2]) * tSign);
	m_tbn = normalMatrix * m_tbn;

	v_uv = uv;
	v_viewPos = viewPos;
	v_viewRes = viewRes;
	m_viewMat = viewMat;
	i_matParam = matParam;
	i_select = select;

	if (matParam == -1) {
		vec3 v = normalize(viewPos - v_pos);
		v_pos -= v * .004f;
	}
	gl_Position = viewProjectionMatrix * vec4(v_pos, 1.0f);
}