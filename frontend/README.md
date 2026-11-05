# InfraQuest AI — Frontend

React 19 + Vite 8 + Tailwind CSS 4로 만든 화면입니다. 프로젝트 전체 소개와 실행 방법은 [상위 README](../README.md)를 보세요.

```bash
npm install
npm run dev      # 개발 서버 (기본 http://localhost:5173)
npm run build    # 배포용 빌드 → dist/
npm run lint     # oxlint
```

- 개발 중에는 `/api` 요청을 `vite.config.js`의 프록시가 백엔드(`http://127.0.0.1:8000`)로 전달합니다.
- 마스코트 등 정적 이미지는 `public/images/` 에 있습니다.
