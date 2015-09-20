# -*- coding: utf-8 -*-
#
# 	Copyright (C) 2013 by Igor E. Novikov
#
# 	This program is free software: you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation, either version 3 of the License, or
# 	(at your option) any later version.
#
# 	This program is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with this program.  If not, see <http://www.gnu.org/licenses/>.

from copy import deepcopy

from uc2 import uc2const, libgeom
from uc2.formats.sk2 import sk2_model
from uc2.formats.sk2 import sk2_const

from sk1 import modes, config
from generic import AbstractController

class EditorChooser(AbstractController):

	mode = modes.SHAPER_MODE

	def __init__(self, canvas, presenter):
		AbstractController.__init__(self, canvas, presenter)

	def start_(self):
		sel_objs = self.selection.objs
		if len(sel_objs) == 1 and sel_objs[0].cid == sk2_model.CURVE:
			self.canvas.set_temp_mode(modes.BEZIER_EDITOR_MODE)
		else:
			self.selection.clear()

	def restore(self):
		self.timer.start()

	def stop_(self):pass

	def on_timer(self):
		self.timer.stop()
		self.start_()

	def mouse_down(self, event):pass

	def mouse_up(self, event):
		self.end = event.get_point()
		self.do_action()

	def mouse_move(self, event):pass

	def do_action(self):
		objs = self.canvas.pick_at_point(self.end)
		if objs and objs[0].cid > sk2_model.PRIMITIVE_CLASS \
		and not objs[0].cid == sk2_model.PIXMAP:
			self.selection.set([objs[0], ])
			self.start_()

class BezierEditor(AbstractController):

	mode = modes.BEZIER_EDITOR_MODE
	target = None
	paths = []
	selected_nodes = []

	def __init__(self, canvas, presenter):
		AbstractController.__init__(self, canvas, presenter)

	def start_(self):
		self.start = []
		self.end = []
		self.snap = self.presenter.snap
		self.target = self.selection.objs[0]
		self.update_paths()
		self.selection.clear()
		self.canvas.selection_redraw()

	def update_paths(self):
		self.selected_nodes = []
		self.paths = []
		for item in self.target.paths:
			if not item[1]:continue
			pth = BezierPath(self.canvas, item, self.target.trafo)
			self.paths.append(pth)

	def stop_(self):
		self.selection.set([self.target, ])
		self.target = None
		self.paths = []
		self.start = []
		self.end = []

	def escape_pressed(self):
		self.canvas.set_mode()

	def repaint(self):
		x0, y0, x1, y1 = self.target.cache_bbox
		p0 = self.canvas.point_doc_to_win([x0, y0])
		p1 = self.canvas.point_doc_to_win([x1, y1])
		self.canvas.renderer.draw_frame(p0, p1)
		for item in self.paths:
			item.repaint()

	def repaint_frame(self):
		self.canvas.renderer.cdc_draw_frame(self.start, self.end, True)

	def on_timer(self):
		if self.draw:
			self.repaint_frame()

	def mouse_down(self, event):
		self.start = []
		self.end = []
		self.start = event.get_point()
		self.timer.start()

	def mouse_up(self, event):
		self.end = event.get_point()
		if self.draw:
			self.timer.stop()
			self.draw = False
			points = self.select_points_by_bbox(self.start + self.end)
			self.set_selected_nodes(points, event.is_shift())
			self.start = []
			self.end = []
			self.canvas.selection_redraw()
		else:
			points = self.select_point_by_click(self.end)
			self.set_selected_nodes(points, event.is_shift())
			self.start = []
			self.end = []
			self.canvas.selection_redraw()

	def mouse_move(self, event):
		if self.start:
			self.end = event.get_point()
			self.draw = True

	def select_points_by_bbox(self, bbox):
		ret = []
		bbox = self.canvas.bbox_win_to_doc(bbox)
		for item in self.paths:
			ret += item.select_points_by_bbox(bbox)
		return ret

	def select_point_by_click(self, win_point):
		paths = [] + self.paths
		paths.reverse()
		for item in paths:
			point = item.pressed_point(win_point)
			if point: return [point, ]
		return []

	def set_selected_nodes(self, points, add_flag=False):
		if not add_flag:
			for item in self.selected_nodes:
				item.selected = False
			self.selected_nodes = []
		for item in points:
			if item.selected and item in self.selected_nodes:
				item.selected = False
				self.selected_nodes.remove(item)
			else:
				item.selected = True
				self.selected_nodes.append(item)

class BezierPath:

	canvas = None
	start_point = []
	points = []
	closed = sk2_const.CURVE_CLOSED
	trafo = []

	def __init__(self, canvas, path, trafo):
		self.canvas = canvas
		path = libgeom.apply_trafo_to_path(path, trafo)
		self.trafo = trafo
		self.start_point = BerzierNode(self.canvas, path[0])
		self.points = []
		for item in path[1]:
			self.points.append(BerzierNode(self.canvas, item))
		self.closed = path[2]

	def pressed_point(self, win_point):
		points = [] + self.points
		points.reverse()
		for item in points:
			if item.is_pressed(win_point):
				return item
		if not self.closed == sk2_const.CURVE_CLOSED:
			if self.start_point.is_pressed(win_point):
				return self.start_point
		return None

	def repaint(self):
		rend = self.canvas.renderer
		if not self.closed == sk2_const.CURVE_CLOSED:
			rend.draw_start_node(self.start_point.get_screen_point(),
								self.start_point.selected)
		for item in self.points[:-1]:
			rend.draw_regular_node(item.get_screen_point(), item.selected)
		rend.draw_last_node(self.points[-1].get_screen_point(),
						self.points[-1].selected)

	def select_points_by_bbox(self, bbox):
		ret = []
		if not self.closed == sk2_const.CURVE_CLOSED:
			if libgeom.is_point_in_bbox(self.start_point.point, bbox):
				ret.append(self.start_point)
		for item in self.points:
			if libgeom.is_point_in_bbox(item.point, bbox):
				ret.append(item)
		return ret


class BerzierNode:

	point = []
	canvas = None
	selected = False

	def __init__(self, canvas, point):
		self.canvas = canvas
		self.point = point

	def is_pressed(self, win_point):
		wpoint = self.canvas.point_doc_to_win(self.point)
		if not len(wpoint) == 2:wpoint = wpoint[2]
		bbox = libgeom.bbox_for_point(wpoint, config.point_sensitivity_size)
		return libgeom.is_point_in_bbox(win_point, bbox)

	def get_screen_point(self):
		wpoint = self.canvas.point_doc_to_win(self.point)
		if len(wpoint) == 2:
			return wpoint
		else:
			return wpoint[2]
