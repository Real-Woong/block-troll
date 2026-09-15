# BlockTroll 상시 구동 (Mac mini)

이 머신은 **추론 전용**이다. 학습/파인튜닝은 Windows + RTX 쪽에서만 한다.

## 엔드포인트

```
http://100.96.86.10:8787
http://jinwoong-kims-mac-mini.tail7bc26c.ts.net:8787   (MagicDNS, 동일)
```

uvicorn은 Tailscale 인터페이스 IP에만 바인드한다. `0.0.0.0`을 듣지 않으므로
타일넷 밖(공개 인터넷, LAN)에서는 도달할 수 없다. `127.0.0.1:8787`도 닫혀 있다.

## 상태 확인 / 재시작 / 중지

```bash
# 상태
launchctl print gui/$(id -u)/com.blocktroll.agent | grep -E "state =|pid =|last exit"
curl -s http://100.96.86.10:8787/health

# 재시작
launchctl kickstart -k gui/$(id -u)/com.blocktroll.agent

# 중지 (다음 로그인/부팅 때 다시 뜸)
launchctl bootout gui/$(id -u)/com.blocktroll.agent

# 다시 등록
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.blocktroll.agent.plist

# 완전 해제 (자동 시작까지 끔)
launchctl bootout gui/$(id -u)/com.blocktroll.agent
rm ~/Library/LaunchAgents/com.blocktroll.agent.plist
```

`KeepAlive=true`이므로 프로세스가 죽으면 launchd가 약 2초 안에 되살린다.
plist 원본은 `launchd/com.blocktroll.agent.plist`에 있고, 수정한 뒤에는
`~/Library/LaunchAgents/`로 복사하고 bootout → bootstrap 해야 반영된다.

## 로그

```bash
tail -f ~/Library/Logs/BlockTroll/agent.log      # 서버 로그 (타임스탬프 포함)
tail -f ~/Library/Logs/BlockTroll/launchd.err.log # 스크립트가 뜨기 전에 죽은 경우
```

20MB를 넘으면 재시작 시 `agent.log.1`로 1회 롤오버한다.

`.env`의 `LOG_COMMENTS=true`로 바꾸면 수집된 댓글 본문이 전부 로그에 남는다.
디버깅할 때만 켜고 되돌릴 것 — 24시간 구동 상태에서는 열람한 모든 댓글이
디스크에 쌓인다. 확장 쪽 진단(`scan-found` 등)은 `LOG_COMMENTS`와 무관하게
`/debug`로 계속 들어온다.

## 모델 켜기 (가중치 확보 후)

현재는 `ENABLE_MODEL=false`라 **룰 기반**으로만 동작한다. Windows에서 학습한
가중치를 받은 뒤:

```bash
# 1) config.json, model.safetensors, tokenizer* 를 아래로 복사
#    /Users/jinwoong_kim/Projects/BlockTroll/models/blocktroll-koelectra/
# 2) .env 에서
ENABLE_MODEL=true
# 3) 재시작 후 model_ready=true 확인
launchctl kickstart -k gui/$(id -u)/com.blocktroll.agent
curl -s http://100.96.86.10:8787/health
```

`scripts/smoke_test.py`로 로드 경로를 따로 검증할 수 있다 (MPS 사용 확인 포함).

## 레포 위치 주의

레포는 `~/Projects/BlockTroll`에 있고 `~/Desktop/project/Project_AI/NLP/BlockTroll`은
심볼릭 링크다. macOS TCC가 `~/Desktop`을 보호해서 launchd가 띄운 프로세스는
Desktop 아래 파일을 열 수 없다 (`Operation not permitted`). **레포를 Desktop 안으로
되돌리면 상시 구동이 깨진다.**
