# 🛒 쇼핑 리스트

아이템 추가·수정·삭제·체크를 한 화면에서 처리하는 가벼운 Streamlit 앱입니다. 요구사항은 `prd.md`를 참고하세요.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 데이터 저장 한계

목록은 앱과 같은 폴더의 `items.json`에 저장됩니다. 경로는 환경변수 `SHOPPING_LIST_DATA`로 바꿀 수 있습니다.

- Streamlit Community Cloud에서는 앱이 재시작·재배포되면 서버 파일이 초기화되어 목록이 사라질 수 있습니다.
- 서버 파일 하나를 모든 접속자가 함께 쓰므로, 목록이 사용자 간에 공유됩니다. 사용자별 목록이 필요하면 외부 DB가 필요합니다.
