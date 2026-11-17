// OmniRoute management API from the server itself (loopback only), using OmniRoute's own CLI machine token
// (HMAC(machine-id, salt) in the x-omniroute-cli-token header; accepted only from 127.0.0.1).
//   node tools/omni.mjs GET /api/combos
//   node tools/omni.mjs POST /api/combos '{"name": ...}'      (body may also be @file.json)
import fs from "node:fs";
import { getCliToken } from "/home/ubuntu/.npm-global/lib/node_modules/omniroute/bin/cli/utils/cliToken.mjs";
const [method = "GET", path = "/api/combos", body] = process.argv.slice(2);
const data = body && body.startsWith("@") ? fs.readFileSync(body.slice(1), "utf8") : body;
const r = await fetch("http://127.0.0.1:20128" + path, {
  method, redirect: "error", body: data || undefined,
  headers: { "x-omniroute-cli-token": await getCliToken(), "content-type": "application/json" },
});
const text = await r.text();
process.stdout.write(JSON.stringify({ status: r.status, body: (() => { try { return JSON.parse(text); } catch { return text; } })() }));
process.exitCode = r.ok ? 0 : 1;
