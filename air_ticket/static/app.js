const form = document.querySelector('#search-form');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const notice = document.querySelector('#notice');
const submit = document.querySelector('#submit');
const more = document.querySelector('#show-more');
const money = value => new Intl.NumberFormat('ko-KR').format(value) + '원';
const cities = {ICN:'서울 인천',GMP:'서울 김포',PUS:'부산 김해',CJU:'제주',NRT:'도쿄 나리타',HND:'도쿄 하네다',KIX:'오사카 간사이',FUK:'후쿠오카',TPE:'타이베이',BKK:'방콕',DAD:'다낭',SIN:'싱가포르'};
let currentResult = null;
let visibleCount = 0;
function localDate(offset) {
  const d = new Date(); d.setDate(d.getDate() + offset);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function dateLabel(value) {
  const date = value.slice(0,10).split('-');
  return `${date[0]}.${date[1]}.${date[2]}${value.includes('T') ? ' '+value.slice(11,16) : ''}`;
}
form.elements.start.value = localDate(14);
form.elements.end.value = localDate(21);
form.elements.start.min = form.elements.end.min = localDate(0);
fetch('/api/status').then(r => {if(!r.ok) throw new Error(); return r.json();}).then(data => {
  const option = document.querySelector('#mode option[value=live]');
  if(data.live_available){ option.disabled=false; option.textContent = data.production ? '실제 항공권 검색' : 'Amadeus 테스트 데이터'; }
}).catch(() => {status.textContent='서버 연결을 확인해 주세요.';});
function node(tag, className, text) {
  const el=document.createElement(tag); el.className=className; el.textContent=text; return el;
}
function setSubmitReady() {
  submit.replaceChildren(document.createTextNode('항공권 찾아보기 '));
  const arrow = node('span','','↗'); arrow.setAttribute('aria-hidden','true'); submit.append(arrow);
  submit.disabled=false;
}
function renderMore() {
  if (!currentResult) return;
  const body=currentResult;
  const next=body.offers.slice(visibleCount,visibleCount+6);
  next.forEach((offer,index)=>{
    const first=visibleCount+index===0;
    const card=node('article',`ticket${first?' best':''}`,'');
    const top=node('div','ticket-top','');
    top.append(node('span','tag',first?'✦ 검색 결과 최저가':`${offer.nights}박 · ${offer.trip_days}일 일정`),node('span','airline',offer.carrier));
    const route=node('div','route','');
    const origin=node('div','airport','');origin.append(node('strong','',body.origin),node('small','',cities[body.origin]||'출발 공항'));
    const dest=node('div','airport','');dest.append(node('strong','',body.destination),node('small','',cities[body.destination]||'도착 공항'));
    const line=node('div','route-line','');
    const track=node('span','','· · · ✈ · · ·');track.setAttribute('aria-hidden','true');
    line.append(track,node('small','',offer.stops===0?'왕복 · 직항':`왕복 · 최대 ${offer.stops}회 경유`));
    route.append(origin,line,dest);
    card.append(top,route,node('p','dates',`가는 편 ${dateLabel(offer.departure)}\n오는 편 ${dateLabel(offer.return_date)}${body.source==='sample'?'':` · 도착 ${dateLabel(offer.arrival)}`}`));
    const bottom=node('div','ticket-bottom','');
    bottom.append(node('div','trip',`${offer.nights}박 기준 · ${offer.trip_days}일 일정\n${offer.weekend?'주말 포함':'평일 여행'}`));
    const price=node('div','price',money(offer.price));
    price.append(node('small','',`성인 ${body.adults}명 총액 · 1인 ${money(Math.ceil(offer.price/body.adults))}`));
    bottom.append(price);card.append(bottom);results.append(card);
  });
  visibleCount+=next.length;
  more.hidden=visibleCount>=body.offers.length;
  more.textContent=`항공권 더 보기 (${visibleCount} / ${body.offers.length}) ↓`;
}
more.addEventListener('click',()=>{
  const firstNewIndex=visibleCount;
  renderMore();
  const firstNew=results.children[firstNewIndex];
  if(firstNew){firstNew.tabIndex=-1;firstNew.focus({preventScroll:true});}
});
document.querySelectorAll('[data-airport]').forEach(button=>{
  button.addEventListener('click',()=>{
    form.elements.destination.value=button.dataset.airport;
    form.elements.destination.focus({preventScroll:true});
    document.querySelector('#search-panel').scrollIntoView({block:'start'});
  });
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  const data=Object.fromEntries(new FormData(form));
  data.direct=form.elements.direct.checked;
  ['min_nights','max_nights','adults','budget'].forEach(k=>data[k]=Number(data[k]));
  submit.disabled=true; submit.textContent='날짜별 항공권 비교 중…';
  status.textContent='선택한 조건에 맞는 날짜 조합을 검색하고 있어요.';
  results.replaceChildren();more.hidden=true;currentResult=null;visibleCount=0;
  results.setAttribute('aria-busy','true');
  notice.textContent = data.mode === 'sample' ? '샘플 데이터 · 표시되는 가격과 항공사는 체험용이며 실제 항공권이 아닙니다.' : '항공권을 조회 중입니다. 테스트 환경의 결과는 실제 운임이 아닙니다.';
  try {
    const response=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const body=await response.json();
    if(!response.ok) throw new Error(body.error || '검색하지 못했습니다. 다시 시도해 주세요.');
    notice.textContent = body.source === 'sample' ? '샘플 데이터 · 표시되는 가격과 항공사는 체험용이며 실제 항공권이 아닙니다.' : body.source === 'test' ? 'Amadeus 테스트 데이터 · 실제 가격이나 예약 가능 여부를 보장하지 않습니다.' : 'Amadeus 검색 결과입니다. 전체 시장 최저가를 보장하지 않으며 날짜별 최대 50건을 조회합니다.';
    status.textContent=`날짜 조합 ${body.searched_dates}개 비교 · 조건에 맞는 항공권 ${body.offers.length}개`;
    currentResult=body;
    if(!body.offers.length){
      const empty=node('div','empty','');const copy=node('div','','');
      copy.append(node('h3','','아직 딱 맞는 여행을 찾지 못했어요.'),node('p','','예산이나 여행 기간, 주말 조건을 조금 바꿔 다시 검색해 보세요.'));
      empty.append(node('span','empty-icon','↗'),copy);results.append(empty);
    }
    renderMore();
  } catch(error){
    status.textContent=error.message;
    results.append(node('div','empty','검색을 완료하지 못했어요. 위 안내를 확인한 뒤 다시 시도해 주세요.'));
  }
  finally {
    results.setAttribute('aria-busy','false');setSubmitReady();
    document.querySelector('.results').scrollIntoView({block:'start'});
  }
});
