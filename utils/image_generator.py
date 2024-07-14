import io
import random
from typing import Tuple

from config import settings
from workers.random_tags_worker import TagSource, RandomTags
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


class A1111ApiWorker:
    def __init__(self):
        self.stable_diffusion_worker = StableDiffusion(settings["a1111_point.url"],
                                                       (settings["a1111_point.login"],
                                                        settings["a1111_point.password"]))
        self.current_model_name: str = ""
        self.current_model_type: TagSource = TagSource.danbooru
        self.current_model_count = 0
        self.checkpoint_list = []

        for e621_model in settings["a1111_config.e621_models"]:
            self.checkpoint_list.append((e621_model, TagSource.e621))

        for e621_model in settings["a1111_config.danbooru_models"]:
            self.checkpoint_list.append((e621_model, TagSource.danbooru))

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
        self.current_model_count = settings["a1111_config.images_per_model"]
        logger.info(f'change model to {model_name}, type {model_type}')

    def get_queue_count(self) -> int:
        result = self.stable_diffusion_worker.progress()
        return result["state"]['job_count']

    def get_progress(self) -> Tuple[int, int]:
        result = self.stable_diffusion_worker.progress()
        return result["progress"], result["eta_relative"]

    def generate_image(self, prompt: str, negative_prompt: str, count_to_generate=1) -> list[SDImage]:
        self.change_checkpoint()

        # TODO style promt random select
        # TODO get random seed from yebi.su?

        # I think is bad logic? When random inside
        static_positive_tags = settings[f"static_positive_tags.{self.current_model_type.value}"]
        static_negative_tags = settings[f"static_negative_tags.{self.current_model_type.value}"]

        pos_prompt = f"""{static_positive_tags} BREAK {prompt}"""

        neg_prompt = f"""{static_negative_tags},{settings["static_negative_tags.all"]} BREAK {negative_prompt}"""

        width, height = random.choice(settings["a1111_config.sizes_list"]).split("x")  # TODO format cheks

        data_dict = {
            "width": width,
            "height": height,
            "prompt": pos_prompt,
            "negative_prompt": neg_prompt,
            "sampler_name": random.choice(settings["a1111_config.samplings_methods"]),
            "scheduler": random.choice(settings["a1111_config.schedulers_methods"]),
            "denoising_strength": settings["a1111_config.denoising_strength"],
            "steps": settings["a1111_config.steps"],
            "hr_second_pass_steps": settings["a1111_config.hr_second_pass_steps"],
            "enable_hr": settings["a1111_config.enable_hr"],
            "hr_scale": settings["a1111_config.hr_scale"],
            "cfg_scale": settings["a1111_config.cfg_scale"],
            "batch_size": count_to_generate,
            "restore_faces": False
        }

        # logger.info(f"start gen image by {width}x{height}}")

        info, images = self.stable_diffusion_worker.generate(**data_dict)

        result_images = []

        for seed, image_info, image_bytes in zip(info["all_seeds"], info["infotexts"], images):
            _, _, ratings, _, general_tags = self.image_tagger.get_image_marks(io.BytesIO(image_bytes))
            result_images.append(SDImage(seed, image_info, image_bytes, self.current_model_name, ratings, general_tags))
            self.current_model_count -= 1

        return result_images


if __name__ == "__main__":
    api1111_worker = A1111ApiWorker()
    for _ in range(50):
        if api1111_worker.current_model_type is TagSource.danbooru:
            rt = RandomTags("../tags_files/tags-13-07-2024.danbooru.csv")
            artist_tags = rt.get_random_tags(n=4)
            artist_tags = [tag.name for tag in artist_tags]
        else:
            rt = RandomTags("../tags_files/tags-21-05-2024.e621.csv")
            rta = RandomTags("../tags_files/tags-21-05-2024.artists.e621.csv")
            artist_tags = rta.get_random_tags(n=4)
            artist_tags = [f"by {tag.name}" for tag in artist_tags]

        tags = rt.get_random_tags(64)
        tags = [tag.name for tag in tags]
        promt = f"{','.join(artist_tags)} BREAK {','.join(tags)}"

        images = api1111_worker.generate_image(promt, "", 1)

        for i, image in enumerate(images):
            if not image.is_safe():
                continue
            with open(f"../test_images_folder/image-{image.seed}.png", "wb") as file:
                print(image.info_text)
                file.write(image.image_bytes)
