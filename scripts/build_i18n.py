from pathlib import Path
from datetime import datetime, timezone
import json, html
import xml.etree.ElementTree as ET

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

def shell(title, desc, path, ko_path, body, active, schema_name=None):
    page_name = schema_name or title.split(" | ")[0]
    breadcrumb_items = [{"@type":"ListItem","position":1,"name":"EPL Run-in Lab","item":SITE+"/en/"}]
    if path != "/en/":
        breadcrumb_items.append({"@type":"ListItem","position":2,"name":page_name,"item":SITE+path})
    structured = {
        "@context":"https://schema.org",
        "@graph":[
            {"@type":"WebSite","@id":SITE+"/#website","url":SITE+"/","name":"EPL Run-in Lab",
             "description":"Data-driven Premier League predictions, fixture difficulty, expected points and power rankings.",
             "inLanguage":["ko","en"]},
            {"@type":"WebPage","@id":SITE+path+"#webpage","url":SITE+path,"name":page_name,
             "description":desc,"isPartOf":{"@id":SITE+"/#website"},"inLanguage":"en"},
            {"@type":"BreadcrumbList","itemListElement":breadcrumb_items}
        ]
    }
    structured_json=json.dumps(structured,ensure_ascii=False).replace("</","<\\/")
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
<script type="application/ld+json">{structured_json}</script>
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
    write('en/predictions',shell('Premier League Predictions & Win Probabilities | EPL Run-in Lab','Premier League and EPL match predictions with win, draw and loss probabilities plus expected points (xPts).','/en/predictions/','/predictions/',body,'/en/predictions/'))

    rows=''.join(f"<tr><td>{x['rank']}</td><td><a href='{SITE}/en/teams/{slug(x['team'])}/'>{esc(x['team'])}</a></td><td><b>{f2(x['xpts'])}</b></td><td>{f2(x['xppg'])}</td></tr>" for x in rankings.get('5',[]))
    body=f'''<h1>EPL fixture difficulty</h1><p class="lead">Higher expected points over the next five matches means an easier projected schedule. This ranking aggregates match-level probabilities rather than simply using opponent league position.</p><button class="share" onclick="sharePage('EPL fixture difficulty')">Share ranking</button><h2>Next 5 matches</h2><table><thead><tr><th>#</th><th>Team</th><th>xPts</th><th>xPPG</th></tr></thead><tbody>{rows}</tbody></table>'''
    write('en/fixture-difficulty',shell('Premier League Fixture Difficulty | Next 5 Matches | EPL Run-in Lab','Premier League fixture difficulty rankings for all 20 EPL teams over the next five matches, based on expected points.','/en/fixture-difficulty/','/fixture-difficulty/',body,'/en/fixture-difficulty/'))

    rows=''.join(f"<tr><td>{x['rank']}</td><td><a href='{SITE}/en/teams/{slug(x['team'])}/'>{esc(x['team'])}</a></td><td><b>{x['score']:.1f}</b></td><td>{x.get('currentEPLRank') or '-'}</td><td>{x['neutralXPPG']:.2f}</td></tr>" for x in powers)
    body=f'''<h1>EPL power ranking</h1><p class="lead">A model-based team strength ranking separate from the league table. Teams are evaluated against a league-average opponent at home and away, then normalised so the strongest team scores 100.</p><h2>Model strength ranking</h2><table><thead><tr><th>#</th><th>Team</th><th>Power Score</th><th>Current EPL rank</th><th>Neutral xPts</th></tr></thead><tbody>{rows}</tbody></table>'''
    write('en/power-ranking',shell('Premier League Power Rankings | EPL Team Strength | EPL Run-in Lab','Data-driven Premier League power rankings comparing the modelled strength of all 20 EPL teams.','/en/power-ranking/','/power-ranking/',body,'/en/power-ranking/'))

    rows=''.join(f"<tr><td>{x['rank']}</td><td><a href='{SITE}/en/teams/{slug(x['team'])}/'>{esc(x['team'])}</a></td><td>{x['played']}</td><td>{x['won']}</td><td>{x['drawn']}</td><td>{x['lost']}</td><td>{x['gd']:+d}</td><td><b>{x['points']}</b></td></tr>" for x in standings)
    body=f'''<h1>Current EPL standings</h1><p class="lead">League table calculated from completed Premier League matches.</p><table><thead><tr><th>#</th><th>Team</th><th>Pl</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th></tr></thead><tbody>{rows}</tbody></table>'''
    write('en/standings',shell('Current EPL Standings & Points | EPL Run-in Lab','Current EPL standings, points, record and goal difference.','/en/standings/','/standings/',body,'/en/standings/'))

    links=''.join(f"<a href='{SITE}/en/teams/{slug(t)}/'>{esc(t)}</a>" for t in teams)
    body=f'''<h1>EPL team analysis</h1><p class="lead">Choose a team to see current position, power score, recent results, upcoming fixtures, win probabilities and expected points.</p><div class="teams">{links}</div>'''
    write('en/teams',shell('Premier League Team Predictions & Fixture Analysis | EPL Run-in Lab','Team-by-team Premier League predictions, win probabilities, upcoming fixtures, expected points and power rankings.','/en/teams/','/teams/',body,'/en/teams/'))

    for t in teams:
        st=sm.get(t,{}); pw=pm.get(t,{}); rr=r5.get(t,{})
        fx=''.join(f"<tr><td>{esc(g['date'])}</td><td>{'Home' if g['venue']=='H' else 'Away'}</td><td>{esc(g['opponent'])}</td><td><b>{pct(g['win'])}</b></td><td>{pct(g['draw'])}</td><td>{pct(g['loss'])}</td><td>{f2(g['xpts'])}</td></tr>" for g in games[t][:5])
        recent=' · '.join(f"{x['date'][5:]} {'Home' if x['venue']=='H' else 'Away'} {x['opponent']} {x['gf']}-{x['ga']} {x['result']}" for x in profiles.get(t,{}).get('recentResults',[])) or 'No completed league matches yet'
        summary=(f"{esc(t)} are currently {st.get('rank','-')} in the Premier League with {st.get('points','-')} points. "
                 f"Their EPL Run-in Lab Power Score is {pw.get('score','-')}, ranked #{pw.get('rank','-')} by the model. "
                 f"Across the next five fixtures, the model projects {f2(rr['xpts']) if rr else '-'} expected points, "
                 f"with a fixture-ease rank of #{rr.get('rank','-')}. The table below shows win, draw and loss probabilities for each upcoming match.")
        body=f'''<h1>{esc(t)} predictions, win probability & upcoming fixtures</h1><p class="lead">{summary}</p><button class="share" onclick="sharePage('{esc(t)} Premier League predictions and fixtures')">Share team analysis</button><div class="grid"><div class="card"><div class="label">Current EPL position</div><div class="big">{st.get('rank','-')}</div><div class="muted">{st.get('points','-')} pts</div></div><div class="card"><div class="label">Power Score</div><div class="big">{pw.get('score','-')}</div><div class="muted">Power rank #{pw.get('rank','-')}</div></div><div class="card"><div class="label">Next 5 xPts</div><div class="big">{f2(rr['xpts']) if rr else '-'}</div><div class="muted">Fixture ease rank #{rr.get('rank','-')}</div></div></div><h2>{esc(t)} recent form</h2><p>{esc(recent)}</p><h2>{esc(t)} next 5 match predictions</h2><table><thead><tr><th>Date</th><th>Venue</th><th>Opponent</th><th>Win</th><th>Draw</th><th>Loss</th><th>xPts</th></tr></thead><tbody>{fx}</tbody></table><h2>Related Premier League analysis</h2><div class="teams"><a href="{SITE}/en/predictions/">Premier League Predictions</a><a href="{SITE}/en/fixture-difficulty/">Fixture Difficulty</a><a href="{SITE}/en/power-ranking/">Power Rankings</a><a href="{SITE}/en/standings/">EPL Standings</a></div>'''
        write(f'en/teams/{slug(t)}',shell(f'{t} Predictions, Win Probability & Fixtures | EPL Run-in Lab',f'{t} Premier League predictions, next-match win probability, next five fixtures, expected points, current position and power ranking.',f'/en/teams/{slug(t)}/',f'/teams/{slug(t)}/',body,'/en/teams/',f'{t} predictions, win probability and fixtures'))

    body='''<h1>Prediction model</h1><p class="lead">EPL Run-in Lab does not ask a generative AI to invent match outcomes. It presents probabilities from a statistical model trained on historical EPL match data.</p><h2>What does it use?</h2><p>Recent points, goals for and against, shots, shots on target, and home/away performance. Older matches gradually receive less weight. Newly promoted clubs receive a conservative prior based on their Championship season until enough EPL matches are available.</p><h2>How are reasons explained?</h2><p>Percentage-point effects come from resetting one factor group to a neutral league level and recalculating the model. Because factors interact non-linearly, individual effects do not have to sum exactly to the final probability.</p><h2>Limitations</h2><p>Injuries, line-ups and tactical changes are not always reflected in real time. Some current-season detailed metrics may lag when free data sources do not provide them immediately.</p>'''
    write('en/model',shell('EPL Run-in Lab Prediction Model & Methodology','How EPL Run-in Lab calculates match probabilities, expected points, fixture difficulty and power rankings.','/en/model/','/model/',body,'/en/model/'))

    patch_korean_static_pages()

    # Keep the sitemap deliberately simple. hreflang remains in each page's HTML <head>;
    # the sitemap only needs canonical URLs + lastmod for reliable Search Console parsing.
    ko=['/','/predictions/','/fixture-difficulty/','/power-ranking/','/standings/','/teams/','/model/']+[f'/teams/{slug(t)}/' for t in teams]
    en=['/en/','/en/predictions/','/en/fixture-difficulty/','/en/power-ranking/','/en/standings/','/en/teams/','/en/model/']+[f'/en/teams/{slug(t)}/' for t in teams]
    today=datetime.now(timezone.utc).strftime('%Y-%m-%d')

    ns='http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', ns)
    root=ET.Element(f'{{{ns}}}urlset')
    for path in ko + en:
        url=ET.SubElement(root, f'{{{ns}}}url')
        ET.SubElement(url, f'{{{ns}}}loc').text = SITE + path
        ET.SubElement(url, f'{{{ns}}}lastmod').text = today

    tree=ET.ElementTree(root)
    try:
        ET.indent(tree, space='  ')
    except AttributeError:
        pass
    sitemap_path=DOCS/'sitemap.xml'
    tree.write(sitemap_path, encoding='utf-8', xml_declaration=True)

    # Fail the build immediately if the generated sitemap is malformed or incomplete.
    check=ET.parse(sitemap_path).getroot()
    generated=check.findall(f'{{{ns}}}url')
    expected=len(ko)+len(en)
    if len(generated) != expected:
        raise RuntimeError(f'sitemap URL count mismatch: expected {expected}, got {len(generated)}')

    (DOCS/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n',encoding='utf-8')



def build_interactive_english_home():
    """Create /en/ from the exact Korean interactive homepage structure, translating presentation text only."""
    src = (DOCS / 'index.html').read_text(encoding='utf-8')
    s = src

    replacements = [
        ('<html lang="ko">','<html lang="en">'),
        ('<meta name="description" content="EPL 승·무·패 확률, 기대 승점, 일정 난이도, 파워 랭킹과 확률의 이유를 데이터로 분석합니다." />','<meta name="description" content="Data-driven EPL win, draw and loss probabilities, expected points, fixture difficulty, power rankings and model explanations." />'),
        ('<title>EPL 경기 예측·일정 난이도·파워 랭킹 | EPL Run-in Lab</title>','<title>EPL Predictions, Fixture Difficulty & Power Rankings | EPL Run-in Lab</title>'),
        ('<link rel="canonical" href="https://epl-run-in-lab.github.io/epl-run-in-lab/">','<link rel="canonical" href="https://epl-run-in-lab.github.io/epl-run-in-lab/en/">'),
        ('<meta property="og:title" content="EPL 경기 예측·일정 난이도·파워 랭킹 | EPL Run-in Lab">','<meta property="og:title" content="EPL Predictions, Fixture Difficulty & Power Rankings | EPL Run-in Lab">'),
        ('<meta property="og:description" content="EPL 승·무·패 확률, 기대 승점, 향후 일정 난이도와 파워 랭킹을 데이터 모델로 분석합니다.">','<meta property="og:description" content="Data-driven EPL probabilities, expected points, upcoming fixture difficulty and power rankings.">'),
        ('<meta property="og:url" content="https://epl-run-in-lab.github.io/epl-run-in-lab/">','<meta property="og:url" content="https://epl-run-in-lab.github.io/epl-run-in-lab/en/">'),
        ('aria-label="메뉴 열기"','aria-label="Open menu"'),
        ('aria-label="언어 선택"','aria-label="Choose language"'),
        ('<a href="./" data-lang="ko"','<a href="../" data-lang="ko"'),
        ('<a href="./en/" data-lang="en"','<a href="./" data-lang="en"'),
        ('>주의사항</button>','>Notice</button>'),
        ('aria-label="다크모드로 전환" title="다크모드로 전환"','aria-label="Switch to dark mode" title="Switch to dark mode"'),
        ('🏠 홈','🏠 Home'),('🎯 경기 예측','🎯 Match Predictions'),('📅 일정 난이도','📅 Fixture Difficulty'),('⚡ 파워 랭킹','⚡ Power Ranking'),('🏆 EPL 순위','🏆 EPL Standings'),('🔍 팀 분석','🔍 Team Analysis'),('🧪 모델 소개','🧪 Model'),
        ('EPL의 현재와 앞으로를 한눈에','The EPL: Now and What’s Ahead'),
        ('승·무·패 확률, 기대 승점, 일정 난이도와 그 이유','Win, draw and loss probabilities, expected points, fixture difficulty and why'),
        ('데이터 불러오는 중…','Loading data…'),
        ('3경기','3 matches'),('5경기','5 matches'),('10경기','10 matches'),
        ('현재 EPL 순위','Current EPL Position'),('향후 기대 승점','Projected Points'),('일정 난이도 순위','Fixture Ease Rank'),('xPts가 높을수록 쉬운 편','Higher xPts means an easier projected run'),('최근 결과','Recent Results'),('현재 시즌 최근 경기','Latest matches this season'),
        ('다음 경기','Next Match'),('자세히 분석하기 →','View Detailed Analysis →'),
        ('예측 해석 시 참고하세요','How to interpret these predictions'),
        ('확률은 통계 모델의 추정치입니다. 부상·로테이션·전술 변화처럼 실시간으로 완전히 반영되지 않는 변수가 있으며, 일부 현재 시즌 세부 지표는 무료 데이터의 한계로 최신 결과와 기존 확보 지표를 함께 사용합니다.','Probabilities are statistical model estimates. Injuries, rotation and tactical changes may not be fully reflected in real time, and some current-season detailed metrics combine the latest results with previously available data because of free-data limitations.'),
        ('향후 일정 미리보기','Upcoming Fixtures Preview'),('전체 일정 난이도 →','Full Fixture Difficulty →'),
        ('<h1>경기 예측</h1>','<h1>Match Predictions</h1>'),('확률뿐 아니라 왜 그런 확률이 나왔는지도 설명합니다.','See not only the probabilities, but also why the model produced them.'),
        ('<h1>일정 난이도</h1>','<h1>Fixture Difficulty</h1>'),('향후 일정에서 기대할 수 있는 승점을 기준으로 20개 팀을 비교합니다.','Compare all 20 teams using expected points from their upcoming fixtures.'),
        ('일정 난이도 순위','Fixture Difficulty Ranking'),('<th>팀</th>','<th>Team</th>'),('향후 일정','Upcoming Fixtures'),
        ('<h1>파워 랭킹</h1>','<h1>Power Ranking</h1>'),('실제 순위가 아니라, 같은 조건에서 붙었을 때 모델이 어느 팀을 더 강하게 보는지 비교합니다.','This is not the league table. It compares which teams the model rates as stronger under the same conditions.'),
        ('Power Score는 어떻게 계산하나요?','How is Power Score calculated?'),('리그 평균 수준의 가상 상대와 홈·원정에서 각각 붙는다고 가정합니다.','Each team is evaluated against a league-average virtual opponent, once at home and once away.'),
        ('현재 예측 모델이 각 팀의 기대 승점(xPts)을 계산한 뒤 홈·원정 값을 평균냅니다. 그 시점에서 가장 높은 팀을 100으로 두고 다른 팀을 상대적으로 환산한 값이 Power Score입니다. 최근 승점, 득점·실점, 슈팅·유효슈팅, 홈·원정 경기력이 같은 예측 모델을 통해 반영됩니다. 따라서 실제 승점이나 <b>Current EPL Position</b>와는 다른 지표입니다.','The prediction model calculates each team’s expected points (xPts) at home and away and averages them. The highest-rated team is set to 100 and the others are scaled relative to it. Recent points, goals for and against, shots, shots on target, and home/away performance all feed through the same model. This is therefore different from actual league points or <b>Current EPL Position</b>.'),
        ('<span>파워</span><span>팀</span><span>점수</span><span>Current EPL Position</span>','<span>Rank</span><span>Team</span><span>Score</span><span>Current EPL Position</span>'),
        ('<h1>EPL 순위</h1>','<h1>EPL Standings</h1>'),('현재 시즌 실제 경기 결과 기준 순위입니다.','The current table based on actual league results this season.'),('<th>경기</th><th>승</th><th>무</th><th>패</th><th>득실</th><th>승점</th>','<th>Pl</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th>'),
        ('<h1 id="teamPageTitle">팀 분석</h1>','<h1 id="teamPageTitle">Team Analysis</h1>'),('현재 상태와 향후 일정을 한 페이지에서 봅니다.','See current form and upcoming fixtures on one page.'),('현재 승점','Current Points'),('향후 5경기 xPts','Next 5 xPts'),('모델이 보는 현재 경기력','Current Model Form'),('향후 5경기','Next 5 Matches'),
        ('<h1>모델 소개</h1>','<h1>Model</h1>'),('예측이 어떤 데이터를 보고, 왜 이런 확률을 만드는지 설명합니다.','How the model uses data and why it produces these probabilities.'),('예측에 사용하는 정보','Inputs used by the model'),('최근 경기 흐름','Recent form'),('승점, 득점, 실점을 최근 경기일수록 더 큰 비중으로 반영합니다.','Points, goals scored and goals conceded are weighted more heavily for recent matches.'),('공격 기회 창출','Chance creation'),('확보 가능한 슈팅과 유효슈팅 정보를 사용합니다.','Uses available shots and shots-on-target data.'),('홈·원정 경기력','Home and away performance'),('전체 성적과 별도로 홈/원정 성적을 따로 계산합니다.','Home and away records are calculated separately from overall form.'),
        ('확률의 이유는 어떻게 계산하나요?','How are the probability reasons calculated?'),('각 요인을 리그 중립 수준으로 되돌린 뒤 모델을 다시 계산합니다. 이때 선택한 팀의 승리 확률이 얼마나 달라지는지를 %p로 보여줍니다. 요인 간 상호작용이 있으므로 각 효과를 단순히 더한 값이 최종 확률과 정확히 일치하지는 않습니다.','The model is recalculated after resetting each factor to a league-neutral level. The change in the selected team’s win probability is shown in percentage points. Because factors interact, the effects do not necessarily add up exactly to the final probability.'),
        ('승격팀은?','What about promoted teams?'),('EPL 표본이 적은 초반에는 직전 Championship 시즌 기록을 과거 승격팀 사례로 보수적으로 변환한 초기 전력값을 함께 사용하고, EPL 경기가 쌓이면 첫 10경기 동안 점차 영향이 줄어듭니다.','Early in the season, when a promoted club has little EPL data, a conservative initial strength estimate derived from its previous Championship season is used. Its influence gradually fades over the first 10 EPL matches.'),
        ('검색 가능한 분석 페이지','Searchable analysis pages'),('>경기 예측</a>','>Match Predictions</a>'),('>일정 난이도</a>','>Fixture Difficulty</a>'),('>파워 랭킹</a>','>Power Ranking</a>'),('>EPL 순위</a>','>EPL Standings</a>'),('>팀별 분석</a>','>Team Analysis</a>'),('>모델 소개</a>','>Model</a>'),
        ('예측 데이터 주의사항','Prediction Data Notice'),('aria-label="닫기"','aria-label="Close"'),
        ('EPL Run-in Lab의 승·무·패 확률과 기대 승점은 과거 및 현재 경기 데이터를 이용한 통계 모델의 추정치입니다. 팀 전력, 부상, 퇴장, 로테이션, 전술 변화처럼 모델에 실시간으로 완전히 반영되지 않는 변수가 존재할 수 있습니다.','EPL Run-in Lab’s win, draw and loss probabilities and expected points are statistical estimates based on historical and current match data. Team strength, injuries, dismissals, rotation and tactical changes may not be fully reflected in real time.'),
        ('현재 시즌의 일부 세부 경기 지표는 무료 데이터 소스에서 즉시 제공되지 않을 수 있어 최신 결과 데이터와 기존에 확보된 지표가 함께 사용될 수 있습니다.','Some detailed current-season metrics may not be immediately available from free data sources, so the model can combine the latest results with previously available metrics.'),
        ('이 수치는 경기 결과를 보장하거나 베팅을 권유하기 위한 정보가 아니라 EPL 일정과 경기 흐름을 데이터 관점에서 비교하기 위한 참고 자료입니다.','These figures do not guarantee match outcomes and are not betting recommendations. They are intended as a data-based reference for comparing EPL fixtures and team trends.'),
        ("themeToggle.title=d?'라이트모드로 전환':'다크모드로 전환'", "themeToggle.title=d?'Switch to light mode':'Switch to dark mode'"),
        ("text:'EPL 경기 예측·일정 난이도·파워 랭킹'", "text:'EPL predictions, fixture difficulty and power rankings'"),
        ("shareBtn.textContent='복사됨';setTimeout(()=>shareBtn.textContent='공유',1300)", "shareBtn.textContent='Copied';setTimeout(()=>shareBtn.textContent='Share',1300)"),
        ("'<span class=\"metric-sub\">현재 시즌 결과 없음</span>'", "'<span class=\"metric-sub\">No results this season</span>'"),
        ("'<div class=\"metric-sub\">예정된 경기가 없습니다.</div>'", "'<div class=\"metric-sub\">No upcoming fixtures.</div>'"),
        ('<div class="chance">승 ${pct(g.win)} · xPts ${fmt(g.xpts)}</div>','<div class="chance">Win ${pct(g.win)} · xPts ${fmt(g.xpts)}</div>'),
        ('<span>${displayTeam(t)} 승</span>','<span>${displayTeam(t)} Win</span>'),('<span>무승부</span>','<span>Draw</span>'),('<span>${displayTeam(t)} 패</span>','<span>${displayTeam(t)} Loss</span>'),
        ("st.rank+'위'", "'#'+st.rank"),("`${st.played}경기 · 승점 ${st.points}`", "`${st.played} matches · ${st.points} pts`"),("`경기당 ${fmt(r.xppg)}점`", "`${fmt(r.xppg)} pts/match`"),("`${r.rank}위 / ${(D.rankings?.[String(H)]||[]).length}`", "`#${r.rank} / ${(D.rankings?.[String(H)]||[]).length}`"),
        ('const factors=(g.details||[]).map(d=>','const factors=(g.details||[]).map(d=>'),
        ('${d.title}</div><p>${d.body}</p>','${d.titleEn||d.title}</div><p>${d.bodyEn||d.body}</p>'),
        ('<div class="metric-label">모델 해석</div>','<div class="metric-label">Model Interpretation</div>'),('${displayTeam(t)} 승 ${pct(g.win)}','${displayTeam(t)} Win ${pct(g.win)}'),
        ('${displayTeam(home)} vs ${displayTeam(away)}에서 모델이 계산한 선택 팀 기준 확률입니다. 아래에서 어떤 요소가 이 확률을 올리고 내렸는지 확인할 수 있습니다.','These are the selected team probabilities calculated by the model for ${displayTeam(home)} vs ${displayTeam(away)}. Below, you can see which factors push the win probability up or down.'),
        ('왜 ${displayTeam(t)}의 승리 확률이 ${pct(g.win)}인가?','Why is ${displayTeam(t)}’s win probability ${pct(g.win)}?'),
        ('설명 데이터가 없습니다.','No explanation data is available.'),('<b>승격팀 전력 보정</b>','<b>Promoted-team strength adjustment</b>'),('${g.promotionNote}','${g.promotionNoteEn||g.promotionNote}'),
        ('각 %p는 해당 요인만 리그 중립 수준으로 바꿔 다시 계산했을 때 선택한 팀의 승리 확률이 얼마나 달라지는지를 뜻합니다. 여러 요인은 서로 영향을 주므로 단순 합산값과 최종 확률은 정확히 일치하지 않을 수 있습니다.','Each percentage-point effect shows how much the selected team’s win probability changes when only that factor is reset to a league-neutral level. Because factors interact, the simple sum of the effects may not exactly match the final probability.'),
        ('`${displayTeam(selectedTeam)} 향후 ${H}경기`','`${displayTeam(selectedTeam)} · Next ${H} matches`'),('중립 상대 xPts','Neutral-opponent xPts'),("r.currentEPLRank+'위'", "'#'+r.currentEPLRank"),('새 update_predictions.py로 자동 업데이트를 한 번 실행하면 파워 랭킹이 생성됩니다.','Run the automatic update once with the latest update_predictions.py to generate the power ranking.'),
        ("pr?`파워 랭킹 ${pr.rank}위`:'자동 업데이트 후 표시'", "pr?`Power rank #${pr.rank}`:'Shown after automatic update'"),
        ("['최근 가중 PPG',ms.ppg]", "['Weighted recent PPG',ms.ppg]"),("['최근 가중 득점',ms.gf]", "['Weighted goals scored',ms.gf]"),("['최근 가중 실점',ms.ga]", "['Weighted goals conceded',ms.ga]"),("['슈팅',ms.shots]", "['Shots',ms.shots]"),("['유효슈팅',ms.sot]", "['Shots on target',ms.sot]"),("['홈 / 원정 PPG'", "['Home / Away PPG'"),
        ("fetch('./data/predictions.json?ts='", "fetch('../data/predictions.json?ts='"),
        ("'데이터 기준: '+(D.asOf||'알 수 없음')+' · 자동 갱신'", "'Data as of: '+(D.asOf||'Unknown')+' · Auto-updated'"),
        ("'데이터를 불러오지 못했습니다.'", "'Could not load data.'"),('predictions.json을 불러올 수 없습니다. GitHub Pages 배포와 Actions 실행 상태를 확인하세요.','Could not load predictions.json. Check the GitHub Pages deployment and Actions run status.'),
    ]
    for old,new in replacements:
        s = s.replace(old,new)

    # Final EN-only cleanup after all generic replacements.
    # '향후 일정' -> 'Upcoming Fixtures' leaves the Korean particle '을',
    # producing 'Upcoming Fixtures을', so handle that exact intermediate form.
    s = s.replace('현재 상태와 Upcoming Fixtures을 한 페이지에서 봅니다.',
                  'See current form and upcoming fixtures on one page.')
    s = s.replace('현재 상태와 Upcoming Fixtures를 한 페이지에서 봅니다.',
                  'See current form and upcoming fixtures on one page.')
    s = s.replace('현재 상태와 향후 일정을 한 페이지에서 봅니다.',
                  'See current form and upcoming fixtures on one page.')
    s = s.replace('향후 5 matches xPts', 'Next 5 xPts')
    s = s.replace('향후 5경기 xPts', 'Next 5 xPts')
    s = s.replace('향후 5 matches', 'Next 5 Matches')
    s = s.replace('향후 5경기', 'Next 5 Matches')

    # Ensure English homepage SEO URLs are self-referencing while Korean remains the alternate.
    s = s.replace('<link rel="alternate" hreflang="ko" href="https://epl-run-in-lab.github.io/epl-run-in-lab/en/">','<link rel="alternate" hreflang="ko" href="https://epl-run-in-lab.github.io/epl-run-in-lab/">')
    s = s.replace('<link rel="alternate" hreflang="en" href="https://epl-run-in-lab.github.io/epl-run-in-lab/">','<link rel="alternate" hreflang="en" href="https://epl-run-in-lab.github.io/epl-run-in-lab/en/">')
    # Bottom crawlable links should stay inside the English URL tree.
    for rel in ['predictions','fixture-difficulty','power-ranking','standings','teams','model']:
        s = s.replace(f'href="./{rel}/"', f'href="./{rel}/"')

    dest = DOCS / 'en' / 'index.html'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(s, encoding='utf-8')

if __name__=='__main__':
    build()
    build_interactive_english_home()
