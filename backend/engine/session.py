"""한 번의 실습(세션): 상태표 + 명령어 기록 + 가설을 묶어서 관리합니다."""
from __future__ import annotations

from .commands import execute
from .judge import evaluate
from .observe import observe
from .state import HOSTS


class Session:
    def __init__(self, scenario) -> None:
        self.scenario = scenario
        self.epoch = 0  # 초기화할 때마다 올라가는 번호(오래 걸리는 AI 작업이 초기화 뒤에 끼어드는 것을 막음)
        self.reset()

    def reset(self) -> None:
        self.state = self.scenario.initial_state()
        self.history: list[dict] = []
        self.seq = 0
        self.counted = 0
        self.unsupported = 0
        self.last_mutation_seq = 0
        self.hypotheses: list[dict] = []
        self.observed: dict[str, dict[str, dict]] = {s: {} for s in HOSTS}  # 서버별 '내가 점검한 결과'
        self.hints: list[dict] = []
        self.hints_used = 0
        self.solution_viewed = False  # 힌트를 모두 쓴 뒤 '해설 보기'를 눌렀는지
        self.solution_after_seq: int | None = None
        self.hint_in_progress = False
        self.epoch += 1
        self.review_done = False
        self.review: dict | None = None
        self.review_in_progress = False

    def run(self, server: str, line: str) -> dict | None:
        server = server.upper()
        if server not in HOSTS:
            raise ValueError(f"알 수 없는 서버: {server}")
        line = " ".join(line.split())  # 공백 정리
        if not line:
            return None
        self.state.tick()
        fault_before = self.scenario.fault_active(self.state)
        res = execute(self.state, server, line)
        if res.facts.get("kind") == "noop":
            return None
        self.seq += 1
        if res.counted:
            self.counted += 1
        if not res.supported:
            self.unsupported += 1
        if res.facts.get("mutated"):
            self.last_mutation_seq = self.seq
        entry = {
            "seq": self.seq, "server": server, "command": line, "output": res.output,
            "exit_code": res.exit_code, "supported": res.supported,
            "time": f"{self.state.clock:%H:%M:%S}",
            "facts": res.facts, "fault_active": fault_before,
        }
        self.history.append(entry)
        self._record_observation(server, res.facts)
        return entry

    def _record_observation(self, server: str, facts: dict) -> None:
        if facts.get("mutated"):
            # 상태를 바꾸는 조치를 하면, 그 전에 점검한 결과는 더 이상 믿을 수 없으니 '다시 확인 필요'로 바꿉니다.
            for items in self.observed.values():
                for item in items.values():
                    item["stale"] = True
            return
        for target, key, ok, text in observe(server, facts):
            self.observed[target][key] = {"ok": ok, "text": text, "stale": False}

    def submit_hypothesis(self, text: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("가설 내용이 비어 있어요.")
        # 가설을 낸 시점(몇 번째 명령어 뒤인지)도 기록해 두면, 리뷰 때 '진단 후 제출했는지' 알 수 있습니다.
        self.hypotheses.append({"text": text, "after_seq": self.seq})

    def add_hint(self, level: int, text: str) -> None:
        self.hints.append({"level": level, "text": text, "after_seq": self.seq})
        self.hints_used = len(self.hints)

    def view_solution(self) -> None:
        if not self.solution_viewed:  # 처음 본 시점(몇 번째 명령어 뒤인지)만 기록합니다
            self.solution_viewed = True
            self.solution_after_seq = self.seq

    def public_solution(self) -> dict | None:
        """해설을 보기 전에는 아무것도 내보내지 않습니다. (정답이 브라우저로 먼저 새지 않게)"""
        if not self.solution_viewed:
            return None
        p = self.progress()
        return {**self.scenario.solution,
                "my_checks": {"evidence": p["evidence"], "root_cause_checked": p["diagnosed"],
                              "hypothesis_submitted": p["hypothesis_submitted"]}}

    def progress(self) -> dict:
        return evaluate(self)

    def public_observed(self) -> dict[str, list[dict]]:
        return {s: list(items.values()) for s, items in self.observed.items()}

    def public_history(self) -> list[dict]:
        """화면으로 보내도 되는 기록 (판정용 내부 정보 제외)"""
        keys = ("seq", "server", "command", "output", "exit_code", "supported", "time")
        return [{k: e[k] for k in keys} for e in self.history]
