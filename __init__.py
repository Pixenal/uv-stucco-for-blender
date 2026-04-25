'''
SPDX-FileCopyrightText: 2025 Caleb Dawson
SPDX-License-Identifier: GPL-3.0-only
'''

bl_info = {
	"name": "UV Stucco",
	"description": "An addon for mapping geometry to meshes.",
	"author": "Caleb \"Pixenal\" Dawson",
	"version": (1, 0),
	"blender": (3, 6, 0),
	"location": "View",
	"category": "3D View"
}

import importlib

if ("bpy" in locals()):
	importlib.reload(props)#type:ignore
	importlib.reload(ops)#type:ignore
	importlib.reload(io_ops)#type:ignore
	importlib.reload(handlers)#type:ignore
	importlib.reload(ui)#type:ignore
else:
	from . import props
	from . import ops
	from . import io_ops
	from . import handlers
	from . import ui

def register() -> None:
	print("Registering UvStuccoB")
	props.register()
	ops.register()
	io_ops.register()
	handlers.register()
	ui.register()

def unregister() -> None:
	print("Unregistering UvStuccoB")
	props.unregister()
	ops.unregister()
	io_ops.unregister()
	handlers.unregister()
	ui.unregister()

