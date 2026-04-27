#!/usr/bin/env python3
"""
Interactive invite registration automation with optional codex-lb device auth.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Error as PlaywrightError,
        Page,
        Playwright,
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )
except ImportError:
    print("ERROR: playwright is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_SELECTORS_PATH = TOOL_DIR / "selectors.json"

DEFAULT_SELECTORS: dict[str, list[str]] = {
    "login_entry": [
        "button:has-text('Log in')",
        "a:has-text('Log in')",
        "button:has-text('Login')",
        "a:has-text('Login')"
    ],
    "email": [
        "input[type='email']",
        "input[type='text'][name='username']",
        "input[name='username']",
        "input[name='email']",
        "input[id='username']",
        "input[id='email']",
        "input[autocomplete='username']",
        "input[inputmode='email']",
        "input[aria-label*='email' i]",
        "input[placeholder*='email' i]",
    ],
    "password": [
        "input[type='password']",
        "input[name='password']",
        "input[name='current-password']",
        "input[autocomplete='current-password']",
        "input[autocomplete='new-password']",
        "input[id='password']",
        "input[placeholder*='password' i]",
    ],
    "continue": [
        "button:has-text('Continue')",
        "button:has-text('Next')",
        "button:has-text('Sign in')",
        "button:has-text('Log in')",
        "input[type='submit'][value*='Continue' i]",
        "input[type='submit'][value*='Next' i]",
    ],
    "submit": [
        "button[type='submit']",
        "button:has-text('Register')",
        "button:has-text('Sign Up')",
        "button:has-text('Create Account')",
        "button:has-text('Submit')",
        "button:has-text('Continue')",
        "input[type='submit']",
    ],
    "otp": [
        "input[name*='otp' i]",
        "input[name*='code' i]",
        "input[placeholder*='otp' i]",
        "input[placeholder*='verification' i]",
        "text=Enter OTP",
        "text=Verification Code",
    ],
    "success": [
        "text=Welcome",
        "text=Registration Complete",
        "text=Success",
        "[class*='success' i]",
        "[class*='confirmed' i]",
        "[data-test='registration-success']",
    ],
    "device_code": [
        "input[name*='code' i]",
        "input[id*='code' i]",
        "input[placeholder*='code' i]",
    ],
    "device_submit": [
        "button[type='submit']",
        "button:has-text('Continue')",
        "button:has-text('Next')",
        "button:has-text('Submit')",
        "input[type='submit']",
    ],
    "name": [
        "input[name*='full' i]",
        "input[placeholder*='full name' i]",
        "input[name*='name' i]",
        "input[id*='name' i]",
        "input[placeholder*='name' i]"
    ],
    "age_input": [
        "input[name='age']",
        "input[name*='age' i]",
        "input[id*='age' i]",
        "input[placeholder='Age']",
        "input[placeholder*='age' i]"
    ],
    "finish_account": [
        "button:has-text('Finish creating account')",
        "button[type='submit']",
        "input[type='submit']"
    ],
    "age_21_30": [
        "text=21-30",
        "label:has-text('21-30')",
        "button:has-text('21-30')"
    ],
    "role_engineering": [
        "text=Engineering",
        "label:has-text('Engineering')",
        "button:has-text('Engineering')"
    ],
    "skip": [
        "button:has-text('Skip')",
        "button:has-text('Skip for now')",
        "button:has-text('Not now')",
        "a:has-text('Skip')"
    ],
    "cookie_dismiss": [
        "button:has-text('Reject non-essential')",
        "button:has-text('Accept all')",
        "button[aria-label='Close']"
    ],
    "registration_url_keywords": [
        "register",
        "signup",
        "sign-up",
        "login",
        "sign-in",
        "auth",
        "verify",
        "invite",
    ],
    "success_url_keywords": [
        "welcome",
        "dashboard",
        "success",
        "home",
    ],
}

NETWORK_ERROR_MARKERS = (
    "ERR_PROXY",
    "ERR_TUNNEL",
    "ERR_CONNECTION",
    "ERR_NETWORK",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_ADDRESS_UNREACHABLE",
    "ERR_TIMED_OUT",
    "proxy",
    "tunnel",
    "connection refused",
    "connection reset",
)

SOCIAL_LOGIN_HOST_MARKERS = (
    "accounts.google.com",
    "appleid.apple.com",
    "login.live.com",
    "login.microsoftonline.com",
)


@dataclass(slots=True)
class RegistrationAccount:
    invite_link: str
    email: str
    password: str
    proxy: Optional[str] = None
    account_name: str = ""

    def __post_init__(self) -> None:
        if not self.account_name:
            self.account_name = self.email.split("@", 1)[0]


@dataclass(slots=True)
class RunConfig:
    headless: bool = False
    flow_mode: str = "playwright"
    run_mode: str = "register-and-auth"
    retry_without_proxy: bool = True
    browser_order: tuple[str, ...] = ("chromium", "msedge", "chrome", "firefox")
    profile_strategy: str = "ephemeral"
    user_data_dir: Optional[Path] = None
    browser_executable: Optional[Path] = None
    browser_use_config_dir: Path = TOOL_DIR / ".browser-use-config"
    account_timeout_seconds: int = 120
    action_timeout_ms: int = 12_000
    navigation_timeout_ms: int = 15_000
    otp_wait_seconds: int = 90
    bridge_dir: Optional[Path] = None
    bridge_timeout_seconds: int = 600
    codex_router_url: Optional[str] = None
    codex_device_url: Optional[str] = None
    device_auth_timeout_seconds: int = 120
    report_path: Path = Path("registration_report.json")
    log_path: Path = Path("registration.log")
    selectors_path: Path = DEFAULT_SELECTORS_PATH


@dataclass(slots=True)
class RegistrationResult:
    account: RegistrationAccount
    status: str = "pending"
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    error_details: Optional[str] = None
    attempted_proxies: list[Optional[str]] = field(default_factory=list)
    fallback_used: bool = False
    phases: dict[str, str] = field(
        default_factory=lambda: {
            "registration": "pending",
            "codex_router_oauth": "skipped",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.account.email,
            "account": self.account.account_name,
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error_details,
            "attempted_proxies": [proxy or "direct" for proxy in self.attempted_proxies],
            "fallback_used": self.fallback_used,
            "phases": self.phases,
        }


class ProxyNetworkError(RuntimeError):
    """Raised when an account-specific proxy fails before the flow can continue."""


class HTTPJSONError(RuntimeError):
    """Raised when the local codex-router API returns an invalid response."""


class PromptBridge:
    def __init__(self, bridge_dir: Path, logger: logging.Logger) -> None:
        self.bridge_dir = bridge_dir
        self.logger = logger
        self.request_path = bridge_dir / "request.json"
        self.response_path = bridge_dir / "response.json"
        self.history_path = bridge_dir / "history.log"
        self.bridge_dir.mkdir(parents=True, exist_ok=True)

    async def request_value(
        self,
        *,
        kind: str,
        account_name: str,
        prompt: str,
        timeout_seconds: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        request_id = f"{kind}-{account_name}-{int(time.time())}"
        payload = {
            "id": request_id,
            "kind": kind,
            "account": account_name,
            "prompt": prompt,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "status": "waiting",
        }
        self._write_json(self.request_path, payload)
        self._append_history({"event": "request", **payload})
        self.logger.info("[%s] Bridge request created: %s", account_name, self.request_path)

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.response_path.exists():
                response = self._read_json(self.response_path)
                if response.get("id") == request_id:
                    self.response_path.unlink(missing_ok=True)
                    self._append_history({"event": "response", **response})
                    self._write_json(
                        self.request_path,
                        {
                            **payload,
                            "status": "answered",
                            "answered_at": datetime.now().isoformat(),
                        },
                    )
                    return str(response.get("value", ""))
            await asyncio.sleep(1)

        self._write_json(
            self.request_path,
            {
                **payload,
                "status": "timed_out",
                "timed_out_at": datetime.now().isoformat(),
            },
        )
        self._append_history({"event": "timeout", **payload})
        return None

    def send_value(self, *, value: str) -> None:
        if not self.request_path.exists():
            raise RuntimeError(f"No pending bridge request found at {self.request_path}")
        request = self._read_json(self.request_path)
        request_id = request.get("id")
        if not request_id:
            raise RuntimeError("Pending bridge request is missing an id")
        payload = {
            "id": request_id,
            "value": value,
            "answered_at": datetime.now().isoformat(),
        }
        self._write_json(self.response_path, payload)
        self.logger.info("Bridge response written to %s", self.response_path)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Bridge file did not contain a JSON object: {path}")
        return parsed

    def _append_history(self, payload: dict[str, Any]) -> None:
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")


class CSVParser:
    @staticmethod
    def parse_file(filepath: Path, logger: logging.Logger) -> list[RegistrationAccount]:
        accounts: list[RegistrationAccount] = []

        try:
            with filepath.open("r", encoding="utf-8", newline="") as handle:
                for row_num, raw_line in enumerate(handle, start=1):
                    if not raw_line.strip():
                        continue

                    row = CSVParser._split_row(raw_line)
                    if row_num == 1 and row and row[0].strip().lower() == "invite_link":
                        logger.info("Skipping header row in %s", filepath)
                        continue

                    account = CSVParser._parse_row(row, logger, row_num=row_num)
                    if account:
                        accounts.append(account)
        except FileNotFoundError as exc:
            raise SystemExit(f"Input file not found: {filepath}") from exc

        logger.info("Parsed %s account(s) from %s", len(accounts), filepath)
        return accounts

    @staticmethod
    def _parse_row(
        row: list[str],
        logger: logging.Logger,
        row_num: int,
    ) -> Optional[RegistrationAccount]:
        if len(row) < 3:
            logger.warning("Skipping row %s: expected at least 3 columns, got %s", row_num, len(row))
            return None

        invite_link = row[0].strip()
        email = row[1].strip()
        password = row[2].strip()
        proxy = row[3].strip() if len(row) > 3 and row[3].strip() else None
        proxy = normalize_proxy_value(proxy)

        if not invite_link or not email or not password:
            logger.warning("Skipping row %s: invite_link, email, and password are required", row_num)
            return None

        return RegistrationAccount(
            invite_link=invite_link,
            email=email,
            password=password,
            proxy=proxy,
        )

    @staticmethod
    def _split_row(raw_line: str) -> list[str]:
        stripped = raw_line.strip()
        delimiter = "|" if "|" in stripped else ","
        return next(csv.reader([stripped], delimiter=delimiter, skipinitialspace=True))


class PlaywrightRuntime:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.playwright: Optional[Playwright] = None
        self._temp_profile_roots: list[Path] = []

    async def start(self) -> None:
        self.playwright = await async_playwright().start()
        self.logger.info("Playwright started")

    async def stop(self) -> None:
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            self.logger.info("Playwright stopped")
        self._cleanup_temp_profiles()

    async def launch_browser(
        self,
        *,
        proxy: Optional[str],
        headless: bool,
        browser_order: tuple[str, ...],
        profile_strategy: str,
        source_user_data_dir: Optional[Path],
    ) -> tuple[Browser, BrowserContext]:
        if not self.playwright:
            raise RuntimeError("Playwright runtime has not been started")

        errors: list[str] = []
        for browser_name in browser_order:
            launch_options: dict[str, Any] = {
                "headless": headless,
                "args": [
                    "--disable-dev-shm-usage",
                    "--no-default-browser-check",
                ],
            }
            if proxy:
                launch_options["proxy"] = build_proxy_settings(proxy)

            try:
                browser, context = await self._launch_named_browser(
                    browser_name,
                    launch_options,
                    profile_strategy=profile_strategy,
                    source_user_data_dir=source_user_data_dir,
                )
                self.logger.info("Launched browser via %s", browser_name)
                return browser, context
            except Exception as exc:
                errors.append(f"{browser_name}: {exc}")
                self.logger.warning("Browser launch failed via %s: %s", browser_name, exc)

        raise RuntimeError(f"Could not launch any configured browser: {' | '.join(errors)}")

    async def _launch_named_browser(
        self,
        browser_name: str,
        launch_options: dict[str, Any],
        *,
        profile_strategy: str,
        source_user_data_dir: Optional[Path],
    ) -> tuple[Browser, BrowserContext]:
        if not self.playwright:
            raise RuntimeError("Playwright runtime has not been started")

        channel: Optional[str] = None
        browser_type = None
        if browser_name == "chromium":
            browser_type = self.playwright.chromium
        elif browser_name == "msedge":
            browser_type = self.playwright.chromium
            channel = "msedge"
        elif browser_name == "chrome":
            browser_type = self.playwright.chromium
            channel = "chrome"
        elif browser_name == "firefox":
            browser_type = self.playwright.firefox
        else:
            raise ValueError(f"Unsupported browser launcher: {browser_name}")

        if profile_strategy == "copy" and source_user_data_dir:
            if browser_name == "firefox":
                raise RuntimeError("profile copy mode is only supported for Chromium-based browsers")

            persistent_options = dict(launch_options)
            if channel:
                persistent_options["channel"] = channel
            temp_user_data_dir = self._create_profile_copy(source_user_data_dir, browser_name)
            context = await browser_type.launch_persistent_context(str(temp_user_data_dir), **persistent_options)
            return context.browser, context

        launch_kwargs = dict(launch_options)
        if channel:
            launch_kwargs["channel"] = channel
        browser = await browser_type.launch(**launch_kwargs)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        return browser, context

    def _create_profile_copy(self, source_user_data_dir: Path, browser_name: str) -> Path:
        if not source_user_data_dir.exists():
            raise FileNotFoundError(f"Browser profile not found: {source_user_data_dir}")

        temp_root = Path(tempfile.mkdtemp(prefix="codex-auth-profile-"))
        target_dir = temp_root / browser_name
        shutil.copytree(source_user_data_dir, target_dir)
        self._temp_profile_roots.append(temp_root)
        self.logger.info("Copied browser profile to %s", target_dir)
        return target_dir

    def _cleanup_temp_profiles(self) -> None:
        for temp_root in self._temp_profile_roots:
            shutil.rmtree(temp_root, ignore_errors=True)
        self._temp_profile_roots.clear()


class CodexRouterOAuthClient:
    def __init__(self, base_url: str, logger: logging.Logger) -> None:
        self.base_url = base_url.rstrip("/")
        self.logger = logger

    async def start_device_flow(self) -> dict[str, Any]:
        payload = await self._request_json("POST", f"{self.base_url}/api/oauth/start", {"forceMethod": "device"})
        method = get_payload_value(payload, "method")
        if method != "device":
            raise HTTPJSONError(f"Expected device OAuth flow, got: {method}")
        return payload

    async def complete_device_flow(self, device_auth_id: str, user_code: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"{self.base_url}/api/oauth/complete",
            {
                "deviceAuthId": device_auth_id,
                "userCode": user_code,
            },
        )

    async def get_status(self) -> dict[str, Any]:
        return await self._request_json("GET", f"{self.base_url}/api/oauth/status")

    async def _request_json(
        self,
        method: str,
        url: str,
        payload: Optional[dict[str, Any]] = None,
        timeout_seconds: float = 15.0,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_json_sync, method, url, payload, timeout_seconds)

    def _request_json_sync(
        self,
        method: str,
        url: str,
        payload: Optional[dict[str, Any]],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise HTTPJSONError(f"{method} {url} failed: HTTP {exc.code} {body}") from exc
        except urllib.error.URLError as exc:
            raise HTTPJSONError(f"{method} {url} failed: {exc}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPJSONError(f"{method} {url} returned invalid JSON: {body}") from exc

        if not isinstance(parsed, dict):
            raise HTTPJSONError(f"{method} {url} returned a non-object JSON payload")
        return parsed


class BrowserUseCLI:
    def __init__(
        self,
        *,
        cdp_url: str,
        config_dir: Path,
        session_name: str,
        logger: logging.Logger,
    ) -> None:
        self.cdp_url = cdp_url
        self.config_dir = config_dir
        self.session_name = session_name
        self.logger = logger
        self.cli_path = shutil.which("browser-use")
        if not self.cli_path:
            raise RuntimeError("browser-use CLI was not found in PATH")

    async def open(self, url: str) -> None:
        await self._run("open", url)

    async def get_title(self) -> str:
        output = await self._run("get", "title")
        title = output.strip()
        if ":" in title:
            prefix, remainder = title.split(":", 1)
            if prefix.strip().lower() == "title":
                return remainder.strip()
        return title

    async def _run(self, *args: str) -> str:
        command = [
            self.cli_path,
            "--headed",
            "--session",
            self.session_name,
            "--cdp-url",
            self.cdp_url,
            *args,
        ]
        env = os.environ.copy()
        env["BROWSER_USE_CONFIG_DIR"] = str(self.config_dir)
        env["BROWSER_USE_CLOUD_SYNC"] = "false"
        env["ANONYMIZED_TELEMETRY"] = "false"
        env["BROWSER_USE_LOGGING_LEVEL"] = "error"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        completed = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown browser-use error"
            raise RuntimeError(f"browser-use command failed: {' '.join(args)} -> {stderr}")
        return completed.stdout


class NativeChromiumSession:
    def __init__(
        self,
        *,
        executable_path: Path,
        logger: logging.Logger,
        proxy: Optional[str] = None,
    ) -> None:
        self.executable_path = executable_path
        self.logger = logger
        self.proxy = proxy
        self.user_data_dir = Path(tempfile.mkdtemp(prefix="codex-auth-browser-"))
        self.port = reserve_tcp_port()
        self.process: Optional[subprocess.Popen[str]] = None

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def start(self) -> None:
        if not self.executable_path.exists():
            raise FileNotFoundError(f"Browser executable not found: {self.executable_path}")

        command = [
            str(self.executable_path),
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            "about:blank",
        ]
        proxy_arg = build_manual_browser_proxy_argument(self.proxy)
        if proxy_arg:
            command.append(proxy_arg)

        self.logger.info("Launching native browser: %s", self.executable_path)
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.to_thread(wait_for_cdp_endpoint, self.cdp_url, 20.0)

    async def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                await asyncio.to_thread(self.process.wait, 10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                await asyncio.to_thread(self.process.wait, 10)
        shutil.rmtree(self.user_data_dir, ignore_errors=True)


class BrowserUseManualHandler:
    def __init__(self, config: RunConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.codex_router = (
            CodexRouterOAuthClient(config.codex_router_url, logger)
            if config.codex_router_url
            else None
        )

    async def register_account(self, account: RegistrationAccount) -> RegistrationResult:
        result = RegistrationResult(account=account)
        result.attempted_proxies.append(account.proxy)
        browser_session: Optional[NativeChromiumSession] = None

        try:
            browser_path = self.config.browser_executable or discover_native_browser_executable()
            if browser_path is None:
                raise RuntimeError("Could not find Chrome or Edge. Pass --browser-executable explicitly.")

            browser_session = NativeChromiumSession(
                executable_path=browser_path,
                logger=self.logger,
                proxy=account.proxy,
            )
            await browser_session.start()
            session_name = build_browser_use_session_name(account)
            browser_use = BrowserUseCLI(
                cdp_url=browser_session.cdp_url,
                config_dir=self.config.browser_use_config_dir,
                session_name=session_name,
                logger=self.logger,
            )
            await browser_use.open(account.invite_link)
            title = await browser_use.get_title()
            self.logger.info("[%s] Opened invite link in native browser. title=%s", account.account_name, title)

            manual_ok = await self._wait_for_manual_registration(account)
            if not manual_ok:
                result.status = "failed"
                result.message = f"Manual registration cancelled for {account.account_name}"
                result.error_details = "User did not confirm registration completion"
                result.phases["registration"] = "failed"
                result.timestamp = datetime.now()
                return result

            result.phases["registration"] = "completed"

            if self.codex_router is None:
                result.status = "registered"
                result.message = f"Registered {account.account_name}"
                result.timestamp = datetime.now()
                return result

            oauth_completed = await self._complete_codex_router_device_auth(browser_use, account)
            if oauth_completed:
                result.phases["codex_router_oauth"] = "completed"
                result.status = "completed"
                result.message = f"Registered and authorized {account.account_name}"
            else:
                result.phases["codex_router_oauth"] = "failed"
                result.status = "failed"
                result.message = f"Registered {account.account_name}, but codex-router auth failed"
                result.error_details = "codex-router device auth did not complete successfully"
            result.timestamp = datetime.now()
            return result
        except Exception as exc:
            result.status = "failed"
            result.message = f"Registration failed for {account.account_name}"
            result.error_details = str(exc)
            result.phases["registration"] = "failed"
            result.timestamp = datetime.now()
            self.logger.exception("[%s] Unexpected error in browser-use/manual flow", account.account_name)
            return result
        finally:
            if browser_session is not None:
                await browser_session.stop()

    async def _wait_for_manual_registration(self, account: RegistrationAccount) -> bool:
        print()
        print("=" * 60)
        print(f"Manual registration in progress for: {account.account_name}")
        print("Use the opened fresh browser session for these steps:")
        print("1. Click Log in.")
        print("2. Enter the provided email and password.")
        print("3. If OTP appears, complete it in the browser.")
        print("4. Finish onboarding with a full name, age in 21-30, Engineering, then Skip.")
        print("5. Return here after the account is fully signed in.")
        print("Type 'done' or press Enter to continue. Type 'skip' to fail this account.")
        print("=" * 60)
        print()
        try:
            response = await asyncio.to_thread(
                input,
                f"Registration status for {account.account_name} [done/skip]: ",
            )
        except EOFError as exc:
            raise RuntimeError(
                "Interactive input is not available. Run this command in your local terminal session."
            ) from exc
        lowered = response.strip().lower()
        return lowered in {"", "done", "ok", "yes", "y"}

    async def _complete_codex_router_device_auth(
        self,
        browser_use: BrowserUseCLI,
        account: RegistrationAccount,
    ) -> bool:
        if self.codex_router is None:
            return True

        self.logger.info("[%s] Starting codex-router device auth", account.account_name)
        start_payload = await self.codex_router.start_device_flow()
        verification_url = get_payload_value(start_payload, "verificationUrl", "verification_url")
        user_code = get_payload_value(start_payload, "userCode", "user_code")
        device_auth_id = get_payload_value(start_payload, "deviceAuthId", "device_auth_id")
        interval_seconds = int(get_payload_value(start_payload, "intervalSeconds", "interval_seconds", default=2))
        expires_in_seconds = int(
            get_payload_value(
                start_payload,
                "expiresInSeconds",
                "expires_in_seconds",
                default=self.config.device_auth_timeout_seconds,
            )
        )

        if not verification_url or not user_code or not device_auth_id:
            raise HTTPJSONError(f"codex-router OAuth start payload is missing fields: {start_payload}")

        await self.codex_router.complete_device_flow(device_auth_id, user_code)
        announce_device_auth(account.account_name, verification_url, user_code)
        await browser_use.open(verification_url)

        deadline = time.monotonic() + min(self.config.device_auth_timeout_seconds, expires_in_seconds)
        while time.monotonic() < deadline:
            status_payload = await self.codex_router.get_status()
            status = get_payload_value(status_payload, "status")
            if status == "success":
                self.logger.info("[%s] codex-router device auth completed", account.account_name)
                return True
            if status == "error":
                message = get_payload_value(status_payload, "errorMessage", "error_message", default="unknown error")
                self.logger.error("[%s] codex-router device auth failed: %s", account.account_name, message)
                return False
            await asyncio.sleep(max(interval_seconds, 1))

        self.logger.warning("[%s] codex-router device auth timed out", account.account_name)
        return False


class RegistrationHandler:
    def __init__(
        self,
        runtime: PlaywrightRuntime,
        config: RunConfig,
        selectors: dict[str, list[str]],
        logger: logging.Logger,
    ) -> None:
        self.runtime = runtime
        self.config = config
        self.selectors = selectors
        self.logger = logger
        self.bridge = PromptBridge(config.bridge_dir, logger) if config.bridge_dir else None
        self.codex_router = (
            CodexRouterOAuthClient(config.codex_router_url, logger)
            if config.codex_router_url
            else None
        )
        self.codex_device_url = config.codex_device_url

    async def register_account(self, account: RegistrationAccount) -> RegistrationResult:
        result = RegistrationResult(account=account)
        proxies_to_try = [account.proxy]

        if account.proxy and self.config.retry_without_proxy:
            proxies_to_try.append(None)

        for index, proxy in enumerate(proxies_to_try, start=1):
            result.attempted_proxies.append(proxy)

            try:
                await self._run_attempt(account, result, proxy)
                if index > 1 and proxy is None:
                    result.fallback_used = True
                return result
            except ProxyNetworkError as exc:
                if index == len(proxies_to_try):
                    result.status = "failed"
                    result.message = f"Proxy/network failure for {account.account_name}"
                    result.error_details = str(exc)
                    result.timestamp = datetime.now()
                    return result

                result.fallback_used = True
                self.logger.warning(
                    "[%s] Proxy attempt failed, retrying without proxy: %s",
                    account.account_name,
                    exc,
                )

        return result

    async def _run_attempt(
        self,
        account: RegistrationAccount,
        result: RegistrationResult,
        proxy: Optional[str],
    ) -> None:
        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            # One brand-new browser process per account keeps sessions isolated.
            browser, context = await self.runtime.launch_browser(
                proxy=proxy,
                headless=self.config.headless,
                browser_order=self.config.browser_order,
                profile_strategy=self.config.profile_strategy,
                source_user_data_dir=self.config.user_data_dir,
            )
            context.set_default_timeout(self.config.action_timeout_ms)
            context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
            page = await context.new_page()

            if self.config.run_mode == "device-auth-only":
                await self._run_device_auth_only(context, account, result, proxy)
                return

            self.logger.info(
                "[%s] Starting flow (%s)",
                account.account_name,
                proxy if proxy else "direct",
            )
            await self._open_invite_link(page, account)
            await self._dismiss_optional_prompts(page, account.account_name)
            await self._enter_login_flow(page, account.account_name)
            await self._fill_registration_form(page, account)
            await self._resolve_otp_if_present(page, account.account_name)
            await self._submit_form(page, account.account_name)
            await self._resolve_otp_if_present(page, account.account_name)
            await self._complete_post_login_onboarding(page, account)
            await self._resolve_otp_if_present(page, account.account_name)

            otp_required = await self._has_any_selector(page, self.selectors["otp"], timeout_ms=1_000)
            if otp_required:
                result.phases["registration"] = "otp_required"
                self._announce_otp_requirement(account.account_name)
                otp_completed = await self._wait_for_otp_completion(page, account.invite_link, account.account_name)
                if not otp_completed:
                    result.status = "otp_required"
                    result.message = f"OTP timed out for {account.account_name}"
                    result.error_details = "OTP did not complete before timeout"
                    result.timestamp = datetime.now()
                    self.logger.warning("[%s] OTP wait timed out", account.account_name)
                    return

                # Some account flows reveal onboarding only after OTP succeeds.
                await self._complete_post_login_onboarding(page, account)
                await self._resolve_otp_if_present(page, account.account_name)

            registered = await self._verify_registration(page, account.invite_link, account.account_name)
            if not registered:
                result.phases["registration"] = "failed"
                result.status = "failed"
                result.message = f"Could not verify registration for {account.account_name}"
                result.error_details = "No success signal matched the current page state"
                result.timestamp = datetime.now()
                return

            result.phases["registration"] = "completed"

            if self.codex_router is None and not self.codex_device_url:
                result.status = "registered"
                result.message = f"Registered {account.account_name}"
                result.timestamp = datetime.now()
                return

            if self.codex_device_url:
                oauth_completed = await self._complete_direct_codex_device_auth(context, account)
            else:
                oauth_completed = await self._complete_codex_router_device_auth(context, account)
            if oauth_completed:
                result.phases["codex_router_oauth"] = "completed"
                result.status = "completed"
                result.message = f"Registered and authorized {account.account_name}"
            else:
                result.phases["codex_router_oauth"] = "failed"
                result.status = "failed"
                result.message = f"Registered {account.account_name}, but codex-router auth failed"
                result.error_details = "codex-router device auth did not complete successfully"

            result.timestamp = datetime.now()
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            if proxy and looks_like_network_error(exc):
                raise ProxyNetworkError(str(exc)) from exc

            result.status = "failed"
            result.message = f"Registration failed for {account.account_name}"
            result.error_details = str(exc)
            result.timestamp = datetime.now()
            self.logger.error("[%s] Playwright error: %s", account.account_name, exc)
        except Exception as exc:
            if proxy and looks_like_network_error(exc):
                raise ProxyNetworkError(str(exc)) from exc

            result.status = "failed"
            result.message = f"Registration failed for {account.account_name}"
            result.error_details = str(exc)
            result.timestamp = datetime.now()
            self.logger.exception("[%s] Unexpected error", account.account_name)
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    async def _run_device_auth_only(
        self,
        context: BrowserContext,
        account: RegistrationAccount,
        result: RegistrationResult,
        proxy: Optional[str],
    ) -> None:
        if not self.codex_device_url:
            raise RuntimeError("device-auth-only mode requires --codex-device-url")

        self.logger.info(
            "[%s] Starting device-auth-only flow (%s)",
            account.account_name,
            proxy if proxy else "direct",
        )
        result.phases["registration"] = "skipped"

        oauth_completed = await self._complete_direct_codex_device_auth(context, account)
        result.timestamp = datetime.now()
        if oauth_completed:
            result.phases["codex_router_oauth"] = "completed"
            result.status = "completed"
            result.message = f"Authorized {account.account_name}"
            return

        result.phases["codex_router_oauth"] = "failed"
        result.status = "failed"
        result.message = f"Device auth failed for {account.account_name}"
        result.error_details = "Direct codex device auth did not reach the ready state"

    async def _open_invite_link(self, page: Page, account: RegistrationAccount) -> None:
        self.logger.info("[%s] Opening invite link", account.account_name)
        try:
            await page.goto(
                account.invite_link,
                wait_until="domcontentloaded",
                timeout=self.config.navigation_timeout_ms,
            )
        except PlaywrightTimeoutError:
            self.logger.warning("[%s] Navigation timed out, continuing with current page state", account.account_name)

        await asyncio.sleep(0.5)
        self.logger.info("[%s] Landed on title=%s url=%s", account.account_name, await self._safe_page_title(page), page.url)

    async def _dismiss_optional_prompts(self, page: Page, account_name: str) -> None:
        await self._click_first(
            page,
            self.selectors["cookie_dismiss"],
            "dismissable prompt",
            account_name,
            required=False,
        )

    async def _enter_login_flow(self, page: Page, account_name: str) -> None:
        await self._wait_for_cloudflare_if_needed(page, account_name)
        clicked = await self._click_first(
            page,
            self.selectors["login_entry"],
            "login entry button",
            account_name,
            required=False,
        )
        if clicked:
            await asyncio.sleep(1.5)
            self.logger.info("[%s] Entered login flow", account_name)
        await self._wait_for_login_inputs(page, account_name)

    async def _fill_registration_form(self, page: Page, account: RegistrationAccount) -> None:
        email_ok = await self._fill_first(page, self.selectors["email"], account.email, "email", account.account_name)
        if not email_ok:
            raise RuntimeError("Could not locate an email input field")

        password_ok = await self._fill_first(
            page,
            self.selectors["password"],
            account.password,
            "password",
            account.account_name,
        )
        if not password_ok:
            await self._submit_email_step(page, account.account_name)
            await self._wait_for_password_stage(page, account.account_name)
            password_ok = await self._fill_first(
                page,
                self.selectors["password"],
                account.password,
                "password",
                account.account_name,
            )

        if not password_ok:
            if self._is_email_verification_url(page.url):
                self.logger.info(
                    "[%s] Flow moved directly to email verification after email submit; treating this as OTP-first path",
                    account.account_name,
                )
                return
            self._raise_if_social_login_branch(page.url, account.account_name)

        if not password_ok:
            self.logger.warning(
                "[%s] Password input not found. title=%s url=%s",
                account.account_name,
                await self._safe_page_title(page),
                page.url,
            )
            raise RuntimeError("Could not locate a password input field")

    async def _wait_for_password_stage(self, page: Page, account_name: str, timeout_seconds: int = 20) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            await self._wait_for_cloudflare_if_needed(page, account_name, max_wait_seconds=5)
            password_ready = await self._has_any_selector(page, self.selectors["password"], timeout_ms=400)
            if password_ready:
                self.logger.info("[%s] Password input detected at url=%s", account_name, page.url)
                return
            await asyncio.sleep(1)

        self.logger.warning(
            "[%s] Password input not detected after wait. title=%s url=%s",
            account_name,
            await self._safe_page_title(page),
            page.url,
        )
        self._raise_if_social_login_branch(page.url, account_name)

    async def _submit_email_step(self, page: Page, account_name: str) -> None:
        exact_button = page.get_by_role("button", name="Continue", exact=True).first
        try:
            await exact_button.wait_for(state="visible", timeout=1_500)
            await exact_button.click()
            await self._wait_for_navigation_settle(page)
            self.logger.info("[%s] Submitted email step with exact Continue button", account_name)
            return
        except (PlaywrightError, PlaywrightTimeoutError):
            pass

        exact_submit = page.locator("input[type='submit'][value='Continue']").first
        try:
            await exact_submit.wait_for(state="visible", timeout=1_000)
            await exact_submit.click()
            await self._wait_for_navigation_settle(page)
            self.logger.info("[%s] Submitted email step with exact Continue submit input", account_name)
            return
        except (PlaywrightError, PlaywrightTimeoutError):
            pass

        await page.keyboard.press("Enter")
        await self._wait_for_navigation_settle(page)
        self.logger.info("[%s] Submitted email step with Enter fallback", account_name)

    def _raise_if_social_login_branch(self, current_url: str, account_name: str) -> None:
        host = urlsplit(current_url).netloc.lower()
        if any(marker in host for marker in SOCIAL_LOGIN_HOST_MARKERS):
            raise RuntimeError(f"Unexpected social-login redirect detected for {account_name}: {current_url}")

    def _is_email_verification_url(self, current_url: str) -> bool:
        parsed = urlsplit(current_url)
        return parsed.netloc.lower() == "auth.openai.com" and "email-verification" in parsed.path.lower()

    async def _wait_for_login_inputs(self, page: Page, account_name: str, timeout_seconds: int = 20) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            await self._wait_for_cloudflare_if_needed(page, account_name, max_wait_seconds=5)

            email_ready = await self._has_any_selector(page, self.selectors["email"], timeout_ms=400)
            password_ready = await self._has_any_selector(page, self.selectors["password"], timeout_ms=400)
            if email_ready or password_ready:
                self.logger.info("[%s] Login inputs detected at url=%s", account_name, page.url)
                return

            if await self._has_any_selector(page, self.selectors["login_entry"], timeout_ms=300):
                await self._click_first(
                    page,
                    self.selectors["login_entry"],
                    "login entry button",
                    account_name,
                    required=False,
                )
                await asyncio.sleep(1)

            await asyncio.sleep(1)

        self.logger.warning("[%s] Login inputs not detected after wait. title=%s url=%s", account_name, await self._safe_page_title(page), page.url)

    async def _wait_for_cloudflare_if_needed(
        self,
        page: Page,
        account_name: str,
        max_wait_seconds: int = 15,
    ) -> None:
        lower_url = page.url.lower()
        lower_title = (await self._safe_page_title(page)).lower()
        if "__cf_chl" not in lower_url and "just a moment" not in lower_title:
            return

        self.logger.warning("[%s] Cloudflare challenge detected, waiting up to %ss", account_name, max_wait_seconds)
        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            await asyncio.sleep(1)
            lower_url = page.url.lower()
            lower_title = (await self._safe_page_title(page)).lower()
            if "__cf_chl" not in lower_url and "just a moment" not in lower_title:
                self.logger.info("[%s] Cloudflare challenge cleared", account_name)
                return

    async def _complete_post_login_onboarding(self, page: Page, account: RegistrationAccount) -> None:
        profile_name = derive_profile_name(account)
        profile_age = derive_profile_age(account)
        for _ in range(12):
            progressed = False

            name_visible = await self._has_any_selector(page, self.selectors["name"], timeout_ms=500)
            age_input_visible = await self._has_any_selector(page, self.selectors["age_input"], timeout_ms=500)
            if name_visible or age_input_visible:
                name_filled = True
                age_filled = True

                if name_visible:
                    name_filled = await self._fill_first(
                        page,
                        self.selectors["name"],
                        profile_name,
                        "full name",
                        account.account_name,
                    )
                if age_input_visible:
                    age_filled = await self._fill_first(
                        page,
                        self.selectors["age_input"],
                        profile_age,
                        "age",
                        account.account_name,
                    )

                if name_filled and age_filled:
                    await self._click_first(
                        page,
                        self.selectors["finish_account"] + self.selectors["continue"] + self.selectors["submit"],
                        "finish account button",
                        account.account_name,
                        required=False,
                    )
                    await self._wait_for_onboarding_transition(page, account.account_name)
                    progressed = True

            if not progressed:
                age_clicked = await self._click_first(
                    page,
                    self.selectors["age_21_30"],
                    "age option 21-30",
                    account.account_name,
                    required=False,
                )
                if age_clicked:
                    await self._click_first(
                        page,
                        self.selectors["continue"] + self.selectors["submit"],
                        "next button",
                        account.account_name,
                        required=False,
                    )
                    progressed = True

            if not progressed:
                role_clicked = await self._click_exact_role_button(page, account.account_name, "Engineering")
                if role_clicked:
                    await self._click_first(
                        page,
                        self.selectors["continue"] + self.selectors["submit"],
                        "next button",
                        account.account_name,
                        required=False,
                    )
                    progressed = True

            if not progressed:
                skip_clicked = await self._click_first(
                    page,
                    self.selectors["skip"],
                    "skip button",
                    account.account_name,
                    required=False,
                )
                if skip_clicked:
                    progressed = True

            if not progressed:
                break

            await asyncio.sleep(2)
            await self._resolve_otp_if_present(page, account.account_name)

    async def _wait_for_onboarding_transition(self, page: Page, account_name: str, timeout_seconds: int = 45) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if await self._has_role_prompt(page):
                self.logger.info("[%s] Role selection prompt detected", account_name)
                return
            current_url = page.url.rstrip("/")
            if current_url == "https://chatgpt.com":
                self.logger.info("[%s] Onboarding finished without role prompt", account_name)
                return
            await asyncio.sleep(1)

        self.logger.warning("[%s] Role selection prompt not detected after finish-account wait. title=%s url=%s", account_name, await self._safe_page_title(page), page.url)

    async def _has_role_prompt(self, page: Page) -> bool:
        prompt_locators = [
            page.get_by_text("What kind of work do you do?", exact=False).first,
            page.get_by_role("button", name="Engineering", exact=True).first,
        ]
        for locator in prompt_locators:
            try:
                await locator.wait_for(state="visible", timeout=500)
                return True
            except (PlaywrightError, PlaywrightTimeoutError):
                continue
        return False

    async def _click_exact_role_button(self, page: Page, account_name: str, role_name: str) -> bool:
        button = page.get_by_role("button", name=role_name, exact=True).first
        try:
            await button.wait_for(state="visible", timeout=2_000)
            await button.click()
            self.logger.info("[%s] Clicked exact role option %s", account_name, role_name)
            return True
        except (PlaywrightError, PlaywrightTimeoutError):
            pass

        return await self._click_first(
            page,
            self.selectors["role_engineering"],
            "engineering role option",
            account_name,
            required=False,
        )

    async def _submit_form(self, page: Page, account_name: str) -> None:
        submit_clicked = await self._click_first(
            page,
            self.selectors["submit"] + self.selectors["continue"],
            "submit button",
            account_name,
            required=False,
        )
        if not submit_clicked:
            await page.keyboard.press("Enter")
            self.logger.info("[%s] Submit button not found, pressed Enter instead", account_name)

        await asyncio.sleep(1)

    async def _complete_codex_router_device_auth(
        self,
        context: BrowserContext,
        account: RegistrationAccount,
    ) -> bool:
        if self.codex_router is None:
            return True

        self.logger.info("[%s] Starting codex-router device auth", account.account_name)
        start_payload = await self.codex_router.start_device_flow()
        verification_url = get_payload_value(start_payload, "verificationUrl", "verification_url")
        user_code = get_payload_value(start_payload, "userCode", "user_code")
        device_auth_id = get_payload_value(start_payload, "deviceAuthId", "device_auth_id")
        interval_seconds = int(get_payload_value(start_payload, "intervalSeconds", "interval_seconds", default=2))
        expires_in_seconds = int(get_payload_value(start_payload, "expiresInSeconds", "expires_in_seconds", default=self.config.device_auth_timeout_seconds))

        if not verification_url or not user_code or not device_auth_id:
            raise HTTPJSONError(f"codex-router OAuth start payload is missing fields: {start_payload}")

        await self.codex_router.complete_device_flow(device_auth_id, user_code)
        self._announce_device_auth(account.account_name, verification_url, user_code)

        page = await context.new_page()
        try:
            device_url = verification_url or "https://auth.openai.com/codex/device"
            await page.goto(device_url, wait_until="domcontentloaded", timeout=self.config.navigation_timeout_ms)
            await asyncio.sleep(0.5)
            filled = await self._fill_first(
                page,
                self.selectors["device_code"],
                user_code,
                "device auth code",
                account.account_name,
            )
            if filled:
                await self._click_first(
                    page,
                    self.selectors["device_submit"],
                    "device code submit button",
                    account.account_name,
                    required=False,
                )
        except PlaywrightError as exc:
            self.logger.warning("[%s] Could not pre-fill device auth code: %s", account.account_name, exc)

        deadline = time.monotonic() + min(self.config.device_auth_timeout_seconds, expires_in_seconds)
        while time.monotonic() < deadline:
            status_payload = await self.codex_router.get_status()
            status = get_payload_value(status_payload, "status")
            if status == "success":
                self.logger.info("[%s] codex-router device auth completed", account.account_name)
                return True
            if status == "error":
                message = get_payload_value(status_payload, "errorMessage", "error_message", default="unknown error")
                self.logger.error("[%s] codex-router device auth failed: %s", account.account_name, message)
                return False
            await asyncio.sleep(max(interval_seconds, 1))

        self.logger.warning("[%s] codex-router device auth timed out", account.account_name)
        return False

    async def _complete_direct_codex_device_auth(
        self,
        context: BrowserContext,
        account: RegistrationAccount,
    ) -> bool:
        if not self.codex_device_url:
            return True

        self.logger.info("[%s] Starting direct codex device auth", account.account_name)
        page = await context.new_page()
        await page.goto(self.codex_device_url, wait_until="domcontentloaded", timeout=self.config.navigation_timeout_ms)
        await asyncio.sleep(1)

        if await self._verify_direct_device_auth(page):
            self.logger.info("[%s] Direct codex device auth page already ready", account.account_name)
            return True

        await self._wait_for_login_inputs(page, account.account_name, timeout_seconds=30)
        login_needed = await self._has_any_selector(page, self.selectors["email"], timeout_ms=500)
        if login_needed:
            await self._fill_registration_form(page, account)
            await self._submit_form(page, account.account_name)
            await self._resolve_otp_if_present(page, account.account_name)

        deadline = time.monotonic() + self.config.device_auth_timeout_seconds
        while time.monotonic() < deadline:
            consent_clicked = await self._complete_direct_codex_consent_if_present(page, account.account_name)
            if consent_clicked:
                await asyncio.sleep(1)
            code_submitted = await self._resolve_device_code_if_present(page, account.account_name)
            if code_submitted:
                await asyncio.sleep(1)
            await self._resolve_otp_if_present(page, account.account_name)
            if await self._verify_direct_device_auth(page):
                self.logger.info("[%s] Direct codex device auth page reached ready state", account.account_name)
                return True
            await asyncio.sleep(1)

        self.logger.warning("[%s] Direct codex device auth timed out at url=%s", account.account_name, page.url)
        return False

    async def _verify_direct_device_auth(self, page: Page) -> bool:
        lower_url = page.url.lower()
        blocking_selectors = (
            self.selectors["email"]
            + self.selectors["password"]
            + self.selectors["otp"]
            + self.selectors["device_code"]
        )
        if await self._has_any_selector(page, blocking_selectors, timeout_ms=300):
            return False

        consent_heading = page.get_by_text("Sign in to Codex with ChatGPT", exact=False).first
        try:
            await consent_heading.wait_for(state="visible", timeout=300)
            return False
        except (PlaywrightError, PlaywrightTimeoutError):
            pass

        device_code_heading = page.get_by_text("Use your device code to grant access to Codex CLI", exact=False).first
        try:
            await device_code_heading.wait_for(state="visible", timeout=300)
            return False
        except (PlaywrightError, PlaywrightTimeoutError):
            pass

        if "deviceauth/callback" in lower_url:
            callback_success_markers = [
                page.get_by_text("Authorized", exact=False).first,
                page.get_by_text("Success", exact=False).first,
                page.get_by_text("You can close this window", exact=False).first,
                page.get_by_text("Return to Codex CLI", exact=False).first,
            ]
            for locator in callback_success_markers:
                try:
                    await locator.wait_for(state="visible", timeout=300)
                    return True
                except (PlaywrightError, PlaywrightTimeoutError):
                    continue
            return False
        success_markers = [
            page.get_by_text("Authorize", exact=False).first,
            page.get_by_text("Success", exact=False).first,
            page.get_by_text("Authorized", exact=False).first,
            page.get_by_text("You can close this window", exact=False).first,
            page.get_by_text("Return to Codex CLI", exact=False).first,
        ]
        for locator in success_markers:
            try:
                await locator.wait_for(state="visible", timeout=300)
                return True
            except (PlaywrightError, PlaywrightTimeoutError):
                continue
        return False

    async def _complete_direct_codex_consent_if_present(self, page: Page, account_name: str) -> bool:
        lower_url = page.url.lower()
        if "sign-in-with-chatgpt/codex/consent" not in lower_url:
            return False

        heading = page.get_by_text("Sign in to Codex with ChatGPT", exact=False).first
        try:
            await heading.wait_for(state="visible", timeout=500)
        except (PlaywrightError, PlaywrightTimeoutError):
            return False

        clicked = await self._click_first(
            page,
            self.selectors["continue"] + self.selectors["submit"],
            "codex consent continue button",
            account_name,
            required=False,
        )
        return clicked

    async def _resolve_device_code_if_present(self, page: Page, account_name: str) -> bool:
        heading = page.get_by_text("Use your device code to grant access to Codex CLI", exact=False).first
        try:
            await heading.wait_for(state="visible", timeout=500)
        except (PlaywrightError, PlaywrightTimeoutError):
            code_visible = await self._has_any_selector(page, self.selectors["device_code"], timeout_ms=500)
            if not code_visible:
                return False

        if self.bridge is not None:
            code_value = await self.bridge.request_value(
                kind="device_code",
                account_name=account_name,
                prompt=f"Device code required for {account_name}",
                timeout_seconds=self.config.bridge_timeout_seconds,
                metadata={"url": page.url},
            )
            if code_value is None:
                self.logger.warning("[%s] Bridge device-code request timed out", account_name)
                return True
        else:
            prompt = f"Enter device code for {account_name} (leave blank to keep manual control in browser): "
            try:
                code_value = await asyncio.to_thread(input, prompt)
            except EOFError:
                self.logger.warning(
                    "[%s] Interactive device-code input is unavailable in this terminal; waiting for manual browser completion",
                    account_name,
                )
                return True

        if not code_value or not code_value.strip():
            return True

        filled = await self._fill_first(
            page,
            self.selectors["device_code"],
            code_value.strip(),
            "device code",
            account_name,
        )
        if filled:
            await self._click_first(
                page,
                self.selectors["device_submit"] + self.selectors["continue"] + self.selectors["submit"],
                "device code submit button",
                account_name,
                required=False,
            )
        return True

    async def _fill_first(
        self,
        page: Page,
        selectors: list[str],
        value: str,
        field_name: str,
        account_name: str,
    ) -> bool:
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=1_000)
                await locator.fill(value)
                self.logger.info("[%s] Filled %s using %s", account_name, field_name, selector)
                return True
            except (PlaywrightError, PlaywrightTimeoutError):
                continue
        return False

    async def _click_first(
        self,
        page: Page,
        selectors: list[str],
        label: str,
        account_name: str,
        *,
        required: bool,
    ) -> bool:
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=1_000)
                await locator.click()
                self.logger.info("[%s] Clicked %s using %s", account_name, label, selector)
                return True
            except (PlaywrightError, PlaywrightTimeoutError):
                continue

        if required:
            raise RuntimeError(f"Could not locate {label}")
        return False

    async def _has_any_selector(
        self,
        page: Page,
        selectors: list[str],
        *,
        timeout_ms: int,
    ) -> bool:
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                return True
            except (PlaywrightError, PlaywrightTimeoutError):
                continue
        return False

    async def _safe_page_title(self, page: Page, retries: int = 5) -> str:
        for attempt in range(retries):
            if page.is_closed():
                return "<closed>"
            try:
                return await page.title()
            except (PlaywrightError, PlaywrightTimeoutError) as exc:
                if page.is_closed():
                    return "<closed>"
                if attempt == retries - 1:
                    self.logger.debug("Falling back after title read failed: %s", exc)
                    return "<unavailable>"
                await asyncio.sleep(0.25)
        return "<unavailable>"

    async def _wait_for_navigation_settle(self, page: Page, timeout_ms: int = 5_000) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except (PlaywrightError, PlaywrightTimeoutError):
            return

    def _announce_otp_requirement(self, account_name: str) -> None:
        print()
        print("=" * 60)
        print(f"OTP required for: {account_name}")
        if self.config.headless:
            print("Headless mode is enabled. OTP only works if the page auto-completes.")
        else:
            print("Enter the OTP in the browser window and submit the form.")
        print(f"The script will wait up to {self.config.otp_wait_seconds} seconds.")
        print("=" * 60)
        print()

    def _announce_device_auth(self, account_name: str, verification_url: str, user_code: str) -> None:
        announce_device_auth(account_name, verification_url, user_code)

    async def _resolve_otp_if_present(self, page: Page, account_name: str) -> bool:
        otp_visible = await self._has_any_selector(page, self.selectors["otp"], timeout_ms=500)
        if not otp_visible:
            return False

        if self.bridge is not None:
            otp_value = await self.bridge.request_value(
                kind="otp",
                account_name=account_name,
                prompt=f"OTP required for {account_name}",
                timeout_seconds=self.config.bridge_timeout_seconds,
                metadata={"url": page.url},
            )
            if otp_value is None:
                self.logger.warning("[%s] Bridge OTP request timed out", account_name)
                return True
            if otp_value.strip():
                filled = await self._fill_first(
                    page,
                    self.selectors["otp"],
                    otp_value.strip(),
                    "otp",
                    account_name,
                )
                if filled:
                    await self._click_first(
                        page,
                        self.selectors["submit"] + self.selectors["continue"],
                        "otp submit button",
                        account_name,
                        required=False,
                    )
            return True

        prompt = f"Enter OTP for {account_name} (leave blank to keep manual control in browser): "
        try:
            otp_value = await asyncio.to_thread(input, prompt)
        except EOFError:
            self.logger.warning(
                "[%s] Interactive OTP input is unavailable in this terminal; waiting for manual browser completion",
                account_name,
            )
            return True
        if otp_value.strip():
            filled = await self._fill_first(
                page,
                self.selectors["otp"],
                otp_value.strip(),
                "otp",
                account_name,
            )
            if filled:
                await self._click_first(
                    page,
                    self.selectors["submit"] + self.selectors["continue"],
                    "otp submit button",
                    account_name,
                    required=False,
                )
        return True

    async def _wait_for_otp_completion(
        self,
        page: Page,
        invite_link: str,
        account_name: str,
    ) -> bool:
        deadline = time.monotonic() + self.config.otp_wait_seconds

        while time.monotonic() < deadline:
            if await self._verify_registration(page, invite_link, account_name):
                return True

            otp_still_visible = await self._has_any_selector(page, self.selectors["otp"], timeout_ms=300)
            if not otp_still_visible:
                form_selectors = self.selectors["email"] + self.selectors["password"] + self.selectors["submit"]
                form_still_visible = await self._has_any_selector(page, form_selectors, timeout_ms=300)
                if not form_still_visible and page.url.rstrip("/") != invite_link.rstrip("/"):
                    return True

            await asyncio.sleep(1)

        return False

    async def _verify_registration(self, page: Page, invite_link: str, account_name: str) -> bool:
        current_url = page.url
        self.logger.info("[%s] Current URL: %s", account_name, current_url)

        if url_looks_successful(
            current_url=current_url,
            invite_link=invite_link,
            success_keywords=self.selectors["success_url_keywords"],
            registration_keywords=self.selectors["registration_url_keywords"],
        ):
            return True

        return await self._has_any_selector(page, self.selectors["success"], timeout_ms=500)


class NativeBrowserRegistrationHandler(RegistrationHandler):
    def __init__(
        self,
        config: RunConfig,
        selectors: dict[str, list[str]],
        logger: logging.Logger,
    ) -> None:
        super().__init__(runtime=None, config=config, selectors=selectors, logger=logger)

    async def _run_attempt(
        self,
        account: RegistrationAccount,
        result: RegistrationResult,
        proxy: Optional[str],
    ) -> None:
        native_session: Optional[NativeChromiumSession] = None
        playwright: Optional[Playwright] = None
        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            browser_path = self.config.browser_executable or discover_native_browser_executable()
            if browser_path is None:
                raise RuntimeError("Could not find Chrome or Edge. Pass --browser-executable explicitly.")

            native_session = NativeChromiumSession(
                executable_path=browser_path,
                logger=self.logger,
                proxy=proxy,
            )
            await native_session.start()
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(native_session.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            context.set_default_timeout(self.config.action_timeout_ms)
            context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
            page = context.pages[0] if context.pages else await context.new_page()

            if self.config.run_mode == "device-auth-only":
                await self._run_device_auth_only(context, account, result, proxy)
                return

            self.logger.info(
                "[%s] Starting flow in native browser (%s)",
                account.account_name,
                proxy if proxy else "direct",
            )
            await self._open_invite_link(page, account)
            await self._dismiss_optional_prompts(page, account.account_name)
            await self._enter_login_flow(page, account.account_name)
            await self._fill_registration_form(page, account)
            await self._submit_form(page, account.account_name)
            await self._resolve_otp_if_present(page, account.account_name)
            await self._complete_post_login_onboarding(page, account)
            await self._resolve_otp_if_present(page, account.account_name)

            otp_required = await self._has_any_selector(page, self.selectors["otp"], timeout_ms=1_000)
            if otp_required:
                result.phases["registration"] = "otp_required"
                self._announce_otp_requirement(account.account_name)
                otp_completed = await self._wait_for_otp_completion(page, account.invite_link, account.account_name)
                if not otp_completed:
                    result.status = "otp_required"
                    result.message = f"OTP timed out for {account.account_name}"
                    result.error_details = "OTP did not complete before timeout"
                    result.timestamp = datetime.now()
                    self.logger.warning("[%s] OTP wait timed out", account.account_name)
                    return

                # Some account flows reveal onboarding only after OTP succeeds.
                await self._complete_post_login_onboarding(page, account)
                await self._resolve_otp_if_present(page, account.account_name)

            registered = await self._verify_registration(page, account.invite_link, account.account_name)
            if not registered:
                result.phases["registration"] = "failed"
                result.status = "failed"
                result.message = f"Could not verify registration for {account.account_name}"
                result.error_details = "No success signal matched the current page state"
                result.timestamp = datetime.now()
                return

            result.phases["registration"] = "completed"

            if self.codex_router is None and not self.codex_device_url:
                result.status = "registered"
                result.message = f"Registered {account.account_name}"
                result.timestamp = datetime.now()
                return

            if self.codex_device_url:
                oauth_completed = await self._complete_direct_codex_device_auth(context, account)
            else:
                oauth_completed = await self._complete_codex_router_device_auth(context, account)
            if oauth_completed:
                result.phases["codex_router_oauth"] = "completed"
                result.status = "completed"
                result.message = f"Registered and authorized {account.account_name}"
            else:
                result.phases["codex_router_oauth"] = "failed"
                result.status = "failed"
                result.message = f"Registered {account.account_name}, but codex-router auth failed"
                result.error_details = "codex-router device auth did not complete successfully"

            result.timestamp = datetime.now()
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            if proxy and looks_like_network_error(exc):
                raise ProxyNetworkError(str(exc)) from exc

            result.status = "failed"
            result.message = f"Registration failed for {account.account_name}"
            result.error_details = str(exc)
            result.timestamp = datetime.now()
            self.logger.error("[%s] Native-browser Playwright error: %s", account.account_name, exc)
        except Exception as exc:
            if proxy and looks_like_network_error(exc):
                raise ProxyNetworkError(str(exc)) from exc

            result.status = "failed"
            result.message = f"Registration failed for {account.account_name}"
            result.error_details = str(exc)
            result.timestamp = datetime.now()
            self.logger.exception("[%s] Unexpected error", account.account_name)
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass
            if native_session:
                await native_session.stop()


class RegistrationOrchestrator:
    def __init__(
        self,
        config: RunConfig,
        selectors: dict[str, list[str]],
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.logger = logger
        if config.flow_mode == "playwright":
            self.runtime: Optional[PlaywrightRuntime] = PlaywrightRuntime(logger)
            self.handler: Any = RegistrationHandler(self.runtime, config, selectors, logger)
        elif config.flow_mode == "native-playwright":
            self.runtime = None
            self.handler = NativeBrowserRegistrationHandler(config, selectors, logger)
        elif config.flow_mode == "browser-use-manual":
            self.runtime = None
            self.handler = BrowserUseManualHandler(config, logger)
        else:
            raise ValueError(f"Unsupported flow mode: {config.flow_mode}")
        self.results: list[RegistrationResult] = []

    async def register_all(self, accounts: list[RegistrationAccount]) -> list[RegistrationResult]:
        if self.runtime is not None:
            await self.runtime.start()

        try:
            for index, account in enumerate(accounts, start=1):
                self.logger.info("-" * 60)
                self.logger.info("Processing account %s/%s: %s", index, len(accounts), account.email)
                self.logger.info("-" * 60)

                try:
                    result = await asyncio.wait_for(
                        self.handler.register_account(account),
                        timeout=self.config.account_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    result = RegistrationResult(
                        account=account,
                        status="failed",
                        message=f"Timed out after {self.config.account_timeout_seconds} seconds",
                        timestamp=datetime.now(),
                        error_details="Account-level timeout",
                        attempted_proxies=[account.proxy],
                        phases={"registration": "failed", "codex_router_oauth": "skipped"},
                    )

                self.results.append(result)

                if index < len(accounts):
                    await asyncio.sleep(1)
        finally:
            if self.runtime is not None:
                await self.runtime.stop()

        return self.results

    def generate_report(self) -> dict[str, Any]:
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_accounts": len(self.results),
            "completed": sum(1 for result in self.results if result.status == "completed"),
            "registered": sum(1 for result in self.results if result.status == "registered"),
            "otp_required": sum(1 for result in self.results if result.status == "otp_required"),
            "failed": sum(1 for result in self.results if result.status == "failed"),
            "results": [result.to_dict() for result in self.results],
        }

        self.config.report_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        self.logger.info("Report saved to %s", self.config.report_path)
        self.logger.info(
            "Summary: total=%s completed=%s registered=%s otp_required=%s failed=%s",
            report["total_accounts"],
            report["completed"],
            report["registered"],
            report["otp_required"],
            report["failed"],
        )
        return report


def setup_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("account_registrar")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def load_selectors(selectors_path: Path) -> dict[str, list[str]]:
    selectors = {key: list(values) for key, values in DEFAULT_SELECTORS.items()}
    if not selectors_path.exists():
        return selectors

    with selectors_path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    for key, value in raw_data.items():
        if key not in selectors:
            raise ValueError(f"Unknown selector key: {key}")
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Selector key '{key}' must be a list of strings")
        selectors[key] = value

    return selectors


def build_proxy_settings(proxy_url: str) -> dict[str, str]:
    parsed = urlsplit(proxy_url)
    if not parsed.scheme or not parsed.hostname or parsed.port is None:
        raise ValueError(f"Invalid proxy URL: {proxy_url}")

    settings = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        settings["username"] = unquote(parsed.username)
    if parsed.password:
        settings["password"] = unquote(parsed.password)
    return settings


def looks_like_network_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker.lower() in message for marker in NETWORK_ERROR_MARKERS)


def url_looks_successful(
    *,
    current_url: str,
    invite_link: str,
    success_keywords: list[str],
    registration_keywords: list[str],
) -> bool:
    current = current_url.lower()
    if any(keyword in current for keyword in success_keywords):
        return True

    changed = current_url.rstrip("/") != invite_link.rstrip("/")
    still_registration = any(keyword in current for keyword in registration_keywords)
    return changed and not still_registration


def get_payload_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def derive_profile_name(account: RegistrationAccount) -> str:
    local_part = account.email.split("@", 1)[0]
    normalized = re.sub(r"[\d._-]+", " ", local_part).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return account.account_name or "User"
    return " ".join(part.capitalize() for part in normalized.split(" "))


def derive_profile_age(account: RegistrationAccount) -> str:
    return "25"


def announce_device_auth(account_name: str, verification_url: str, user_code: str) -> None:
    print()
    print("=" * 60)
    print(f"codex-router device auth for: {account_name}")
    print(f"Verification URL: {verification_url}")
    print(f"User code: {user_code}")
    print("Complete the device auth in the currently opened browser window.")
    print("=" * 60)
    print()


def normalize_proxy_value(raw_value: Optional[str]) -> Optional[str]:
    if raw_value is None:
        return None

    stripped = raw_value.strip()
    if not stripped:
        return None

    if stripped.startswith(("http://", "https://", "socks5://", "socks5h://")):
        return stripped.strip("\"'")

    proxy_match = re.search(
        r'--proxy\s+(?:"(?P<double>[^"]+)"|\'(?P<single>[^\']+)\'|(?P<bare>\S+))',
        stripped,
        flags=re.IGNORECASE,
    )
    if proxy_match:
        extracted = (
            proxy_match.group("double")
            or proxy_match.group("single")
            or proxy_match.group("bare")
        )
        return extracted.strip()

    return stripped


def parse_browser_order(raw_value: str) -> tuple[str, ...]:
    allowed = {"chromium", "msedge", "chrome", "firefox"}
    parsed = tuple(part.strip().lower() for part in raw_value.split(",") if part.strip())
    if not parsed:
        raise ValueError("browser order cannot be empty")

    invalid = [name for name in parsed if name not in allowed]
    if invalid:
        raise ValueError(f"unsupported browser launcher(s): {', '.join(invalid)}")

    return parsed


def reserve_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def wait_for_cdp_endpoint(cdp_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    version_url = f"{cdp_url.rstrip('/')}/json/version"
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(version_url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("webSocketDebuggerUrl"):
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for CDP endpoint at {version_url}: {last_error}")


def discover_native_browser_executable() -> Optional[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")

    candidates = [
        Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe" if local_app_data else None,
        Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe" if program_files else None,
        Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe" if program_files_x86 else None,
        Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe" if local_app_data else None,
        Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe" if program_files else None,
        Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe" if program_files_x86 else None,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def build_manual_browser_proxy_argument(proxy_url: Optional[str]) -> Optional[str]:
    if not proxy_url:
        return None

    parsed = urlsplit(proxy_url)
    if not parsed.scheme or not parsed.hostname or parsed.port is None:
        raise ValueError(f"Invalid proxy URL: {proxy_url}")

    if parsed.username or parsed.password:
        raise ValueError("Authenticated proxies are not supported in browser-use/manual mode")

    return f"--proxy-server={parsed.scheme}://{parsed.hostname}:{parsed.port}"


def build_browser_use_session_name(account: RegistrationAccount) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = re.sub(r"[^a-z0-9-]+", "-", account.account_name.lower()).strip("-") or "account"
    return f"codex-auth-{safe_name}-{timestamp}"


def select_accounts(
    accounts: list[RegistrationAccount],
    *,
    start_at: int = 1,
    limit: Optional[int] = None,
) -> list[RegistrationAccount]:
    if start_at < 1:
        raise ValueError("--start-at must be at least 1")
    start_index = start_at - 1
    selected = accounts[start_index:]
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be at least 1")
        selected = selected[:limit]
    return selected


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Automate invite registration flows with optional codex-lb device auth."
    )
    parser.add_argument("input_csv", type=Path, help="Pipe-delimited CSV file: invite_link|email|password|proxy")
    parser.add_argument("--selectors", type=Path, default=DEFAULT_SELECTORS_PATH, help="Selector JSON file")
    parser.add_argument("--report", type=Path, default=Path("registration_report.json"), help="Output JSON report path")
    parser.add_argument("--log", type=Path, default=Path("registration.log"), help="Output log path")
    parser.add_argument("--headless", action="store_true", help="Run Chromium headless")
    parser.add_argument(
        "--flow-mode",
        choices=["playwright", "native-playwright", "browser-use-manual"],
        default="playwright",
        help="Choose the browser driver. native-playwright uses a fresh real browser and then attaches to it.",
    )
    parser.add_argument(
        "--run-mode",
        choices=["register-and-auth", "device-auth-only"],
        default="register-and-auth",
        help="register-and-auth uses the invite link first; device-auth-only skips registration and opens the codex device page directly.",
    )
    parser.add_argument(
        "--browser-order",
        default="chromium,msedge,chrome,firefox",
        help="Comma-separated browser fallback order",
    )
    parser.add_argument(
        "--profile-strategy",
        choices=["ephemeral", "copy"],
        default="ephemeral",
        help="Use a fresh temporary browser or a copied existing Chromium profile",
    )
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        help="Browser user-data directory to copy when --profile-strategy copy is used",
    )
    parser.add_argument(
        "--browser-executable",
        type=Path,
        help="Chrome or Edge executable path for native-playwright or browser-use-manual mode",
    )
    parser.add_argument(
        "--browser-use-config-dir",
        type=Path,
        default=TOOL_DIR / ".browser-use-config",
        help="Writable browser-use config directory",
    )
    parser.add_argument("--otp-wait-seconds", type=int, default=90, help="Max seconds to wait for OTP completion")
    parser.add_argument("--bridge-dir", type=Path, help="Directory for assistant bridge request/response files")
    parser.add_argument(
        "--bridge-timeout-seconds",
        type=int,
        default=600,
        help="Max seconds to wait for assistant bridge responses",
    )
    parser.add_argument("--account-timeout-seconds", type=int, default=120, help="Max seconds per account")
    parser.add_argument("--action-timeout-ms", type=int, default=12_000, help="Timeout per element/action")
    parser.add_argument("--navigation-timeout-ms", type=int, default=15_000, help="Timeout for navigation")
    parser.add_argument("--codex-router-url", help="Enable the follow-up codex-lb device auth step")
    parser.add_argument(
        "--codex-device-url",
        default="https://auth.openai.com/codex/device",
        help="Direct codex device-auth page to open after registration. Set empty string to disable.",
    )
    parser.add_argument(
        "--device-auth-timeout-seconds",
        type=int,
        default=120,
        help="Max seconds to wait for codex-lb device auth to finish",
    )
    parser.add_argument(
        "--no-retry-without-proxy",
        action="store_true",
        help="Disable the automatic direct-connection retry after proxy/network failures",
    )
    parser.add_argument("--start-at", type=int, default=1, help="1-based input row offset for debugging")
    parser.add_argument("--limit", type=int, help="Only process the first N accounts after --start-at")
    return parser


async def async_main(argv: Optional[list[str]] = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    logger = setup_logger(args.log)

    try:
        selectors = load_selectors(args.selectors)
    except Exception as exc:
        logger.error("Could not load selectors: %s", exc)
        return 1

    accounts = CSVParser.parse_file(args.input_csv, logger)
    if not accounts:
        logger.error("No valid accounts found in %s", args.input_csv)
        return 1

    try:
        accounts = select_accounts(accounts, start_at=args.start_at, limit=args.limit)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    if not accounts:
        logger.error("The selected account range is empty")
        return 1

    config = RunConfig(
        headless=args.headless,
        flow_mode=args.flow_mode,
        run_mode=args.run_mode,
        retry_without_proxy=not args.no_retry_without_proxy,
        browser_order=parse_browser_order(args.browser_order),
        profile_strategy=args.profile_strategy,
        user_data_dir=args.user_data_dir or discover_default_chromium_user_data_dir(),
        browser_executable=args.browser_executable,
        browser_use_config_dir=args.browser_use_config_dir,
        account_timeout_seconds=args.account_timeout_seconds,
        action_timeout_ms=args.action_timeout_ms,
        navigation_timeout_ms=args.navigation_timeout_ms,
        otp_wait_seconds=args.otp_wait_seconds,
        bridge_dir=args.bridge_dir,
        bridge_timeout_seconds=args.bridge_timeout_seconds,
        codex_router_url=args.codex_router_url,
        codex_device_url=args.codex_device_url or None,
        device_auth_timeout_seconds=args.device_auth_timeout_seconds,
        report_path=args.report,
        log_path=args.log,
        selectors_path=args.selectors,
    )

    orchestrator = RegistrationOrchestrator(config, selectors, logger)
    results = await orchestrator.register_all(accounts)
    report = orchestrator.generate_report()

    print()
    print("=" * 60)
    print("REGISTRATION SUMMARY")
    print("=" * 60)
    print(f"Total accounts: {report['total_accounts']}")
    print(f"Completed: {report['completed']}")
    print(f"Registered only: {report['registered']}")
    print(f"OTP required: {report['otp_required']}")
    print(f"Failed: {report['failed']}")
    print("-" * 60)
    for result in results:
        print(f"{result.status.upper():12} {result.account.email} -> {result.message}")
    print("=" * 60)

    return 0 if report["failed"] == 0 and report["otp_required"] == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    try:
        return asyncio.run(async_main(argv))
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 130


def discover_default_chromium_user_data_dir() -> Optional[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None

    candidates = [
        Path(local_app_data) / "Google" / "Chrome" / "User Data" / "Default",
        Path(local_app_data) / "Microsoft" / "Edge" / "User Data" / "Default",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
