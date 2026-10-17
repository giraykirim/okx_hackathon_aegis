// A real MCP stdio client, not an exchange REST adapter. Public tools only.
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { validatePublicTool } from './atk-mcp-tools.mjs';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';

const [operation, site] = process.argv.slice(2);
const requests = {
  ticker: { name: 'market_get_ticker', arguments: { instId: 'BTC-USDT', demo: false } },
  instruments: { name: 'market_get_instruments', arguments: { instType: 'SPOT', instId: 'BTC-USDT', demo: false } },
};
if (!Object.hasOwn(requests, operation) || !['tr', 'global', 'eea', 'us'].includes(site)) {
  throw new Error('Public operation/site not allowlisted');
}
const serverArgs = [
  '--import', fileURLToPath(new URL('./atk-isolation.mjs', import.meta.url)),
  fileURLToPath(new URL('../node_modules/@okx_ai/okx-trade-mcp/dist/index.js', import.meta.url)),
  '--modules', 'market', '--read-only', '--site', site, '--demo',
];
const transport = new StdioClientTransport({
  command: process.execPath, args: serverArgs, env: process.env,
  stderr: 'pipe', maxBufferSize: 2_000_000,
});
transport.stderr?.resume(); // Drain without logging arbitrary provider text.
const client = new Client({ name: 'aegis-backend', version: '1.0.0' });
const output = { server_args: serverArgs };
let current;
try {
  await client.connect(transport, { timeout: 4000 });
  current = { request_ts: new Date().toISOString() };
  let started = performance.now();
  output.discovery = current;
  try {
    current.result = await client.listTools({}, { timeout: 4000 });
  } finally {
    current.latency_ms = performance.now() - started;
  }
  const request = requests[operation];
  validatePublicTool(current.result, request);
  current = { request_ts: new Date().toISOString() };
  output.call = current;
  started = performance.now();
  try {
    current.result = await client.callTool(request, undefined, { timeout: 10000 });
  } finally {
    current.latency_ms = performance.now() - started;
  }
} catch {
  output.failed = true; // Never serialize raw exceptions, stderr or private configuration.
} finally {
  await client.close();
}
process.stdout.write(JSON.stringify(output));
