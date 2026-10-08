# Sternberg 기억 실험

Python + Pygame으로 실행하는 대문자 기억·판단 과제입니다. 안내 → 연습(정답 피드백) → 소음 없는 반응시간 보정 → 대기 → 본 실험 → 휴식 → 나머지 본 실험 순서입니다. 각 시행은 **set 제시 → 기억 유지(delay) → probe 및 응답 → intertrial interval**로 진행됩니다.

## 설치와 실행

Python 3.10 이상, 화면과 오디오 출력 장치, 한글 글꼴이 필요합니다. Windows에서는 기본 맑은 고딕을 사용합니다. Linux에서는 Noto Sans CJK/Nanum Gothic을 설치하거나 `font_file`에 한글 TTF/OTF 파일 경로를 지정하세요.

Windows 명령 프롬프트:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python sternberg.py --participant P001
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python sternberg.py --participant P001
```

안내 화면에서는 스페이스로 진행합니다. probe가 나타난 뒤 **왼쪽 방향키 = T(있음), 오른쪽 방향키 = F(없음)**를 누릅니다. 최초 유효 응답 하나만 처리하며, 응답 전 단계의 키 입력과 길게 누른 키의 자동 반복은 무시합니다. ESC 또는 창 닫기는 중단하고 그때까지의 결과와 진행 중 시행을 저장합니다.

## 메모장 설정

`config.ini`를 메모장으로 열고 UTF-8로 저장하세요. 시간 단위는 초입니다. 다시 실행할 때 적용됩니다.

| 설정 | 의미 |
|---|---|
| `set_size` | 최초 set의 글자 수(1~25, 중복 없음) |
| `memorize_seconds` | set을 화면에 제시하고 외우는 시간 |
| `delay_seconds` | set이 사라진 뒤 기억을 유지하는 시간 |
| `response_timeout_seconds` | probe 응답 제한 시간 |
| `trials` | 본 실험 시행 수 |
| `calibration_trials` | 반응시간 보정 시행 수 |
| `practice_trials` | 안내 후 연습 시행 수 |
| `break_seconds` | 본 실험 절반 이상 완료 후 최소 휴식 시간 |
| `post_calibration_wait_seconds` | 보정 이후 본 실험 시작 전 대기 시간 |
| `intertrial_seconds` | 시행 사이 대기 시간 |
| `seed` | 재현을 위한 난수 시드(빈칸이면 새로 생성) |
| `stimuli_file` | 본 실험 자극 CSV 경로(빈칸이면 자동 생성) |
| `output_dir` | 결과 폴더 |
| `quiet_rms`, `loud_rms` | 두 소음의 상대 RMS 출력값 |
| `low_cutoff_hz`, `high_cutoff_hz` | 저역 통과 / 고역 통과 필터의 경계 |

경로는 설정 파일이 있는 폴더를 기준으로 해석합니다. 기본 시행 수 24에서는 12번째 이후에 한 번 쉽니다. 홀수 N은 `ceil(N/2)`번째 뒤에 쉽니다. 시행이 1개면 중간 휴식은 없습니다. 휴식 시간이 끝난 뒤 스페이스를 눌러 재개합니다.

보정 과제는 연습과 동일한 기억 과제를 소음 없이 수행합니다. **정답을 맞힌 응답만** 평균에 포함합니다. 오답·무응답은 제외합니다. 유효 정답이 없으면 평균은 빈칸으로 저장하고 안내 후 진행합니다. 보정 결과는 측정·기록용이며 응답 제한 시간을 자동으로 바꾸지 않습니다.

## 소음 조건

본 실험의 모든 시행에 소음을 한 번 배정합니다. 제시(set), 유지(delay), 응답(probe) 중 한 단계 × 저역/고역 × 작은/큰 음량의 12조건을 무작위 순서로 배정합니다. 12시행마다 각 조건이 한 번씩 나타나므로 전체 조건 수 차이는 최대 1입니다. 소음은 해당 단계에 들어가서 시작하고 단계 종료에 정지합니다. probe 단계 소음은 응답하거나 제한 시간이 끝나면 정지합니다. 연습·보정·휴식·시행 간 대기에는 소음이 없습니다.

FFT로 대역 밖 성분을 제거한 가우시안 백색소음을 사용합니다. 기본 저역은 0~1,000 Hz(DC 제외), 고역은 4,000 Hz~Nyquist입니다. 양쪽 채널에 같은 신호가 나옵니다. 조건별 긴 버퍼를 준비해 세션 내 반복 사용하며 시드와 버퍼 SHA-256을 기록합니다. 두 음량은 필터 이후 RMS로 정규화합니다. 시스템·헤드폰 음량을 포함한 **실제 dB SPL은 측정하지 않습니다**. 물리적 음압을 통제하는 실험에는 동일 장비에서 별도 음압 보정이 필요합니다.

## 외부 자극 파일과 결과

직접 자극을 지정하려면 `stimuli_file = stimuli.csv`처럼 설정하고 다음 형식으로 저장하세요:

```csv
set,probe
ABCDE,A
FGHIJ,Z
```

행 수는 `trials`와 같아야 하고 set은 중복 없는 대문자 `set_size`개, probe는 대문자 1개여야 합니다. 파일 순서를 유지합니다. 정답은 set 포함 여부로 계산합니다. 예시 2행을 사용하려면 `trials = 2`로 설정하세요. 파일을 지정하지 않으면 T/F 정답 수가 최대 1만 차이 나도록 자극을 생성합니다. 소음 조건은 자극과 독립적으로 배정합니다.

결과는 `results/피험자ID_UTC시각/`에 저장됩니다:

- `planned_stimuli.csv`: 연습·보정·본 실험의 모든 계획 자극 및 본 실험 소음 조건.
- `trials.csv`: 시행마다 즉시 저장. set, probe, 정답(`expected`), 입력(`response`), 정오(`correct`), 반응시간(ms), 무응답(`timeout`), 완료/중단 상태, 소음 단계·필터·음량·RMS, 단계 시작 시각, 소음 재생/정지 명령 시각, 보정 평균과 휴식 위치.
- `session.json`: 실제 사용 설정·시드·피험자 ID·완료 상태·보정 유효 응답 수·소음 버퍼 해시·세션 시각. 실명 대신 익명 ID를 사용하세요.

T/F는 포함 여부를 뜻하고 `correct`는 피험자의 답이 정답과 일치하는지를 뜻합니다. 무응답은 response/반응시간을 빈칸, timeout=True, correct=False로 저장합니다. 중단된 시행은 status로 식별하며 아직 측정하지 않은 값은 빈칸입니다. 단계 시각은 세션 시작 기준 `perf_counter` 초입니다. 반응시간은 화면 flip 직후부터 입력 처리까지 측정합니다. 기록은 소프트웨어 시각으로, 실제 모니터·소리 출력 지연을 측정하지 않습니다. 소음의 실제 단계 길이는 응답 속도와 프레임 주기에 따라 달라집니다.

## 개발 검증

```sh
.venv/bin/python -m unittest -v
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python sternberg.py --smoke-test --participant CHECK
```

두 번째 명령은 화면·오디오를 가상 장치로 실행하고 자동으로 정답을 입력합니다. 결과에는 `SMOKE_` 접두사와 `smoke_test=true`가 붙으며 실제 피험자 데이터로 사용하면 안 됩니다. 실제 헤드폰 출력·한글 화면 가독성·물리적 타이밍은 대상 컴퓨터에서 확인하세요.
