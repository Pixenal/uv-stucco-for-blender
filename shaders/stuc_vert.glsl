/*
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
*/

void main() {
	if (args.mapZBounds.x == args.mapZBounds.y) {
		f_gradient = 1.0;
	}
	else {
		float boundsSize = args.mapZBounds.y - args.mapZBounds.x;
		f_gradient = (position.z - args.mapZBounds.x) / boundsSize;
		f_gradient = 1.0 - (1.0 - clamp(f_gradient, .0, 1.0)) * .5;
	}
	v_pos = vec3(args.modelMat * vec4(position, 1.0f));
	mat3 normalMatrix = mat3(
		normalize(args.modelMat[0].xyz),
		normalize(args.modelMat[1].xyz),
		normalize(args.modelMat[2].xyz)
	);
	normalMatrix = transpose(inverse(normalMatrix));
	m_tbn = mat3(
		normalize(tangent),
		normalize(bitangent),
		normalize(normal)
	);
	m_tbn = normalMatrix * m_tbn;

	v_uv = uv;
	i_select = select;
	m_viewMat = viewMat;

	gl_Position = args.viewProjMat * vec4(v_pos, 1.0f);
	if (args.matParam == -1) {
		gl_Position.z += .00000001f;//push back so edit overlay can render on top
	}
}