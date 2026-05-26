import React from 'react'
import '../styles.css'

interface Metadata {
  total_duration: number;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    interaction_price: number;
  };
}

interface OutputDisplayProps {
  streamingText: string;
  completedResponse: any | null;
  error: string | null;
  isStreaming: boolean;
  policyReview?: {
    attempts?: number
    policy_compliant?: boolean
    reviews?: Array<{
      attempt?: number
      compliant?: boolean
      score?: number
      issues?: string[]
      correction_instructions?: string
    }>
  } | null;
}

const OutputDisplay: React.FC<OutputDisplayProps> = ({ 
  streamingText, 
  completedResponse, 
  error,
  isStreaming,
  policyReview
}) => {
  if (error) {
    return (
      <div className="output-container error">
        <h3>Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!streamingText && !completedResponse) {
    return (
      <div className="output-container placeholder">
        <p>Response will appear here...</p>
      </div>
    );
  }

  return (
    <div className="output-container">
      <div className="streaming-response">
        <h3>Response</h3>
        <div className="response-text">
          {streamingText}
          {isStreaming && <span className="cursor">▌</span>}
        </div>
      </div>

      {completedResponse && (
        <div className="completed-response">
          {policyReview && (
            <div className={`policy-review ${policyReview.policy_compliant ? 'policy-pass' : 'policy-warn'}`}>
              <span className="label">Policy review:</span>
              <span className="value">
                {policyReview.policy_compliant ? 'passed' : 'needs correction'}
                {typeof policyReview.attempts === 'number' ? ` after ${policyReview.attempts} pass${policyReview.attempts === 1 ? '' : 'es'}` : ''}
              </span>
            </div>
          )}

          <div className="intent-badge">
            Intent: <span className={`intent-${completedResponse.intent}`}>
              {completedResponse.intent.toUpperCase()}
            </span>
          </div>

          <div className="metadata-section">
            <h4>Metadata</h4>
            <div className="metadata-grid">
              <div className="metadata-item">
                <span className="label">Duration:</span>
                <span className="value">
                  {completedResponse.metadata.total_duration.toFixed(2)}s
                </span>
              </div>
              <div className="metadata-item">
                <span className="label">Prompt Tokens:</span>
                <span className="value">
                  {completedResponse.metadata.usage.prompt_tokens}
                </span>
              </div>
              <div className="metadata-item">
                <span className="label">Completion Tokens:</span>
                <span className="value">
                  {completedResponse.metadata.usage.completion_tokens}
                </span>
              </div>
              <div className="metadata-item">
                <span className="label">Total Tokens:</span>
                <span className="value">
                  {completedResponse.metadata.usage.total_tokens}
                </span>
              </div>
              <div className="metadata-item">
                <span className="label">Cost:</span>
                <span className="value">
                  ${completedResponse.metadata.usage.interaction_price.toFixed(6)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OutputDisplay
