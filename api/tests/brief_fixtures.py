"""Entirely fictional CVs; generated in memory, with no fixture dependencies."""
from io import BytesIO
from zipfile import ZipFile
from xml.sax.saxutils import escape
import struct
import zlib

CVS = [
    'Alex Chen\nComputer Science student.\nBuilt a React dashboard for a university assignment.\nDesigned interface mockups in Figma.\nUsed pair programming on the dashboard project.',
    'Sam Rivera\nSoftware engineering intern for six months.\nImplemented Python REST APIs using FastAPI.\nWrote PostgreSQL queries for an inventory system.\nParticipated in code reviews during the internship.',
    'MAYA SINGH\nDATA SCIENCE STUDENT\nPYTHON AND PANDAS\nBUILT A CSV CLEANING TOOL\nCOMPLETED A STATISTICS COURSE',
    'Jordan Lee\nDesign student.\nCreated Figma prototypes for a campus recycling app.\nConducted five usability interviews for a class project.\nPresented the research findings to classmates.',
]


def pdf(text: str) -> bytes:
    stream = b'BT /F1 12 Tf 40 790 Td 18 TL ' + b' '.join(('(' + line.replace('(', '\\(').replace(')', '\\)') + ') Tj T*').encode() for line in text.splitlines()) + b' ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    data = b'%PDF-1.4\n'; offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data)); data += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(f'{n:010d} 00000 n \n'.encode() for n in offsets[1:])
    return data + f'trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def docx(text: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + ''.join('<w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p>' for line in text.splitlines()) + '</w:body></w:document>')
    return output.getvalue()


def png(text: str) -> bytes:
    # A tiny bitmap font keeps the real multimodal smoke test dependency-free.
    glyphs = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [
        '01110 10001 10001 11111 10001 10001 10001','11110 10001 10001 11110 10001 10001 11110',
        '01111 10000 10000 10000 10000 10000 01111','11110 10001 10001 10001 10001 10001 11110',
        '11111 10000 10000 11110 10000 10000 11111','11111 10000 10000 11110 10000 10000 10000',
        '01111 10000 10000 10111 10001 10001 01111','10001 10001 10001 11111 10001 10001 10001',
        '11111 00100 00100 00100 00100 00100 11111','00111 00010 00010 00010 10010 10010 01100',
        '10001 10010 10100 11000 10100 10010 10001','10000 10000 10000 10000 10000 10000 11111',
        '10001 11011 10101 10101 10001 10001 10001','10001 11001 10101 10011 10001 10001 10001',
        '01110 10001 10001 10001 10001 10001 01110','11110 10001 10001 11110 10000 10000 10000',
        '01110 10001 10001 10001 10101 10010 01101','11110 10001 10001 11110 10100 10010 10001',
        '01111 10000 10000 01110 00001 00001 11110','11111 00100 00100 00100 00100 00100 00100',
        '10001 10001 10001 10001 10001 10001 01110','10001 10001 10001 10001 10001 01010 00100',
        '10001 10001 10001 10101 10101 10101 01010','10001 10001 01010 00100 01010 10001 10001',
        '10001 10001 01010 00100 00100 00100 00100','11111 00001 00010 00100 01000 10000 11111']))
    lines = text.upper().splitlines(); scale = 4
    width = max(map(len, lines)) * 6 * scale + 64; height = len(lines) * 12 * scale + 64
    rows = [bytearray([255] * width) for _ in range(height)]
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            for gy, bits in enumerate(glyphs.get(char, '00000 ' * 7).split()):
                for gx, bit in enumerate(bits):
                    if bit == '1':
                        for sy in range(scale):
                            for sx in range(scale): rows[32+y*12*scale+gy*scale+sy][32+x*6*scale+gx*scale+sx] = 25
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b''.join(b'\0'+row for row in rows))) + chunk(b'IEND', b'')


def request_data():
    return {'setup': {'name': 'Fictional food team', 'context': '48h hackathon, AI for Earth', 'constraints': 'A demonstrable prototype, no paid data sources'},
            'members': [{'id':f'm{i+1}', 'label':'', 'text':CVS[i] if i==3 else ''} for i in range(4)],
            'project_text':'An app that helps students waste less food.'}


def uploads():
    return [('cv:m1', ('alex.pdf', pdf(CVS[0]), 'application/pdf')),
            ('cv:m2', ('sam.docx', docx(CVS[1]), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
            ('cv:m3', ('maya.png', png(CVS[2]), 'image/png'))]
