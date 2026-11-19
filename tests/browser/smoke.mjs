#!/usr/bin/env node
// Browser smoke test for the guide. Optional: it needs Playwright with Chromium, which the
// project does not depend on. Without it this prints a notice and exits 0.
//
//   make test-ui                         uses a Playwright that Node can resolve
//   CLIMB_PLAYWRIGHT=/path/to/node_modules/playwright make test-ui
//
// Everything runs against a disposable home, a free loopback port, a synthetic Claude CLI and
// synthetic brew/gh/open. No account, provider, installer or project of yours is touched.
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

async function loadPlaywright() {
  const wanted = process.env.CLIMB_PLAYWRIGHT;
  try {
    if (wanted) return createRequire(import.meta.url)(wanted);
    return await import("playwright");
  } catch { return null; }
}
const playwright = await loadPlaywright();
if (!playwright?.chromium) {
  console.log("Browser smoke test skipped: Playwright is not installed. Set CLIMB_PLAYWRIGHT to a playwright module folder to run it.");
  process.exit(0);
}
if (process.platform !== "darwin") {
  console.log("Browser smoke test skipped: the in-guide terminal it exercises needs macOS.");
  process.exit(0);
}

const temp = fs.mkdtempSync(path.join(os.tmpdir(), "climb-ui-"));
const dir = (name) => { const p = path.join(temp, name); fs.mkdirSync(p, { recursive: true }); return p; };
const bin = dir("bin"), home = dir("home"), state = dir("state"), projects = dir("projects");
const tool = (name, body) => fs.writeFileSync(path.join(bin, name), "#!/bin/sh\n" + body + "\n", { mode: 0o700 });
const ghSource = path.join(temp, "gh-after-install");
fs.writeFileSync(ghSource, '#!/bin/sh\n[ "$1" = "--version" ] && { echo "gh version 0.0.0 (fixture)"; exit 0; }\nexit 1\n', { mode: 0o700 });
tool("open", "exit 0");
tool("xcode-select", "exit 0");
tool("brew", `echo "brew $*" >> "${path.join(temp, "ran.log")}"
[ "$1" = "--version" ] && { echo "Homebrew 0.0.0 (fixture)"; exit 0; }
if [ "$1" = "install" ]; then echo "==> Fetching fixture"; sleep 1; cp "${ghSource}" "${path.join(bin, "gh")}"; echo "==> Summary: installed"; exit 0; fi
exit 0`);
const fakeClaude = path.join(temp, "fake-claude");
fs.copyFileSync(path.join(ROOT, "tests", "fixtures", "fake_claude.py"), fakeClaude); fs.chmodSync(fakeClaude, 0o700);
const calls = path.join(temp, "calls.jsonl"); fs.writeFileSync(calls, "");

const port = await new Promise((resolve) => { const s = net.createServer(); s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => resolve(p)); }); });
const base = "http://localhost:" + port;
const backend = spawn(process.execPath, [path.join(ROOT, "climb-agent.mjs"), "--no-open"], {
  cwd: temp, stdio: "ignore",
  env: { PATH: [bin, path.dirname(process.execPath), "/usr/bin", "/bin", "/usr/sbin", "/sbin"].join(":"), HOME: home, CLIMB_PORT: String(port),
    CLIMB_CLAUDE_BIN: fakeClaude, CLIMB_STATE_DIR: state, CLIMB_WORKDIR: projects, CLIMB_OLLAMA_PORT: "1", CLIMB_FEEDBACK_REPO: "owner/project", FIXTURE_CALLS: calls, FIXTURE_AUTH: "signed-in" }
});

const results = [];
const check = (name, ok, detail = "") => { results.push(ok); console.log((ok ? "ok   " : "FAIL ") + name + (ok || !detail ? "" : " — " + detail)); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let browser;
try {
  for (let i = 0; i < 80; i++) {
    try { const r = await fetch(base + "/api/health", { method: "POST", headers: { "Content-Type": "application/json", "X-Climb": "1" }, body: "{}" }); if (r.ok) break; } catch {}
    await sleep(100);
  }
  browser = await playwright.chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [], realInstalls = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // A guard, not a fixture: a real installer command must never reach the shell from a test.
  await page.route("**/api/terminal", async (route) => {
    const body = route.request().postDataJSON() || {};
    if (body.op === "write" && /Homebrew\/install|githubusercontent|xcode-select --install/.test(body.data || "")) { realInstalls.push(body.data); return route.fulfill({ json: { ok: true } }); }
    return route.continue();
  });
  const text = (selector) => page.evaluate((s) => document.querySelector(s)?.innerText || "", selector);
  const fits = () => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

  // 1. A new person learns what this is and has one thing to press.
  await page.goto(base + "/#start"); await page.waitForSelector("main h1");
  const first = await text("main");
  check("first screen says what the guide is", /sets up this laptop/i.test(first) && /What happens, in order/i.test(first));
  check("first screen has one primary action", await page.locator("main a.btn").count() === 1, "primary links: " + await page.locator("main a.btn").count());

  // 2. The interview reaches the brief by keyboard-reachable controls.
  await page.click("main a.btn");
  await sleep(400);
  for (let step = 0; step < 30 && (await page.evaluate(() => location.hash)) === "#interview"; step++) {
    const question = await text("main h1, main h2");
    const field = page.locator("main input:not([type=checkbox]):not([type=radio]), main textarea").first();
    if (await field.count()) { await field.click(); await field.pressSequentially("Sam"); }
    else await page.locator("main button").first().click();
    // A single choice moves on by itself; only press Continue when this question is still showing.
    const onward = page.locator("main button", { hasText: /^(Continue|Finish)/ });
    if ((await text("main h1, main h2")) === question && await onward.count()) await onward.first().click();
    // Wait for the next question (or the brief) and let it settle before acting again.
    await page.waitForFunction((before) => location.hash !== "#interview" || (document.querySelector("main h1, main h2")?.innerText || "") !== before, question, { timeout: 5000 }).catch(() => {});
    await sleep(400);
  }
  await page.waitForFunction(() => /path/i.test(document.querySelector("main h1")?.innerText || ""), null, { timeout: 5000 }).catch(() => {});
  check("interview ends on the brief", (await page.evaluate(() => location.hash)) === "#brief", await page.evaluate(() => location.hash));
  check("brief names the person", /Sam/.test(await text("main h1")), await text("main h1"));

  // 3. A partial answer in the first lesson shows its consequence.
  await page.goto(base + "/#idea/section-climb-one-step"); await page.waitForSelector(".hill-practice");
  await page.click("text=Add a landmark"); await sleep(1100);
  check("partial answer reports who did not arrive", /1 of 3 arrived/.test(await text(".hill-result")));
  check("partial answer is not marked correct", await page.evaluate(() => document.querySelector('.scene-choice[aria-pressed="true"]')?.dataset.outcome) === "some");

  // 4. Setup runs in a real terminal: the button types the command, the step notices it finished, typing works.
  await page.goto(base + "/#laptop/step-tools"); await page.waitForSelector('[data-live="setup"]');
  await page.waitForFunction(() => /Install/.test(document.querySelector("#setup-go")?.innerText || ""), null, { timeout: 15000 });
  await page.click("#setup-go");
  await page.waitForFunction(() => /Ready/.test(document.querySelector("#setup-go")?.innerText || ""), null, { timeout: 40000 }).catch(() => {});
  check("install button reaches Ready by itself", /Ready/.test(await text("#setup-go")), await text("#setup-go"));
  check("install output appears in the terminal", /Summary: installed/.test(await text('[data-live="setup"]')));
  await page.click('[data-live="setup"]'); await page.keyboard.type("echo smoke-$((40+2))"); await page.keyboard.press("Enter");
  await page.waitForFunction(() => /smoke-42/.test(document.querySelector('[data-live="setup"]')?.innerText || ""), null, { timeout: 8000 }).catch(() => {});
  check("typing in the terminal runs a command", /smoke-42/.test(await text('[data-live="setup"]')));
  const ran = fs.existsSync(path.join(temp, "ran.log")) ? fs.readFileSync(path.join(temp, "ran.log"), "utf8") : "";
  check("exactly one install was started", (ran.match(/^brew install /gm) || []).length === 1, ran.trim().split("\n").join(" | "));
  await page.locator("main button", { hasText: "Close terminal" }).click(); await sleep(400);

  // 5. Suggestions can go to GitHub as an issue the person submits, with copying kept as the other way.
  await page.goto(base + "/#feedback"); await page.waitForSelector(".feedback textarea");
  const opened = [];
  await page.exposeFunction("recordOpen", (url) => opened.push(url));
  await page.evaluate(() => { window.open = (url) => { window.recordOpen(String(url)); return null; }; });
  await page.locator("main button", { hasText: "Open a GitHub issue" }).click(); await sleep(300);
  check("feedback opens a prefilled issue on the configured repository", opened.length === 1 && opened[0].startsWith("https://github.com/owner/project/issues/new?"), opened.join(" | "));
  check("the issue text does not carry the person's name", opened.length === 1 && !/Sam/.test(decodeURIComponent(opened[0])));
  check("copying the text stays available", await page.locator("main button", { hasText: "Copy the text" }).count() === 1);

  // 6. Narrow screens do not scroll sideways.
  await page.setViewportSize({ width: 390, height: 844 });
  for (const hash of ["#start", "#laptop/step-tools", "#first", "#feedback"]) { await page.goto(base + "/" + hash); await sleep(700); check("no sideways scroll at 390 on " + hash, await fits()); }
  await page.locator("main button", { hasText: "Close terminal" }).click().catch(() => {});

  // 7. The file copy says what it is and shows no pretend terminal.
  const file = await context.newPage();
  file.on("pageerror", (e) => errors.push("file copy: " + e.message));
  await file.goto(pathToFileURL(path.join(ROOT, "the-climb.html")).href + "#laptop/step-tools"); await sleep(900);
  const fileText = await file.evaluate(() => document.querySelector("main").innerText);
  check("file copy explains that it cannot run commands", /file copy/i.test(fileText));
  check("file copy shows no terminal", await file.locator(".pty-window").count() === 0);

  check("no real installer command reached the shell", realInstalls.length === 0, realInstalls.join(" | "));
  check("no page errors", errors.length === 0, errors.join(" | "));
} catch (error) {
  check("smoke test ran to the end", false, error.message.split("\n")[0]);
} finally {
  if (browser) await browser.close();
  backend.kill("SIGTERM");
  await sleep(300);
  fs.rmSync(temp, { recursive: true, force: true });
}
const failed = results.filter((ok) => !ok).length;
console.log(failed ? `\n${failed} of ${results.length} browser checks failed.` : `\nAll ${results.length} browser checks passed.`);
process.exit(failed ? 1 : 0);
