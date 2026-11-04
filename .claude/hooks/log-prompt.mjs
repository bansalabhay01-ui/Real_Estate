// LeadOps prompt logger
//
// Claude Code runs this script every time someone sends a prompt in this
// project (a UserPromptSubmit hook, switched on in .claude/settings.json).
// It adds the prompt to PROMPTS.md in the project root, with the date, time
// and the sender's git name. Anything that looks like a key, token or
// password is masked first.
//
// It prints nothing on success, because whatever a UserPromptSubmit hook
// prints is added to Claude's context. On failure it exits with code 1,
// which Claude Code reports without blocking the prompt.

import { appendFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { userInfo } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// This file lives in <project>/.claude/hooks/, so the project root is two levels up.
const projectRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const logFile = join(projectRoot, "PROMPTS.md");

// [pattern, replacement]. Order matters: specific key formats before generic ones.
const SECRET_PATTERNS = [
  [/\bsk-ant-[A-Za-z0-9_-]{8,}/g, "sk-ant-****"], // Anthropic
  [/\bsk-[A-Za-z0-9_-]{20,}/g, "sk-****"], // OpenAI-style
  [/\bAIza[0-9A-Za-z_-]{30,}/g, "AIza****"], // Google / Gemini
  [/\bgsk_[A-Za-z0-9]{20,}/g, "gsk_****"], // Groq
  [/\bhf_[A-Za-z0-9]{20,}/g, "hf_****"], // Hugging Face
  [/\bgh[pousr]_[A-Za-z0-9]{20,}/g, "gh*_****"], // GitHub tokens
  [/\bgithub_pat_[A-Za-z0-9_]{20,}/g, "github_pat_****"],
  [/\bAKIA[0-9A-Z]{16}\b/g, "AKIA****"], // AWS access key ID
  [/\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g, "eyJ****"], // JWTs (e.g. Supabase keys)
  [/\b([A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*\s*[=:]\s*)\S+/g, "$1****"], // API_KEY=value
  [/\b(password\s*[=:]\s*)\S+/gi, "$1****"], // password: value
  [/(\b[a-z][a-z0-9+.-]*:\/\/[^\s:@/]+:)[^\s@/]+@/gi, "$1****@"], // scheme://user:password@host
];

const mask = (text) => SECRET_PATTERNS.reduce((out, [re, sub]) => out.replace(re, sub), text);

function authorName() {
  try {
    const name = execFileSync("git", ["config", "user.name"], {
      cwd: projectRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 3000,
    }).trim();
    if (name) return name;
  } catch {
    // git missing or no name configured: fall back to the OS user name
  }
  return userInfo().username;
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const prompt = String(input.prompt ?? "").trim();
  if (!prompt) return;

  // Quote every line so Markdown inside the prompt can't break the log's layout.
  const quoted = mask(prompt)
    .split(/\r?\n/)
    .map((line) => (line ? `> ${line}` : ">"))
    .join("\n");

  const header = existsSync(logFile) ? "" : "# Prompt Log\n";
  appendFileSync(logFile, `${header}\n### ${timestamp()} · ${authorName()}\n\n${quoted}\n`, "utf8");
}

main().then(
  () => process.exit(0),
  (err) => {
    process.stderr.write(`log-prompt hook: ${err?.message ?? err}\n`);
    process.exit(1);
  },
);
