# EPL Run-in Lab 사이트 배포 가이드

이 폴더를 그대로 GitHub에 올리면 됩니다.

## 구조
- `docs/index.html` : 사이트 화면
- `docs/data/predictions.json` : 사이트가 읽는 계산 결과
- `scripts/update_predictions.py` : 최신 EPL 데이터를 받아 예측을 다시 계산
- `model_data/` : 10년 EPL + 10년 Championship 학습 데이터
- `.github/workflows/update-and-deploy.yml` : 매일 자동 계산 + GitHub Pages 배포
- `requirements.txt` : Python 라이브러리

---

# 1. football-data.org API 키 만들기

1. football-data.org에 가입합니다.
2. 발급된 API Token을 복사합니다.
3. 이 토큰은 사이트 코드에 직접 적지 않습니다. GitHub Secret에 저장합니다.

GitHub Actions에서만 토큰을 사용하므로 방문자에게 API 키가 노출되지 않습니다.

---

# 2. GitHub 저장소 만들기

1. github.com 로그인
2. 오른쪽 위 `+` → `New repository`
3. Repository name: 예) `epl-run-in-lab`
4. 처음에는 `Public` 권장
5. `Create repository`

README 자동 생성 옵션은 켜도 되고 안 켜도 됩니다.

---

# 3. 이 폴더의 파일을 전부 GitHub에 올리기

가장 쉬운 방법:

1. 이 ZIP 파일을 PC에서 압축 해제
2. 생성된 `epl-run-in-lab-site` 폴더를 엽니다.
3. GitHub 저장소 화면에서 `Add file` → `Upload files`
4. 아래 항목을 전부 올립니다.

반드시 포함:
- `.github`
- `docs`
- `model_data`
- `scripts`
- `README.md`
- `requirements.txt`

`.github`는 숨김 폴더일 수 있습니다. Windows 탐색기에서 안 보이면 `보기 → 표시 → 숨긴 항목`을 켜세요.

업로드 후 아래 `Commit changes`를 누릅니다.

---

# 4. API 키를 GitHub Secret에 넣기

저장소에서:

`Settings`
→ `Secrets and variables`
→ `Actions`
→ `New repository secret`

Name:
`FOOTBALL_DATA_TOKEN`

Secret:
football-data.org에서 받은 실제 API Token

→ `Add secret`

이 이름은 정확히 `FOOTBALL_DATA_TOKEN`이어야 합니다.

---

# 5. GitHub Pages를 Actions 방식으로 설정하기

저장소에서:

`Settings`
→ 왼쪽 `Pages`
→ `Build and deployment`
→ `Source`
→ `GitHub Actions`

이제 HTML 파일을 직접 배포하는 것이 아니라, 자동 계산 작업이 끝난 결과를 GitHub Pages가 배포합니다.

---

# 6. 첫 계산을 직접 실행하기

저장소 상단:

`Actions`
→ 왼쪽에서 `Update EPL predictions and deploy Pages`
→ `Run workflow`
→ 다시 `Run workflow`

작업이 성공하면 초록색 체크가 표시됩니다.

이 작업이 하는 일:
1. 최신 EPL 경기 결과와 향후 일정 조회
2. 10년 EPL 데이터로 모델 구성
3. 10년 Championship 데이터로 승격팀 초기 전력 보정
4. 각 향후 경기 승/무/패 계산
5. 기대 승점 계산
6. "왜 이 확률인가?" 설명 계산
7. 사이트용 JSON 생성
8. GitHub Pages 배포

---

# 7. 사이트 주소 확인하기

성공 후:

`Settings`
→ `Pages`

위쪽에 공개 주소가 표시됩니다.

일반적으로 저장소가 `epl-run-in-lab`이라면 다음 형태입니다.

`https://내아이디.github.io/epl-run-in-lab/`

이 주소가 실제 공개 사이트입니다.

---

# 8. 자동 업데이트

현재 설정은 매일 한국시간 약 오전 6:10에 자동 실행됩니다.

즉 주말 경기가 끝난 다음 날:
- 새 결과 반영
- 팀 장기 경기력 변경
- 홈/원정 경기력 변경
- 승격팀 보정 비중 변경
- 다음 경기 승무패 확률 변경
- 향후 3/5/10경기 기대승점 변경
- 일정 순위 변경
- 확률 설명 변경

까지 자동으로 다시 계산됩니다.

PC가 켜져 있을 필요가 없습니다.

업데이트 시간을 바꾸려면:
`.github/workflows/update-and-deploy.yml`

안의:
`cron: "10 21 * * *"`

을 수정하면 됩니다. 현재 값은 UTC 21:10, 즉 한국시간 다음 날 06:10입니다.

---

# 9. 사이트 화면을 수정하고 싶을 때

디자인/문구:
`docs/index.html`

모델 계산:
`scripts/update_predictions.py`

를 수정하면 됩니다.

수정 후에는 GitHub Actions에서 `Run workflow`를 한 번 누르면 새 버전이 배포됩니다.

---

# 10. 현재 모델의 한계

football-data.org의 기본 경기 데이터만 자동 수집하는 현재 구조에서는
실시간 시즌의 슈팅/유효슈팅을 직접 추가하지 않습니다.

따라서:
- 승점
- 득점
- 실점
- 홈/원정 결과

는 새 경기마다 자동 반영되지만,
슈팅/유효슈팅은 기존 역사 데이터와 승격팀 보정값을 중심으로 유지됩니다.

나중에 슈팅/유효슈팅까지 제공하는 데이터 소스를 연결하면 이 부분도 완전 자동화할 수 있습니다.

---

# 11. 도메인은 나중에 붙여도 됩니다

처음에는 GitHub Pages 기본 주소로 검증하세요.

방문자가 생기고 사이트를 계속 운영하기로 결정한 뒤 `.com` 같은 도메인을 구매해서 GitHub Pages의 Custom domain에 연결하는 편이 낫습니다.
