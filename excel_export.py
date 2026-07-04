"""Dependency-free XLSX exports for RUMI Manager."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZIP_DEFLATED, ZipFile

DAY_NAMES = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]


def integer(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def time_minutes(value: str) -> int:
    hour, minute = map(int, str(value or "00:00")[:5].split(":"))
    return hour * 60 + minute


def excel_column(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def excel_date_serial(value: str) -> int:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return (parsed - date(1899, 12, 30)).days


def clean_text(value) -> str:
    text = str(value if value is not None else "")
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)


def cell(reference: str, value=None, style: int = 0, *, numeric: bool = False) -> str:
    style_attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{reference}"{style_attr}/>'
    if numeric:
        return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'
    text = xml_escape(clean_text(value), {'"': '&quot;'})
    return f'<c r="{reference}"{style_attr} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def row(row_number: int, cells: list[str], *, height: float | None = None) -> str:
    height_attr = f' ht="{height}" customHeight="1"' if height else ""
    return f'<row r="{row_number}"{height_attr}>' + "".join(cells) + "</row>"


def normalize_time(value):
    text = str(value or "")
    return text[:5] if len(text) >= 5 else text


def build_schedule_week_xlsx(
    shifts: list[dict],
    employees: list[dict],
    start_date: str,
    end_date: str,
    location_label: str,
    exported_by: str,
) -> bytes:
    """Build an XLSX with a weekly matrix and a detailed shift sheet."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    days = [(start + timedelta(days=index)).isoformat() for index in range(7)]

    normalized_shifts = []
    for raw in shifts:
        item = dict(raw)
        item["start_time"] = normalize_time(item.get("start_time"))
        item["end_time"] = normalize_time(item.get("end_time"))
        normalized_shifts.append(item)
    shifts = sorted(
        normalized_shifts,
        key=lambda item: (
            str(item.get("shift_date", "")),
            str(item.get("start_time", "")),
            str(item.get("employee_name", "")),
        ),
    )

    people: dict[int, dict] = {}
    for employee in employees:
        employee_id = integer(employee.get("id"))
        if employee_id:
            people[employee_id] = {
                "id": employee_id,
                "code": employee.get("code") or "",
                "name": employee.get("name") or "Nhân viên",
                "role": employee.get("role") or "",
            }
    for shift in shifts:
        employee_id = integer(shift.get("employee_id"))
        if employee_id and employee_id not in people:
            people[employee_id] = {
                "id": employee_id,
                "code": shift.get("employee_code") or "",
                "name": shift.get("employee_name") or "Nhân viên",
                "role": shift.get("employee_role") or "",
            }

    by_person_day: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for shift in shifts:
        by_person_day[(integer(shift.get("employee_id")), str(shift.get("shift_date")))].append(shift)

    assigned_ids = {integer(item.get("employee_id")) for item in shifts if integer(item.get("employee_id"))}
    total_hours = round(
        sum(max(time_minutes(item.get("end_time")) - time_minutes(item.get("start_time")), 0) / 60 for item in shifts),
        2,
    )
    week_display = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
    generated_at = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

    schedule_rows: list[str] = [
        row(1, [cell("A1", f"RUMI · LỊCH LÀM TUẦN {week_display}", 1)], height=30),
        row(2, [cell("A2", f"Cửa hàng: {location_label} · Xuất bởi: {exported_by} · {generated_at}", 2)], height=23),
        row(3, [
            cell("A3", "Tổng ca", 2), cell("B3", len(shifts), 8, numeric=True),
            cell("C3", "Nhân viên đã xếp", 2), cell("D3", len(assigned_ids), 8, numeric=True),
            cell("E3", "Tổng giờ dự kiến", 2), cell("F3", total_hours, 8, numeric=True),
            cell("G3", "Phạm vi", 2), cell("H3", location_label, 8),
        ], height=22),
    ]
    headers = ["Mã NV", "Nhân viên", "Vị trí", *DAY_NAMES]
    schedule_rows.append(row(5, [cell(f"{excel_column(index)}5", header, 3) for index, header in enumerate(headers, 1)], height=28))

    people_rows = sorted(people.values(), key=lambda person: (str(person.get("name", "")).casefold(), person.get("code", "")))
    if not people_rows:
        people_rows = [{"id": 0, "code": "", "name": "Chưa có nhân viên", "role": ""}]

    schedule_row_number = 6
    for person in people_rows:
        cells = [
            cell(f"A{schedule_row_number}", person.get("code", ""), 5),
            cell(f"B{schedule_row_number}", person.get("name", ""), 4),
            cell(f"C{schedule_row_number}", person.get("role", ""), 4),
        ]
        max_entries = 1
        for column_index, day in enumerate(days, 4):
            entries = []
            for shift in by_person_day.get((integer(person.get("id")), day), []):
                attendance = shift.get("attendance") or {}
                status = attendance.get("status") or shift.get("status") or "Đã xếp"
                location = shift.get("location_name") or "RUMI"
                note = str(shift.get("note") or "").strip()
                text = f"{shift.get('start_time', '')}–{shift.get('end_time', '')} · {location} · {status}"
                if note:
                    text += f" · {note}"
                entries.append(text)
            value = "\n".join(entries) if entries else "—"
            max_entries = max(max_entries, len(entries))
            cells.append(cell(f"{excel_column(column_index)}{schedule_row_number}", value, 4))
        schedule_rows.append(row(schedule_row_number, cells, height=min(34 + max_entries * 16, 96)))
        schedule_row_number += 1
    schedule_last_row = schedule_row_number - 1

    detail_headers = ["STT", "Ngày", "Thứ", "Bắt đầu", "Kết thúc", "Số giờ", "Mã NV", "Nhân viên", "Vị trí", "Cửa hàng", "Địa chỉ", "Trạng thái", "Ghi chú"]
    detail_rows: list[str] = [
        row(1, [cell("A1", f"RUMI · CHI TIẾT CA LÀM TUẦN {week_display}", 1)], height=30),
        row(2, [cell("A2", f"Cửa hàng: {location_label} · Tổng {len(shifts)} ca · {total_hours} giờ", 2)], height=23),
        row(4, [cell(f"{excel_column(index)}4", header, 3) for index, header in enumerate(detail_headers, 1)], height=28),
    ]
    detail_row_number = 5
    for index, shift in enumerate(shifts, 1):
        shift_day = datetime.strptime(shift["shift_date"], "%Y-%m-%d").date()
        hours = round(max(time_minutes(shift.get("end_time")) - time_minutes(shift.get("start_time")), 0) / 60, 2)
        attendance = shift.get("attendance") or {}
        status = attendance.get("status") or shift.get("status") or "Đã xếp"
        values = [
            (index, 5, True),
            (excel_date_serial(shift["shift_date"]), 6, True),
            (DAY_NAMES[shift_day.weekday()], 5, False),
            (shift.get("start_time", ""), 5, False),
            (shift.get("end_time", ""), 5, False),
            (hours, 7, True),
            (shift.get("employee_code", ""), 5, False),
            (shift.get("employee_name", ""), 4, False),
            (shift.get("employee_role", ""), 4, False),
            (shift.get("location_name", ""), 4, False),
            (shift.get("location_address", ""), 4, False),
            (status, 5, False),
            (shift.get("note", ""), 4, False),
        ]
        detail_rows.append(row(detail_row_number, [
            cell(f"{excel_column(column)}{detail_row_number}", value, style, numeric=numeric)
            for column, (value, style, numeric) in enumerate(values, 1)
        ], height=24))
        detail_row_number += 1
    detail_rows.append(row(detail_row_number, [
        cell(f"A{detail_row_number}", "TỔNG", 8),
        cell(f"B{detail_row_number}", len(shifts), 8, numeric=True),
        cell(f"F{detail_row_number}", total_hours, 8, numeric=True),
    ], height=24))
    detail_last_row = detail_row_number

    schedule_sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:J{schedule_last_row}"/>
  <sheetViews><sheetView workbookViewId="0"><pane xSplit="3" ySplit="5" topLeftCell="D6" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="20"/>
  <cols><col min="1" max="1" width="13" customWidth="1"/><col min="2" max="2" width="24" customWidth="1"/><col min="3" max="3" width="18" customWidth="1"/><col min="4" max="10" width="27" customWidth="1"/></cols>
  <sheetData>{''.join(schedule_rows)}</sheetData>
  <autoFilter ref="A5:J{schedule_last_row}"/>
  <mergeCells count="3"><mergeCell ref="A1:J1"/><mergeCell ref="A2:J2"/><mergeCell ref="H3:J3"/></mergeCells>
  <pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
  <pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0" paperSize="9"/>
</worksheet>'''

    detail_sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:M{detail_last_row}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="20"/>
  <cols><col min="1" max="1" width="7" customWidth="1"/><col min="2" max="3" width="13" customWidth="1"/><col min="4" max="5" width="11" customWidth="1"/><col min="6" max="6" width="10" customWidth="1"/><col min="7" max="7" width="13" customWidth="1"/><col min="8" max="10" width="21" customWidth="1"/><col min="11" max="11" width="30" customWidth="1"/><col min="12" max="12" width="18" customWidth="1"/><col min="13" max="13" width="30" customWidth="1"/></cols>
  <sheetData>{''.join(detail_rows)}</sheetData>
  <autoFilter ref="A4:M{max(4, detail_last_row - 1)}"/>
  <mergeCells count="2"><mergeCell ref="A1:M1"/><mergeCell ref="A2:M2"/></mergeCells>
  <pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
  <pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0" paperSize="9"/>
</worksheet>'''

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>
  <fonts count="4"><font><sz val="11"/><name val="Aptos"/><family val="2"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="16"/><name val="Aptos Display"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Aptos"/></font><font><b/><color rgb="FF4A2E24"/><sz val="11"/><name val="Aptos"/></font></fonts>
  <fills count="6"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF4A2E24"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFA06445"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF8F1EA"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEAD8C9"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFDCC8B8"/></left><right style="thin"><color rgb="FFDCC8B8"/></right><top style="thin"><color rgb="FFDCC8B8"/></top><bottom style="thin"><color rgb="FFDCC8B8"/></bottom><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="9"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf><xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf><xf numFmtId="2" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf><xf numFmtId="2" fontId="3" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="14000"/></bookViews><sheets><sheet name="Lịch tuần" sheetId="1" r:id="rId1"/><sheet name="Chi tiết ca" sheetId="2" r:id="rId2"/></sheets><calcPr calcId="191029"/></workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'''
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    core_properties = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Lịch làm tuần RUMI</dc:title><dc:creator>RUMI Manager</dc:creator><cp:lastModifiedBy>{xml_escape(clean_text(exported_by))}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified></cp:coreProperties>'''
    app_properties = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>RUMI Manager</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop><HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>2</vt:i4></vt:variant></vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="2" baseType="lpstr"><vt:lpstr>Lịch tuần</vt:lpstr><vt:lpstr>Chi tiết ca</vt:lpstr></vt:vector></TitlesOfParts><Company>RUMI</Company><AppVersion>5.3.2</AppVersion></Properties>'''

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("docProps/core.xml", core_properties)
        archive.writestr("docProps/app.xml", app_properties)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", schedule_sheet)
        archive.writestr("xl/worksheets/sheet2.xml", detail_sheet)
    return buffer.getvalue()
