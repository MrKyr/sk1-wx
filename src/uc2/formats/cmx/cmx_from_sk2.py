# -*- coding: utf-8 -*-
#
#  Copyright (C) 2019 by Igor E. Novikov
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

import logging

from uc2 import libimg, libgeom, uc2const, utils, sk2const, cms
from uc2.formats.cmx import cmx_model, cmx_const, cmx_instr
from uc2.formats.sk2.crenderer import CairoRenderer

LOG = logging.getLogger(__name__)
mkinstr = cmx_instr.make_instruction

SK2_CAP_MAP = {
    sk2const.CAP_BUTT: cmx_const.CMX_MITER_CAP,
    sk2const.CAP_ROUND: cmx_const.CMX_ROUND_CAP,
    sk2const.CAP_SQUARE: cmx_const.CMX_SQUARE_CAP,
}

SK2_JOIN_MAP = {
    sk2const.JOIN_MITER: cmx_const.CMX_MITER_JOIN,
    sk2const.JOIN_ROUND: cmx_const.CMX_ROUND_JOIN,
    sk2const.JOIN_BEVEL: cmx_const.CMX_BEVEL_JOIN,
}


class SK2_to_CMX_Translator(object):
    root = None
    cmx_doc = None
    cmx_model = None
    sk2_doc = None
    sk2_model = None
    sk2_mtds = None
    cmx_cfg = None
    coef = 1.0
    rifx = False

    def translate(self, sk2_doc, cmx_doc):
        self.cmx_doc = cmx_doc
        self.cmx_model = cmx_doc.model
        self.cmx_cfg = cmx_doc.config
        self.sk2_doc = sk2_doc
        self.sk2_model = self.root = sk2_doc.model
        self.sk2_mtds = sk2_doc.methods

        self.make_template()
        self.translate_doc()
        self.index_model()
        self.add_info()
        self.cmx_doc.update()

        self.cmx_doc = None
        self.cmx_model = None
        self.cmx_cfg = None
        self.sk2_doc = None
        self.sk2_model = None
        self.sk2_mtds = None

    def _make_preview(self):
        return libimg.generate_preview(
            self.sk2_doc, CairoRenderer, size=self.cmx_cfg.preview_size,
            transparent=False, img_format='BMP', encoded=False)

    def make_el(self, cmx_id, **kwargs):
        kwargs['identifier'] = cmx_id
        return cmx_model.make_cmx_chunk(self.cmx_cfg, **kwargs)

    def _int2word(self, val):
        return utils.py_int2signed_word(int(val * self.coef), self.rifx)

    def _int2dword(self, val):
        return utils.py_int2signed_dword(int(val * self.coef), self.rifx)

    def _add_color(self, color):
        doc_cms = self.sk2_doc.cms
        rclr = self.cmx_model.chunk_map['rclr']
        clr = (5, 5, (0, 0, 0))  # Fallback RGB black
        if color[0] == uc2const.COLOR_RGB:
            model = cmx_const.COLOR_MODELS.index(cmx_const.CMX_RGB)
            palette = cmx_const.COLOR_PALETTES.index('User')
            vals = cms.val_255(color[1])
            clr = (model, palette, vals)
        elif color[0] == uc2const.COLOR_CMYK:
            model = cmx_const.COLOR_MODELS.index(cmx_const.CMX_RGB)
            palette = cmx_const.COLOR_PALETTES.index('User')
            vals = cms.val_100(color[1])
            clr = (model, palette, vals)
        else:
            model = cmx_const.COLOR_MODELS.index(cmx_const.CMX_RGB)
            palette = cmx_const.COLOR_PALETTES.index('User')
            vals = doc_cms.get_rgb_color255(color)
            clr = (model, palette, vals)
        return rclr.add_color(clr)

    def _add_line_style(self, outline):
        rott = self.cmx_model.chunk_map['rott']
        linestyle = (0x01, 0x00)
        if not outline:
            spec = 0x02
            join = SK2_JOIN_MAP.get(outline[5], cmx_const.CMX_MITER_JOIN)
            cap = SK2_JOIN_MAP.get(outline[4], cmx_const.CMX_MITER_CAP)
            joincap = join << 4 + cap
            linestyle = (spec, joincap)
        return rott.add_linestyle(linestyle)

    def _add_pen(self, outline):
        rpen = self.cmx_model.chunk_map['rpen']
        width = int(self.coef * outline[1])
        aspect = 100
        angle = 0
        matrix_flag = 1
        return rpen.add_pen((width, aspect, angle, matrix_flag))

    def _add_dash(self, outline):
        rdot = self.cmx_model.chunk_map['rdot']
        return rdot.add_dashes([] + outline[3])

    def _add_outline(self, outline):
        rotl = self.cmx_model.chunk_map['rotl']
        linestyle = self._add_line_style(outline)
        screen = 1
        color = self._add_color(outline[2])
        arrowheads = 1
        pen = self._add_pen(outline)
        dashes = self._add_dash(outline)
        return rotl.add_outline(
            (linestyle, screen, color, arrowheads, pen, dashes))

    def _make_bbox(self, bbox):
        x0, y0, x1, y1 = bbox
        return x0 * self.coef, y1 * self.coef, x1 * self.coef, y0 * self.coef

    def make_template(self):
        self.rifx = self.cmx_cfg.rifx
        cont_obj = self.make_el(cmx_const.CONT_ID)
        self.cmx_model.add(cont_obj)
        self.cmx_model.add(self.make_el(cmx_const.CCMM_ID))
        self.cmx_model.add(self.make_el(cmx_const.DISP_ID,
                                        bmp=self._make_preview()))
        if self.cmx_cfg.pack:
            self.root = self.make_el(cmx_const.PACK_ID)
            self.cmx_model.add(self.root)

        objs = []
        for page in self.sk2_mtds.get_pages():
            self.root.add(self.make_el(cmx_const.PAGE_ID))
            self.root.add(self.make_el(cmx_const.RLST_ID))
            if not self.cmx_cfg.v1:
                self.root.add(self.make_el(cmx_const.RLST_ID))
            for layer in page.childs:
                objs.extend(layer.childs)

        cmx_ids = [cmx_const.ROTL_ID, cmx_const.ROTT_ID, cmx_const.RPEN_ID,
                   cmx_const.RDOT_ID, cmx_const.ROTA_ID, cmx_const.RCLR_ID,
                   cmx_const.RSCR_ID, cmx_const.INDX_ID]
        for cmx_id in cmx_ids:
            self.root.add(self.make_el(cmx_id))
        self.cmx_model.update_map()

        self.coef = 1.0

        if objs:
            bbox = [] + objs[0].cache_bbox
            for obj in objs[1:]:
                bbox = libgeom.sum_bbox(bbox, obj.cache_bbox)
            max_value = max([abs(item) for item in bbox])
            frame = 255 * 255 / 2.0
            self.coef = uc2const.pt_to_mm * frame / max_value
        else:
            bbox = [0.0, 1.0, 1.0, 0.0]
            self.coef = 1.0

        cont_obj.set('factor',
                     utils.py_float2double(1.0 / self.coef, self.rifx))
        cont_obj.set('unit', cmx_const.CONT_UNIT_MM)

        cont_obj.set('bbox_x0', self._int2dword(bbox[0]))
        cont_obj.set('bbox_y1', self._int2dword(bbox[3]))
        cont_obj.set('bbox_x1', self._int2dword(bbox[2]))
        cont_obj.set('bbox_y0', self._int2dword(bbox[1]))

    def translate_doc(self):
        index = 0
        cont_obj = self.cmx_model.chunk_map['cont']
        cmx_pages = self.cmx_model.chunk_map['pages']
        for page in self.sk2_mtds.get_pages():
            cmx_page = cmx_pages[index][0]
            rlsts = cmx_pages[index][1:]
            if self.cmx_cfg.v1:
                self.make_v1_page(page, index + 1, cmx_page, rlsts)
                rlst = rlsts[0]
                layers_num = len(cmx_page.childs[0].childs) - 1
                for i in range(layers_num):
                    rlst.add_rlist((2, 9, i + 1))
                cont_obj.data['tally'] += cmx_page.count()
            index += 1
        pg = cmx_pages[0][0].childs[0]
        cont_obj.data['bbox'] = tuple(pg.get_bbox())

    def make_v1_page(self, page, page_num, cmx_page, rlst):
        kwargs = {
            'page_number': page_num,
            'flags': 0,
            'bbox': (0, 0, 0, 0),
            'tail': '\x00\x00\x01\x00\x00\x00',
        }
        page_instr = mkinstr(self.cmx_cfg,
                             identifier=cmx_const.BEGIN_PAGE, **kwargs)
        cmx_page.add(page_instr)

        layer_count = 1
        for layer in (x for x in page.childs if x.childs):
            kwargs = {
                'page_number': page_num,
                'layer_number': layer_count,
                'flags': 0,
                'tally': 0,
                'layer_name': layer.name,
                'tail': '\x01\x00\x00\x00',
            }
            layer_instr = mkinstr(self.cmx_cfg,
                                  identifier=cmx_const.BEGIN_LAYER, **kwargs)
            page_instr.add(layer_instr)

            for obj in layer.childs:
                self.make_v1_objects(layer_instr, obj)

            layer_count += 1

            layer_instr.add(
                mkinstr(self.cmx_cfg, identifier=cmx_const.END_LAYER))
            layer_instr.data['tally'] = layer_instr.count() + 1

        page_instr.add(
            mkinstr(self.cmx_cfg, identifier=cmx_const.END_PAGE))
        page_instr.data['bbox'] = page_instr.get_bbox()

    def make_v1_objects(self, parent_instr, obj):
        if obj.is_group and obj.childs:
            kwargs = {
                'bbox': (0, 0, 0, 0),
                'tail': '\x00\x00',
            }
            group_instr = mkinstr(self.cmx_cfg,
                                  identifier=cmx_const.BEGIN_GROUP, **kwargs)
            parent_instr.add(group_instr)

            for item in obj.childs:
                self.make_v1_objects(group_instr, item)

            group_instr.add(
                mkinstr(self.cmx_cfg, identifier=cmx_const.END_GROUP))

            group_instr.data['bbox'] = group_instr.get_bbox()

        elif obj.is_primitive:
            curve = obj.to_curve()
            if not curve:
                return
            elif curve.is_group:
                self.make_v1_objects(parent_instr, curve)
            elif obj.paths:
                style = obj.style
                attrs = {
                    'style_flags': 1 if style[0] else 0,
                    'fill_type': cmx_const.INSTR_FILL_EMPTY,
                }
                attrs['style_flags'] += 2 if style[1] else 0
                if style[0] and style[0][1] == sk2const.FILL_SOLID:
                    attrs['fill_type'] = cmx_const.INSTR_FILL_UNIFORM
                    attrs['fill'] = (self._add_color(style[0][2]), 1)
                if style[1]:
                    attrs['outline'] = self._add_outline(style[1])
                trafo = libgeom.multiply_trafo(
                    [self.coef, 0.0, 0.0, self.coef, 0.0, 0.0], obj.trafo)
                paths = libgeom.apply_trafo_to_paths(obj.paths, trafo)
                attrs['points'] = []
                attrs['nodes'] = []
                for path in paths:
                    x, y = path[0]
                    attrs['points'].append((int(x), int(y)))
                    node = cmx_const.NODE_MOVE + cmx_const.NODE_USER
                    if path[2] == sk2const.CURVE_CLOSED:
                        node += cmx_const.NODE_CLOSED
                    attrs['nodes'].append(node)

                    for point in path[1]:
                        if len(point) == 2:
                            x, y = point
                            attrs['points'].append((int(x), int(y)))
                            node = cmx_const.NODE_LINE + cmx_const.NODE_USER
                            attrs['nodes'].append(node)
                        else:
                            p0, p1, p2, flag = point
                            for item in (p0, p1, p2):
                                x, y = item
                                attrs['points'].append((int(x), int(y)))
                            node = cmx_const.NODE_ARC
                            attrs['nodes'].append(node)
                            attrs['nodes'].append(node)
                            node = cmx_const.NODE_CURVE + cmx_const.NODE_USER
                            attrs['nodes'].append(node)

                    if path[2] == sk2const.CURVE_CLOSED:
                        attrs['nodes'][-1] += cmx_const.NODE_CLOSED

                attrs['bbox'] = self._make_bbox(obj.cache_bbox)

                attrs['tail'] = ''

                curve_instr = mkinstr(self.cmx_cfg,
                                      identifier=cmx_const.POLYCURVE, **attrs)
                parent_instr.add(curve_instr)

    def index_model(self):
        pass

    def _default_notes(self):
        appdata = self.sk2_doc.appdata
        name = "Created by %s" % appdata.app_name
        ver = "%s%s" % (appdata.version, appdata.revision)
        link = "(https://%s/)" % appdata.app_domain
        return "%s %s %s" % (name, ver, link)

    def add_info(self):
        info = self.make_el(cmx_const.INFO_ID)
        self.cmx_model.add(info)

        metainfo = self.sk2_model.metainfo
        keys = metainfo[2] or ''
        notes = metainfo[3] or self._default_notes()

        info.add(self.make_el(cmx_const.IKEY_ID, text=keys))
        info.add(self.make_el(cmx_const.ICMT_ID, text=notes))
