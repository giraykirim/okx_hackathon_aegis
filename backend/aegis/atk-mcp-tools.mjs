import Ajv from 'ajv';

// Names confirmed by real tools/list; schemas and read-only annotations checked every session.
export function validatePublicTool(catalog, request) {
  const names = ['market_get_ticker', 'market_get_instruments'];
  if (!names.includes(request.name) || catalog.nextCursor) throw new Error('Unsupported public tool catalog');
  const tool = catalog.tools.find(tool => tool.name === request.name);
  if (!tool || tool.annotations?.readOnlyHint !== true || tool.annotations?.destructiveHint !== false) {
    throw new Error('Required discovered read-only tool unavailable');
  }
  const validate = new Ajv({ strict: false }).compile(tool.inputSchema);
  if (!validate(request.arguments)) throw new Error('Discovered input schema rejected arguments');
}
