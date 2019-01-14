# coding=utf-8
import copy
import io
import math
from datetime import datetime

import xlsxwriter
from django.http import FileResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Table


class Spreadsheet(object):
    merge_format = dict(bold=1, align='center', valign='vcenter')
    date_format = dict(num_format='yyyy/mm/dd', border=1, font_size=10)

    fields_list = list(['att_date', 'check_in_time1', 'check_out_time1',
                        'check_in_time2', 'check_out_time2', 'check_in_time3',
                        'check_out_time3', 'remark'])

    fields_name_list = list([u'考勤日期', u'上班1', u'下班1', u'上班2', u'下班2', u'上班3', u'下班3', u'备注'])

    def __init__(self, request, data, statistics, *args):  # 注意data是个列表 statistics
        now = datetime.now()
        filename = '{0}{1}.xlsx'.format(request.GET.get('exporttblName'), now.strftime('%Y%m%d%H%M%S'))
        self._year = request.GET.get('query_year')
        self._month = request.GET.get('query_month')

        self.field_value_map = args[0].copy()  # 暂时传递字典 使用

        self.statistics = copy.copy(statistics)
        self.lister = request.user.username
        self.filename = filename

        self._fields_list = copy.copy(self.fields_list)
        self._fields_name_list = copy.copy(self.fields_name_list)

        self._merge_format = self.merge_format.copy()
        self._date_format = self.date_format.copy()
        self._normal_cell_format = self.merge_format.copy()
        self._top_border = self.merge_format.copy()
        self._left_border = dict()
        self._right_border = dict()

        self.data = data

    def write_data(self, data):  # 在内存创建表格，并写入数据
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, options={'in_memory': True})  # options={'in_memory': True}
        worksheet = workbook.add_worksheet()
        worksheet.set_default_row(25)  # the default value height of row
        worksheet.set_margins(0.2, 0, 0, 0)  # page margin
        worksheet.set_print_scale(52)  # 缩放比例 scale
        worksheet.set_landscape()  # set the orientation of a worksheet’s printed page to landscape
        worksheet.set_paper(9)  # A4

        self._merge_format = workbook.add_format(self._merge_format)
        self._date_format = workbook.add_format(self._date_format)
        self._top_border.update(top=1)
        self._top_border = workbook.add_format(self._top_border)
        self._left_border.update(left=1)
        self._left_border = workbook.add_format(self._left_border)
        self._right_border.update(right=1)
        self._right_border = workbook.add_format(self._right_border)
        self._normal_cell_format.update(border=1)
        self._normal_cell_format = workbook.add_format(self._normal_cell_format)

        self._write_data(worksheet, data)  # 写数据
        workbook.close()
        output.seek(0)
        response = FileResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename={0}'.format(self.filename)
        return response

    def _write_data(self, worksheet, data):
        length = len(data)
        border = [((i + 1) * 9, (i + 2) * 9, (i + 3) * 9) for i in range(0, length, 3)]
        group_by3_list = (data[i: i + 3] for i in xrange(0, length, 3))  # 三个一组 步长3切片

        i, j = 0, 0
        for group_list in group_by3_list:
            for data_dict in group_list:
                col = border[i][j]

                header = u'{0}年{1}月份考勤明细表'.format(self._year, self._month)
                worksheet.merge_range(0, col - 9, 0, col - 2, header, self._merge_format)  # write the head data

                info_field = ['emp_name', 'dept_name', 'group_name', 'emp_pin']
                user_info_str = self._info(info_field, data_dict)
                worksheet.merge_range(1, col - 9, 1, col - 2, user_info_str, self._merge_format)  # write the info head

                self._write_common(worksheet, col - 9)  # write the common data

                self._write_common(worksheet, col - 9, row=3, att_flag=True,
                                   data=data_dict['data'])  # write the att data

                the_length = len(data_dict['data'])
                self._merge_body(worksheet, 3 + the_length, col - 9, data_dict)  # write the body data

                foot = '  '.join([u'审核: ', u'制表: {}'.format(self.lister), u'员工确认:  '])
                # write the foot
                worksheet.merge_range(11 + the_length, col - 9, 11 + the_length, col - 2, foot, self._top_border)

                j += 1

            worksheet.set_v_pagebreaks([col])  # 设置垂直分页符
            i += 1
            j = 0

    def _merge_body(self, worksheet, row, col, data):
        field_by2_list = (self.statistics[i: i + 2] for i in range(0, len(self.statistics), 2))
        format_o = u'{0}: {1}  '
        format_d = u'{0}: {1}  天'

        r, c = row, col
        for field_list in field_by2_list:
            for field in field_list:
                val = (format_d if field.startswith('Leave_') else format_o).format(self.field_value_map[field],
                                                                                    data[field])
                border = self._right_border if c % 3 else self._left_border
                worksheet.merge_range(r, c, r, c + 3, val, border)

                c += 4
                if len(field_list) == 1:  # 右悬空, 补齐边框
                    worksheet.merge_range(r, c, r, c + 3, None, self._right_border)
            c = col
            r += 1

    def _write_common(self, worksheet, col_start_num, row=2, att_flag=False, data=None):
        if att_flag is False:
            for f in self._fields_name_list:
                worksheet.write(row, col_start_num, f, self._normal_cell_format)
                col_start_num += 1

        if att_flag is True:
            for d in data:
                col = col_start_num
                for f in self._fields_list:
                    worksheet.write(row, col, d[f],
                                    self._date_format if f == 'att_date' else self._normal_cell_format)
                    col += 1
                row += 1
        worksheet.set_column(row, col_start_num, 10)

    def _info(self, info_field_list, data):
        _info_list = list()
        for field in info_field_list:
            field_str = u'{0}: {1} '.format(self.field_value_map[field], data[field])
            _info_list.append(field_str)
        return ' '.join(_info_list)

    def __call__(self, *args, **kwargs):
        return self.write_data(self.data)


class PDF2response(object):
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='t1',
                              fontName='STSong-Light',
                              fontSize=14,
                              leading=22,
                              alignment=TA_CENTER))

    styles.add(ParagraphStyle(name='t2',
                              fontName='STSong-Light',
                              fontSize=10,
                              leading=22,
                              wordWrap='CJK',
                              alignment=TA_CENTER))

    styles.add(ParagraphStyle(name='t3',
                              fontName='STSong-Light',
                              fontSize=8,
                              leading=22,
                              alignment=TA_CENTER))

    fd_list = ['att_date', 'check_in_time1', 'check_out_time1',
               'check_in_time2', 'check_out_time2', 'check_in_time3',
               'check_out_time3', 'remark']

    fd_name_list = [u'考勤日期', u'上班1', u'下班1', u'上班2', u'下班2', u'上班3', u'下班3', u'备注']

    def __init__(self, request, data, *args):
        now = datetime.now()
        filename = '{0}{1}'.format(request.GET.get('exporttblName'), now.strftime('%Y%m%d%H%M%S'))
        self.filename = filename
        self._year = request.GET.get('query_year')
        self._month = request.GET.get('query_month')
        self.lister = request.user.username
        self.data = data

        self.field_value_map = args[0].copy()  # 报表{字段: 字段名}映射

    def draw_2response(self):
        story = self.story()  # todo: I have 3 ideas to realize the shape (like this: |||) in a page, maybe do work-_-

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, topMargin=15, bottomMargin=15)  # todo
        doc.build(story)

        output.seek(0)
        response = FileResponse(output, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename={0}.pdf'.format(self.filename)
        return response

    def story(self):
        story = list()

        for data_dict in self.data:
            header = u'{0}年{1}月份考勤明细表'.format(self._year, self._month)
            story.append(Paragraph(header, self.styles['t1']))  # add top head

            info_field = ['emp_name', 'dept_name', 'group_name', 'emp_pin']
            info_head = self._info(info_field, data_dict)
            story.append(Paragraph(info_head, self.styles['t2']))  # add the head after top
            # grid data
            grid_data = list()
            grid_data.append(self.fd_name_list)  # add the th

            self.td(data_dict['data'], grid_data)  # add the td

            used_fd = list()
            used_fd.extend(info_field)
            _dict = data_dict.copy()
            del _dict['data']
            rows = int(self.td4(_dict, grid_data, used_fd))  # add the rest td

            length = len(data_dict['data']) + 1
            rows += length
            table = Table(grid_data, colWidths=[40] * 8, rowHeights=[15] * rows, style=self.table_style(length))
            story.append(table)  # add the grid data

            foot = '  '.join([u'审核:____', u'制表: {}'.format(self.lister), u'员工确认:____'])
            story.append(Paragraph(foot, self.styles['t2']))  # add the foot
            story.append(PageBreak())  # 下一页

        return story

    @staticmethod
    def table_style(length):
        style = [
            ('FONTNAME', (0, 0), (-1, -1), 'STSong-Light'),  # 字体
            ('FONTSIZE', (0, 0), (-1, -1), 8),  # 字体大小
            ('ALIGN', (0, 0), (-2, -2), 'CENTER'),  # 中间对齐
            ('ALIGN', (0, length), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # 上下居中对齐
            ('SPAN', (0, length), (-1, -1)),  # 合并
            ('GRID', (0, 0), (-1, -1), 0.1, colors.slategray),  # 设置表格框线为灰色，线宽为0.1
        ]
        return style

    @staticmethod
    def nest_table_style():
        style = [
            ('FONTNAME', (0, 0), (-1, -1), 'STSong-Light'),  # 字体
            ('FONTSIZE', (0, 0), (-1, -1), 8),  # 字体大小
            ('ALIGN', (0, 0), (-2, -2), 'LEFT'),  # 中间对齐
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # 上下居中对齐
        ]
        return style

    def td(self, data, grid_list):
        for d in data:
            td_list = list()

            for f in self.fd_list:
                td_list.append(d[f])

            grid_list.append(td_list)

    def td4(self, data_dict, grid_list, used_field):
        format_o = u'{0}: {1}  '
        format_d = u'{0}: {1}  天'
        td_list = [""] * 8
        n = 0

        tmp_list = list()
        _grid_list = list()
        _tmp_list = list()
        for k, v in data_dict.items():  # prepare grid data for merge cell
            if k not in used_field:
                val = (format_d if k.startswith('Leave_') else format_o).format(self.field_value_map[k], v)

                if n == 2:
                    n = 0

                _tmp_list.append(val)

                if n == 1:
                    tmp_list.append(td_list)
                    _grid_list.append(_tmp_list)
                    _tmp_list = list()

                n += 1

        if n == 0:
            tmp_list.append(td_list)
            _tmp_list.append('')
            _grid_list.append(_tmp_list)

        nest_table = Table(_grid_list, colWidths=[160] * 2, rowHeights=[15] * len(_grid_list),
                           style=self.nest_table_style())
        tmp_list[0][0] = nest_table
        grid_list.extend(tmp_list)
        return math.ceil(len([k for k, v in data_dict.items() if k not in used_field]) / 2.0)

    def _info(self, info_field_list, data):
        _info_list = list()
        for field in info_field_list:
            field_str = u'{0}: {1} '.format(self.field_value_map[field], data[field])
            _info_list.append(field_str)
        return ' '.join(_info_list)

    def __call__(self, *args, **kwargs):
        return self.draw_2response()
