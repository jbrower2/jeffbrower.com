#!/usr/bin/env python3
"""Build a local HTML grid of the pauper decks: Pokémon on the left, an aligned trainer matrix on
the right (one column per distinct trainer so they line up down the decks). Multiples show as "Nx"
before a single card image. Uses the tcgdex card images (same source as types.html); open locally."""
import json, glob, re, os
from collections import Counter, defaultdict
from cards import load_cards

HERE = os.path.dirname(os.path.abspath(__file__))
POKE = os.path.dirname(HERE)
BY_KEY, BY_NAME = load_cards()
OUT = os.path.join(HERE, 'pauper_grid.html')
ETYPE_COLOR = {'Grass': '#4fae5a', 'Fire': '#e8503a', 'Water': '#3f9be8', 'Lightning': '#e8b93f',
               'Psychic': '#b062d6', 'Fighting': '#d17a3a', 'Darkness': '#5b6070', 'Metal': '#8a94a6'}

# prefer the plain base printing over full-art/holo variants (lower rank = more preferred)
RARITY_RANK = {'Common': 0, 'Uncommon': 1, 'Promo': 2, 'ACE SPEC Rare': 3,
               'Ultra Rare': 5, 'Special illustration rare': 6, 'Hyper rare': 7}

# ---- image index from carddata: name / (name,localId) -> [(rarity_rank, base_url)] ----
img_kl, img_nm = defaultdict(list), defaultdict(list)
for f in glob.glob(os.path.join(POKE, 'carddata', '*.json')):
    d = json.load(open(f))
    cards = d if isinstance(d, list) else d.get('cards') or next((v for v in d.values() if isinstance(v, list)), [])
    for c in cards:
        if c.get('image'):
            rank = RARITY_RANK.get(c.get('rarity'), 4)
            lid = re.sub(r'\D', '', str(c.get('localId') or ''))
            lid = str(int(lid)) if lid else ''
            img_kl[(c['name'], lid)].append((rank, c['image']))
            img_nm[c['name']].append((rank, c['image']))


def _pick(cands):
    """Choose the base Common/Uncommon printing (lowest rarity rank); deterministic tie-break by URL."""
    return min(cands, key=lambda x: (x[0], x[1]))[1] if cands else None


def card_img(card):
    """Base tcgdex URL for a deck Pokémon (matched by name+localId, set-preferred, rarity-tiebroken)."""
    m = re.search(r'(\d+)', card.id or '')
    lid = str(int(m.group(1))) if m else ''
    cands = img_kl.get((card.name, lid)) or []
    setc = (card.set or '').lower()
    matched = [(r, b) for r, b in cands if setc and setc in b.lower()]
    return _pick(matched or cands or img_nm.get(card.name) or [])


def trainer_img(name):
    """Base tcgdex URL for a trainer — the plain Common/Uncommon printing, not a full-art variant."""
    return _pick(img_nm.get(name) or [])


def thumb(base, count, label):
    # keep a fixed-height count line (nbsp when 1x) so every image aligns to the same baseline
    n = f'{count}&times;' if count > 1 else '&nbsp;'
    if base:
        return (f'<span class="card" data-hi="{base}/high.webp" title="{label}">'
                f'<b>{n}</b><img loading="lazy" src="{base}/low.webp"></span>')
    return f'<span class="card noimg" title="{label}"><b>{n}</b><span class="nm">{label}</span></span>'


IMGPOP_JS = """<div id="imgpop"><img alt=""></div>
<script>
(function(){
  var pop=document.getElementById('imgpop'),img=pop.querySelector('img'),cur=null,W=340,H=475;
  function move(e){var x=e.clientX+22,y=e.clientY-H/3;
    if(x+W>innerWidth-8)x=e.clientX-W-22;
    y=Math.max(8,Math.min(y,innerHeight-H-8));
    pop.style.left=x+'px';pop.style.top=y+'px';}
  document.addEventListener('mouseover',function(e){
    var el=e.target.closest?e.target.closest('[data-hi]'):null;
    if(el&&el!==cur){cur=el;img.src=el.getAttribute('data-hi');pop.style.display='block';move(e);}});
  document.addEventListener('mousemove',function(e){if(cur)move(e);});
  document.addEventListener('mouseout',function(e){
    var el=e.target.closest?e.target.closest('[data-hi]'):null;
    if(el&&cur===el&&(!e.relatedTarget||!el.contains(e.relatedTarget))){cur=null;pop.style.display='none';img.removeAttribute('src');}});
})();
</script>"""


def build():
    decks = json.load(open(os.path.join(HERE, 'pauper_decklists.json')))
    # order decks by leaderboard score if available
    order = list(decks)
    lb = os.path.join(HERE, 'pauper_leaderboard.json')
    if os.path.exists(lb):
        rank = {row[2]: i for i, row in enumerate(json.load(open(lb))['board'])}
        order.sort(key=lambda n: rank.get(n, 999))
    # collect all distinct trainers, ordered by how many decks run them (common ones leftmost)
    tfreq = Counter()
    for e in decks.values():
        for k in e['cards']:
            if k.startswith('T|'):
                tfreq[k[2:]] += 1
    trainers = [t for t, _ in tfreq.most_common()]

    rows = []
    for name in order:
        e = decks[name]
        # pokemon (with counts), sorted by count desc then stage
        pk = []
        for k, v in e['cards'].items():
            if k.startswith('P|'):
                c = BY_KEY[k[2:]]
                pk.append((c, v))
        pk.sort(key=lambda x: (-x[1], -x[0].stage, x[0].name))
        poke_html = ''.join(thumb(card_img(c), v, c.name) for c, v in pk)
        # energy badge(s)
        en_html = ''
        for k, v in e['cards'].items():
            if k.startswith('E|'):
                t = k[2:]
                en_html += f'<span class="en" style="background:{ETYPE_COLOR.get(t,"#888")}">{v}&times; {t[:1]}</span>'
        # trainer cells (aligned columns)
        tc = {k[2:]: v for k, v in e['cards'].items() if k.startswith('T|')}
        tds = []
        for t in trainers:
            if t in tc:
                tds.append(f'<td>{thumb(trainer_img(t), tc[t], t)}</td>')
            else:
                tds.append('<td></td>')
        npoke = sum(v for _, v in pk)
        rows.append(f'<tr><th class="dname">{name}<span class="cc">{npoke}P</span></th>'
                    f'<td class="poke">{poke_html}</td><td class="en-cell">{en_html}</td>{"".join(tds)}</tr>')

    # trainer header cells: just the vertical name (no thumbnail); hover to preview the card
    def _th(t):
        b = trainer_img(t)
        hi = f' data-hi="{b}/high.webp"' if b else ''
        return f'<th class="th"{hi} title="{t}"><span class="thn">{t}</span></th>'
    thead = ''.join(_th(t) for t in trainers)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Pauper decks — card grid</title>
<style>
:root{{color-scheme:light dark}}
body{{font:13px/1.3 system-ui,-apple-system,sans-serif;margin:0;background:#111318;color:#e7e9f0}}
h1{{padding:14px 16px 4px;margin:0;font-size:19px}}
.sub{{padding:0 16px 12px;color:#969db0}}
.wrap{{overflow:auto;max-height:calc(100vh - 60px)}}
table{{border-collapse:separate;border-spacing:0}}
th,td{{border-bottom:1px solid #262b35;border-right:1px solid #1c2029;padding:3px 4px;vertical-align:top}}
thead th{{position:sticky;top:0;z-index:3;background:#191c24;vertical-align:bottom;text-align:center;padding-top:8px}}
.th{{width:46px;min-width:46px;cursor:zoom-in}}
.thn{{writing-mode:vertical-rl;transform:rotate(180deg);font-size:10.5px;color:#aeb4c4;white-space:nowrap;margin:0 auto;display:inline-block}}
.dname{{position:sticky;left:0;z-index:2;background:#191c24;text-align:left;min-width:150px;max-width:150px;font-weight:600;font-size:12px}}
thead .dname,thead .poke,thead .en-h{{z-index:4}}
.cc{{color:#7f8798;font-weight:400;margin-left:5px}}
.poke{{position:sticky;left:150px;z-index:2;background:#14161c;min-width:360px;max-width:360px}}
.poke .card{{display:inline-flex;flex-direction:column;align-items:center;margin:1px}}
.en-cell,.en-h{{position:sticky;left:510px;z-index:2;background:#14161c;min-width:52px}}
.card{{display:inline-flex;flex-direction:column;align-items:center;cursor:zoom-in}}
.card img{{width:42px;border-radius:3px;display:block}}
.card b{{font-size:10px;color:#ffd66b;line-height:1;min-height:10px}}
#imgpop{{position:fixed;display:none;z-index:100;pointer-events:none}}
#imgpop img{{width:340px;border-radius:11px;box-shadow:0 12px 40px rgba(0,0,0,.6);display:block}}
.card.noimg .nm{{font-size:8px;width:40px;height:56px;display:flex;align-items:center;text-align:center;border:1px solid #333;border-radius:3px;padding:2px}}
.en{{display:inline-block;color:#fff;border-radius:4px;padding:1px 5px;margin:1px;font-size:11px;font-weight:600}}
tbody tr:hover td,tbody tr:hover th{{background:#1e2430}}
tbody tr:hover .poke,tbody tr:hover .dname,tbody tr:hover .en-cell{{background:#1e2430}}
</style></head><body>
<h1>Pauper decks — card grid</h1>
<div class="sub">{len(decks)} decks, ranked by score. Pokémon (left, frozen) &middot; energy &middot; {len(trainers)} trainer columns aligned down the field. Multiples shown as <b style="color:#ffd66b">N&times;</b>. Scroll right for trainers.</div>
<div class="wrap"><table>
<thead><tr><th class="dname">Deck</th><th class="poke">Pok&eacute;mon</th><th class="en-h">En</th>{thead}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
{IMGPOP_JS}
</body></html>"""
    open(OUT, 'w').write(html)
    print(f"wrote {OUT} ({len(html)//1024} KB) | {len(decks)} decks, {len(trainers)} trainer columns")


if __name__ == '__main__':
    build()
