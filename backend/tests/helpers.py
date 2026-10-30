import io
from pypdf import PdfWriter


def pdf_bytes(label="Synthetic test document"):
    """Deterministic, parseable synthetic PDF; never real clinical data."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": label})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
