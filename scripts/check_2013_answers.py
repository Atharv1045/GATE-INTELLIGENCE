import pypdf

reader = pypdf.PdfReader('storage/uploads/shared/8d26e8b8-1654-4ebe-8441-278eb4af7971_2013_CS.pdf')
print(f"Total pages in 2013 CS: {len(reader.pages)}")
for p in range(max(0, len(reader.pages)-3), len(reader.pages)):
    print(f"--- Page {p+1} ---")
    print(reader.pages[p].extract_text()[:400])
