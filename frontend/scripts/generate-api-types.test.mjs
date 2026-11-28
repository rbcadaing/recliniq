import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { OUTPUT_PATH, SNAPSHOT_PATH, render, toType } from './generate-api-types.mjs'

describe('toType', () => {
  it('maps primitives, nullables, and arrays', () => {
    expect(toType({ type: 'string', format: 'uuid' })).toBe('string')
    expect(toType({ type: 'integer' })).toBe('number')
    expect(toType({ anyOf: [{ type: 'string' }, { type: 'null' }] })).toBe('string | null')
    expect(toType({ type: ['boolean', 'null'] })).toBe('boolean | null')
    expect(
      toType({ type: 'array', items: { anyOf: [{ type: 'string' }, { type: 'null' }] } }),
    ).toBe('(string | null)[]')
  })

  it('maps enums, consts, and refs', () => {
    expect(toType({ enum: ['a', 'b'] })).toBe('"a" | "b"')
    expect(toType({ const: 'bearer' })).toBe('"bearer"')
    expect(toType({ $ref: '#/components/schemas/Role' })).toBe("components['schemas']['Role']")
  })

  it('marks properties not listed in required as optional', () => {
    const type = toType({
      type: 'object',
      properties: { id: { type: 'string' }, 'x-note': { type: 'string' } },
      required: ['id'],
    })
    expect(type).toBe('{\n  id: string\n  "x-note"?: string\n}')
  })

  it('maps free-form and typed maps', () => {
    expect(toType({ type: 'object' })).toBe('Record<string, unknown>')
    expect(toType({ type: 'object', additionalProperties: { type: 'string' } })).toBe(
      'Record<string, string>',
    )
  })

  it('rejects refs it cannot resolve', () => {
    expect(() => toType({ $ref: 'other.json#/Foo' })).toThrow('Unsupported $ref')
  })
})

describe('render', () => {
  it('sorts schemas so output is deterministic', () => {
    const output = render({
      components: { schemas: { B: { type: 'string' }, A: { type: 'integer' } } },
    })
    expect(output.indexOf('A: number')).toBeLessThan(output.indexOf('B: string'))
  })

  it('matches the committed schema.ts for the committed snapshot', () => {
    const snapshot = JSON.parse(readFileSync(SNAPSHOT_PATH, 'utf8'))
    expect(render(snapshot)).toBe(readFileSync(OUTPUT_PATH, 'utf8'))
  })
})
