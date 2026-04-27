from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from account_registrar import (
    DEFAULT_SELECTORS_PATH,
    CSVParser,
    PromptBridge,
    RegistrationAccount,
    RegistrationOrchestrator,
    RunConfig,
    build_manual_browser_proxy_argument,
    derive_profile_age,
    derive_profile_name,
    load_selectors,
    parse_browser_order,
    select_accounts,
    setup_logger,
)


def test_csv_parser_skips_header_and_invalid_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "accounts.csv"
    csv_path.write_text(
        "\n".join(
            [
                "invite_link|email|password|proxy",
                "https://example.com/register|one@example.com|Pass123|",
                "missing-columns",
                "https://example.com/register|two@example.com|Pass456|http://127.0.0.1:9999",
            ]
        ),
        encoding="utf-8",
    )

    logger = setup_logger(tmp_path / "parser.log")
    accounts = CSVParser.parse_file(csv_path, logger)

    assert [account.email for account in accounts] == ["one@example.com", "two@example.com"]


def test_csv_parser_accepts_comma_rows_and_curl_proxy_syntax(tmp_path: Path) -> None:
    csv_path = tmp_path / "accounts.csv"
    csv_path.write_text(
        (
            "https://chatgpt.com/auth/login?inv_ws_name=Gptku&inv_email=234salah%40gptku.sbs"
            "&wId=6c4a338d-a967-4fee-8f2a-c91a8a916e25&accept_wId=6c4a338d-a967-4fee-8f2a-c91a8a916e25, "
            "234salah@premixio.com, Premixio#123, "
            "\"curl --proxy \"\"http://exvenator:13asorcerer@31.59.20.176:6754/\"\"\""
        ),
        encoding="utf-8",
    )

    logger = setup_logger(tmp_path / "parser.log")
    accounts = CSVParser.parse_file(csv_path, logger)

    assert len(accounts) == 1
    assert accounts[0].email == "234salah@premixio.com"
    assert accounts[0].password == "Premixio#123"
    assert accounts[0].proxy == "http://exvenator:13asorcerer@31.59.20.176:6754/"


def test_registration_plus_codex_router_device_auth_flow(tmp_path: Path) -> None:
    with MockFlowServer() as site:
        config = RunConfig(
            headless=True,
            report_path=tmp_path / "report.json",
            log_path=tmp_path / "run.log",
            otp_wait_seconds=5,
            codex_router_url=site.base_url,
            device_auth_timeout_seconds=10,
        )
        logger = setup_logger(config.log_path)
        orchestrator = RegistrationOrchestrator(config, load_selectors(DEFAULT_SELECTORS_PATH), logger)
        accounts = [
            RegistrationAccount(
                invite_link=site.url("/register?flow=otp"),
                email="otp@example.com",
                password="Pass123",
            ),
        ]

        results = asyncio.run(orchestrator.register_all(accounts))
        report = orchestrator.generate_report()

    assert results[0].status == "completed"
    assert results[0].phases["registration"] == "completed"
    assert results[0].phases["codex_router_oauth"] == "completed"
    assert report["completed"] == 1
    assert json.loads(config.report_path.read_text(encoding="utf-8"))["completed"] == 1


def test_direct_codex_device_auth_only_flow(tmp_path: Path) -> None:
    with MockFlowServer() as site:
        config = RunConfig(
            headless=True,
            flow_mode="playwright",
            run_mode="device-auth-only",
            report_path=tmp_path / "report.json",
            log_path=tmp_path / "run.log",
            otp_wait_seconds=5,
            codex_device_url=site.url("/device"),
            device_auth_timeout_seconds=10,
        )
        logger = setup_logger(config.log_path)
        orchestrator = RegistrationOrchestrator(config, load_selectors(DEFAULT_SELECTORS_PATH), logger)
        accounts = [
            RegistrationAccount(
                invite_link="https://example.com/should-not-be-opened",
                email="otp@example.com",
                password="Pass123",
            ),
        ]

        results = asyncio.run(orchestrator.register_all(accounts))

    assert results[0].status == "completed"
    assert results[0].phases["registration"] == "skipped"
    assert results[0].phases["codex_router_oauth"] == "completed"


def test_chatgpt_style_gate_and_onboarding_flow(tmp_path: Path) -> None:
    with MockFlowServer() as site:
        config = RunConfig(
            headless=True,
            report_path=tmp_path / "report.json",
            log_path=tmp_path / "run.log",
            otp_wait_seconds=5,
        )
        logger = setup_logger(config.log_path)
        orchestrator = RegistrationOrchestrator(config, load_selectors(DEFAULT_SELECTORS_PATH), logger)
        accounts = [
            RegistrationAccount(
                invite_link=site.url("/register?flow=gate"),
                email="234salah@premixio.com",
                password="Pass123",
            ),
        ]

        results = asyncio.run(orchestrator.register_all(accounts))

    assert results[0].status == "registered"
    assert results[0].phases["registration"] == "completed"


def test_proxy_failure_falls_back_to_direct_connection(tmp_path: Path) -> None:
    with MockFlowServer() as site:
        config = RunConfig(
            headless=True,
            report_path=tmp_path / "report.json",
            log_path=tmp_path / "run.log",
            otp_wait_seconds=5,
        )
        logger = setup_logger(config.log_path)
        orchestrator = RegistrationOrchestrator(config, load_selectors(DEFAULT_SELECTORS_PATH), logger)
        accounts = [
            RegistrationAccount(
                invite_link=site.url("/register?flow=success"),
                email="fallback@example.com",
                password="Pass123",
                proxy="http://127.0.0.1:9",
            ),
        ]

        results = asyncio.run(orchestrator.register_all(accounts))

    assert results[0].status == "registered"
    assert results[0].fallback_used is True
    assert results[0].attempted_proxies == ["http://127.0.0.1:9", None]


def test_parse_browser_order_accepts_supported_names() -> None:
    assert parse_browser_order("chromium, msedge,chrome,firefox") == (
        "chromium",
        "msedge",
        "chrome",
        "firefox",
    )


def test_derive_profile_name_strips_digits() -> None:
    account = RegistrationAccount(
        invite_link="https://example.com/register",
        email="234salah@premixio.com",
        password="Pass123",
    )
    assert derive_profile_name(account) == "Salah"


def test_derive_profile_age_uses_21_to_30_range() -> None:
    account = RegistrationAccount(
        invite_link="https://example.com/register",
        email="234salah@premixio.com",
        password="Pass123",
    )
    assert derive_profile_age(account) == "25"


def test_select_accounts_applies_start_at_and_limit() -> None:
    accounts = [
        RegistrationAccount("https://example.com/1", "one@example.com", "Pass123"),
        RegistrationAccount("https://example.com/2", "two@example.com", "Pass123"),
        RegistrationAccount("https://example.com/3", "three@example.com", "Pass123"),
    ]

    selected = select_accounts(accounts, start_at=2, limit=1)

    assert [account.email for account in selected] == ["two@example.com"]


def test_manual_browser_proxy_argument_rejects_authenticated_proxy() -> None:
    try:
        build_manual_browser_proxy_argument("http://user:pass@127.0.0.1:8080")
    except ValueError as exc:
        assert "Authenticated proxies" in str(exc)
    else:
        raise AssertionError("Expected authenticated proxy to be rejected")


def test_prompt_bridge_round_trip(tmp_path: Path) -> None:
    logger = setup_logger(tmp_path / "bridge.log")
    bridge = PromptBridge(tmp_path / "bridge", logger)

    async def run_flow() -> str | None:
        async def answer_later() -> None:
            await asyncio.sleep(0.1)
            bridge.send_value(value="654321")

        answer_task = asyncio.create_task(answer_later())
        try:
            return await bridge.request_value(
                kind="otp",
                account_name="sample",
                prompt="OTP required",
                timeout_seconds=5,
            )
        finally:
            await answer_task

    value = asyncio.run(run_flow())

    assert value == "654321"


class MockFlowServer:
    def __enter__(self) -> "MockFlowServer":
        self.server = MockHTTPServer(("127.0.0.1", 0), MockFlowHandler)
        self.server.oauth_polling_started = False
        self.server.device_completed = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"


class MockHTTPServer(ThreadingHTTPServer):
    oauth_polling_started: bool
    device_completed: bool


class MockFlowHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        flow = query.get("flow", ["success"])[0]

        if parsed.path == "/register":
            self._send_html(self.render_register(flow))
            return
        if parsed.path == "/login-email":
            self._send_html(self.render_login_email())
            return
        if parsed.path == "/login-password":
            self._send_html(self.render_login_password())
            return
        if parsed.path == "/profile-name":
            self._send_html(self.render_profile_about_you())
            return
        if parsed.path == "/profile-role":
            self._send_html(self.render_profile_role())
            return
        if parsed.path == "/profile-connect":
            self._send_html(self.render_profile_connect())
            return
        if parsed.path == "/otp":
            self._send_html(self.render_otp())
            return
        if parsed.path == "/welcome":
            self._send_html(self.render_success())
            return
        if parsed.path == "/device":
            self._send_html(self.render_device())
            return
        if parsed.path == "/device/complete":
            self.server.device_completed = True
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/oauth/status":
            status = "success" if self.server.oauth_polling_started and self.server.device_completed else "pending"
            self._send_json({"status": status, "errorMessage": None})
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        payload = self._read_json()

        if parsed.path == "/api/oauth/start":
            self._send_json(
                {
                    "method": "device",
                    "verificationUrl": f"http://127.0.0.1:{self.server.server_port}/device",
                    "userCode": "ABCD-1234",
                    "deviceAuthId": "device-auth-1",
                    "intervalSeconds": 1,
                    "expiresInSeconds": 30,
                }
            )
            return

        if parsed.path == "/api/oauth/complete":
            assert payload["deviceAuthId"] == "device-auth-1"
            assert payload["userCode"] == "ABCD-1234"
            self.server.oauth_polling_started = True
            self._send_json({"status": "pending"})
            return

        self.send_error(404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        return parsed

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def render_register(flow: str) -> str:
        if flow == "gate":
            return """
<!doctype html>
<html>
  <body>
    <button id="login-button">Log in</button>
    <script>
      document.getElementById("login-button").addEventListener("click", function() {
        window.location.href = "/login-email";
      });
    </script>
  </body>
</html>
"""
        next_path = "/otp" if flow == "otp" else "/welcome"
        return f"""
<!doctype html>
<html>
  <body>
    <form id="register-form">
      <input type="email" name="email" placeholder="Email address" />
      <input type="password" name="password" placeholder="Password" />
      <button type="submit">Register</button>
    </form>
    <script>
      const form = document.getElementById("register-form");
      form.addEventListener("submit", function(event) {{
        event.preventDefault();
        window.location.href = "{next_path}";
      }});
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_login_email() -> str:
        return """
<!doctype html>
<html>
  <body>
    <form id="email-form">
      <input type="email" name="email" placeholder="Email address" />
      <button type="submit">Continue</button>
    </form>
    <script>
      document.getElementById("email-form").addEventListener("submit", function(event) {
        event.preventDefault();
        window.location.href = "/login-password";
      });
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_login_password() -> str:
        return """
<!doctype html>
<html>
  <body>
    <form id="password-form">
      <input type="password" name="password" placeholder="Password" />
      <button type="submit">Continue</button>
    </form>
    <script>
      document.getElementById("password-form").addEventListener("submit", function(event) {
        event.preventDefault();
        window.location.href = "/profile-name";
      });
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_profile_about_you() -> str:
        return """
<!doctype html>
<html>
  <body>
    <form id="about-you-form">
      <input type="text" name="full_name" placeholder="Full name" />
      <input type="text" name="age" placeholder="Age" />
      <button type="submit">Finish creating account</button>
    </form>
    <script>
      document.getElementById("about-you-form").addEventListener("submit", function(event) {
        event.preventDefault();
        setTimeout(function() {
          window.location.href = "/profile-role";
        }, 500);
      });
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_profile_role() -> str:
        return """
<!doctype html>
<html>
  <body>
    <button id="role-option">Engineering</button>
    <button id="next-button">Next</button>
    <script>
      document.getElementById("next-button").addEventListener("click", function() {
        window.location.href = "/profile-connect";
      });
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_profile_connect() -> str:
        return """
<!doctype html>
<html>
  <body>
    <button id="skip-button">Skip</button>
    <script>
      document.getElementById("skip-button").addEventListener("click", function() {
        window.location.href = "/welcome";
      });
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_otp() -> str:
        return """
<!doctype html>
<html>
  <body>
    <div>Enter OTP</div>
    <input type="text" name="otp_code" placeholder="OTP code" />
    <script>
      setTimeout(function() {
        window.location.href = "/welcome";
      }, 800);
    </script>
  </body>
</html>
"""

    @staticmethod
    def render_success() -> str:
        return """
<!doctype html>
<html>
  <body>
    <div class="success" data-test="registration-success">Welcome</div>
  </body>
</html>
"""

    @staticmethod
    def render_device() -> str:
        return """
<!doctype html>
<html>
  <body>
    <form id="device-form">
      <input type="text" name="device_code" placeholder="Enter code" />
      <button type="submit">Continue</button>
    </form>
    <script>
      const form = document.getElementById("device-form");
      form.addEventListener("submit", function(event) {
        event.preventDefault();
        fetch("/device/complete").then(() => {
          document.body.innerHTML = "<div>Authorized</div>";
        });
      });
      setTimeout(function() {
        form.requestSubmit();
      }, 900);
    </script>
  </body>
</html>
"""
