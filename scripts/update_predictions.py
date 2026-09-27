#!/usr/bin/env python3
import json, os, re, html
from pathlib import Path
from datetime import datetime, timezone
import requests

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'; PRED=DOCS/'data/predictions.json'; ARCH=DOCS/'data/match_archive.json'
BASE='https://api.goal-api.com/v1'; LEAGUE='cmr77dvkr005nrx06lp7rvp49'
SITE='https://epl-run-in-lab.github.io/epl-run-in-lab'
ALIASES={"Manchester Utd":"Man United","Manchester United":"Man United","Manchester City":"Man City","Nottingham Forest":"Nottingham","Brighton & Hove Albion":"Brighton","Tottenham Hotspur":"Tottenham","Newcastle United":"Newcastle","AFC Bournemouth":"Bournemouth","Ipswich Town":"Ipswich","Hull City":"Hull","Coventry City":"Coventry","Leeds United":"Leeds","Arsenal FC":"Arsenal"}
def canon(x): return ALIASES.get(str(x).strip(),str(x).strip())
def slug(x): return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',x.lower())).strip('-')
def api(path):
    key=os.getenv('GOAL_API_KEY')
    if not key: raise RuntimeError('GOAL_API_KEY secret is missing.')
    r=requests.get(BASE+path,headers={'Authorization':f'Bearer {key}'},timeout=30); r.raise_for_status(); j=r.json()
    if not j.get('success',False): raise RuntimeError(f'GOAL API error for {path}: {j}')
    return j.get('data',[])
def load_archive():
    if not ARCH.exists(): return {'version':1,'startedAt':datetime.now(timezone.utc).isoformat(),'matches':{}}
    return json.loads(ARCH.read_text(encoding='utf-8'))
def key_for(s): return str(s.get('footballDataId') or f"{s['date']}|{s['home']}|{s['away']}")
def normalize_list(v): return v if isinstance(v,list) else []
def timeline(goals,cards,subs):
    out=[]
    for g in goals:
        scorer=g.get('homeScorer') or g.get('awayScorer') or 'Unknown'; side='home' if g.get('homeScorer') else 'away'
        assist=g.get('homeAssist') or g.get('awayAssist')
        out.append({'minute':g.get('time'),'minuteNum':g.get('timeNum') or int(str(g.get('time','0')).split('+')[0]),'type':'GOAL','side':side,'player':scorer,'assist':assist,'score':g.get('score')})
    for c in cards:
        player=c.get('homeFault') or c.get('awayFault') or 'Unknown'; side='home' if c.get('homeFault') else 'away'
        out.append({'minute':c.get('time'),'minuteNum':c.get('timeNum') or int(str(c.get('time','0')).split('+')[0]),'type':'CARD','side':side,'player':player,'card':c.get('card')})
    for x in subs:
        team=canon(x.get('team','')); side=x.get('side')
        out.append({'minute':x.get('time'),'minuteNum':x.get('timeNum') or int(str(x.get('time','0')).split('+')[0]),'type':'SUBSTITUTION','side':side,'team':team,'substitution':x.get('substitution')})
    return sorted(out,key=lambda z:(z.get('minuteNum',0),z.get('type','')))
def find_result(snapshot, results):
    for r in results:
        if r.get('matchStatus')!='FINISHED': continue
        if canon(r.get('homeTeamName'))==snapshot['home'] and canon(r.get('awayTeamName'))==snapshot['away']:
            return r
    return None
def pct(x): return f'{float(x)*100:.1f}%'
def esc(x): return html.escape(str(x),quote=True)
def factor_lines(factors,lang='ko'):
    if not factors: return '<p class="muted">저장된 요인 설명이 없습니다.</p>' if lang=='ko' else '<p class="muted">No saved factor explanation is available.</p>'
    rows=[]
    for f in factors[:6]:
        title=f.get('title' if lang=='ko' else 'titleEn') or f.get('title') or f.get('group','')
        text=f.get('text' if lang=='ko' else 'textEn') or f.get('text') or ''
        rows.append(f'<div class="factor"><b>{esc(title)}</b><div class="muted">{esc(text)}</div></div>')
    return ''.join(rows)
def scorer_lines(events,side):
    a=[]
    for e in events:
        if e['type']=='GOAL' and e.get('side')==side:
            name=e['player'].replace('(o.g.)','').strip(); og=' (OG)' if '(o.g.)' in e['player'] else ''
            a.append(f"{esc(name)} {esc(e['minute'])}'{og}")
    return '<br>'.join(a) or '&nbsp;'
def event_html(events,home,away,lang):
    rows=[]
    for e in events:
        team=home if e.get('side')=='home' else away if e.get('side')=='away' else e.get('team','')
        if e['type']=='GOAL':
            label='득점' if lang=='ko' else 'Goal'; detail=esc(e['player'])+(f" · {'도움' if lang=='ko' else 'Assist'} {esc(e['assist'])}" if e.get('assist') else '')
        elif e['type']=='CARD': label='카드' if lang=='ko' else 'Card'; detail=f"{esc(e['player'])} · {esc(e.get('card',''))}"
        else:
            label='교체' if lang=='ko' else 'Substitution'; detail=esc(e.get('substitution','')).replace('|',' → ')
        rows.append(f'<div class="event"><span class="minute">{esc(e.get("minute","?"))}\'</span><div><b>{esc(team)} · {label}</b><div class="muted">{detail}</div></div></div>')
    return ''.join(rows) or ('<p class="muted">기록된 이벤트가 없습니다.</p>' if lang=='ko' else '<p class="muted">No events recorded.</p>')
def page(m,lang='ko'):
    s=m['snapshot']; r=m['result']; ev=m.get('timeline',[]); home=s['home']; away=s['away']; date=s['date']; path=f"/matches/{date}/{slug(home)}-{slug(away)}/"; canonical=SITE+('/en'+path if lang=='en' else path)
    if lang=='ko':
        title=f'{home} {r["homeGoals"]}-{r["awayGoals"]} {away} 경기 분석 | EPL Run-in Lab'; lead=f'{date} EPL 경기 결과와 경기 전 EPL Run-in Lab 예측을 함께 확인합니다.'; pred='경기 전 EPL Run-in Lab 예측'; factors='예측에 영향을 준 요소'; timeline_title='경기 타임라인'; captured=f"예측 저장 시각: {esc(s['capturedAt'])} · 킥오프 전에 저장된 값으로 경기 종료 후 다시 계산하지 않습니다."; labels=('홈승','무승부','원정승','기대 승점')
    else:
        title=f'{home} {r["homeGoals"]}-{r["awayGoals"]} {away} Match Report | EPL Run-in Lab'; lead=f'{date} Premier League result with the pre-match EPL Run-in Lab prediction snapshot.'; pred='Pre-match EPL Run-in Lab prediction'; factors='Factors behind the prediction'; timeline_title='Match timeline'; captured=f"Prediction captured: {esc(s['capturedAt'])}. This snapshot was saved before kickoff and is not recalculated after the result."; labels=('Home win','Draw','Away win','Expected points')
    return f'''<!doctype html><html lang="{'en' if lang=='en' else 'ko'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(lead)}"><link rel="canonical" href="{canonical}"><script async src="https://www.googletagmanager.com/gtag/js?id=G-2MHM6WELBT"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','G-2MHM6WELBT');</script><style>:root{{--bg:#f5f7fb;--panel:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--soft:#eef2f7}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,sans-serif}}.top{{height:64px;border-bottom:1px solid var(--line);background:#fff;display:flex;align-items:center;padding:0 20px}}.top a{{font-weight:900;color:var(--text);text-decoration:none}}main{{max-width:900px;margin:auto;padding:34px 18px 70px}}.muted{{color:var(--muted);font-size:13px}}.score{{display:grid;grid-template-columns:1fr auto 1fr;gap:18px;align-items:start;text-align:center;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:25px;margin:24px 0}}.team{{font-size:21px;font-weight:850}}.num{{font-size:38px;font-weight:950}}.scorers{{font-size:13px;line-height:1.7;margin-top:8px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.card,.factor{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}}.big{{font-size:24px;font-weight:900;margin-top:4px}}h2{{margin-top:34px}}.factor{{margin:9px 0}}.event{{display:grid;grid-template-columns:54px 1fr;gap:10px;padding:12px 0;border-bottom:1px solid var(--line)}}.minute{{font-weight:900}}@media(max-width:650px){{.score{{grid-template-columns:1fr auto 1fr;gap:8px;padding:18px 10px}}.team{{font-size:15px}}.num{{font-size:30px}}.grid{{grid-template-columns:1fr}}}}</style></head><body><div class="top"><a href="{SITE}/{'en/' if lang=='en' else ''}">EPL Run-in Lab</a></div><main><h1>{esc(home)} {r['homeGoals']}–{r['awayGoals']} {esc(away)}</h1><p class="muted">{esc(lead)}</p><section class="score"><div><div class="team">{esc(home)}</div><div class="scorers">{scorer_lines(ev,'home')}</div></div><div class="num">{r['homeGoals']} – {r['awayGoals']}</div><div><div class="team">{esc(away)}</div><div class="scorers">{scorer_lines(ev,'away')}</div></div></section><h2>{pred}</h2><div class="grid"><div class="card"><div class="muted">{labels[0]}</div><div class="big">{pct(s['homeWin'])}</div></div><div class="card"><div class="muted">{labels[1]}</div><div class="big">{pct(s['draw'])}</div></div><div class="card"><div class="muted">{labels[2]}</div><div class="big">{pct(s['awayWin'])}</div></div></div><p class="muted">{captured}</p><div class="grid"><div class="card"><div class="muted">{esc(home)} {labels[3]}</div><div class="big">{s['homeXPts']:.2f}</div></div><div class="card"><div class="muted">{esc(away)} {labels[3]}</div><div class="big">{s['awayXPts']:.2f}</div></div></div><h2>{factors}</h2>{factor_lines(s.get('homeFactors',[]),lang)}<h2>{timeline_title}</h2>{event_html(ev,home,away,lang)}</main></body></html>'''
def write_pages(archive):
    for m in archive['matches'].values():
        if m.get('status')!='FINISHED': continue
        s=m['snapshot']; rel=Path('matches')/s['date']/f"{slug(s['home'])}-{slug(s['away'])}"
        for lang in ('ko','en'):
            d=DOCS/(rel if lang=='ko' else Path('en')/rel); d.mkdir(parents=True,exist_ok=True); (d/'index.html').write_text(page(m,lang),encoding='utf-8')
def main():
    pred=json.loads(PRED.read_text(encoding='utf-8')); archive=load_archive(); now=datetime.now(timezone.utc).isoformat()
    # Freeze every currently upcoming model prediction. Existing snapshots are immutable.
    for s in pred.get('fixtureSnapshots',[]):
        k=key_for(s)
        if k not in archive['matches']:
            ss=dict(s); ss['capturedAt']=now; archive['matches'][k]={'status':'SNAPSHOT','snapshot':ss}
    results=api(f'/leagues/{LEAGUE}/results')
    for k,m in list(archive['matches'].items()):
        if m.get('status')=='FINISHED': continue
        r=find_result(m['snapshot'],results)
        if not r: continue
        fid=r['id']; goals=normalize_list(api(f'/fixtures/{fid}/events')); cards=normalize_list(api(f'/fixtures/{fid}/cards')); subs=normalize_list(api(f'/fixtures/{fid}/substitutions'))
        m.update({'status':'FINISHED','goalApiFixtureId':fid,'result':{'homeGoals':int(r['homeTeamScore']),'awayGoals':int(r['awayTeamScore']),'referee':r.get('matchReferee'),'stadium':r.get('matchStadium')},'goals':goals,'cards':cards,'substitutions':subs,'timeline':timeline(goals,cards,subs),'finalizedAt':now})
    ARCH.parent.mkdir(parents=True,exist_ok=True); ARCH.write_text(json.dumps(archive,ensure_ascii=False,indent=2),encoding='utf-8')
    # Add report links only when a genuine frozen pre-match snapshot and final result both exist.
    finished={(m['snapshot']['date'],m['snapshot']['home'],m['snapshot']['away']):m for m in archive['matches'].values() if m.get('status')=='FINISHED'}
    for team,p in pred.get('teamProfiles',{}).items():
        for rr in p.get('recentResults',[]):
            home=team if rr['venue']=='H' else rr['opponent']; away=rr['opponent'] if rr['venue']=='H' else team
            if (rr['date'],home,away) in finished: rr['reportUrl']=f"./matches/{rr['date']}/{slug(home)}-{slug(away)}/"
    PRED.write_text(json.dumps(pred,ensure_ascii=False,indent=2),encoding='utf-8'); write_pages(archive)
    print(f"Match archive: {len(archive['matches'])} snapshots, {len(finished)} finalized reports")
if __name__=='__main__': main()
