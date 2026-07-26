"""Live end-to-end for slice C. Boots a real uvicorn per scenario and drives it over HTTP.

Usage (from server/):
    .venv/bin/python tests/e2e_live.py            # all three scenarios
    .venv/bin/python tests/e2e_live.py --mock     # MOCK_LLM=1, zero API calls
    .venv/bin/python tests/e2e_live.py --real     # real DeepSeek calls (spends pennies)
    .venv/bin/python tests/e2e_live.py --badkey   # invalid key → fail-open mode

Exit code 0 = all pass. Not collected by pytest (filename doesn't start with test_).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

SERVER_DIR = Path(__file__).resolve().parent.parent
UVICORN = SERVER_DIR / ".venv" / "bin" / "uvicorn"

PRODUCT = {
    "title": "Sony WH-1000XM5 Headphones",
    "price_cents": 34800,
    "currency": "USD",
    "url": "https://a.co/x",
    "image_url": "https://x.jpg",
    "site": "amazon",
    "dom_snippet": "Sony WH-1000XM5 $348",
}
MEDICAL = {
    "title": "Omron Platinum Blood Pressure Monitor",
    "price_cents": 8900,
    "currency": "USD",
    "url": "https://a.co/2",
    "image_url": "https://x.jpg",
    "site": "amazon",
    "dom_snippet": "clinically validated blood pressure monitor",
}
FROZEN = {"session_id", "verdict", "reply", "turn", "turns_remaining", "score", "savings_total_cents"}

failures = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), "-", name, extra)
    if not cond:
        failures.append(name)


class Server:
    def __init__(self, port, env_overrides):
        self.port = port
        env = {**os.environ, "PYTHONUNBUFFERED": "1", **env_overrides}
        self.proc = subprocess.Popen(
            [str(UVICORN), "main:app", "--port", str(port)],
            cwd=SERVER_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def wait_ready(self, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                httpx.get(f"http://localhost:{self.port}/api/stats/1", timeout=2)
                return True
            except Exception:
                if self.proc.poll() is not None:
                    return False
                time.sleep(0.4)
        return False

    def stop(self):
        self.proc.terminate()
        try:
            out, _ = self.proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, _ = self.proc.communicate()
        return out or ""


def interrogate(port, session_id=None, message=None, product=PRODUCT, timeout=15):
    started = time.time()
    r = httpx.post(
        f"http://localhost:{port}/api/interrogate",
        json={"user_id": 1, "product": product, "session_id": session_id, "message": message},
        timeout=timeout,
    )
    return r, time.time() - started


def scenario_mock():
    print("\n=== SCENARIO: MOCK_LLM=1 (zero API calls) ===")
    s = Server(8010, {"MOCK_LLM": "1"})
    try:
        check("mock server boots", s.wait_ready())
        base = httpx.get("http://localhost:8010/api/stats/1").json()["saved_cents"]

        r1, _ = interrogate(8010)
        b1 = r1.json()
        check("turn1 200 + frozen fields", r1.status_code == 200 and set(b1) == FROZEN)
        check("turn1 pending", b1["verdict"] == "pending" and b1["turn"] == 1)

        sid = b1["session_id"]
        b2 = interrogate(8010, sid, "I want it")[0].json()
        check("turn2 pending", b2["verdict"] == "pending" and b2["turn"] == 2)
        b3 = interrogate(8010, sid, "just because")[0].json()
        check("turn3 denied final", b3["verdict"] == "denied" and b3["turns_remaining"] == 0)
        check("savings increment == price", b3["savings_total_cents"] == base + PRODUCT["price_cents"])

        sid2 = interrogate(8010)[0].json()["session_id"]
        ap = interrogate(8010, sid2, "my headphones broke and I need them for work calls")[0].json()
        check("strong answer approved", ap["verdict"] == "approved")

        prof = httpx.put("http://localhost:8010/api/profile/1", json={"savings_goal": "e2e goal"}).json()
        check("profile PUT applies", prof["savings_goal"] == "e2e goal")
        check("profile GET reflects", httpx.get("http://localhost:8010/api/profile/1").json()["savings_goal"] == "e2e goal")

        bad = httpx.post(
            "http://localhost:8010/api/interrogate",
            content='{"user_id":',
            headers={"Content-Type": "application/json"},
        )
        check("malformed body not a 500", bad.status_code < 500, f"(got {bad.status_code})")
    finally:
        out = s.stop()
    check("startup announced mock mode", "MOCK_LLM=1" in out)


def scenario_real():
    print("\n=== SCENARIO: real DeepSeek (deepseek-v4-flash) ===")
    s = Server(8011, {"MOCK_LLM": "0"})
    try:
        check("real server boots", s.wait_ready())

        r1, t1 = interrogate(8011)
        b1 = r1.json()
        check("turn1 200 + frozen fields", r1.status_code == 200 and set(b1) == FROZEN)
        check("turn1 pending with a real question", b1["verdict"] == "pending" and len(b1["reply"]) > 10)
        check(f"turn1 under 8s ({t1:.1f}s)", t1 < 8.5)

        sid = b1["session_id"]
        b2, t2 = interrogate(8011, sid, "my only headphones snapped this morning and I take client calls all day, already budgeted")
        b2 = b2.json()
        check("strong justification approved", b2["verdict"] == "approved", f"(score {b2['score']})")
        check(f"turn2 under 8s ({t2:.1f}s)", t2 < 8.5)

        med, tm = interrogate(8011, product=MEDICAL)
        med = med.json()
        check("medical item hard-approved turn 1", med["verdict"] == "approved" and med["score"] == 100)
        check(f"medical under 8s ({tm:.1f}s)", tm < 8.5)
    finally:
        out = s.stop()
    check("startup validated key", "DeepSeek key valid" in out)


def scenario_badkey():
    print("\n=== SCENARIO: invalid key → fail-open ===")
    s = Server(8012, {"MOCK_LLM": "0", "DEEPSEEK_API_KEY": "sk-invalid-e2e-key"})
    try:
        check("bad-key server still boots", s.wait_ready())
        r, _ = interrogate(8012)
        b = r.json()
        check("interrogation fails open (approved)", r.status_code == 200 and b["verdict"] == "approved")
        check("fail-open keeps frozen fields", set(b) == FROZEN)
    finally:
        out = s.stop()
    check("startup shouted about invalid key", "INVALID" in out)


if __name__ == "__main__":
    args = set(sys.argv[1:])
    run_all = not args
    if run_all or "--mock" in args:
        scenario_mock()
    if run_all or "--real" in args:
        scenario_real()
    if run_all or "--badkey" in args:
        scenario_badkey()

    print()
    if failures:
        print(f"{len(failures)} E2E FAILURES: {failures}")
        sys.exit(1)
    print("E2E: ALL PASS")
