import './App.css'
import { useState } from 'react';
import { streamHandleEmail } from './api';
import InputForm from './components/inputForm/InputForm';
import OutputDisplay from './components/outputDisplay/OutputDisplay';

function App() {
  const [streamingText, setStreamingText] = useState('');
  const [completedResponse, setCompletedResponse] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (emailText: string) => {
    setStreamingText('');
    setCompletedResponse(null);
    setError('');
    setIsLoading(true);

    await streamHandleEmail(
      emailText,
      (delta) => {
        setStreamingText((prev) => prev + delta);
      },
      (response) => {
        setCompletedResponse(response);
        setIsLoading(false);
      },
      (errorMsg) => {
        setError(errorMsg);
        setIsLoading(false);
      }
    );
  };

  return (
    <div className="app-container">
      <div className="app-header">
        <h1>🤖 Support Ticket MVP</h1>
        <p>Real-time AI-powered support ticket handling with streaming responses</p>
      </div>
      
      <div className="app-content">
        <InputForm onSubmit={handleSubmit} isLoading={isLoading} />
        <OutputDisplay 
          streamingText={streamingText}
          completedResponse={completedResponse}
          error={error}
          isStreaming={isLoading}
        />
      </div>
    </div>
  )
}

export default App

