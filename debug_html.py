import email, glob
from email import policy
from bs4 import BeautifulSoup
import re

files = glob.glob(r'C:\Users\zsely\Downloads\h*\*35245146*')
path = files[0]
print("File:", path)

with open(path, 'rb') as f:
    raw = f.read()

msg = email.message_from_bytes(raw, policy=policy.compat32)
html_part = None
for part in msg.walk():
    if part.get_content_type() == 'text/html':
        charset = part.get_content_charset() or 'utf-8'
        html_part = part.get_payload(decode=True).decode(charset, errors='replace')
        break

soup = BeautifulSoup(html_part, 'lxml')

# Find spans with price text and show ancestors
print("=== PRICE SPAN ANCESTORS ===")
candidates = soup.find_all('span', string=re.compile(r'milli.*Ft'))
for c in candidates[:3]:
    print("Text:", c.get_text(strip=True))
    for i, anc in enumerate(list(c.parents)[:8]):
        cls = anc.get('class')
        id_ = anc.get('id')
        print(f"  parent[{i}]: <{anc.name}> class={cls} id={id_}")
    print()

# Also check what the full price container looks like
print("=== DIVS WITH PRICE-RELATED CLASSES ===")
for el in soup.find_all(class_=re.compile(r'price|ar|\\bft\\b', re.I)):
    txt = el.get_text(strip=True)[:60]
    if txt:
        print(f"<{el.name}> class={el.get('class')}  text={txt!r}")

# H1 elements
print("\n=== H1 ELEMENTS ===")
for h1 in soup.find_all('h1'):
    print(f"class={h1.get('class')}  text={h1.get_text(strip=True)[:80]!r}")

# Look for 'Ár' label in the params
print("\n=== 'Ar' LABEL SEARCH ===")
ar_tags = soup.find_all(string=re.compile(r'^\s*Ár\s*$'))
for t in ar_tags:
    parent = t.parent
    sib = parent.find_next_sibling()
    print(f"Found 'Ar' in <{parent.name}> class={parent.get('class')}")
    if sib:
        print(f"  next sibling: <{sib.name}> class={sib.get('class')} text={sib.get_text(strip=True)[:60]!r}")
