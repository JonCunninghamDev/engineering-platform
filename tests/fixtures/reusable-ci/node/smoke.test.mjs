import test from 'node:test';
import assert from 'node:assert/strict';

test('node capability is available', () => {
  assert.equal(typeof process.version, 'string');
  assert.match(process.version, /^v\d+/);
});
