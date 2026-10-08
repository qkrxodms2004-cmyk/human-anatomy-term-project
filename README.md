# Sternberg 기억 실험

Python + Pygame으로 실행하는 대문자 기억·판단 과제입니다. 안내 → 연습(정답 피드백) → 소음 없는 반응시간 보정 → 대기 → 본 실험 → 휴식 → 나머지 본 실험 순서입니다. 각 시행은 **set 제시 → 기억 유지(delay) → probe 및 응답 → intertrial interval**로 진행됩니다.

## 설치와 실행

Python 3.10 이상, 화면과 오디오 출력 장치, 한글 글꼴이 필요합니다. Windows에서는 기본 맑은 고딕을 사용합니다. Linux에서는 Noto Sans CJK/Nanum Gothic을 설치하거나 `font_file`에 한글 TTF/OTF 파일 경로를 지정하세요.

Windows 명령 프롬프트:

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python sternberg.py
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python sternberg.py
```

안내 화면에서는 스페이스로 진행합니다. probe가 나타난 뒤 **왼쪽 방향키 = T(있음), 오른쪽 방향키 = F(없음)**를 누릅니다. 최초 유효 응답 하나만 처리하며, 응답 전 단계의 키 입력과 길게 누른 키의 자동 반복은 무시합니다. ESC 또는 창 닫기는 중단하고 그때까지의 결과와 진행 중 시행을 저장합니다.

실행하면 먼저 피험자 ID 입력 화면이 나타납니다. ID를 입력하고 **Enter**를 누르면 실험 안내가 시작됩니다. **Backspace**로 삭제하고 **ESC** 또는 창 닫기로 취소할 수 있습니다. 빈 ID나 허용하지 않는 문자가 있으면 안내를 표시하고 다시 입력받습니다. ID는 문자·숫자·하이픈·밑줄로 1~60자이며 문자나 숫자가 최소 하나 필요합니다. 확인한 ID는 결과 폴더 이름과 `session.json`의 `participant`에 저장됩니다. ID 입력을 취소하면 결과 폴더를 생성하지 않습니다.

명령행에서 `.venv/bin/python sternberg.py --participant P001`처럼 지정하면 입력 화면을 생략할 수 있습니다. 검증용 `--smoke-test`도 입력 없이 진행합니다.

## 메모장 설정

`config.ini`를 메모장으로 열고 UTF-8로 저장하세요. 시간 단위는 초입니다. 다시 실행할 때 적용됩니다.

| 설정 | 의미 |
|---|---|
| `set_size` | 최초 set의 글자 수(1~25, 중복 없음) |
| `memorize_seconds` | set을 화면에 제시하고 외우는 시간 |
| `delay_seconds` | set이 사라진 뒤 기억을 유지하는 시간 |
| `response_timeout_seconds` | probe 응답 제한 시간 |
| `trials_per_condition` | 조건당 시행 수 n(양의 정수). 본 실험 총 시행 수는 7n |
| `calibration_trials` | 반응시간 보정 시행 수 |
| `practice_trials` | 안내 후 연습 시행 수 |
| `break_seconds` | 본 실험 절반 이상 완료 후 최소 휴식 시간 |
| `post_calibration_wait_seconds` | 보정 이후 본 실험 시작 전 대기 시간 |
| `intertrial_seconds` | 시행 사이 대기 시간 |
| `seed` | 재현을 위한 난수 시드(빈칸이면 새로 생성) |
| `stimuli_file` | 본 실험 자극 CSV 경로(빈칸이면 자동 생성) |
| `output_dir` | 결과 폴더 |
| `noise_rms` | 고역·저역 소음에 공통인 상대 RMS 출력값 |
| `low_min_hz`, `low_max_hz` | 저역 소음의 최소·최대 주파수(Hz) |
| `high_min_hz`, `high_max_hz` | 고역 소음의 최소·최대 주파수(Hz) |

경로는 설정 파일이 있는 폴더를 기준으로 해석합니다. 기본 `trials_per_condition = 4`이면 7조건 × 4회 = 본 실험 28시행이며, 14번째 이후에 한 번 쉽니다. `n = 5`이면 총 35시행, 18번째 뒤에 쉽니다. **휴식 종료 2초 전에 본 실험 재개 예고를 표시하고, 휴식 시간이 끝나면 스페이스 입력 없이 다음 시행을 자동으로 시작합니다.** 예고 시간은 설정한 휴식 시간에 포함되며 추가 대기하지 않습니다. 휴식 시간이 2초 이하이면 처음부터 예고 문구를 표시합니다. 연습·보정 시행 수는 7n에 포함하지 않습니다.

기존 설정 파일의 `trials`는 `trials_per_condition`으로 교체하세요. 기존 `low_cutoff_hz`/`high_cutoff_hz`, `quiet_rms`/`loud_rms`도 위의 주파수 범위와 `noise_rms` 설정으로 교체하세요. 이전 키가 남아 있으면 실수로 다른 조건으로 실행하지 않도록 오류를 표시합니다.

보정 과제는 연습과 동일한 기억 과제를 소음 없이 수행합니다. **정답을 맞힌 응답만** 평균에 포함합니다. 오답·무응답은 제외합니다. 유효 정답이 없으면 평균은 빈칸으로 저장하고 안내 후 진행합니다. 보정 결과는 측정·기록용이며 응답 제한 시간을 자동으로 바꾸지 않습니다.

## 소음 조건

다음 7조건을 **각각 정확히 n회씩** 계획하고 전체 7n시행의 순서를 무작위로 섞습니다. quiet는 작은 음량이 아니라 **소음을 전혀 재생하지 않는 대조 조건**입니다. 음량은 추가 조건으로 나누지 않고, 고역·저역에 공통으로 `noise_rms`를 사용합니다.

| 결과의 `noise_condition` | 재생 대역 | 재생 단계 |
|---|---|---|
| `low_set` | 저역 | set 제시 |
| `high_set` | 고역 | set 제시 |
| `low_delay` | 저역 | 기억 유지 |
| `high_delay` | 고역 | 기억 유지 |
| `low_probe` | 저역 | probe 응답 |
| `high_probe` | 고역 | probe 응답 |
| `quiet` | 무소음 | 재생하지 않음 |

소음은 배정 단계에 들어가서 시작하고 단계 종료에 정지합니다. probe 단계 소음은 응답하거나 제한 시간이 끝나면 정지합니다. 연습·보정·휴식·시행 간 대기에는 소음이 없습니다. 오답이나 시간 초과도 해당 조건의 한 시행으로 기록하며 추가 시행하지 않습니다. 중도 종료하면 수행한 조건별 횟수는 달라질 수 있습니다.

FFT로 지정 범위 밖 성분을 제거한 가우시안 백색소음을 사용합니다. 기본 저역은 20~1,000 Hz, 고역은 4,000~12,000 Hz입니다. 양쪽 범위의 하한과 상한 모두 수정할 수 있습니다. `0 <= low_min_hz < low_max_hz < high_min_hz < high_max_hz <= sample_rate/2`를 지켜야 합니다. DC(0 Hz)는 제외합니다. 너무 좁은 범위에 FFT 주파수 성분이 없으면 오류를 표시합니다.

양쪽 채널에 같은 신호가 나옵니다. 대역별 긴 버퍼를 준비해 세션 내 반복 사용하며 시드와 버퍼 SHA-256을 기록합니다. 필터 이후 공통 RMS로 정규화합니다. 시스템·헤드폰 음량을 포함한 **실제 dB SPL은 측정하지 않습니다**. 물리적 음압을 통제하는 실험에는 동일 장비에서 별도 음압 보정이 필요합니다.

## 외부 자극 파일과 결과

직접 자극을 지정하려면 `stimuli_file = stimuli.csv`처럼 설정하고 다음 형식으로 저장하세요:

```csv
set,probe
ABCDE,A
FGHIJ,Z
```

행 수는 `7 * trials_per_condition`과 같아야 하고 set은 중복 없는 대문자 `set_size`개, probe는 대문자 1개여야 합니다. 위 예시는 파일 형식을 보여 주는 첫 2행이며, `n = 1`이어도 총 7행을 작성해야 합니다. 파일 순서를 유지하고 소음 조건만 독립적으로 무작위 배정합니다. 정답은 set 포함 여부로 계산합니다. 파일을 지정하지 않으면 T/F 정답 수가 전체에서 최대 1만 차이 나도록 자극을 생성합니다.

결과는 `results/피험자ID_UTC시각/`에 저장됩니다:

- `planned_stimuli.csv`: 연습·보정·본 실험의 모든 계획 자극 및 본 실험 소음 조건.
- `trials.csv`: 시행마다 즉시 저장. set, probe, 정답(`expected`), 입력(`response`), 정오(`correct`), 반응시간(ms), 무응답(`timeout`), 완료/중단 상태, 7조건 구분(`noise_condition`), 소음 단계·필터·RMS·재생 주파수 하한/상한(`noise_min_hz`, `noise_max_hz`), 단계 시작 시각, 소음 재생/정지 명령 시각, 보정 평균과 휴식 위치. quiet는 단계·필터가 `none`, RMS와 재생 길이가 0, 주파수와 재생/정지 시각은 빈칸입니다.
- `session.json`: 실제 사용 설정·시드·피험자 ID·완료 상태·보정 유효 응답 수·소음 버퍼 해시·세션 시각. 실명 대신 익명 ID를 사용하세요.

T/F는 포함 여부를 뜻하고 `correct`는 피험자의 답이 정답과 일치하는지를 뜻합니다. 무응답은 response/반응시간을 빈칸, timeout=True, correct=False로 저장합니다. 중단된 시행은 status로 식별하며 아직 측정하지 않은 값은 빈칸입니다. 단계 시각은 세션 시작 기준 `perf_counter` 초입니다. 반응시간은 화면 flip 직후부터 입력 처리까지 측정합니다. 기록은 소프트웨어 시각으로, 실제 모니터·소리 출력 지연을 측정하지 않습니다. 소음의 실제 단계 길이는 응답 속도와 프레임 주기에 따라 달라집니다.

## 개발 검증

```sh
.venv/bin/python -m unittest -v
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python sternberg.py --smoke-test --participant CHECK
```

두 번째 명령은 화면·오디오를 가상 장치로 실행하고 자동으로 정답을 입력합니다. 검증용으로 n=1, 연습 1회, 보정 2회, 본 실험 7회로 단축합니다. 결과에는 `SMOKE_` 접두사와 `smoke_test=true`가 붙으며 실제 피험자 데이터로 사용하면 안 됩니다. 실제 헤드폰 출력·한글 화면 가독성·물리적 타이밍은 대상 컴퓨터에서 확인하세요.
