from __future__ import annotations

import socket
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path

import pytest
import uvicorn

from review_panel.app import create_app
from test_review_api import make_repo, packet, write_packet


@contextmanager
def live_server(repo: Path):
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(repo),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_for_port(port)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_port(port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"Server did not start on port {port}")


def test_browser_can_batch_approve_and_submit_review(tmp_path: Path):
    pytest.importorskip("selenium")
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver import Chrome, ChromeOptions, Edge, EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as ec
    from selenium.webdriver.support.ui import WebDriverWait

    repo = make_repo(tmp_path)
    write_packet(repo, packet())

    driver = None
    errors: list[str] = []

    edge_options = EdgeOptions()
    add_browser_options(edge_options)
    for edge_binary in (
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
    ):
        if edge_binary.exists():
            edge_options.binary_location = str(edge_binary)
            break
    try:
        driver = Edge(options=edge_options)
    except WebDriverException as exc:
        errors.append(f"Edge: {exc}")

    options = ChromeOptions()
    add_browser_options(options)
    if driver is None:
        try:
            driver = Chrome(options=options)
        except WebDriverException as exc:
            errors.append(f"Chrome: {exc}")

    if driver is None:
        pytest.skip(f"Selenium browser driver unavailable: {' | '.join(errors)}")

    with driver:
        with live_server(repo) as base_url:
            wait = WebDriverWait(driver, 10)
            driver.get(base_url)
            wait.until(ec.text_to_be_present_in_element((By.CSS_SELECTOR, ".review-item-title"), "sdtm_spec_ae_v1_001"))
            driver.find_element(By.CSS_SELECTOR, "#reviewer-input").send_keys("Lead Programmer")
            driver.find_element(By.CSS_SELECTOR, "#approve-all-button").click()
            driver.switch_to.alert.accept()
            try:
                submit = wait.until(enabled_element(By.CSS_SELECTOR, "#submit-button"))
            except TimeoutException as exc:
                diagnostics = driver.execute_script(
                    """
                    return {
                      reviewer: document.querySelector('#reviewer-input')?.value,
                      status: document.querySelector('#submit-status')?.textContent,
                      disabled: document.querySelector('#submit-button')?.disabled,
                      checkedApproved: document.querySelectorAll("input[value='approved']:checked").length
                    };
                    """
                )
                driver.save_screenshot(str(tmp_path / "review-panel-debug.png"))
                raise AssertionError(diagnostics) from exc
            submit.click()
            driver.switch_to.alert.accept()
            wait.until(ec.text_to_be_present_in_element((By.CSS_SELECTOR, "#submit-status"), "waiting for Runtime confirmation"))
            driver.save_screenshot(str(tmp_path / "review-panel-browser-flow.png"))


def add_browser_options(options):
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,900")


def enabled_element(by: str, selector: str):
    def _predicate(driver):
        element = driver.find_element(by, selector)
        return element if element.is_enabled() else False

    return _predicate
