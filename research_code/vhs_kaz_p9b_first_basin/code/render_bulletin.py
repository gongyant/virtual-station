from pathlib import Path
import sys,json
import pdfplumber
import pypdfium2 as pdfium
root=Path(sys.argv[1]);p=root/'source/OFFICIAL_HYDROLOGICAL_BULLETIN_2023.pdf';doc=pdfium.PdfDocument(p)
with pdfplumber.open(p) as pdf:
    for no in [149,177,178,179]:
        page=doc.get_page(no-1);page.render(scale=1.7).to_pil().save(root/'figures'/f'OFFICIAL_BULLETIN_PAGE_{no}_QA.png')
        q=pdf.pages[no-1];(root/'evidence'/f'BULLETIN_PAGE_{no}_WORDS.json').write_text(json.dumps(q.extract_words(),ensure_ascii=False,indent=2),encoding='utf-8')
print('Rendered original official pages149,177,178,179 for transcription QA; not new scientific figures.')
