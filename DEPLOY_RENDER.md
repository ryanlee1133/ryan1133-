# V8 Render 공개 URL 배포

1. 이 프로젝트 전체를 GitHub 저장소에 업로드합니다.
2. Render Dashboard → New → Web Service → GitHub 저장소를 연결합니다.
3. Runtime은 Docker, Plan은 Free를 선택합니다.
4. Health Check Path는 `/health`.
5. 환경변수 `WHISPER_MODEL=tiny`를 사용합니다.
6. 배포가 완료되면 Render가 HTTPS `onrender.com` 공개 URL을 제공합니다.
7. 갤럭시 Chrome에서 그 주소를 열고 메뉴 → 홈 화면에 추가/앱 설치.

## 무료 서버 주의
무료 Render Web Service는 512 MB RAM / 0.1 CPU 수준이라 긴 영상 AI 처리는 느리거나 메모리 부족이 날 수 있습니다.
무료 테스트는 짧은 영상과 Whisper tiny를 권장합니다.
서비스는 15분 동안 요청이 없으면 sleep되며 다음 접속 때 재기동 시간이 걸릴 수 있습니다.
업로드/생성 파일은 영구 보관용이 아니며 재시작/재배포 시 사라질 수 있습니다.

## 성능 업그레이드
1~2GB RAM 이상의 서버에서는 `WHISPER_MODEL=base` 또는 `small`로 변경해 인식 품질을 높일 수 있습니다.
