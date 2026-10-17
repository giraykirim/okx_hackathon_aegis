import test from 'node:test';
import assert from 'node:assert/strict';
import { validatePublicTool } from '../aegis/atk-mcp-tools.mjs';

const request = { name: 'market_get_ticker', arguments: { instId: 'BTC-USDT', demo: false } };
const tool = {
  name: request.name,
  inputSchema: { type: 'object', required: ['instId'], properties: { instId: { type: 'string' }, demo: { type: 'boolean' } } },
  annotations: { readOnlyHint: true, destructiveHint: false },
};
test('actual discovered input schema accepts public ticker arguments', () => {
  assert.doesNotThrow(() => validatePublicTool({ tools: [tool] }, request));
});
test('missing, writable, destructive and private tools are rejected before calling', () => {
  for (const annotations of [{}, { readOnlyHint: false }, { readOnlyHint: true, destructiveHint: true }]) {
    assert.throws(() => validatePublicTool({ tools: [{ ...tool, annotations }] }, request));
  }
  assert.throws(() => validatePublicTool({ tools: [] }, request));
  assert.throws(() => validatePublicTool({ tools: [tool] }, { name: 'spot_place_order', arguments: {} }));
});
test('changed schema and incomplete paginated discovery fail closed', () => {
  assert.throws(() => validatePublicTool({ tools: [tool] }, { ...request, arguments: { instId: null } }));
  assert.throws(() => validatePublicTool({ tools: [tool], nextCursor: 'more' }, request));
});
