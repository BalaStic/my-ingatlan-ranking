import json

with open('ingatlanok.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for i, ing in enumerate(data, 1):
    ar = ing.get('Ár', '')
    cim = ing.get('cím', '')
    terulet = ing.get('Alapterület', '')
    szobak = ing.get('Szobák', '')
    parkolas = ing.get('Parkolás', '')
    kor = ing.get('Építés éve', '')
    telek = ing.get('Telekterület', '')
    
    ar_ertek = ar.replace(' millió Ft', '').replace(',', '.').strip()
    try:
        ar_szam = float(ar_ertek)
    except:
        ar_szam = 0
    
    terulet_szam = int(terulet.replace(' m2', '').strip()) if terulet else 0
    telek_szam = int(telek.replace(' m2', '').strip()) if telek else 0
    
    szoba_count = 0
    if szobak:
        parts = szobak.replace('+', ' ').split()
        for p in parts:
            if p.isdigit():
                szoba_count += int(p)
            elif 'fél' in p:
                szoba_count += 1
    
    issues = []
    if ar_szam > 150:
        issues.append(f'Ar > 150M: {ar_szam}M')
    if 'Budapest' not in cim:
        issues.append('Nem budapesti')
    if terulet_szam < 120:
        issues.append(f'Alapterulet < 120: {terulet_szam}m²')
    if 'önálló garázs' not in parkolas.lower():
        issues.append(f'Nincs onallo garazs: {parkolas}')
    if szoba_count < 5:
        issues.append(f'Szobak < 5: {szoba_count} (mezo: {szobak})')
    
    pre1990 = False
    if kor and '1950' in kor:
        pre1990 = True
    
    status = 'OK' if not issues else 'KIZARVA: ' + '; '.join(issues)
    
    print(f'{i}. {cim}')
    print(f'   Ar: {ar_szam}M | Terulet: {terulet_szam}m² | Telek: {telek_szam}m² | Szobak: {szoba_count} ({szobak})')
    print(f'   Kor: {kor} | Pre-1990: {pre1990}')
    print(f'   Parkolas: {parkolas}')
    print(f'   >>> {status}')
    print()