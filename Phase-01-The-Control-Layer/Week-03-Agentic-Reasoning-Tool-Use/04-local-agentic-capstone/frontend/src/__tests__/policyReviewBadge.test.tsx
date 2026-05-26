/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'
import OutputDisplay from '../components/outputDisplay/OutputDisplay'

expect.extend(matchers as any)

describe('policy review badge', () => {
  it('renders policy status when a review is available', () => {
    render(
      <OutputDisplay
        streamingText="Final approved response."
        completedResponse={{ intent: 'simple', metadata: { total_duration: 1, usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2, interaction_price: 0.001 } }}}
        error={null}
        isStreaming={false}
        policyReview={{ attempts: 2, policy_compliant: true, reviews: [] }}
      />
    )

    expect(screen.getByText(/policy review/i)).toBeInTheDocument()
    expect(screen.getByText(/passed after 2 passes/i)).toBeInTheDocument()
  })
})