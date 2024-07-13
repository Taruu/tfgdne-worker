import random
from typing import Tuple

from config import settings
from workers.random_tags_worker import TagSource
from workers.stable_difusion_a1111_worker import StableDiffusion
from loguru import logger


class A1111ApiWorker:
    def __init__(self):
        self.stable_diffusion_worker = StableDiffusion(settings["a1111_config.url"],
                                                       (settings["a1111_config.login"],
                                                        settings["a1111_config.password"]))
        self.current_model_type: TagSource = TagSource.danbooru
        self.current_model_count = 0
        self.checkpoint_list = []

        for e621_model in settings["a1111_config.e621_models"]:
            self.checkpoint_list.append((e621_model, TagSource.e621))

        for e621_model in settings["a1111_config.danbooru_models"]:
            self.checkpoint_list.append((e621_model, TagSource.danbooru))

        self.change_checkpoint()

        logger.info(f'connect to server {settings["a1111_config.url"]}')

    def change_checkpoint(self):
        if self.current_model_count > 0:
            return
        model_name, model_type = random.choice(self.checkpoint_list)

        self.stable_diffusion_worker.set_checkpoint(model_name)
        self.current_model_type = model_type
        self.current_model_count = settings["a1111_config.images_per_model"]
        logger.info(f'change model to {model_name}, type {model_type}')

    def get_queue_count(self) -> int:
        result = self.stable_diffusion_worker.progress()
        return result["state"]['job_count']

    def get_progress(self) -> Tuple[int, int]:
        result = self.stable_diffusion_worker.progress()
        return result["progress"], result["eta_relative"]

    def generate_image(self, prompt: str, negative_prompt: str) -> Tuple[bytes, str]:
        self.change_checkpoint()
        # TODO select random source

        static_positive_tags = settings[f"static_positive_tags.{self.current_model_type}"]
        static_negative_tags = settings[f"static_negative_tags.{self.current_model_type}"]

        pos_prompt = f"""
        {static_positive_tags}, {settings["static_positive_tags.all"]}
        BREAK
        {prompt}
        BREAK
        """

        neg_prompt = f"""
        {negative_prompt}
        BREAK
        {static_negative_tags}
        BREAK
        {settings["static_negative_tags.all"]}
        """

        # I think is bad logic? When random inside
        data_dict = {
            "prompt": pos_prompt,
            "negative_prompt": neg_prompt,
            "sampler_name": random.choice(settings["a1111_config.samplings_methods"]),
            "scheduler": random.choice(settings["a1111_config.schedulers_methods"]),
            "denoising_strength": settings["a1111_config.all"],
            "steps": settings["a1111_config.steps"],
            "hr_second_pass_steps": settings["a1111_config.hr_second_pass_steps"],
            "enable_hr": settings["a1111_config.enable_hr"],
            "hr_scale": settings["a1111_config.hr_scale"],
            "cfg_scale": settings["a1111_config.cfg_scale"]
        }

        info, images = self.stable_diffusion_worker.generate(data_dict)
        print(info["infotexts"])
