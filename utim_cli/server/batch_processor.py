"""
Offline / Background Batch API Processor for OpenAI / DeepInfra / OpenRouter /v1/batches.

Handles:
1. Packaging multiple JSON requests into a .jsonl batch file.
2. Uploading the batch file to POST /v1/files.
3. Creating a batch job via POST /v1/batches.
4. Polling until completion and retrieving final output results.
"""

import os
import json
import time
import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("utim.batch_processor")

class BatchAPIProcessor:
    """Manages true offline /v1/batches file jobs."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepinfra.com/v1/openai"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_batch_job(self, requests_list: List[Dict[str, Any]], model_id: str) -> Optional[Dict[str, Any]]:
        """Package requests into a .jsonl batch payload and submit to POST /v1/batches."""
        jsonl_lines = []
        for idx, req_payload in enumerate(requests_list):
            item = {
                "custom_id": f"request-{idx}-{int(time.time())}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model_id,
                    "messages": req_payload.get("messages", []),
                    "max_tokens": req_payload.get("max_tokens", 1500),
                    "temperature": req_payload.get("temperature", 0.2)
                }
            }
            jsonl_lines.append(json.dumps(item))

        jsonl_content = "\n".join(jsonl_lines)
        print(f"[BATCH FILE API] Packaging {len(requests_list)} requests into .jsonl payload for model '{model_id}'...")

        # Step 1: Upload file to /v1/files
        try:
            files_url = f"{self.base_url}/files"
            file_response = requests.post(
                files_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("batch_input.jsonl", jsonl_content.encode("utf-8"), "application/jsonl")},
                data={"purpose": "batch"},
                timeout=30
            )
            if file_response.status_code != 200:
                print(f"[BATCH FILE API ERROR] Failed to upload batch file: {file_response.text}")
                return None

            file_id = file_response.json().get("id")
            print(f"✓ [BATCH FILE UPLOADED] File ID: {file_id}")

            # Step 2: Create batch job via /v1/batches
            batches_url = f"{self.base_url}/batches"
            batch_payload = {
                "input_file_id": file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h"
            }
            batch_resp = requests.post(batches_url, json=batch_payload, headers=self.headers, timeout=30)
            if batch_resp.status_code == 200:
                batch_job = batch_resp.json()
                print(f"[BATCH JOB CREATED] Job ID: {batch_job.get('id')} | Status: {batch_job.get('status')}")
                return batch_job
            else:
                print(f"[BATCH JOB CREATED ERROR]: {batch_resp.text}")
                return None

        except Exception as exc:
            print(f"[BATCH PROCESSOR EXCEPTION]: {exc}")
            return None

    def poll_and_retrieve_results(self, batch_id: str, poll_interval: float = 0.3, timeout: int = 300) -> Optional[List[Dict[str, Any]]]:
        """Poll batch job until status is completed and download output file."""
        start_time = time.time()
        batch_url = f"{self.base_url}/batches/{batch_id}"

        while time.time() - start_time < timeout:
            resp = requests.get(batch_url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                job_data = resp.json()
                status = job_data.get("status")
                print(f"⏳ [BATCH POLLING] Job ID '{batch_id}' | Status: {status}")

                if status == "completed":
                    output_file_id = job_data.get("output_file_id")
                    if output_file_id:
                        file_content_url = f"{self.base_url}/files/{output_file_id}/content"
                        content_resp = requests.get(file_content_url, headers=self.headers, timeout=30)
                        if content_resp.status_code == 200:
                            results = []
                            for line in content_resp.text.strip().splitlines():
                                if line:
                                    results.append(json.loads(line))
                            print(f"✓ [BATCH COMPLETED] Downloaded {len(results)} completed results!")
                            return results
                elif status in ["failed", "cancelled", "expired"]:
                    print(f"[BATCH JOB FAILED] Job ended with status: {status}")
                    return None

            time.sleep(poll_interval)
        
        print(f"[BATCH TIMEOUT] Reached timeout of {timeout}s waiting for job '{batch_id}'")
        return None
