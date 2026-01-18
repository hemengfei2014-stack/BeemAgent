import asyncio
import time
import aiohttp
import numpy as np
import json
import sys
import multiprocessing
import os

API_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-30B-A3B-Thinking-2507"
PROMPT = "Explain the theory of relativity in simple terms."
CONCURRENT_REQUESTS_PER_PROCESS = 4

async def send_request(session):
    start_time = time.time()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 128,
        "temperature": 0.7
    }
    try:
        async with session.post(API_URL, json=payload) as response:
            if response.status != 200:
                text = await response.text()
                # print(f"Request failed: {response.status} - {text}")
                return None, None
            data = await response.json()
            end_time = time.time()
            latency = end_time - start_time
            # tokens calculation (approx)
            if 'usage' in data:
                output_tokens = data['usage']['completion_tokens']
            else:
                output_tokens = 0
            return latency, output_tokens
    except Exception as e:
        print(f"Request error: {e}")
        return None, None

async def run_worker_async(num_requests, concurrency):
    async with aiohttp.ClientSession() as session:
        results = []
        
        # Batch execution
        for i in range(0, num_requests, concurrency):
            batch_tasks = []
            current_batch_size = min(concurrency, num_requests - i)
            for _ in range(current_batch_size):
                batch_tasks.append(send_request(session))
            
            if batch_tasks:
                batch_results = await asyncio.gather(*batch_tasks)
                results.extend(batch_results)
            
        return results

def worker_process(num_requests, concurrency):
    """Entry point for each worker process."""
    return asyncio.run(run_worker_async(num_requests, concurrency))

def generate_report(num_processes, total_requests, latencies, output_tokens, total_time):
    if not latencies:
        return f"Process Count: {num_processes} - All requests failed."

    total_tokens = sum(output_tokens)
    successful_requests = len(latencies)
    
    report = []
    report.append(f"=== Performance Report (Processes: {num_processes}) ===")
    report.append(f"Model: {MODEL}")
    report.append(f"Total Requests: {total_requests}")
    report.append(f"Successful Requests: {successful_requests}")
    report.append(f"Total Time: {total_time:.2f} s")
    report.append(f"Total Output Tokens: {total_tokens}")
    report.append(f"Throughput (req/s): {successful_requests / total_time:.2f}")
    report.append(f"Throughput (tok/s): {total_tokens / total_time:.2f}")
    report.append(f"Average Latency: {np.mean(latencies):.2f} s")
    report.append(f"P95 Latency: {np.percentile(latencies, 95):.2f} s")
    report.append("============================================\n")
    
    return "\n".join(report)

def run_benchmark(num_processes, total_requests):
    print(f"Starting benchmark with {num_processes} processes...")
    requests_per_process = total_requests // num_processes
    remainder = total_requests % num_processes
    
    process_args = []
    for i in range(num_processes):
        reqs = requests_per_process + (1 if i < remainder else 0)
        if reqs > 0:
            process_args.append((reqs, CONCURRENT_REQUESTS_PER_PROCESS))
            
    start_benchmark = time.time()
    
    with multiprocessing.Pool(processes=num_processes) as pool:
        results_list = pool.starmap(worker_process, process_args)
        
    total_time = time.time() - start_benchmark
    
    # Flatten results
    all_results = []
    for res in results_list:
        all_results.extend(res)
        
    latencies = [r[0] for r in all_results if r[0] is not None]
    output_tokens = [r[1] for r in all_results if r[1] is not None]
    
    return generate_report(num_processes, total_requests, latencies, output_tokens, total_time)

if __name__ == "__main__":
    # Define process counts to test
    process_counts = [1, 2, 4, 8]
    total_requests = 24  # Divisible by 1, 2, 4, 8
    
    all_reports = ""
    
    for p_count in process_counts:
        report = run_benchmark(p_count, total_requests)
        print(report)
        all_reports += report + "\n"
        
        # Save individual result
        with open(f"benchmark_result_p{p_count}.txt", "w") as f:
            f.write(report)
            
    # Save summary
    with open("benchmark_summary.txt", "w") as f:
        f.write(all_reports)
