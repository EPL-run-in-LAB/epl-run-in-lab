# EPL Run-in Lab

정적 웹사이트 + GitHub Actions 자동 업데이트 구조입니다.

## 자동 업데이트 구조
1. football-data.org API에서 현재 Premier League 경기/일정 수집
2. 2016/17~2025/26 EPL 역사 데이터로 모델 구성
3. 2016/17~2025/26 Championship 데이터로 승격팀 초기 전력 보정
4. 향후 각 경기 승/무/패, 기대승점, 요인별 설명 재계산
5. `docs/data/predictions.json` 생성
6. GitHub Pages 자동 배포

## 필요한 GitHub Secret
`FOOTBALL_DATA_TOKEN`

## 업데이트 주기
`.github/workflows/update-and-deploy.yml` 기준 매일 한국시간 오전 6:10.

## 로컬 실행
```bash
pip install -r requirements.txt
export FOOTBALL_DATA_TOKEN="YOUR_TOKEN"
python scripts/update_predictions.py
python -m http.server 8000 -d docs
```
그 다음 http://localhost:8000 접속.
