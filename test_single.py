import glob, json, sys
sys.path.insert(0, '.')
from extract_ingatlan import extract_html_from_mhtml, extract_data

files = glob.glob(r'C:\Users\zsely\Downloads\h*\*35245146*')
print("Found:", files)
path = files[0]
html, url = extract_html_from_mhtml(path)
d = extract_data(html, url, mhtml_path=path)
print(json.dumps(d, ensure_ascii=False, indent=2))
