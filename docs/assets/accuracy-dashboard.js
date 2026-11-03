/* Forecast accuracy dashboard, no external dependencies. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
const en = (document.documentElement.lang||'ko').toLowerCase().startsWith('en');
const labels = en ? {
 all:'All teams',hit:'Correct',miss:'Incorrect',loading:'Loading verified results…',
 failed:'Unable to load prediction accuracy data.',max:'Highest-probability outcome',
 warn:n=>'Only '+n+' completed matches have eligible pre-match predictions. This is a small sample, not proof of model quality.',
 confidence:'Avg. confidence',observed:'Actual accuracy',sparse:'Small sample',matches:'matches',
 more:'Show more matches',details:'Match details',
 home:'Home',draw:'Draw',away:'Away',correct:'Correct',incorrect:'Missed',
 frozen:'Frozen before kickoff',empty:'No matches match these filters.'
} : {
 all:'전체 팀',hit:'예측 적중',miss:'예측 실패',loading:'검증 결과를 불러오는 중…',
 failed:'예측 정확도 데이터를 불러오지 못했습니다.',max:'가장 높은 확률의 결과',
 warn:n=>'경기 전 예측과 종료 결과가 연결된 '+n+'경기만 평가했습니다. 표본이 작아 모델의 우수성을 증명하지 않습니다.',
 confidence:'평균 예측 확신도',observed:'실제 적중률',sparse:'적은 표본',matches:'경기',
 more:'경기 더 보기',details:'경기 상세',
 home:'홈승',draw:'무승부',away:'원정승',correct:'적중',incorrect:'실패',
 frozen:'경기 시작 전 저장한 확률',empty:'조건에 맞는 경기가 없습니다.'
};
const koNames={'Arsenal':'아스널','Aston Villa':'애스턴 빌라','Bournemouth':'본머스','Brentford':'브렌트퍼드','Brighton':'브라이턴','Burnley':'번리','Chelsea':'첼시','Coventry':'코번트리','Crystal Palace':'크리스털 팰리스','Everton':'에버튼','Fulham':'풀럼','Hull':'헐 시티','Ipswich':'입스위치','Leeds':'리즈','Liverpool':'리버풀','Man City':'맨시티','Man United':'맨유','Newcastle':'뉴캐슬','Nottingham':'노팅엄','Sunderland':'선덜랜드','Tottenham':'토트넘','West Ham':'웨스트햄','Wolves':'울버햄프턴'};
const teamName = n => en ? n : (koNames[n]||n);
const fmt = (n,d=2) => typeof n==='number' && Number.isFinite(n) ? n.toFixed(d) : '—';
const pct = p => fmt(p*100,1)+'%';
const signed = n => (n>0?'+':'')+fmt(n);
const el=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e};
const td=(tr,txt,cls)=>{const e=el('td',cls,txt);tr.append(e);return e};
const put=(id,txt)=>{const target=$(id);if(target)target.textContent=txt};
let data=null, team='all', hit='all', visible=20;
function summary(){
 const r=data.results,s=data.sample;
 put('accCount',String(s.eligibleFinalizedFixtures));
 put('accAccuracy',pct(r.top1Accuracy));
 put('accBrier',fmt(r.multiclassBrierSum,4));
 put('accLoss',fmt(r.logLoss,4));
 put('accBrier2',fmt(r.multiclassBrierSum,4));
 put('accLoss2',fmt(r.logLoss,4));
 put('accCountNote',r.top1Correct+' / '+s.eligibleFinalizedFixtures+(en?' correct':' 적중'));
 put('accDates',s.firstFixtureDate+' — '+s.lastFixtureDate);
 put('accLimit',labels.warn(s.eligibleFinalizedFixtures));
 put('accBaseBrier',fmt(r.uniformOneThirdBrier,4));
 put('accBaseLoss',fmt(r.uniformOneThirdLogLoss,4));
 put('accBaseHome',pct(r.alwaysPredictHomeAccuracyOnSample));
 put('accStatus',labels.frozen+' · '+s.eligibleFinalizedFixtures+' '+labels.matches);
}
function selectTeams(){
 const input=$('accTeamFilter');
 input.replaceChildren(new Option(labels.all,'all'));
 for(const t of data.teamRecords.slice().sort((a,b)=>teamName(a.team).localeCompare(teamName(b.team),en?'en':'ko')))
   input.add(new Option(teamName(t.team),t.team));
}
function renderTeams(){
 const body=$('accTeamRows');body.replaceChildren();
 const max=Math.max(1,...data.teamRecords.map(t=>Math.abs(t.pointsAboveExpected)));
 for(const t of data.teamRecords){
   const row=el('tr'),nameCell=td(row,'');
   const button=el('button','acc-team-link',teamName(t.team));button.type='button';
   button.addEventListener('click',()=>{
     team=t.team;$('accTeamFilter').value=team;visible=20;renderFixtures();
     $('accFixtureSection').scrollIntoView({behavior:'smooth',block:'start'});
   });
   nameCell.append(button);
   td(row,String(t.matches));td(row,fmt(t.expectedPoints));td(row,String(t.actualPoints));
   const slot=td(row,'');const modifier=t.pointsAboveExpected>0?'positive':t.pointsAboveExpected<0?'negative':'';
   slot.append(el('span','acc-delta '+modifier,signed(t.pointsAboveExpected)));
   const track=el('div','acc-small-bar'),bar=el('i',modifier);
   bar.style.width=fmt(100*Math.abs(t.pointsAboveExpected)/max,1)+'%';
   track.append(bar);slot.append(track);body.append(row);
 }
}
function calibration(){
 const body=$('accCalibrationRows');body.replaceChildren();
 const groups=[[0,.4,'<40%'],[.4,.5,'40–50%'],[.5,.6,'50–60%'],[.6,1.001,'≥60%']];
 for(const [min,max,label] of groups){
   const set=data.fixtures.filter(r=>{const v=Math.max(...Object.values(r.probabilities));return v>=min && v<max});
   const confidence=set.length?set.reduce((sum,r)=>sum+Math.max(...Object.values(r.probabilities)),0)/set.length:null;
   const observed=set.length?set.reduce((sum,r)=>sum+r.correctTop1,0)/set.length:null;
   const box=el('div','acc-cal-row'),head=el('div','acc-cal-top');
   head.append(el('span','',label),el('span','muted',set.length+' '+labels.matches));box.append(head);
   for(const [name,value,klass] of [[labels.confidence,confidence,''],[labels.observed,observed,'observed']]){
     const row=el('div','acc-cal-detail'),track=el('div','acc-track'),bar=el('i',klass);
     bar.style.width=value===null?'0%':pct(Math.max(0,Math.min(1,value)));
     track.append(bar);row.append(el('span','',name),track,el('span','',value===null?'—':pct(value)));
     box.append(row);
   }
   if(set.length && set.length<5)box.append(el('div','acc-footnote',labels.sparse));
   body.append(box);
 }
}
function fixtures(){
 const rows=data.fixtures.filter(r=>(team==='all'||team===r.home||team===r.away)
   &&(hit==='all'||(hit==='correct'?r.correctTop1===1:r.correctTop1===0)))
   .slice().sort((a,b)=>b.utcDate.localeCompare(a.utcDate));
 const body=$('accFixtureRows');body.replaceChildren();
 put('accFixtureCount',rows.length+' '+labels.matches);
 $('accNoFixtures').classList.toggle('acc-hidden',rows.length>0);
 for(const r of rows.slice(0,visible)){
   const tr=el('tr');
   td(tr,r.date);td(tr,teamName(r.home)+' — '+teamName(r.away));
   td(tr,r.homeGoals+'–'+r.awayGoals);
   td(tr,[r.probabilities.home,r.probabilities.draw,r.probabilities.away].map(pct).join(' / '),'acc-prob');
   td(tr,labels[r.mostLikelyOutcome]||r.mostLikelyOutcome);
   const status=td(tr,'');status.append(el('span','acc-badge '+(r.correctTop1?'hit':'miss'),r.correctTop1?labels.correct:labels.incorrect));
   const detail=td(tr,'');
   const slug=n=>n.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
   const link=el('a','acc-link',labels.details);
   link.href=(en?'../':'./')+'matches/'+r.date+'/'+slug(r.home)+'-'+slug(r.away)+'/';
   detail.append(link);body.append(tr);
 }
 $('accShowMore').classList.toggle('acc-hidden',rows.length<=visible);
}
function wire(){
 $('accTeamFilter').addEventListener('change',e=>{team=e.target.value;visible=20;fixtures()});
 $('accHitFilter').addEventListener('change',e=>{hit=e.target.value;visible=20;fixtures()});
 $('accShowMore').addEventListener('click',()=>{visible+=20;fixtures()});
}
async function load(){
 put('accStatus',labels.loading);
 try{
   const url=(en?'../':'./')+'data/forecast_accuracy.json?v='+Date.now();
   const response=await fetch(url,{cache:'no-store'});
   if(!response.ok)throw Error('HTTP '+response.status);
   data=await response.json();
   if(!data.results||!data.sample||!Array.isArray(data.fixtures)||!Array.isArray(data.teamRecords))
     throw Error('Unsupported accuracy schema');
   summary();selectTeams();renderTeams();calibration();fixtures();
 }catch(err){put('accStatus',labels.failed);console.error('Accuracy dashboard',err)}
}
wire();load();
})();
