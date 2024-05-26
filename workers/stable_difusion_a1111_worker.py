import requests
from requests.auth import HTTPBasicAuth
import base64
import ujson


class StableDiffusion:
    def __init__(self, endpoint_url, credentials=None):
        self.endpoint_url = endpoint_url
        self.credentials = HTTPBasicAuth(*credentials) if credentials else None

    def post_request(self, method, **data):
        print(data)
        response = requests.post(
            f'{self.endpoint_url}/{method}',
            json=data,
            auth=self.credentials,
            timeout=1000
        )
        response_data = response.json()

        if response.status_code != 200:
            print(response_data)
            raise StableDiffusionError(response_data)

        return response_data

    def set_checkpoint(self, checkpoint_name):
        return self.post_request(
            'sdapi/v1/options',
            sd_model_checkpoint=checkpoint_name
        )

    def generate(self, prompt, **kwargs):
        response = self.post_request(
            'sdapi/v1/txt2img',
            prompt=prompt,
            **kwargs
        )
        return ujson.loads(response['info']), [
            base64.b64decode(image) for image in response['images']
        ]

    def interrogate(self, image, model):
        encoded_image = base64.b64encode(image).decode('ASCII')
        return self.post_request(
            'sdapi/v1/interrogate',
            image=encoded_image,
            model=model
        )['caption']


class StableDiffusionError(Exception):
    def __init__(self, message):
        super().__init__(message)


if __name__ == "__main__":
    stable_diffusion_worker = StableDiffusion('http://127.0.0.1:7860/', ("user", "test"))

    info, images = stable_diffusion_worker.generate("fox, girl, fennec, dress,", enable_hr=True, hr_scale=1.7,
                                                    denoising_strength=0.7, )
    print(info["infotexts"])
    for i, image in enumerate(images):
        with open(f"image{i}.png", "wb") as file:
            file.write(image)
