import pypdf

reader = pypdf.PdfReader('validation/uploads/2012_CS.pdf')
for p in [17, 18]:
    print(f"=== PAGE {p+1} ===")
    print(reader.pages[p].extract_text())
