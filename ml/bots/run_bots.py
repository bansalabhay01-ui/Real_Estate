"""Real Playwright bots, for testing LeadOps and for the live attack demo.

    backend\\.venv\\Scripts\\python ml/bots/run_bots.py --api http://localhost:8000          # all three bots, headless
    backend\\.venv\\Scripts\\python ml/bots/run_bots.py --kind stealth --headed             # watch the stealth bot work
    backend\\.venv\\Scripts\\python ml/bots/run_bots.py --kind naive --count 5 --api http://localhost:8000

(Mac/Linux: backend/.venv/bin/python.) The site must be running (npm run dev) with its backend.

Bots:
  naive    fills in every field, the hidden honeypot too, and submits in under a second
  stealth  hides navigator.webdriver, uses a normal browser's user agent, moves the mouse, scrolls, types with pauses
           and skips the hidden field: only its behaviour gives it away
  scraper  opens every listing in a few seconds and copies the prices

Every run opens the site through a lo_test=bot tester link, so its visits join the real test set (ml/train.py).
They drive the Edge or Chrome already installed; elsewhere run `python -m playwright install chromium` once.
With --api, each bot prints the label LeadOps gave it.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
LISTING_LINKS = "a[href^='/property/']"
HIDE_WEBDRIVER = "Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false });"


def tester_link(site: str, kind: str) -> str:
    return f"{site}/?lo_test=bot&lo_tester=bot-{kind}"


def pause(rng: random.Random, low: float, high: float) -> None:
    time.sleep(rng.uniform(low, high))


def launch(playwright, browser: str, *, headed: bool, slow_mo: int, stealth: bool):
    """Edge, then Chrome, then Playwright's own Chromium (needs `python -m playwright install chromium`)."""
    args = ["--disable-blink-features=AutomationControlled"] if stealth else []
    channels = ["msedge", "chrome", None] if browser == "auto" else [None if browser == "chromium" else browser]
    problem = None
    for channel in channels:
        try:
            return playwright.chromium.launch(channel=channel, headless=not headed, slow_mo=slow_mo, args=args)
        except PlaywrightError as error:
            problem = error
    raise SystemExit(f"Couldn't start a browser: {problem}\nInstall Edge or Chrome, or run: python -m playwright install chromium")


def wander(page, rng: random.Random, moves: int) -> None:
    """Scripted mouse moves: straight lines in a few big steps, which is what gives a stealth bot away."""
    width, height = page.viewport_size["width"], page.viewport_size["height"]
    for _ in range(moves):
        page.mouse.move(rng.randint(50, width - 50), rng.randint(80, height - 80), steps=rng.randint(5, 12))
        pause(rng, 0.2, 0.6)


def open_listing(page, rng: random.Random, *, by_mouse: bool) -> None:
    links = page.locator(LISTING_LINKS)
    link = links.nth(rng.randrange(links.count()))
    link.scroll_into_view_if_needed()
    if by_mouse:
        box = link.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=rng.randint(6, 12))
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    else:
        link.click()
    page.wait_for_url("**/property/**")
    page.wait_for_selector("h1")


def naive_bot(page, site: str, rng: random.Random) -> str:
    page.goto(tester_link(site, "naive"))
    page.wait_for_selector(LISTING_LINKS)
    href = page.locator(LISTING_LINKS).first.get_attribute("href")
    page.goto(site + href)
    page.wait_for_selector("form")
    fields = [
        ("input[autocomplete=name]", "test"),
        ("input[type=tel]", "9999999999"),
        ("input[type=email]", "test@test.com"),
        ("form textarea", "Best SEO services for your site. Visit http://promo.example"),
        ("input[name=website]", "http://promo.example"),  # the hidden honeypot: a dumb bot fills every field
    ]
    for selector, value in fields:
        page.locator(selector).first.fill(value, force=True)
    page.locator("form input[type=checkbox]").check(force=True)
    page.get_by_role("button", name="Send enquiry").click()
    page.wait_for_selector("text=Enquiry sent", timeout=10_000)
    return f"sent a junk enquiry about {href.rsplit('/', 1)[-1]}"


def stealth_bot(page, site: str, rng: random.Random) -> str:
    page.goto(tester_link(site, "stealth"))
    page.wait_for_selector(LISTING_LINKS)
    wander(page, rng, 3)
    page.mouse.wheel(0, rng.randint(400, 900))
    pause(rng, 1.0, 2.0)
    for _ in range(2):  # look at two homes like a person would, then go back
        open_listing(page, rng, by_mouse=True)
        for _ in range(3):
            page.mouse.wheel(0, rng.randint(250, 600))
            wander(page, rng, 2)
            pause(rng, 1.0, 2.5)
        page.go_back()
        page.wait_for_selector(LISTING_LINKS)
        pause(rng, 0.8, 1.6)
    open_listing(page, rng, by_mouse=True)
    page.locator("#enquiry").scroll_into_view_if_needed()
    wander(page, rng, 2)
    for label, text in (("Your name", "Rahul Verma"), ("Mobile number", "9812345670"), ("Email (optional)", "rahul.verma81@gmail.com")):
        field = page.get_by_label(label)
        field.click()
        field.press_sequentially(text, delay=rng.randint(60, 140))  # real key presses, at a steady machine rhythm
        pause(rng, 0.3, 0.8)
    page.locator("form input[type=checkbox]").click()  # the honeypot stays empty: this bot skips hidden fields
    page.get_by_role("button", name="Send enquiry").click()
    page.wait_for_selector("text=Enquiry sent", timeout=10_000)
    return "browsed 3 homes and sent a believable enquiry"


def scraper_bot(page, site: str, rng: random.Random) -> str:
    page.goto(tester_link(site, "scraper"))
    page.wait_for_selector(LISTING_LINKS)
    hrefs = page.eval_on_selector_all(LISTING_LINKS, "links => [...new Set(links.map(a => a.getAttribute('href')))]")
    prices = {}
    for href in hrefs:
        page.goto(site + href)
        page.wait_for_selector("h1")
        prices[href] = page.locator("p.tabular").first.inner_text()
    return f"copied {len(prices)} prices"


BOTS = {"naive": naive_bot, "stealth": stealth_bot, "scraper": scraper_bot}


def label_from(api: str, visitor_id: str) -> str:
    try:
        with urllib.request.urlopen(f"{api}/visitors/{visitor_id}", timeout=10) as response:
            visitor = json.loads(response.read())["visitor"]
    except (urllib.error.URLError, TimeoutError, KeyError) as error:
        return f"(couldn't read its label: {error})"
    score = visitor.get("score") or {}
    reasons = "; ".join(score.get("reasons", [])[:2])
    return f"{visitor.get('label') or 'not scored'}" + (f": {reasons}" if reasons else "")


def run_one(playwright, kind: str, number: int, args, rng: random.Random) -> None:
    stealth = kind == "stealth"
    browser = launch(playwright, args.browser, headed=args.headed, slow_mo=args.slow_mo, stealth=stealth)
    try:
        options = {"viewport": {"width": 1366, "height": 768}}
        if stealth:  # look like an ordinary Indian desktop browser
            options.update(user_agent=DESKTOP_UA, locale="en-IN", timezone_id="Asia/Kolkata")
        context = browser.new_context(**options)
        if stealth:
            context.add_init_script(HIDE_WEBDRIVER)
        page = context.new_page()
        started = time.time()
        what = BOTS[kind](page, args.site, rng)
        page.evaluate("window.LeadOps && window.LeadOps.flush()")
        page.wait_for_timeout(1500)  # let the last events reach the backend
        visitor_id = page.evaluate("window.LeadOps ? window.LeadOps.ids().visitor_id : null")
        line = f"{kind} #{number}: {what} in {time.time() - started:.0f} s"
        if visitor_id:
            line += f", visitor {visitor_id[:8]}"
            if args.api:
                time.sleep(1)
                line += f" -> {label_from(args.api, visitor_id)}"
        else:
            line += " (the tracking script didn't load: is the backend running?)"
        print(line, flush=True)
    finally:
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Playwright bots against the LeadOps demo site.")
    parser.add_argument("--site", default="http://localhost:5173", help="the demo site")
    parser.add_argument("--api", help="the backend, to print each bot's label, e.g. http://localhost:8000")
    parser.add_argument("--kind", choices=[*BOTS, "all"], default="all")
    parser.add_argument("--count", type=int, default=1, help="runs of each bot")
    parser.add_argument("--headed", action="store_true", help="show the browser (for the live demo)")
    parser.add_argument("--slow-mo", type=int, default=0, help="milliseconds between actions, to watch them")
    parser.add_argument("--browser", choices=["auto", "msedge", "chrome", "chromium"], default="auto")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    args.site = args.site.rstrip("/")
    if args.api:  # Windows: "localhost" costs ~2 s per request from Python (IPv6 first)
        args.api = args.api.rstrip("/").replace("://localhost", "://127.0.0.1")

    rng = random.Random(args.seed)
    kinds = list(BOTS) if args.kind == "all" else [args.kind]
    with sync_playwright() as playwright:
        for kind in kinds:
            for number in range(1, args.count + 1):
                try:
                    run_one(playwright, kind, number, args, rng)
                except PlaywrightError as error:
                    print(f"{kind} #{number} failed: {error.message.splitlines()[0]}. Is the site running at {args.site}?",
                          file=sys.stderr)
                    return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
