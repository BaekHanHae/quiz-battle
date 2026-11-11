#!/usr/bin/env bash
# quiz-battle 문제 은행 소스 데이터 다운로드.
# EDRDG 라이선스(CC BY-SA 4.0) §4의 "정기 갱신 절차" 조건에 맞춰 재실행 가능하게 둔다.
# 원본 데이터는 repo에 넣지 않는다 (sources/는 .gitignore 대상). 파생 은행만 표기와 함께 들어간다.
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p sources

KANJIDIC2_URL="https://www.edrdg.org/kanjidic/kanjidic2.xml.gz"
JMDICT_URL="http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"

echo "Downloading kanjidic2.xml.gz ..."
curl -fSL --retry 3 -o sources/kanjidic2.xml.gz "$KANJIDIC2_URL"

echo "Downloading JMdict_e.gz ..."
curl -fSL --retry 3 -o sources/JMdict_e.gz "$JMDICT_URL"

TODAY="$(date -u +%Y-%m-%d)"
K_SIZE="$(stat -c %s sources/kanjidic2.xml.gz)"
J_SIZE="$(stat -c %s sources/JMdict_e.gz)"
K_SHA="$(sha256sum sources/kanjidic2.xml.gz | cut -d' ' -f1)"
J_SHA="$(sha256sum sources/JMdict_e.gz | cut -d' ' -f1)"

cat > SOURCES.md <<EOF
# 문제 은행 소스 데이터

파생 문제 은행(data/questions_*.json 중 source=jmdict-kanjidic2 항목)의 원본 데이터.
원본 파일 자체는 repo에 포함하지 않는다 (이 디렉터리는 .gitignore 대상).

| 파일 | 출처 URL | 다운로드 날짜 | 크기(bytes) | SHA-256 | 라이선스 |
|---|---|---|---|---|---|
| kanjidic2.xml.gz | $KANJIDIC2_URL | $TODAY | $K_SIZE | $K_SHA | CC BY-SA 4.0 (EDRDG) |
| JMdict_e.gz | $JMDICT_URL | $TODAY | $J_SIZE | $J_SHA | CC BY-SA 4.0 (EDRDG) |

- 출처: EDRDG (Electronic Dictionary Research and Development Group) — https://www.edrdg.org/
- 라이선스 전문: https://www.edrdg.org/edrdg/licence.html (CC BY-SA 4.0)
- 갱신: 이 스크립트를 다시 실행하면 최신본으로 다시 받고 이 표도 갱신된다.
  (EDRDG 라이선스 §4: 데이터를 쓰는 소프트웨어는 정기 갱신 절차를 둘 것)
EOF

echo "Done. See SOURCES.md"
ls -la sources/
