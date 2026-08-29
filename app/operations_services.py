"""Pure calculations and portable downloads for the operations module."""

from io import BytesIO


def money_summary(planned, expenses, sponsorships):
    committed = sum(item.amount for item in expenses if item.status == "Approved")
    pending = sum(item.amount for item in expenses if item.status == "Pending")
    received = sum(item.amount for item in sponsorships if item.status == "Received")
    remaining = planned - committed
    return {"planned": planned, "committed": committed, "pending": pending, "received": received,
            "remaining": remaining, "utilization": round(committed / planned * 100, 1) if planned else 0}


def forecast_attendance(events):
    historical = [event.expected_participants for event in events if event.status == "Completed"]
    return round(sum(historical) / len(historical)) if historical else 0


def make_basic_pdf(title, rows):
    """Create a one-page printable report without another production package."""
    sanitized = [title, ""] + [" | ".join(str(value) for value in row) for row in rows]
    stream = ["BT", "/F1 18 Tf", "54 760 Td"]
    for index, line in enumerate(sanitized):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream += ["/F1 11 Tf" if index > 0 else "/F1 18 Tf", f"({safe[:110]}) Tj", "0 -22 Td"]
    stream.append("ET")
    payload = "\n".join(stream).encode("latin-1", "replace")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
               b"<< /Length " + str(len(payload)).encode() + b" >>\nstream\n" + payload + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    output = BytesIO(); output.write(b"%PDF-1.4\n"); offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(output.tell()); output.write(f"{number} 0 obj\n".encode()); output.write(body); output.write(b"\nendobj\n")
    start = output.tell(); output.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode())
    return output.getvalue()
