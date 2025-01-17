import time
import uuid

import requests
from requests.auth import HTTPBasicAuth
import base64
import ujson
import websocket  # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
from urllib.parse import urlparse


class Comfy:
    def __init__(self, endpoint_url, token=None):
        self.endpoint_url = endpoint_url
        self.endpoint_url_parsed = urlparse(endpoint_url)

        self.client_id = str(uuid.uuid4())
        self.token = token

        self.websocket = websocket.WebSocket()
        self._image_timeout = 60 * 4

    def get_images_from_prompt(self, prompt_id : int):
        token = f"&token={self.token}" if self.token else ""

        self.websocket.connected(f"ws://{self.endpoint_url_parsed.netloc}/ws?clientId={self.client_id}{token}")
        end_time = time.time() + self._image_timeout
        while time.time() > end_time:
            output = self.websocket.recv()
            if isinstance(output, str):
                message = json.loads(output)
                data = message["data"]
                if (data["node"] is None) and (data["prompt_id"] ==
        self.websocket.close()
        pass

    def _method_api(self, method: str, prompt_id="", url_values="", data=None, json_result=True):
        method_string = f"{self.endpoint_url}/{method}{prompt_id}?{url_values}token={self.token}"

        request_data = urllib.request.Request(method_string)

        if data:
            request_data = urllib.request.Request(method_string, data=data)

        with urllib.request.urlopen(request_data) as response:
            if json_result:
                return json.loads(response.read())
            return response.json()

    def set_checkpoint(self, checkpoint_name):
        return self._post_request(
            'sdapi/v1/options',
            sd_model_checkpoint=checkpoint_name
        )

    def generate(self, **kwargs):
        """sdapi/v1/txt2img"""
        response = self._post_request(
            'sdapi/v1/txt2img',
            **kwargs
        )
        return ujson.loads(response['info']), [
            base64.b64decode(image) for image in response['images']
        ]

    def progress(self):
        response = self._get_request('sdapi/v1/progress')
        return response

    def interrogate(self, image_bytes: bytes, model: str):
        encoded_image = base64.b64encode(image_bytes).decode('ASCII')
        return self._post_request(
            'sdapi/v1/interrogate',
            image=encoded_image,
            model=model
        )['caption']


class StableDiffusionError(Exception):
    def __init__(self, message):
        super().__init__(message)


if __name__ == "__main__":
    stable_diffusion_worker = StableDiffusion('http://127.0.0.1:7860/', ("user", "test"))

    info, images = stable_diffusion_worker.generate(prompt="fox, girl, fennec, dress,", enable_hr=True, hr_scale=1.7,
                                                    denoising_strength=0.7, steps=25, hr_second_pass_steps=25)
    print(info)
    print(info["infotexts"])
    for i, image in enumerate(images):
        with open(f"image{i}.png", "wb") as file:
            file.write(image)
