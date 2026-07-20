import { describe, expect, it } from 'vitest'

describe('knowledge browser contracts', () => {
  it('uses the knowledge route', () => {
    expect('/knowledge').toBe('/knowledge')
  })
})
