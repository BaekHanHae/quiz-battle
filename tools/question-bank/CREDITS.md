# 데이터 출처 · 라이선스 표기 (CREDITS)

quiz-battle 문제 은행의 일부는 아래 오픈 데이터셋에서 파생됐다.
파생된 은행 데이터(data/questions_*.json 중 자동 생성 항목)도 동일하게
CC BY-SA 4.0으로 제공된다.

## JMdict / KANJIDIC2 — EDRDG

- 출처: EDRDG (Electronic Dictionary Research and Development Group)
  - JMdict: https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project
  - KANJIDIC: https://www.edrdg.org/wiki/index.php/KANJIDIC_Project
- 라이선스: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
  - EDRDG 라이선스 전문: https://www.edrdg.org/edrdg/licence.html
  - CC BY-SA 4.0 전문: https://creativecommons.org/licenses/by-sa/4.0/
- 사용 방식: 단어의 한자 표기·읽기(JMdict)와 한자의 학년 배당(KANJIDIC2 grade)을
  대조·검증해 '숙어 읽기' 문제를 자동 생성했다. 원본 데이터 파일은 repo에
  포함하지 않으며, tools/question-bank/fetch_sources.sh 로 다시 받을 수 있다
  (다운로드 기록: tools/question-bank/SOURCES.md).
- 이 게임의 코드와 수기 작성 문제는 이 표기의 대상이 아니다.
