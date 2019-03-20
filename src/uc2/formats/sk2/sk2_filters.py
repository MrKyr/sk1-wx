# -*- coding: utf-8 -*-
#
#  Copyright (C) 2015 by Igor E. Novikov
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import cairo
import logging
from base64 import b64encode
from cStringIO import StringIO

from uc2 import libgeom, sk2const
from uc2.formats.generic_filters import AbstractLoader, AbstractSaver
from uc2.formats.sk2 import sk2_model
from uc2.formats.sk2.crenderer import CairoRenderer

LOG = logging.getLogger(__name__)


class SK2_Loader(AbstractLoader):
    name = 'SK2_Loader'
    parent_stack = []
    break_flag = False
    line = None

    def do_load(self):
        self.model = None
        self.break_flag = False
        self.parent_stack = []
        line = self.fileptr.readline()
        if not line[:len(sk2const.SK2DOC_ID)] == sk2const.SK2DOC_ID:
            while self.fileptr.readline().rstrip('\n') != sk2const.SK2DOC_START:
                pass
        while True:
            if self.break_flag:
                break
            self.line = self.fileptr.readline()
            self.line = self.line.rstrip('\n')

            self.check_loading()

            if self.line:
                try:
                    code = compile('self.' + self.line, '<string>', 'exec')
                    exec code
                except Exception as e:
                    msg = 'Parsing error in "%s"', self.line
                    self.send_error(msg)
                    raise

    def obj(self, tag):
        obj_cid = sk2_model.TAGNAME_TO_CID[tag]
        obj = sk2_model.CID_TO_CLASS[obj_cid](self.config)
        if self.model is None:
            self.model = obj
            self.parent_stack.append(obj)
        else:
            self.parent_stack[-1].childs.append(obj)
            self.parent_stack.append(obj)

    def set_field(self, item, val):
        obj = self.parent_stack[-1]
        if item.startswith('is_'):
            return
        if obj.is_pixmap:
            if item == 'bitmap':
                obj.set_bitmap(val, True)
                return
            elif item == 'alpha_channel':
                if val:
                    obj.set_alpha_channel(val, True)
                return
            elif item in ('size', 'colorspace'):
                return
        obj.__dict__[item] = val

    def obj_end(self):
        self.parent_stack = self.parent_stack[:-1]
        if not self.parent_stack:
            self.break_flag = True


class SK2_Saver(AbstractSaver):
    name = 'SK2_Saver'

    def __init__(self):
        super(SK2_Saver, self).__init__()

    def do_save(self):
        self.presenter.update()
        if self.config.preview:
            preview = self.generate_preview()
            w, h = self.config.preview_size
            self.writeln(sk2const.SK2XML_START)
            self.writeln(sk2const.SK2XML_ID + sk2const.SK2VER)
            size = '%x' % len(preview)
            size = '0' * (8 - len(size)) + size
            self.writeln('%s -->' % size)
            self.writeln(sk2const.SK2SVG_START % (w, h))
            self.writeln(sk2const.SK2IMG_TAG)
            self.writeln(preview)
            self.writeln(sk2const.SK2IMG_TAG_END % (w, h))
            self.writeln(sk2const.SK2DOC_START)
        else:
            self.writeln(sk2const.SK2DOC_ID + sk2const.SK2VER)
        self.save_obj(self.model)
        if self.config.preview:
            self.writeln('-->\n</svg>')

    def save_obj(self, obj):
        self.writeln("obj('%s')" % sk2_model.CID_TO_TAGNAME[obj.cid])
        props = obj.__dict__
        keys = props.keys() if not obj.is_pixmap \
            else props.keys() + ['bitmap', 'alpha_channel']
        for item in keys:
            if item not in sk2_model.GENERIC_FIELDS and \
                    not item.startswith('cache') and \
                    not item.startswith('is_'):
                if item == 'bitmap':
                    item_str = "'%s'" % obj.get_bitmap()
                elif item == 'alpha_channel':
                    item_str = None if not obj.has_alpha() \
                        else "'%s'" % obj.get_alpha_channel()
                elif obj.is_pixmap and item in ('size', 'colorspace'):
                    item_str = None
                else:
                    item_str = self.field_to_str(props[item])
                if item_str is not None:
                    self.writeln("set_field('%s',%s)" % (item, item_str))
        for child in obj.childs:
            self.save_obj(child)
        self.writeln("obj_end()")

    def generate_preview(self):
        wp, hp = self.config.preview_size
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(wp), int(hp))
        ctx = cairo.Context(surface)
        if not self.config.preview_transparent:
            ctx.set_source_rgb(1.0, 1.0, 1.0)
            ctx.paint()
        # ---rendering
        mthds = self.presenter.methods
        layers = mthds.get_visible_layers(mthds.get_page())
        bbox = mthds.count_bbox(layers)
        if bbox:
            x, y, x1, y1 = bbox
            w = abs(x1 - x) or 1.0
            h = abs(y1 - y) or 1.0
            coef = min(wp / w, hp / h) * 0.99
            trafo0 = [1.0, 0.0, 0.0, 1.0, -x - w / 2.0, -y - h / 2.0]
            trafo1 = [coef, 0.0, 0.0, -coef, 0.0, 0.0]
            trafo2 = [1.0, 0.0, 0.0, 1.0, wp / 2.0, hp / 2.0]
            trafo = libgeom.multiply_trafo(trafo0, trafo1)
            trafo = libgeom.multiply_trafo(trafo, trafo2)
            ctx.set_matrix(cairo.Matrix(*trafo))
            rend = CairoRenderer(self.presenter.cms)
            rend.antialias_flag = True
            for item in layers:
                rend.render(ctx, item.childs)
        # ---rendering
        image_stream = StringIO()
        surface.write_to_png(image_stream)
        return b64encode(image_stream.getvalue())
