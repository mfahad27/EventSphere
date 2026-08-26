"""Small, dependency-free services used only by Milestone 3."""

from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


POSITIVE_WORDS = {"excellent", "great", "good", "amazing", "awesome", "love", "helpful", "happy", "best", "enjoyed", "smooth", "fantastic", "wonderful", "satisfied"}
NEGATIVE_WORDS = {"bad", "poor", "terrible", "awful", "hate", "disappointing", "delay", "late", "issue", "problem", "worst", "unhappy", "confusing", "rude"}


def analyse_sentiment(comment):
    """Return a transparent lexical sentiment label without an ML dependency."""
    words = {word.strip(".,!?;:()[]{}\"'").lower() for word in (comment or "").split()}
    score = len(words & POSITIVE_WORDS) - len(words & NEGATIVE_WORDS)
    return "Positive" if score > 0 else "Negative" if score < 0 else "Neutral"


def build_certificate_pdf(participant_name, event_name, event_date, certificate_id):
    """Create a compact, standards-compliant one-page PDF using only the stdlib."""
    lines = [
        "EVENTSPHERE", "CERTIFICATE OF PARTICIPATION", "", "This certificate is proudly presented to", participant_name,
        "", "for participating in", event_name, f"held on {event_date}", "", f"Certificate ID: {certificate_id}",
        "", "EventSphere Organizer",
    ]
    commands = ["BT", "/F1 15 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index in (0, 1):
            commands.extend(["/F1 22 Tf" if index == 0 else "/F1 18 Tf", f"({escape(str(line))}) Tj", "0 -32 Td"])
        elif index == 4:
            commands.extend(["/F1 20 Tf", f"({escape(str(line))}) Tj", "0 -32 Td"])
        else:
            commands.extend(["/F1 13 Tf", f"({escape(str(line))}) Tj", "0 -24 Td"])
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    output = BytesIO(); output.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(output.tell()); output.write(f"{number} 0 obj\n".encode()); output.write(body); output.write(b"\nendobj\n")
    xref = output.tell(); output.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return output.getvalue()


def build_xlsx(headers, rows):
    """Generate a real .xlsx workbook, avoiding a new production dependency."""
    def cell(value, row, col):
        reference = chr(65 + col) + str(row)
        return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>'
    sheet_rows = []
    for row_number, values in enumerate([headers, *rows], 1):
        sheet_rows.append("<row r=\"%d\">%s</row>" % (row_number, "".join(cell(value, row_number, col) for col, value in enumerate(values))))
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>%s</sheetData></worksheet>' % "".join(sheet_rows)
    content_types = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    root_rels = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook = '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>'
    rels = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types); archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook); archive.writestr("xl/_rels/workbook.xml.rels", rels); archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()
