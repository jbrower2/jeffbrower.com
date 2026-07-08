#!/usr/bin/env python3
"""Printing-level parser for types.html.

Every <tr class="cardrow"> is ONE distinct card printing, kept separate with its
own set/number, price, rarity category, and mechanics. Keyed by species name ->
[printings]. This is the source of truth for deck legality and the simulator.

WHY printing-level: many Pokemon have multiple DIFFERENT cards under one name
(e.g. two "Palafin"). A name-keyed parse silently drops variants and mis-pairs
price with mechanics. Never dedupe by name.

Run:  python3 parse_printings.py   ->  writes printings.json next to this script.
"""
import re, json, os
from html import unescape
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
POKE = os.path.dirname(HERE)                       # docs/pokemon
html = open(os.path.join(POKE, 'types.html'), encoding='utf-8').read()

fam_re = re.compile(r'<section class="family" data-types="([^"]*)">(.*?)</section>', re.S)
head_re = re.compile(r'<span class="dex">#(\d+)</span><h2>([^<]*)</h2>')
row_re = re.compile(r'<tr class="cardrow ([^"]*)">(.*?)</tr>', re.S)
sp_re = re.compile(r'<div class="cname">(.*?)</div>\s*<div class="crarity">(.*?)</div>', re.S)
price_re = re.compile(r'<td class="pr">\s*\$([0-9.]+)')
mech_re = re.compile(r'<td class="mech"><div class="ctext">(.*?)</div></td>', re.S)
meta_re = re.compile(r'<div class="meta">([^<]*)</div>')
atk_re = re.compile(r'<div class="atk"><b>(.*?)</b>(.*?)</div>', re.S)
ab_re = re.compile(r'<div class="ab"><b>(.*?)</b>(.*?)</div>', re.S)
setcell_re = re.compile(r'<td class="setcell"><a[^>]*>([^<]*)</a>\s*<span class="lid">([^<]*)</span>')
en_re = re.compile(r'<span class="en" title="([^"]*)">')
# NOTE: energy letters are ambiguous ("F" = Fire AND Fighting) -> always use title.
ABBR = {'Grass': 'G', 'Fire': 'R', 'Water': 'W', 'Lightning': 'L', 'Psychic': 'P',
        'Fighting': 'F', 'Darkness': 'D', 'Metal': 'M', 'Colorless': 'C'}

def strip(t):
    t = re.sub(r'<span class="en"[^>]*title="([^"]*)"[^>]*>\w</span>', lambda m: '{' + m.group(1)[0] + '}', t)
    t = re.sub(r'<span class="dmg">(\d+)</span>', r'[\1]', t)
    t = re.sub(r'<[^>]+>', '', t)
    return unescape(re.sub(r'\s+', ' ', t)).strip()

byname = defaultdict(list)
n_print = 0
for fm in fam_re.finditer(html):
    body = fm.group(2)
    hm = head_re.search(body)
    dex, fname = (hm.group(1), unescape(hm.group(2))) if hm else ('?', '?')
    cur = crar = None
    for rm in row_re.finditer(body):
        cls, rb = rm.group(1), rm.group(2)
        sm = sp_re.search(rb)
        if sm:
            cur = unescape(strip(sm.group(1))); crar = strip(sm.group(2))
        if cur is None:
            continue
        cat = ('cat-green' if 'cat-green' in cls else 'cat-yellow' if 'cat-yellow' in cls
               else 'cat-red' if 'cat-red' in cls else 'cat-none')
        pm = price_re.search(rb); price = float(pm.group(1)) if pm else None
        stm = setcell_re.search(rb)
        setcode, lid = (stm.group(1), stm.group(2)) if stm else ('?', '?')
        mm = mech_re.search(rb); mech = mm.group(1) if mm else ''
        metam = meta_re.search(mech)
        abils = [{'name': strip(a).replace('Ability: ', ''), 'text': strip(b)} for a, b in ab_re.findall(mech)]
        atks = []
        for am in atk_re.finditer(mech):
            bold = am.group(1)
            cost = ''.join(ABBR.get(c, '?') for c in en_re.findall(bold))
            nm = strip(re.sub(r'<span class="en".*?</span>', '', bold))
            atks.append({'cost': cost, 'name': nm, 'text': strip(am.group(2))})
        # energy identity: non-colorless energy this card pays for (attacks + ability {X} refs)
        et = set(ch for a in atks for ch in a['cost'] if ch in 'GRWLPFDM')
        for ab in abils:
            et |= set(re.findall(r'\{([GRWLPFDM])\}', ab['text']))
        byname[cur].append({
            'dex': dex, 'family': fname, 'name': cur, 'rarity': crar,
            'set': setcode, 'id': lid, 'cat': cat, 'price': price,
            'ex': bool(re.search(r' ex$| ex ', cur + ' ')),
            'energy': ''.join(sorted(et)),
            'meta': metam.group(1).strip() if metam else '',
            'abils': abils, 'atks': atks,
            'sig': tuple(sorted([a['name'] for a in abils] + [a['name'] for a in atks])),
        })
        n_print += 1

json.dump({'byname': byname}, open(os.path.join(HERE, 'printings.json'), 'w'), indent=0)
multi = sum(1 for ps in byname.values() if len({p['sig'] for p in ps}) > 1)
print(f'printings: {n_print} | names: {len(byname)} | names with >1 distinct-mechanic printing: {multi}')
print(f'wrote {os.path.join(HERE, "printings.json")}')
