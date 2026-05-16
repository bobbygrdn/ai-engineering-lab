import './App.css'
import { useEffect, useState} from 'react';
import { backendHeartbeat } from './api';

function App() {
  const [heartbeat, setHeartbeat] = useState(null);

  useEffect(() => {
    const fetchHeartbeat = async () => {
      try {
        const data = await backendHeartbeat();
        setHeartbeat(data);
      } catch (error) {
        console.error('Error fetching backend heartbeat:', error);
      }
    };

    fetchHeartbeat();
  }, []);

  return (
    <>
      <h1>Welcome to the frontend!</h1>
      {heartbeat && <p>Backend heartbeat: {JSON.stringify(heartbeat)}</p>}
    </>
  )
}

export default App
