import React, { useState } from 'react'
import '../styles.css'

interface InputFormProps {
  onSubmit: (emailText: string) => void;
  isLoading: boolean;
}

const InputForm: React.FC<InputFormProps> = ({ onSubmit, isLoading }) => {
  const [emailText, setEmailText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (emailText.trim()) {
      onSubmit(emailText);
      setEmailText('');
    }
  };

  return (
    <div className="input-form-container">
      <h2>Support Ticket Handler</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          value={emailText}
          onChange={(e) => setEmailText(e.target.value)}
          placeholder="Enter your support email text here..."
          disabled={isLoading}
          rows={6}
          className="email-textarea"
        />
        <button 
          type="submit" 
          disabled={isLoading || !emailText.trim()}
          className="submit-button"
        >
          {isLoading ? 'Processing...' : 'Send Request'}
        </button>
      </form>
    </div>
  )
}

export default InputForm
