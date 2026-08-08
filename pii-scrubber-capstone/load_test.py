import asyncio
import aiohttp
import time

# The target URL of your local FastAPI container
URL = "http://localhost:8000/v1/redact" # Update if your endpoint route is different

# The messy medical data payload
PAYLOAD = {
    "text": "Patient Sarah Jenkins (DOB: 08/14/1982) was admitted to Cedar Sinai Hospital by Dr. Robert Chen. Please forward her labs to r.chen@cedarsinai.org or call 555-0199."
}

# The number of simultaneous users hitting the server
CONCURRENT_REQUESTS = 100

async def fetch(session, request_id):
    """Sends a single request and tracks the time and status."""
    start_time = time.time()
    try:
        async with session.post(URL, json=PAYLOAD, timeout=30) as response:
            status = response.status
            await response.read() # Wait for the full response body
            latency = time.time() - start_time
            return {"id": request_id, "status": status, "latency": latency}
    except Exception as e:
        latency = time.time() - start_time
        return {"id": request_id, "status": "ERROR", "error": str(e), "latency": latency}

async def main():
    print(f"🚀 Firing {CONCURRENT_REQUESTS} simultaneous requests at {URL}...")
    
    # We use a single session connection pool for all requests
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        
        # Create a list of 100 pending tasks
        tasks = [fetch(session, i) for i in range(CONCURRENT_REQUESTS)]
        
        # asyncio.gather fires them all concurrently
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time

    # Tally up the results
    successes = [r for r in results if r["status"] == 200]
    failures = [r for r in results if r["status"] != 200]
    
    if successes:
        avg_latency = sum(r["latency"] for r in successes) / len(successes)
    else:
        avg_latency = 0

    print("\n📊 --- LOAD TEST RESULTS ---")
    print(f"Total Wall-Clock Time: {total_time:.2f} seconds")
    print(f"Successful Requests:   {len(successes)}")
    print(f"Failed/Timeouts:       {len(failures)}")
    print(f"Average Latency:       {avg_latency:.2f} seconds per request")
    
    if failures:
        print("\n⚠️ Sample Error:")
        print(failures[0])

if __name__ == "__main__":
    asyncio.run(main())