# EPL Run-in Lab — 상업화 대비 데이터 출처 전수 감사
검토일: 2026-11-03 | 대상: 현재 main 브랜치의 코드·배포 파일·데이터 원본 | 광고 배포 판정: **아직 불가 (기존 소스의 권리 확인·교체 필요)**

## 범위와 해석
- 이 문서는 광고·제휴·유료 사용을 포함한 상업적 운영을 가정한 **출처별 위험 및 기술 전환 계획**이다.
- *CC0 오픈 데이터*와 *API 무료 요금제*는 동의어가 아니다. 무료 접근이 재게시·광고·학습·장기 보유를 자동 허용하지 않는다.
- 구단 로고·사진·대회 상표는 경기 결과의 단순 사실정보와 달리 별도 권리가 존재할 수 있다.
- 기존 모델을 변경하거나 현재 운영 데이터 소스를 자동 교체하지 않는다. 모든 계약 및 변경은 검증 후 별도 승인/배포한다.

## 실제 사용 중인 소스 및 판단

### R1 — 모델 학습용 EPL·Championship 10시즌 CSV: **높은 위험 / 원출처 미확인**
- 입력: \`model_data/epl_master_2016_2026.csv\`, \`model_data/championship_master_2016_2026.csv\`
- 사용: \`scripts/update_predictions.py\` → \`load_historical\`, 과거 10시즌 학습, 슈팅/유효슈팅·승점 등.
- 확인된 사실: CSV 필드에 HS, AS, HST, AST, HF, AF, HC, AC, 카드 등이 존재한다. Football-Data.co.uk에서 흔히 쓰는 형식과 닮았지만 **원자료 출처를 코드만으로 확정할 수 없다**. 메타데이터/허락 증빙이 없어 상업적 사용을 승인할 수 없다.
- 관련 공식 조건: [Football-Data.co.uk Fair usage](https://football-data.co.uk/contact.php) 는 무료 CSV를 개인·학술 연구에 한정하며 **상업 및 AI 모델 학습에 사용 허가를 주지 않는다고 명시**한다. 원본이 이 소스였다면 데이터 교체/상업 계약이 필요하다.
- 대체 A: [OpenFootball CC0](https://github.com/openfootball/football.json) EPL/Championship 결과의 새 입력 파이프라인과 별도 모델 실험. 다만 슈팅/유효슈팅 등이 없어 기존 모델과 동일한 특성으로 재현할 수 없다.
- 대체 B: 상업용 역사적 경기·슈팅 자료가 필요한 경우 계약이 허용하는 API 이용. 후보: [TheStatsAPI](https://football-data.co.uk/thestatsapi.php), [FootyStats API](https://footystats.org/api/documentations/faq). 실제 역사적 기간, HS/HST 제공, 모델 학습과 공개 통계·DB 보유 권한을 계약서로 확인해야 한다.
- 전환 시 기존 모델의 과거 확률·설명을 덮어쓰지 않고 새 모델을 별도로 만들고, 시간 순서 검증/Brier Score/Log Loss 비교 후 교체한다.

### R2 — EPL 현재 시즌 일정·결과: **계약·표시 확인 필요**
- 입력: \`scripts/update_predictions.py\` → \`fetch_api\`, \`https://api.football-data.org/v4/competitions/PL/matches\` (\`FOOTBALL_DATA_TOKEN\` GitHub Secret).
- 사용: 최신 EPL 경기/예정 일정·실제 스코어·순위·예측 출력 JSON.
- 공식 [이용 약관](https://www.football-data.org/about) 2.3은 API 키가 단일 애플리케이션/도메인에 적용된다고 설명한다. 7.1은 사이트에 *Football data provided by the Football-Data.org API* 출처를 표시하도록 하고, 9.1은 **구독 해지 후 API에서 취득한 경기 자료를 사이트에서 참조하는 것을 제한**한다.
- [공식 FAQ](https://www.football-data.org/documentation/faq) 역시 명시적 화면 출처 표기를 요구한다.
- 검사 결과: 현재 \`docs/index.html\`과 \`scripts/build_i18n.py\`의 공통 템플릿에 위 필수 문구를 찾지 못함. 웹 화면에 출처 표시 추가 필요(실제 모든 생성 페이지에도 반영 확인).
- 상업적 사용, 임시 저장/중개, 사후 보유 및 광고 수익 포함 여부를 업체와 현재 구독 플랜 기준으로 확인할 것.

### R3 — 컵대회·유럽대항전 2026/27 실시간 일정: **차단 항목 (비상업 조건)**
- 입력: \`scripts/update_competition_schedule.py\` → [open-matchday](https://github.com/oladeeayo/open-matchday)
- 사용/공개: \`docs/data/competition_schedule.json\`, \`docs/data/competition_results_archive.json\`와 \`docs/data/fixture_congestion.json\`의 파생 일정, GitHub Pages.
- 원저장소는 informational, **non-commercial use**를 명시하며 원 제공자 권리도 유보한다. 파생 통계를 만들었다는 이유만으로 광고 수익화를 자동 허용한다고 볼 수 없다.
- 대체 A: 해당 시즌/대회에 충분한 결과를 갖춘 [OpenFootball CC0](https://github.com/openfootball/champions-league) 또는 국가별 CC0 소스. 다만 미공개 경기나 최신 컵 일정은 자료가 부실할 수 있어 자동 대체하지 않는다.
- 대체 B: 현 시즌 유럽대항전·EFL·FA컵 일정까지 포함한 상업용 API 계약. 데이터 수집 경로를 운영 본선과 분리해 새 파이프라인 검증 후 교체.
- 조치: 광고 도입 전에 open-matchday 인입/재배포 권한을 확보하거나 파이프라인을 완전히 교체한다.

### R4 — 경기별 골·카드·교체 이벤트: **상당한 계약 위험**
- 입력: \`scripts/update_match_archive.py\` → \`https://api.goal-api.com/v1\` (\`GOAL_API_KEY\` GitHub Secret)
- 사용/공개: \`docs/data/match_archive.json\`에 각 경기의 \`goals\`, \`cards\`, \`substitutions\`, \`timeline\`과 경기 상세 HTML이 포함된다.
- [GOAL API 공식 이용약관](https://goal-api.com/terms) §6은 API 자료를 서비스에 편입하는 제한적 권리를 주지만 원천 스포츠 데이터/제삼자 상업 권리를 보증하지 않는다. 원시 데이터의 별도 피드 재판매·재배포를 금지한다. §7은 로고/이미지의 지식재산권을 이전하지 않는다.
- 현재처럼 공개 JSON에 사건별 API 필드를 저장해 배포하는 방식은 **재게시/보유 및 공개 형태에 관한 서면 허가 확인이 특히 필요**하다. 이것이 곧바로 약관 위반이라는 단정은 아니다.
- 대체 A: 적법한 CC0 결과만으로 경기 결과 페이지 유지(이벤트·선수시간 정보는 제거 또는 미제공).
- 대체 B: 경기 이벤트의 퍼블리싱·서버 저장·광고를 명시적으로 허용하는 계약형 상세 데이터 제공업체로 이전.

### R5 — 신규 2021/22~2025/26 해외 4대 리그 + UEFA 역사 기록: **CC0 공개 데이터로 구축됨**
- 입력: \`data/history/snapshots/**\`, \`data/history/uefa/raw/**\`, 각 source manifest/코드.
- 출처: [openfootball/football.json](https://github.com/openfootball/football.json),
  [openfootball/champions-league](https://github.com/openfootball/champions-league),
  [openfootball/espana](https://github.com/openfootball/espana),
  [openfootball/italy](https://github.com/openfootball/italy).
- 원저장소 CC0-1.0 이용 조건은 역사적 경기 데이터의 상업적 재사용을 허용한다. 개별 경기장의 지도/구단 상표/저작물/제삼자 콘텐츠까지 면책해 주지는 않는다.
- \`scripts/build_history_warehouse.py\` 및 \`scripts/build_uefa_history.py\`는 이전 R1~R4 데이터에 의존하지 않는다.
- 2025/26 UEL·UECL 본선 파일이 CC0 저장소에 없어 **권리 불명 소스로 채우지 않고 누락을 명시**한다.

### R6 — UI 외부 자산·분석
- \`docs/index.html\` / \`scripts/build_i18n.py\`에서 Google Analytics (\`googletagmanager.com/gtag/js\`) 로드가 확인됨.
- 추후 광고 도입 시 개인정보/쿠키/동의 안내와 광고 사업자 계약을 별도 확인한다. 이것은 경기 데이터 저작권과 별개 문제다.
- 향후 구단 엠블럼·경기 사진·선수 초상권을 사용할 경우 별도 라이선스가 필요할 수 있다.

## 대체 공급자 후보 조사 (현재 도입·계약 없음)
| 후보 | 공개된 조건 | 불확실점 / 권장 조치 |
| --- | --- | --- |
| [OpenFootball CC0](https://github.com/openfootball/football.json) | 상업적 재사용 가능한 과거 경기 스코어 | 2026/27 모든 컵 일정, 슈팅 통계, 선수 이벤트의 공백을 메우지 못함 |
| [TheStatsAPI](https://football-data.co.uk/thestatsapi.php) | 제공업체 소개에서 상업 애플리케이션 가능 명시; 요금 £39/월부터 | 실제 필요 리그·기간, 클럽/선수 상세, 원자료 보유/재게시·파생 모델 권한을 플랜 계약으로 확인 |
| [FootyStats API](https://footystats.org/api/documentations/faq) | 웹사이트, 자체 DB 저장, 예측 모델 사용 가능 명시 | [약관](https://footystats.org/api/documentations/terms-of-use-and-legal)은 원시 데이터 재판매/재배포를 금지. GitHub Pages 공개 JSON 형태 확인 필요 |
| [football-data.org](https://www.football-data.org/about) | EPL 일정·결과 API 운영 중 | 광고/저장/구독 해지 후 권리 및 필수 attribution 확인 |
| [GOAL API](https://goal-api.com/terms) | 이벤트 데이터 현재 사용 중 | 원천 권리·공개 JSON·영속 보관·광고 조건 서면 확인 |

## 광고 활성화 전 통과 조건
- [ ] 기존 R1 과거 CSV의 원본·라이선스/영구 보유 및 상업적 **모델 학습** 허용 확인 또는 대체
- [ ] R2 football-data.org의 표시 의무 충족 및 광고/보존/해지 조건 확인
- [ ] R3 open-matchday 인입·파생 데이터 권한 확보 또는 교체
- [ ] R4 GOAL API 이벤트의 광고·캐시·영구 보관·공개 JSON 권한 확인 또는 교체
- [ ] 사이트에 실제 사용 중인 소스/라이선스/출처 표시 및 변경 이력 유지
- [ ] 외부 로고/사진 자산의 권리 검토
- [ ] 광고 및 Google Analytics 관련 개인정보·쿠키 동의 사항 별도 점검
- [ ] 대체 데이터로 재학습 시 예측·지표 정확도 검증 후 전환

**현재 결론:** 신규 CC0 과거 데이터는 독립적으로 활용 가능하지만,
기존 EPL 모델과 현 시즌 일정·이벤트 피드의 권한이 확인되기 전에는
사이트 전체에 상업 광고를 붙일 준비가 완료됐다고 판단하지 않는다.
