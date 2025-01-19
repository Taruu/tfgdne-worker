import io
import json
import random
import time
from sched import scheduler
from typing import Tuple

from config import settings
from workers.comfy_worker import Comfy
from workers.random_utils import TagSource, RandomTags
from workers.stable_difusion_a1111_worker import StableDiffusion
from loguru import logger

from workers.wdv3_jax_worker import ImageTaggerWorker


class SDImage:
    def __init__(self, seed: int, info_text: str, image_bytes: bytes, model_name: str, ratings: dict,
                 general_tags: dict):
        self.seed = seed
        self.info_text = info_text
        self.image_bytes = image_bytes
        self.model_name = model_name
        # {'general': 0, 'sensitive': 0, 'questionable': 0, 'explicit': 0}
        self.ratings = ratings
        self.general_tags = general_tags

    def is_safe(self):
        value = self.ratings.get("questionable") + self.ratings.get("explicit")
        return not (value > 0.55)


class ComfyApiWorker:
    def __init__(self):
        self.comfy_worker = Comfy(settings["comfy_point"], settings["token"])
        self.current_model_name = {}
        self.checkpoint_list = []

        for model in settings.get("models"):
            if not "comfy_workflow" in model:
                continue
            comfy_workflow = self._read_workflow(model["name"])
            model_with_workflow = model
            model_with_workflow["comfy_workflow"] = comfy_workflow
            self.checkpoint_list.append(model_with_workflow)

        if not len(self.checkpoint_list):
            raise Exception("No any config for comfy workflow")

        self.current_model_name = random.choice(self.checkpoint_list)

    def _read_workflow(self, name: str) -> dict:
        with open(f"{settings['comfy_api_config']['workflow_folder']}/{name}.json") as file:
            return json.load(file)

    def change_checkpoint(self):
        self.current_model_name = random.choice(self.checkpoint_list)

    def get_progress(self):

        pass

    def generate_image(self, prompt: str, negative_prompt: str, artist_prompt: str, count_to_generate=1) -> list[
        SDImage]:

        current_status = self.comfy_worker.get_queue()
        while (len(current_status['queue_running']) > 0) or (len(current_status['queue_pending']) > 0):
            has_sleep = True
            current_status = self.comfy_worker.get_queue()
            logger.info(f'Comfy used now. Go to sleep')
            time.sleep(settings["comfy_api_config.time_to_sleep_if_has_usage"])


class A1111ApiWorker:
    def __init__(self):
        self.stable_diffusion_worker = StableDiffusion(settings["a1111_point.url"],
                                                       (settings["a1111_point.login"],
                                                        settings["a1111_point.password"]))
        self.current_model_name: str = ""
        self.current_model_type: TagSource = TagSource.danbooru
        self.current_model_count = 0
        self.checkpoint_list = []

        for model_info in settings["models"]["list"]:
            self.checkpoint_list.append((model_info["name"], model_info["tags_type"]))

        self.change_checkpoint()

        self.image_tagger = ImageTaggerWorker()

        logger.info(f'connect to server {settings["a1111_point.url"]}')

    def change_checkpoint(self):
        if self.current_model_count > 0:
            return
        model_name, model_type = random.choice(self.checkpoint_list)

        self.stable_diffusion_worker.set_checkpoint(model_name)
        self.current_model_name = model_name
        self.current_model_type = model_type
        self.current_model_count = settings["models.images_per_model"]
        logger.info(f'change model to {model_name}, type {model_type}')

    def get_queue_count(self) -> int:
        result = self.stable_diffusion_worker.progress()
        return result["state"]['job_count']

    def get_progress(self) -> Tuple[int, int]:
        result = self.stable_diffusion_worker.progress()
        return result

    def generate_image(self, prompt: str, negative_prompt: str, artist_prompt: str, count_to_generate=1) -> list[
        SDImage]:
        self.change_checkpoint()

        # TODO style promt random select
        # TODO get random seed from yebi.su?

        # I think is bad logic? When random inside
        static_positive_tags = settings[f"static_positive_tags.{self.current_model_type.value}"]
        static_negative_tags = settings[f"static_negative_tags.{self.current_model_type.value}"]

        pos_prompt = f"{artist_prompt} BREAK {static_positive_tags}, {prompt}"

        neg_prompt = f"{static_negative_tags}, {settings['static_negative_tags.all']}, {negative_prompt}"

        width, height = random.choice(settings["a1111_api_config.sizes_list"]).split("x")  # TODO format cheks

        data_dict = {
            "width": width,
            "height": height,
            "prompt": pos_prompt,
            "negative_prompt": neg_prompt,
            "sampler_name": random.choice(settings["models_samplers"].values()),
            "scheduler": random.choice(settings["models_shedulers"].values()),
            "denoising_strength": settings["a1111_api_config.denoising_strength"],
            "steps": settings["a1111_api_config.steps"],
            "hr_second_pass_steps": settings["a1111_api_config.hr_second_pass_steps"],
            "enable_hr": settings["a1111_api_config.enable_hr"],
            "hr_scale": settings["a1111_api_config.hr_scale"],
            "cfg_scale": settings["a1111_api_config.cfg_scale"],
            "batch_size": count_to_generate,
            "restore_faces": False
        }

        # logger.info(f"start gen image by {width}x{height}}")
        has_sleep = False
        current_status = self.stable_diffusion_worker.progress()
        while (current_status['state']['job_count'] > 0) or (current_status['eta_relative'] > 0):
            has_sleep = True
            current_status = self.stable_diffusion_worker.progress()
            logger.info(f'SD used now. Go to sleep')
            time.sleep(settings["a1111_api_config.time_to_sleep_if_has_usage"])

        if has_sleep:
            self.current_model_count = 0
            self.change_checkpoint()

        info, images = self.stable_diffusion_worker.generate(**data_dict)

        result_images = []

        for seed, image_info, image_bytes in zip(info["all_seeds"], info["infotexts"], images):
            _, _, ratings, _, general_tags = self.image_tagger.get_image_marks(io.BytesIO(image_bytes))
            result_images.append(SDImage(seed, image_info, image_bytes, self.current_model_name, ratings, general_tags))
            self.current_model_count -= 1

        return result_images
