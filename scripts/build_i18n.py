from pathlib import Path
from datetime import datetime, timezone
import json, html

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
DATA = DOCS / 'data' / 'predictions.json'
SITE = 'https://epl-run-in-lab.github.io/epl-run-in-lab'

SLUG = {
    'Man City':'man-city','Man United':'man-united','Aston Villa':'aston-villa',
    'Crystal Palace':'crystal-palace','Newcastle':'newcastle','Tottenham':'tottenham',
    'Nottingham':'nottingham','Bournemouth':'bournemouth','Brighton':'brighton',
    'Coventry':'coventry','Ipswich':'ipswich','Sunderland':'sunderland','Brentford':'brentford',
    'Chelsea':'chelsea','Arsenal':'arsenal','Liverpool':'liverpool','Everton':'everton',
    'Fulham':'fulham','Leeds':'leeds','Hull':'hull'
}

def esc(x): return html.escape(str(x), quote=True)
def pct(x): return f'{float(x)*100:.1f}%'
def f2(x): return f'{float(x):.2f}'
def slug(team): return SLUG.get(team, team.lower().replace(' ','-').replace("'",''))

def write(rel, content):
    p = DOCS / rel / 'index.html'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')

def shell(title, desc, path, ko_path, body, active):
    nav = [
        ('Home','/en/'),('Match Predictions','/en/predictions/'),('Fixture Difficulty','/en/fixture-difficulty/'),
        ('Power Ranking','/en/power-ranking/'),('EPL Standings','/en/standings/'),
        ('Team Analysis','/en/teams/'),('Model','/en/model/')
    ]
    links=''.join(f'<a class="nav {"active" if p==active else ""}" href="{SITE}{p}">{lab}</a>' for lab,p in nav)
    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}{path}">
<link rel="alternate" hreflang="ko" href="{SITE}{ko_path}">
<link rel="alternate" hreflang="en" href="{SITE}{path}">
<link rel="alternate" hreflang="x-default" href="{SITE}{ko_path}">
<meta property="og:type" content="website"><meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{SITE}{path}">
<meta property="og:locale" content="en_GB"><meta name="twitter:card" content="summary">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2MHM6WELBT"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','G-2MHM6WELBT');</script>
<style>
:root{{--bg:#f5f7fb;--panel:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--soft:#eef2f7}}
body.dark{{--bg:#0b1220;--panel:#111827;--text:#f3f4f6;--muted:#9ca3af;--line:#263244;--soft:#182235}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,sans-serif;line-height:1.55}}
header{{position:sticky;top:0;z-index:20;background:var(--panel);border-bottom:1px solid var(--line)}}.top{{max-width:1180px;margin:auto;padding:14px 20px;display:flex;align-items:center;gap:12px}}
.brand{{font-weight:900;text-decoration:none;color:var(--text);white-space:nowrap}}nav{{display:flex;gap:6px;overflow:auto;flex:1}}.nav{{text-decoration:none;color:var(--muted);padding:7px 9px;border-radius:9px;white-space:nowrap;font-size:14px}}.nav.active,.nav:hover{{background:var(--soft);color:var(--text)}}
.actions{{display:flex;gap:6px;align-items:center}}.plain{{border:0;background:transparent;color:var(--muted);padding:8px 9px;border-radius:9px;cursor:pointer;font-weight:700}}.plain:hover{{background:var(--soft);color:var(--text)}}
.lang{{position:relative}}.menu{{display:none;position:absolute;right:0;top:40px;min-width:140px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px;box-shadow:0 14px 35px rgba(0,0,0,.14);z-index:40}}.menu.show{{display:block}}.menu a{{display:block;text-decoration:none;color:var(--text);padding:9px 10px;border-radius:8px}}.menu a:hover{{background:var(--soft)}}
.switch{{width:42px;height:24px;border:0;border-radius:99px;background:#111827;padding:3px;cursor:pointer;display:flex;align-items:center}}.knob{{width:18px;height:18px;background:#fff;border-radius:50%;display:block;transition:.2s}}body.dark .switch{{background:#e5e7eb}}body.dark .knob{{transform:translateX(18px);background:#111827}}
main{{max-width:1100px;margin:auto;padding:34px 20px 70px}}h1{{font-size:clamp(28px,5vw,44px);line-height:1.15;margin:0 0 10px}}h2{{margin-top:34px}}.lead{{color:var(--muted);max-width:780px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:22px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}}.label{{font-size:13px;color:var(--muted)}}.big{{font-size:27px;font-weight:900;margin-top:4px}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}}th,td{{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{font-size:12px;color:var(--muted)}}.muted{{color:var(--muted)}}.share{{border:1px solid var(--line);background:var(--panel);color:var(--text);padding:9px 12px;border-radius:10px;cursor:pointer;font-weight:700}}.teams{{display:flex;flex-wrap:wrap;gap:8px}}.teams a{{text-decoration:none;color:var(--text);background:var(--panel);border:1px solid var(--line);padding:9px 12px;border-radius:10px}}
.modal-bg{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:80;align-items:center;justify-content:center;padding:20px}}.modal-bg.show{{display:flex}}.modal{{max-width:560px;width:100%;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}}.close{{float:right;border:0;background:transparent;color:var(--text);font-size:22px;cursor:pointer}}
footer{{max-width:1100px;margin:auto;padding:0 20px 40px;color:var(--muted);font-size:12px}}
@media(max-width:760px){{nav{{display:none}}.grid{{grid-template-columns:1fr}}th,td{{padding:10px 7px;font-size:13px}}.notice{{display:none}}}}
</style></head><body>
<header><div class="top"><a class="brand" href="{SITE}/en/">EPL Run-in Lab</a><nav>{links}</nav><div class="actions">
<div class="lang"><button class="plain" id="langBtn">Language ▾</button><div class="menu" id="langMenu"><a href="{SITE}{ko_path}">한국어</a><a href="{SITE}{path}">English</a></div></div>
<button class="plain notice" id="noticeBtn">Notice</button><button class="switch" id="theme" aria-label="Dark mode"><span class="knob"></span></button>
</div></div></header><main>{body}</main>
<footer>Probabilities are model estimates and do not guarantee match results. EPL Run-in Lab is not an official service of the Premier League or any club.</footer>
<div class="modal-bg" id="noticeModal"><div class="modal"><button class="close" id="noticeClose">×</button><h3>Important notice</h3>
<p>Probabilities and expected points are statistical estimates based on available historical and current match data. Injuries, line-ups and tactical changes may not be fully reflected.</p>
<p>Some detailed current-season metrics may not be immediately available from free data sources, so previously available records can still affect the model.</p></div></div>
<script>
const b=document.body,t=document.getElementById('theme');if(localStorage.getItem('runin-theme')==='dark')b.classList.add('dark');t.onclick=()=>{{b.classList.toggle('dark');localStorage.setItem('runin-theme',b.classList.contains('dark')?'dark':'light')}};
const lb=document.getElementById('langBtn'),lm=document.getElementById('langMenu');lb.onclick=e=>{{e.stopPropagation();lm.classList.toggle('show')}};document.addEventListener('click',()=>lm.classList.remove('show'));lm.onclick=e=>e.stopPropagation();
const nm=document.getElementById('noticeModal');document.getElementById('noticeBtn').onclick=()=>nm.classList.add('show');document.getElementById('noticeClose').onclick=()=>nm.classList.remove('show');nm.onclick=e=>{{if(e.target===nm)nm.classList.remove('show')}};
async function sharePage(text){{const d={{title:document.title,text,url:location.href}};if(navigator.share){{try{{await navigator.share(d);return}}catch(e){{}}}}await navigator.clipboard.writeText(location.href)}}
</script></body></html>'''

def patch_korean_static_pages():
    for p in DOCS.rglob('index.html'):
        rel_parts = p.relative_to(DOCS).parts
        if 'en' in rel_parts or p == DOCS/'index.html':
            continue
        rel = p.relative_to(DOCS).parent.as_posix()
        ko_path = '/' if rel=='.' else f'/{rel}/'
        en_path = '/en/' if ko_path=='/' else '/en' + ko_path
        s = p.read_text(encoding='utf-8')
        if 'hreflang="ko"' not in s:
            canon = f'<link rel="canonical" href="{SITE}{ko_path}">'
            s = s.replace(canon, canon + f'\n<link rel="alternate" hreflang="ko" href="{SITE}{ko_path}">\n<link rel="alternate" hreflang="en" href="{SITE}{en_path}">\n<link rel="alternate" hreflang="x-default" href="{SITE}{ko_path}">')
        if 'id="langBtn"' not in s:
            control = (
                '<div class="lang" style="position:relative">'
                '<button class="plain" id="langBtn">Language ▾</button>'
                f'<div class="menu" id="langMenu" style="display:none;position:absolute;right:0;top:40px;min-width:140px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px;box-shadow:0 14px 35px rgba(0,0,0,.14);z-index:40">'
                f'<a href="{SITE}{ko_path}" style="display:block;text-decoration:none;color:var(--text);padding:9px 10px">한국어</a>'
                f'<a href="{SITE}{en_path}" style="display:block;text-decoration:none;color:var(--text);padding:9px 10px">English</a>'
                '</div></div>'
            )
            s = s.replace('<button class="switch" id="theme"', control + '<button class="switch" id="theme"')
            s = s.replace("const b=document.body,t=document.getElementById('theme');", "const lb=document.getElementById('langBtn'),lm=document.getElementById('langMenu');if(lb){lb.onclick=e=>{e.stopPropagation();lm.style.display=lm.style.display==='block'?'none':'block'};document.addEventListener('click',()=>lm.style.display='none');lm.onclick=e=>e.stopPropagation();}const b=document.body,t=document.getElementById('theme');")
        p.write_text(s,encoding='utf-8')

def build():
    d=json.loads(DATA.read_text(encoding='utf-8'))
    games=d.get('games',{}); standings=d.get('standings',[]); rankings=d.get('rankings',{}); powers=d.get('powerRankings',[]); profiles=d.get('teamProfiles',{})
    teams=sorted(games)
    sm={x['team']:x for x in standings}; pm={x['team']:x for x in powers}; r5={x['team']:x for x in rankings.get('5',[])}

    top=rankings.get('5',[])[:3]
    cards=''.join(f"<div class='card'><div class='label'>Fixture ease #{x['rank']}</div><div class='big'>{esc(x['team'])}</div><div class='muted'>Next 5 xPts {f2(x['xpts'])}</div></div>" for x in top)
    body=f'''<h1>EPL predictions, fixture difficulty and power rankings</h1><p class="lead">EPL Run-in Lab turns historical and current match data into win/draw/loss probabilities, expected points (xPts), fixture difficulty and model-based team strength rankings.</p><div class="grid">{cards}</div><h2>Explore</h2><div class="teams"><a href="{SITE}/en/predictions/">Match Predictions</a><a href="{SITE}/en/fixture-difficulty/">Fixture Difficulty</a><a href="{SITE}/en/power-ranking/">Power Ranking</a><a href="{SITE}/en/standings/">Standings</a><a href="{SITE}/en/teams/">Team Analysis</a></div>'''
    write('en',shell('EPL Predictions, Fixture Difficulty & Power Rankings | EPL Run-in Lab','Data-driven EPL win probabilities, expected points, fixture difficulty and power rankings.','/en/','/',body,'/en/'))

    rows=[]
    for t in teams:
        if games[t]:
            g=games[t][0]; venue='Home' if g['venue']=='H' else 'Away'
            rows.append(f"<tr><td><a href='{SITE}/en/teams/{slug(t)}/'>{esc(t)}</a></td><td>{esc(g['date'])}</td><td>{esc(g['opponent'])} ({venue})</td><td><b>{pct(g['win'])}</b></td><td>{pct(g['draw'])}</td><td>{pct(g['loss'])}</td><td>{f2(g['xpts'])}</td></tr>")
    body=f'''<h1>EPL match predictions</h1><p class="lead">Compare each team's next-match win, draw and loss probabilities together with expected points (xPts).</p><button class="share" onclick="sharePage('EPL next-match predictions')">Share predictions</button><h2>Next match by team</h2><table><thead><tr><th>Team</th><th>Date</th><th>Opponent</th><th>Win</th><th>Draw</th><th>Loss</th><th>xPts</th></tr></thead><tbody>{''.join(rows)}</tbody></table>'''
    write('en/predictions',shell('EPL Match Predictions & Win Probabilities | EPL Run-in Lab','EPL next-match win, draw and loss probabilities with expected points (xPts).','/en/predictions/','/predictions/',body,'/en/predictions/'))

    rows=''.join(f"<tr><td>{x['rank']}</td><td><a href='{SITE}/en/teams/{slug(x['team'])}/'>{esc(x['team'])}</a></td><td><b>{f2(x['xpts'])}</b></td><td>{f2(x['xppg'])}</td></tr>" for x in rankings.get('5',[]))
    body=f'''<h1>EPL fixture difficulty</h1><p class="lead">Higher expected points over the next five matches means an easier projected schedule. This ranking aggregates match-level probabilities rather than simply using opponent league position.</p><button class="share" onclick="sharePage('EPL fixture difficulty')">Share ranking</button><h2>Next 5 matches</h2><table><thead><tr><th>#</th><th>Team</th><th>xPts</th><th>xPPG</th></tr></thead><tbody>{rows}</tbody></table>'''
    write('en/fixture-difficulty',shell('EPL Fixture Difficulty Rankings | Next 5 Matches | EPL Run-in Lab','Rank all 20 EPL teams by modelled fixture difficulty over the next five matches.','/en/fixture-difficulty/','/fixture-difficulty/',body,'/en/fixture-difficulty/'))

    rows=''.join(f"<tr><td>{x['rank']}</td><td><a href='{SITE}/en/teams/{slug(x['team'])}/'>{esc(x['team'])}</a></td><td><b>{x['score']:.1f}</b></td><td>{x.get('currentEPLRank') or '-'}</td><td>{x['neutralXPPG']:.2f}</td></tr>" for x in powers)
    body=f'''<h1>EPL power ranking</h1><p class="lead">A model-based team strength ranking separate from the league table. Teams are evaluated against a league-average opponent at home and away, then normalised so the strongest team scores 100.</p><h2>Model strength ranking</h2><table><thead><tr><th>#</th><th>Team</th><th>Power Score</th><th>Current EPL rank</th><th>Neutral xPts</th></tr></thead><tbody>{rows}</tbody></table>'''
    write('en/power-ranking',shell('EPL Power Rankings | Data-Driven Team Strength | EPL Run-in Lab','Model-based EPL power rankings, separate from current league position.','/en/power-ranking/','/power-ranking/',body,'/en/power-ranking/'))

    rows=''.join(f"<tr><td>{x['rank']}</td><td><a href='{SITE}/en/teams/{slug(x['team'])}/'>{esc(x['team'])}</a></td><td>{x['played']}</td><td>{x['won']}</td><td>{x['drawn']}</td><td>{x['lost']}</td><td>{x['gd']:+d}</td><td><b>{x['points']}</b></td></tr>" for x in standings)
    body=f'''<h1>Current EPL standings</h1><p class="lead">League table calculated from completed Premier League matches.</p><table><thead><tr><th>#</th><th>Team</th><th>Pl</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th></tr></thead><tbody>{rows}</tbody></table>'''
    write('en/standings',shell('Current EPL Standings & Points | EPL Run-in Lab','Current EPL standings, points, record and goal difference.','/en/standings/','/standings/',body,'/en/standings/'))

    links=''.join(f"<a href='{SITE}/en/teams/{slug(t)}/'>{esc(t)}</a>" for t in teams)
    body=f'''<h1>EPL team analysis</h1><p class="lead">Choose a team to see current position, power score, recent results, upcoming fixtures, win probabilities and expected points.</p><div class="teams">{links}</div>'''
    write('en/teams',shell('EPL Team Predictions & Fixture Analysis | EPL Run-in Lab','Team-by-team EPL predictions, upcoming fixtures, expected points and model strength.','/en/teams/','/teams/',body,'/en/teams/'))

    for t in teams:
        st=sm.get(t,{}); pw=pm.get(t,{}); rr=r5.get(t,{})
        fx=''.join(f"<tr><td>{esc(g['date'])}</td><td>{'Home' if g['venue']=='H' else 'Away'}</td><td>{esc(g['opponent'])}</td><td><b>{pct(g['win'])}</b></td><td>{pct(g['draw'])}</td><td>{pct(g['loss'])}</td><td>{f2(g['xpts'])}</td></tr>" for g in games[t][:5])
        recent=' · '.join(f"{x['date'][5:]} {'Home' if x['venue']=='H' else 'Away'} {x['opponent']} {x['gf']}-{x['ga']} {x['result']}" for x in profiles.get(t,{}).get('recentResults',[])) or 'No completed league matches yet'
        body=f'''<h1>{esc(t)} predictions & upcoming fixtures</h1><p class="lead">Current EPL position, power score, next five win/draw/loss probabilities and expected points for {esc(t)}.</p><button class="share" onclick="sharePage('{esc(t)} EPL predictions and fixtures')">Share team analysis</button><div class="grid"><div class="card"><div class="label">Current EPL position</div><div class="big">{st.get('rank','-')}</div><div class="muted">{st.get('points','-')} pts</div></div><div class="card"><div class="label">Power Score</div><div class="big">{pw.get('score','-')}</div><div class="muted">Power rank #{pw.get('rank','-')}</div></div><div class="card"><div class="label">Next 5 xPts</div><div class="big">{f2(rr['xpts']) if rr else '-'}</div><div class="muted">Fixture ease rank #{rr.get('rank','-')}</div></div></div><h2>Recent matches</h2><p>{esc(recent)}</p><h2>Next 5 match predictions</h2><table><thead><tr><th>Date</th><th>Venue</th><th>Opponent</th><th>Win</th><th>Draw</th><th>Loss</th><th>xPts</th></tr></thead><tbody>{fx}</tbody></table>'''
        write(f'en/teams/{slug(t)}',shell(f'{t} Predictions, Fixtures & Win Probability | EPL Run-in Lab',f'{t} next-match probabilities, upcoming fixtures, expected points, current EPL position and power ranking.',f'/en/teams/{slug(t)}/',f'/teams/{slug(t)}/',body,'/en/teams/'))

    body='''<h1>Prediction model</h1><p class="lead">EPL Run-in Lab does not ask a generative AI to invent match outcomes. It presents probabilities from a statistical model trained on historical EPL match data.</p><h2>What does it use?</h2><p>Recent points, goals for and against, shots, shots on target, and home/away performance. Older matches gradually receive less weight. Newly promoted clubs receive a conservative prior based on their Championship season until enough EPL matches are available.</p><h2>How are reasons explained?</h2><p>Percentage-point effects come from resetting one factor group to a neutral league level and recalculating the model. Because factors interact non-linearly, individual effects do not have to sum exactly to the final probability.</p><h2>Limitations</h2><p>Injuries, line-ups and tactical changes are not always reflected in real time. Some current-season detailed metrics may lag when free data sources do not provide them immediately.</p>'''
    write('en/model',shell('EPL Run-in Lab Prediction Model & Methodology','How EPL Run-in Lab calculates match probabilities, expected points, fixture difficulty and power rankings.','/en/model/','/model/',body,'/en/model/'))

    patch_korean_static_pages()

    ko=['/','/predictions/','/fixture-difficulty/','/power-ranking/','/standings/','/teams/','/model/']+[f'/teams/{slug(t)}/' for t in teams]
    en=['/en/','/en/predictions/','/en/fixture-difficulty/','/en/power-ranking/','/en/standings/','/en/teams/','/en/model/']+[f'/en/teams/{slug(t)}/' for t in teams]
    today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    urls='\n'.join(f'  <url><loc>{SITE}{p}</loc><lastmod>{today}</lastmod></url>' for p in ko+en)
    (DOCS/'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n',encoding='utf-8')
    (DOCS/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n',encoding='utf-8')

if __name__=='__main__':
    build()
