import time
import uuid

import requests
import random
from requests.auth import HTTPBasicAuth
import base64
import ujson
import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
from urllib.parse import urlparse

from config import settings


class Comfy:
    def __init__(self, endpoint_url, token=None):
        self.endpoint_url = endpoint_url
        self.endpoint_url_parsed = urlparse(endpoint_url)

        self.client_id = str(uuid.uuid4())
        self.token = token

        self.websocket = websocket.WebSocket()
        self.current_status = None

        ws_token = f"&token={self.token}" if self.token else ""
        print(f"ws://{self.endpoint_url_parsed.netloc}/ws?clientId={self.client_id}{ws_token}")
        self.websocket.connect(f"ws://{self.endpoint_url_parsed.netloc}/ws?clientId={self.client_id}{ws_token}")

        self._image_timeout = 60 * 10

    def queue_workflow(self, workflow: dict):
        prompt_data = {"prompt": workflow, "client_id": self.client_id}
        prompt_data_raw = json.dumps(prompt_data).encode()
        return self._method_api("prompt", data=prompt_data_raw)

    def _get_image(self, file_info: dict):
        """Get image from server folder"""
        url_values = urllib.parse.urlencode(file_info)
        return self._method_api("api/view", url_values=url_values, json_result=False)

    def _get_history(self, prompt_id):
        return self._method_api("history", prompt_id=prompt_id)

    def get_queue(self):
        return self._method_api("queue")

    def get_images_from_prompt(self, prompt_id: int):
        end_time = time.time() + self._image_timeout
        output_images_by_node_id = {}

        while time.time() < end_time:
            output = self.websocket.recv()
            self.current_status = output
            if isinstance(output, str):
                message = json.loads(output)
                if message["type"] != 'executing':
                    continue

                data = message["data"]
                if (data["node"] is None) and (data["prompt_id"] == prompt_id):
                    break
            else:
                continue
        if time.time() > end_time:
            raise Exception("Timeout image get form prompt")

        history = self._get_history(prompt_id).get(prompt_id)

        for node_id, node_output in history.get('outputs').items():
            if "images" in node_output:
                images_output = []
                for image_info in node_output.get("images"):
                    image_data = self._get_image(image_info)
                    images_output.append(image_data)
                output_images_by_node_id[node_id] = images_output
        return output_images_by_node_id

    def __del__(self):
        self.websocket.close()

    def _method_api(self, method: str, prompt_id="", url_values="", data=None, json_result=True):

        prompt_id = prompt_id if not prompt_id else f"/{prompt_id}"
        url_values = url_values if not url_values else f"{url_values}&"

        method_string = f"{self.endpoint_url}/{method}{prompt_id}?{url_values}token={self.token}"
        request_data = urllib.request.Request(method_string)

        if data:
            request_data = urllib.request.Request(method_string, data=data)

        with urllib.request.urlopen(request_data) as response:
            if json_result:
                return json.loads(response.read())
            return response.read()


class StableDiffusionError(Exception):
    def __init__(self, message):
        super().__init__(message)


if __name__ == "__main__":
    prompt_text = """
    {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 8,
                "denoise": 1,
                "latent_image": [
                    "5",
                    0
                ],
                "model": [
                    "4",
                    0
                ],
                "negative": [
                    "7",
                    0
                ],
                "positive": [
                    "6",
                    0
                ],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": 8566257,
                "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "fluffyrock-576-704-832-960-1088-lion-low-lr-e130-terminal-snr-e103.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": 512,
                "width": 512
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "4",
                    1
                ],
                "text": "masterpiece best quality girl"
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "4",
                    1
                ],
                "text": "bad hands"
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [
                    "3",
                    0
                ],
                "vae": [
                    "4",
                    2
                ]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ComfyUI",
                "images": [
                    "8",
                    0
                ]
            }
        }
    }
    """

    comf_worker = Comfy("http://192.168.16.42:7007", settings["comfy_point"]["token"])
    print()
    print(comf_worker.get_queue())
    for key, item in comf_worker.get_queue().items():
        print(key, item)
    prompt = json.loads(prompt_text)
    # set the text prompt for our positive CLIPTextEncode
    prompt["6"]["inputs"]["text"] = "masterpiece best quality man"

    # set the seed for our KSampler node
    prompt["3"]["inputs"]["seed"] = 5
    with open("../comfy-workflows/EasyFluffV11.2.json") as file:
        prompt = json.load(file)

    seed = random.random() * 10_0000
    prompt["3"]['inputs']["seed"] = int(seed)
    prompt["39"]['inputs']["seed"] = int(seed)
    print(prompt)
    result = comf_worker.queue_workflow(prompt)
    print("resinque", result.get("prompt_id"))
    next_res = comf_worker.get_images_from_prompt(result.get("prompt_id"))
    print()
    for key, value in next_res.items():
        print(key, type(value), len(value), type(value[0]))
