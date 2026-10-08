"""Sternberg memory task. Run: python sternberg.py --participant P001."""
from __future__ import annotations

import argparse
import configparser
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import secrets
import statistics
import string
import time

import numpy as np

STAGES = ("set", "delay", "probe")


@dataclass
class Settings:
    set_size: int = 5
    memorize_seconds: float = 2.0
    delay_seconds: float = 2.0
    response_timeout_seconds: float = 3.0
    trials_per_condition: int = 4
    calibration_trials: int = 10
    practice_trials: int = 3
    break_seconds: float = 30.0
    post_calibration_wait_seconds: float = 10.0
    intertrial_seconds: float = 1.0
    stimuli_file: str = ""
    output_dir: str = "results"
    seed: int = 0
    sample_rate: int = 44100
    low_min_hz: float = 20.0
    low_max_hz: float = 1000.0
    high_min_hz: float = 4000.0
    high_max_hz: float = 12000.0
    noise_rms: float = .05
    fullscreen: bool = False
    width: int = 1100
    height: int = 750
    font_file: str = ""

    @property
    def trials(self) -> int:
        return 7 * self.trials_per_condition


def load_settings(path: Path) -> Settings:
    parser = configparser.ConfigParser(inline_comment_prefixes=(";",))
    if not parser.read(path, encoding="utf-8-sig"):
        raise ValueError(f"설정 파일을 찾을 수 없습니다: {path}")
    cfg = Settings()
    if parser.has_option("experiment", "trials"):
        raise ValueError("기존 trials 대신 trials_per_condition에 조건당 시행 수 n을 설정하세요. 총 시행 수는 7n입니다.")
    if any(parser.has_option("audio", name) for name in
           ("low_cutoff_hz", "high_cutoff_hz", "quiet_rms", "loud_rms")):
        raise ValueError("기존 오디오 설정을 low_min_hz/low_max_hz, high_min_hz/high_max_hz, noise_rms로 바꿔 주세요.")
    for section, names in {
        "experiment": list(asdict(cfg))[:13],
        "audio": ["sample_rate", "low_min_hz", "low_max_hz", "high_min_hz", "high_max_hz", "noise_rms"],
        "display": ["fullscreen", "width", "height", "font_file"],
    }.items():
        if section not in parser:
            raise ValueError(f"설정에 [{section}]이 필요합니다.")
        for name in names:
            if name not in parser[section]:
                continue
            default = getattr(cfg, name)
            if name == "seed":
                value = parser.get(section, name).strip()
                setattr(cfg, name, int(value) if value else secrets.randbits(32))
            elif isinstance(default, bool):
                setattr(cfg, name, parser.getboolean(section, name))
            elif isinstance(default, str):
                setattr(cfg, name, parser.get(section, name).strip())
            elif isinstance(default, int):
                setattr(cfg, name, parser.getint(section, name))
            else:
                setattr(cfg, name, parser.getfloat(section, name))
    # Resolve paths relative to the configuration, not the current directory.
    for name in ("stimuli_file", "output_dir", "font_file"):
        value = getattr(cfg, name)
        if value:
            setattr(cfg, name, str((path.parent / value).resolve()))
    validate_settings(cfg)
    return cfg


def validate_settings(c: Settings) -> None:
    if not 1 <= c.set_size <= 25:
        raise ValueError("set_size는 1~25여야 합니다 (불일치 probe 생성에 한 글자 필요).")
    for name in ("trials_per_condition", "calibration_trials", "practice_trials"):
        if getattr(c, name) < 1:
            raise ValueError(f"{name}은 1 이상이어야 합니다.")
    for name in ("memorize_seconds", "delay_seconds", "response_timeout_seconds",
                 "break_seconds", "post_calibration_wait_seconds", "intertrial_seconds"):
        value = getattr(c, name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name}은 유한한 양수여야 합니다.")
    if c.sample_rate not in (22050, 44100, 48000):
        raise ValueError("sample_rate는 22050, 44100, 48000 중 하나여야 합니다.")
    if not 0 <= c.low_min_hz < c.low_max_hz < c.high_min_hz < c.high_max_hz <= c.sample_rate / 2:
        raise ValueError("주파수 범위는 0 <= low_min < low_max < high_min < high_max <= sample_rate/2여야 합니다.")
    if not (0 < c.noise_rms <= .15):
        raise ValueError("음량은 0 < noise_rms <= 0.15여야 합니다.")
    if c.width < 800 or c.height < 600:
        raise ValueError("화면 크기는 최소 800 x 600이어야 합니다.")


def make_stimuli(count: int, size: int, rng: random.Random) -> list[dict]:
    targets = [True] * (count // 2) + [False] * (count // 2)
    if count % 2:
        targets.append(rng.choice((True, False)))
    rng.shuffle(targets)
    result = []
    for present in targets:
        letters = rng.sample(string.ascii_uppercase, size)
        probe = rng.choice(letters if present else [x for x in string.ascii_uppercase if x not in letters])
        result.append({"set": "".join(letters), "probe": probe})
    return result


def read_stimuli(path: str, count: int, size: int) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not {"set", "probe"} <= set(reader.fieldnames or []):
            raise ValueError("자극 CSV에 set,probe 열이 필요합니다.")
        rows = list(reader)
    if len(rows) != count:
        raise ValueError(f"자극 CSV 행 수({len(rows)})는 총 시행 수 7n({count})과 같아야 합니다.")
    result = []
    for index, row in enumerate(rows, 2):
        letters = "".join(row["set"].split())
        probe = row["probe"].strip()
        if (len(letters) != size or len(set(letters)) != size
                or any(x not in string.ascii_uppercase for x in letters)
                or len(probe) != 1 or probe not in string.ascii_uppercase):
            raise ValueError(f"자극 CSV {index}행: 중복 없는 대문자 set({size}개), 대문자 probe(1개)가 필요합니다.")
        result.append({"set": letters, "probe": probe})
    return result


def noise_conditions(repetitions: int, rng: random.Random) -> list[dict]:
    if repetitions < 1:
        raise ValueError("조건당 시행 수는 1 이상이어야 합니다.")
    pool = [{"noise_condition": f"{f}_{s}", "noise_stage": s, "noise_filter": f}
            for s in STAGES for f in ("low", "high")]
    pool.append({"noise_condition": "quiet", "noise_stage": "none", "noise_filter": "none"})
    result = [condition.copy() for condition in pool for _ in range(repetitions)]
    rng.shuffle(result)
    return result


def filtered_noise(c: Settings, kind: str, seed: int) -> np.ndarray:
    if kind not in ("low", "high"):
        raise ValueError("소음 필터는 low 또는 high여야 합니다.")
    # A long reusable buffer avoids generating audio inside timed trial stages.
    duration = max(c.memorize_seconds, c.delay_seconds, c.response_timeout_seconds) + .1
    if duration > 600:
        raise ValueError("소음 단계별 최대 시간은 600초입니다.")
    n = max(128, math.ceil(duration * c.sample_rate))
    raw = np.random.default_rng(seed).normal(size=n)
    spectrum = np.fft.rfft(raw)
    frequencies = np.fft.rfftfreq(n, 1 / c.sample_rate)
    minimum, maximum = getattr(c, f"{kind}_min_hz"), getattr(c, f"{kind}_max_hz")
    mask = (frequencies > 0) & (frequencies >= minimum) & (frequencies <= maximum)
    spectrum[~mask] = 0
    wave = np.fft.irfft(spectrum, n)
    rms = np.sqrt(np.mean(wave ** 2))
    if rms == 0:
        raise ValueError("지정한 시간과 필터에서 소음을 만들 수 없습니다.")
    wave *= c.noise_rms / rms
    if np.max(np.abs(wave)) >= 1:
        raise ValueError("소음 피크가 출력 범위를 초과했습니다. RMS 음량을 줄이세요.")
    mono = np.round(wave * 32767).astype(np.int16)
    return np.ascontiguousarray(np.column_stack((mono, mono)))


FIELDS = ["phase", "trial", "set", "probe", "expected", "response", "correct",
          "response_time_ms", "timeout", "status", "noise_stage", "noise_filter",
          "noise_condition", "noise_target_rms", "noise_min_hz", "noise_max_hz",
          "noise_play_command_s", "noise_stop_command_s", "noise_command_duration_ms",
          "set_onset_s", "delay_onset_s", "probe_onset_s", "response_time_s",
          "intertrial_onset_s", "trial_end_s", "calibration_mean_ms", "break_after", "timing_json"]


class QuitExperiment(Exception):
    pass


def validate_participant(value: str) -> str:
    value = value.strip()
    if (not 1 <= len(value) <= 60 or not any(x.isalnum() for x in value)
            or any(not (x.isalnum() or x in "-_") for x in value)):
        raise ValueError("ID는 문자·숫자·-·_로 1~60자 입력하세요. 문자 또는 숫자가 필요합니다.")
    return value


def setup_display(p, c):
    p.display.init()
    p.font.init()
    screen = p.display.set_mode((c.width, c.height), p.FULLSCREEN if c.fullscreen else 0)
    p.display.set_caption("Sternberg 기억 실험")
    fonts = ["malgungothic", "applesdgothicneo", "nanumgothic", "notosanscjkkr", "notosanscjksc"]
    font_path = c.font_file or next((p.font.match_font(x) for x in fonts if p.font.match_font(x)), None)
    if not font_path:
        raise RuntimeError("한글 글꼴이 없습니다. config.ini의 font_file에 한글 TTF/OTF 경로를 지정하세요.")
    return screen, font_path


def prompt_participant(c: Settings) -> str | None:
    """Collect an ID before creating any session or initializing experiment audio."""
    import pygame as p
    try:
        screen, font_path = setup_display(p, c)
        font = p.font.Font(font_path, 28)
        clock = p.time.Clock()
        value, composition, error = "", "", ""
        p.key.start_text_input()
        box = p.Rect(50, 220, screen.get_width() - 100, 65)
        p.key.set_text_input_rect(box)
        while True:
            screen.fill((18, 22, 30))
            lines = [("피험자 ID를 입력하세요", 65),
                     ("실명 대신 익명 ID를 사용하세요. 예: P001", 120),
                     ("문자·숫자·-·_ 사용 / 최대 60자", 165),
                     ("Enter: 확인 및 시작   |   Backspace: 삭제   |   ESC: 종료", 340),
                     (error, 400)]
            for line, y in lines:
                rendered = font.render(line, True, (255, 170, 170) if y == 400 else (235, 235, 235))
                if rendered.get_width() > screen.get_width() - 40:
                    size = max(12, int(28 * (screen.get_width() - 40) / rendered.get_width()))
                    rendered = p.font.Font(font_path, size).render(line, True, (235, 235, 235))
                screen.blit(rendered, ((screen.get_width() - rendered.get_width()) // 2, y))
            p.draw.rect(screen, (55, 70, 95), box)
            p.draw.rect(screen, (255, 220, 110), box, 2)
            text = value + composition + "|"
            size = min(28, max(10, int(28 * (box.width - 24) / max(1, font.size(text)[0]))))
            rendered = p.font.Font(font_path, size).render(text, True, (255, 220, 110))
            screen.blit(rendered, (box.x + 12, box.y + (box.height - rendered.get_height()) // 2))
            p.display.flip()
            for event in p.event.get():
                if event.type == p.QUIT or (event.type == p.KEYDOWN and event.key == p.K_ESCAPE):
                    return None
                if event.type == p.TEXTINPUT:
                    value += event.text
                    composition, error = "", ""
                elif event.type == p.TEXTEDITING:
                    composition = event.text
                elif event.type == p.KEYDOWN and not composition:
                    if event.key == p.K_BACKSPACE:
                        value, error = value[:-1], ""
                    elif event.key in (p.K_RETURN, p.K_KP_ENTER):
                        try:
                            return validate_participant(value)
                        except ValueError as exc:
                            error = str(exc)
            clock.tick(60)
    finally:
        if p.display.get_init():
            p.key.stop_text_input()
        p.quit()


class Experiment:
    def __init__(self, c: Settings, participant: str, smoke: bool = False):
        import pygame
        self.pg = pygame
        self.cfg, self.smoke = c, smoke
        self.origin = time.perf_counter()
        self.active_row = None
        self.calibration_mean = ""
        self.clock = pygame.time.Clock()
        self.audio_channel = None
        rng = random.Random(c.seed)
        self.practice = make_stimuli(c.practice_trials, c.set_size, rng)
        self.calibration = make_stimuli(c.calibration_trials, c.set_size, rng)
        self.main = read_stimuli(c.stimuli_file, c.trials, c.set_size) if c.stimuli_file else make_stimuli(c.trials, c.set_size, rng)
        for trial, condition in zip(self.main, noise_conditions(c.trials_per_condition, rng)):
            trial.update(condition)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        safe = validate_participant(participant)
        self.folder = Path(c.output_dir) / (f"SMOKE_{safe}_{stamp}" if smoke else f"{safe}_{stamp}")
        self.folder.mkdir(parents=True, exist_ok=False)
        self.metadata = {"participant": safe, "started_utc": stamp, "settings": asdict(c),
                         "main_trial_count": c.trials,
                         "smoke_test": smoke, "status": "initializing", "audio_hashes": {}, "waits": [],
                         "timing_note": "perf_counter times relative to session start; flip / audio command timestamps, not measured physical onsets"}
        self.save_metadata()
        with (self.folder / "planned_stimuli.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["phase", "trial", "set", "probe", "noise_condition", "noise_stage", "noise_filter"])
            writer.writeheader()
            for phase, rows in (("practice", self.practice), ("calibration", self.calibration), ("main", self.main)):
                for index, row in enumerate(rows, 1):
                    writer.writerow({"phase": phase, "trial": index, **row})
        self.result_file = (self.folder / "trials.csv").open("w", encoding="utf-8-sig", newline="")
        self.writer = csv.DictWriter(self.result_file, fieldnames=FIELDS)
        self.writer.writeheader()
        self.result_file.flush()

    def now(self):
        return time.perf_counter() - self.origin

    def save_metadata(self):
        target = self.folder / "session.json"
        temp = self.folder / "session.json.tmp"
        temp.write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)

    def setup(self):
        p, c = self.pg, self.cfg
        p.mixer.pre_init(c.sample_rate, -16, 2, 512)
        p.init()
        if not p.mixer.get_init():
            raise RuntimeError("오디오 장치를 초기화하지 못했습니다. 소음 실험은 오디오가 필요합니다.")
        self.screen, font_path = setup_display(p, c)
        p.key.set_repeat()
        self.font = p.font.Font(font_path, 28)
        self.big_font = p.font.Font(font_path, 64)
        self.font_path = font_path
        self.sounds = {}
        self.audio_channel = p.mixer.Channel(0)
        for index, kind in enumerate(("low", "high")):
            data = filtered_noise(c, kind, (c.seed + index + 1) % 2**32)
            self.metadata["audio_hashes"][kind] = hashlib.sha256(data.tobytes()).hexdigest()
            self.sounds[kind] = p.sndarray.make_sound(data)
        self.metadata.update(status="running", display_font=font_path, audio_driver=p.mixer.get_init())
        self.save_metadata()

    def draw(self, lines, large=""):
        p = self.pg
        self.screen.fill((18, 22, 30))
        y = 65
        for line in lines:
            rendered = self.font.render(line, True, (235, 235, 235))
            if rendered.get_width() > self.screen.get_width() - 40:
                size = max(12, int(28 * (self.screen.get_width() - 40) / rendered.get_width()))
                rendered = p.font.Font(self.font_path, size).render(line, True, (235, 235, 235))
            self.screen.blit(rendered, (self.screen.get_width() // 2 - rendered.get_width() // 2, y))
            y += 45
        if large:
            # Wrap long sets so set_size=25 remains visible on the minimum screen.
            chunks = [large[i:i+23] for i in range(0, len(large), 23)]
            for i, chunk in enumerate(chunks):
                rendered = self.big_font.render(chunk, True, (255, 220, 110))
                self.screen.blit(rendered, (self.screen.get_width() // 2 - rendered.get_width() // 2, y + 50 + i * 80))
        p.display.flip()
        return self.now()

    def events(self):
        events = self.pg.event.get()
        for event in events:
            if event.type == self.pg.QUIT or (event.type == self.pg.KEYDOWN and event.key == self.pg.K_ESCAPE):
                raise QuitExperiment()
        return events

    def message(self, lines):
        self.pg.event.clear(self.pg.KEYDOWN)
        onset = self.draw(lines + ["스페이스를 눌러 계속하세요.  |  ESC: 종료"])
        while True:
            for event in self.events():
                if event.type == self.pg.KEYDOWN and event.key == self.pg.K_SPACE:
                    return
            if self.smoke and self.now() - onset > .03:
                return
            self.clock.tick(120)

    def wait(self, seconds, lines, purpose="intertrial", row=None):
        onset = self.draw(lines + ["방향키를 누르지 말고 기다리세요."])
        if row is not None:
            row["intertrial_onset_s"] = onset
        try:
            while self.now() - onset < seconds:
                self.events()
                self.clock.tick(120)
        finally:
            self.metadata["waits"].append({"purpose": purpose, "onset_s": onset,
                                           "end_s": self.now(), "requested_seconds": seconds})
        return onset

    def write_row(self, row):
        self.writer.writerow(row)
        self.result_file.flush()

    def stop_noise(self, row):
        if self.audio_channel is not None and row.get("noise_play_command_s", "") != "" and row.get("noise_stop_command_s", "") == "":
            self.audio_channel.stop()
            row["noise_stop_command_s"] = self.now()
            row["noise_command_duration_ms"] = 1000 * (row["noise_stop_command_s"] - row["noise_play_command_s"])

    def stage(self, name, seconds, lines, large, row):
        # Discard premature presses before the probe; held keys do not auto-repeat.
        self.events()
        self.pg.event.clear(self.pg.KEYDOWN)
        onset = self.draw(lines, large)
        row[f"{name}_onset_s"] = onset
        if row["noise_stage"] == name:
            row["noise_play_command_s"] = self.now()
            self.audio_channel.play(self.sounds[row["noise_filter"]])
        response, rt = "", ""
        while True:
            for event in self.events():
                received = self.now()
                if (name == "probe" and received - onset < seconds
                        and event.type == self.pg.KEYDOWN and event.key in (self.pg.K_LEFT, self.pg.K_RIGHT)):
                    response = "T" if event.key == self.pg.K_LEFT else "F"
                    rt = 1000 * (received - onset)
                    row["response_time_s"] = received
                    break
            elapsed = self.now() - onset
            if self.smoke and name == "probe" and elapsed > .03 and elapsed < seconds:
                response, rt = row["expected"], elapsed * 1000
                row["response_time_s"] = self.now()
            if response or elapsed >= seconds:
                break
            self.clock.tick(120)
        if row["noise_stage"] == name:
            self.stop_noise(row)
        return response, rt

    def trial(self, stimulus, phase, number, count):
        c = self.cfg
        row = dict.fromkeys(FIELDS, "")
        row.update(phase=phase, trial=number, **stimulus, status="running", break_after=False,
                   expected="T" if stimulus["probe"] in stimulus["set"] else "F",
                   calibration_mean_ms=self.calibration_mean)
        if phase == "main":
            if row["noise_condition"] == "quiet":
                row.update(noise_target_rms=0, noise_command_duration_ms=0)
            else:
                row.update(noise_target_rms=c.noise_rms,
                           noise_min_hz=getattr(c, f'{row["noise_filter"]}_min_hz'),
                           noise_max_hz=getattr(c, f'{row["noise_filter"]}_max_hz'))
        self.active_row = row
        label = {"practice": "연습", "calibration": "반응시간 보정", "main": "본 실험"}[phase]
        header = f"{label}  {number} / {count}"
        self.stage("set", c.memorize_seconds, [header, "아래 대문자들을 기억하세요. 아직 답하지 마세요."], " ".join(stimulus["set"]), row)
        self.stage("delay", c.delay_seconds, [header, "알파벳을 마음속으로 기억하고 +를 바라보세요.", "아직 답하지 마세요."], "+", row)
        response, rt = self.stage("probe", c.response_timeout_seconds,
                                  [header, "이 글자가 방금 기억한 set에 있었나요?", "왼쪽 ←: T (있음)     오른쪽 →: F (없음)", "가능한 한 빠르고 정확하게 답하세요."], stimulus["probe"], row)
        row.update(response=response, response_time_ms=rt, timeout=not bool(response),
                   correct=bool(response) and response == row["expected"])
        self.wait(c.intertrial_seconds, ["다음 시행을 기다리세요. 기억했던 알파벳은 이제 잊어도 됩니다."], row=row)
        row["trial_end_s"] = self.now()
        row["status"] = "completed"
        row["break_after"] = phase == "main" and number == math.ceil(count / 2) and number < count
        row["timing_json"] = json.dumps({s: row[f"{s}_onset_s"] for s in (*STAGES, "intertrial")})
        self.write_row(row)
        self.active_row = None
        if phase == "practice":
            feedback = "정답입니다." if row["correct"] else ("시간이 초과되었습니다." if row["timeout"] else "오답입니다.")
            self.message([feedback, f'정답: {row["expected"]}  |  {stimulus["probe"]}의 set 포함 여부를 판단하세요.'])
        return row

    def run(self):
        try:
            self.setup()
            self.message(["Sternberg 기억 실험 안내", "1. 처음 나타나는 대문자 set을 기억합니다.", "2. set이 사라지면 +를 보며 계속 기억합니다.", "3. 한 글자(probe)가 나타나면 set에 있었는지 판단합니다.", "왼쪽 ←: T (있음)     오른쪽 →: F (없음)", "응답에는 시간 제한이 있습니다. 빠르고 정확하게 답하세요.", "4. 다음 시행까지 기다립니다. 소음이 없는 시행도 있습니다.", "먼저 연습하고, 소음 없이 반응시간을 보정합니다."])
            for i, stimulus in enumerate(self.practice, 1):
                self.trial(stimulus, "practice", i, len(self.practice))
            self.message(["반응시간 보정", "연습과 같은 방식으로 빠르고 정확하게 답하세요.", "정답 응답의 평균 반응시간을 계산합니다. 소음은 없습니다."])
            rows = [self.trial(s, "calibration", i, len(self.calibration)) for i, s in enumerate(self.calibration, 1)]
            correct_rts = [r["response_time_ms"] for r in rows if r["correct"]]
            self.calibration_mean = statistics.mean(correct_rts) if correct_rts else ""
            self.metadata.update(calibration_mean_ms=self.calibration_mean,
                                 calibration_valid_responses=len(correct_rts), calibration_total=len(rows))
            self.save_metadata()
            if not correct_rts:
                self.message(["보정에서 유효한 정답 응답이 없어 평균 반응시간을 계산하지 못했습니다.", "결과에 평균은 빈칸으로 저장됩니다. 본 실험은 계속 진행합니다."])
            self.wait(self.cfg.post_calibration_wait_seconds,
                      ["반응시간 보정이 끝났습니다. 곧 본 실험을 시작합니다.", "본 실험에서도 왼쪽: 있음(T), 오른쪽: 없음(F)입니다."], "post_calibration")
            for i, stimulus in enumerate(self.main, 1):
                row = self.trial(stimulus, "main", i, len(self.main))
                if row["break_after"]:
                    self.wait(self.cfg.break_seconds, ["절반 이상의 시행을 마쳤습니다. 잠시 쉬세요.", "휴식 시간이 끝나면 안내에 따라 재개하세요."], "break")
                    self.message(["휴식이 끝났습니다.", "왼쪽: 있음(T), 오른쪽: 없음(F)를 기억하세요."])
            self.metadata["status"] = "completed"
            self.message(["실험을 모두 마쳤습니다. 감사합니다.", "결과는 외부 CSV 파일에 저장되었습니다."])
        except (QuitExperiment, KeyboardInterrupt):
            self.metadata["status"] = "aborted"
        except Exception:
            self.metadata["status"] = "error"
            raise
        finally:
            if self.active_row is not None:
                self.stop_noise(self.active_row)
                self.active_row.update(status=self.metadata["status"], trial_end_s=self.now())
                self.write_row(self.active_row)
            if self.audio_channel is not None:
                self.audio_channel.stop()
            self.metadata["ended_utc"] = datetime.now(timezone.utc).isoformat()
            self.save_metadata()
            self.result_file.close()
            self.pg.quit()
            print(f"결과: {self.folder}")


def main():
    parser = argparse.ArgumentParser(description="Sternberg 기억 실험")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.ini"))
    parser.add_argument("--participant", help="지정하면 시작 화면의 ID 입력을 생략합니다")
    parser.add_argument("--smoke-test", action="store_true", help="개발 검증용 자동 응답; 피험자 데이터가 아님")
    args = parser.parse_args()
    cfg = load_settings(args.config.resolve())
    if args.smoke_test:
        cfg.trials_per_condition, cfg.calibration_trials, cfg.practice_trials = 1, 2, 1
        cfg.stimuli_file = ""
        for name in ("memorize_seconds", "delay_seconds", "response_timeout_seconds", "break_seconds",
                     "post_calibration_wait_seconds", "intertrial_seconds"):
            setattr(cfg, name, .08)
    participant = args.participant
    if participant is None:
        participant = "CHECK" if args.smoke_test else prompt_participant(cfg)
    if participant is not None:
        Experiment(cfg, participant, args.smoke_test).run()


if __name__ == "__main__":
    main()
