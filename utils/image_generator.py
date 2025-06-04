import copy
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


class AIImage:
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
        self.comfy_worker = Comfy(settings["comfy_point"]["url"], settings["comfy_point"]["token"])
        self.current_model_info = {}
        self.current_model_count = 0
        self.checkpoint_list = []
        self.current_status = {}

        for model in settings["models"]["list"]:
            if not "comfy_workflow" in model:
                continue
            model = dict(model)
            comfy_workflow = self._read_workflow(model["name"])

            model.update({"comfy_workflow": comfy_workflow, "tags_type": TagSource(model.get("tags_type"))})
            self.checkpoint_list.append(model)

        if not len(self.checkpoint_list):
            raise Exception("No any config for comfy workflow")

        self.current_model_info = random.choice(self.checkpoint_list)

        self.image_tagger = ImageTaggerWorker()
        logger.info(f'connect to server {settings["comfy_point.url"]}')
        logger.info(f"use model {self.current_model_info.get('name')}")

    def _read_workflow(self, name):
        with open(f"{settings['comfy_api_config']['workflow_folder']}/{name}.json") as file:
            return json.load(file)

    def _fill_workflow(self, workflow: dict, positive_prompt: str, negative_prompt: str, seed: int):
        local_workflow = copy.deepcopy(workflow)
        positive_block_id = None
        negative_block_id = None

        for key, value in local_workflow.items():
            if "inputs" in value:
                if "cfg" in value["inputs"]:
                    local_workflow[key]["inputs"]["cfg"] = settings["comfy_api_config"]["cfg_scale"]
                if "seed" in value["inputs"]:
                    local_workflow[key]["inputs"]["seed"] = seed
                if "sampler_name" in value["inputs"]:
                    local_workflow[key]["inputs"]["sampler_name"] = random.choice(
                        list(settings["models_samplers"].keys()))
                if "scheduler" in value["inputs"]:
                    local_workflow[key]["inputs"]["scheduler"] = random.choice(
                        list(settings["models_shedulers"].keys()))

                # look at titlename to know is input or dummy item
                if "positive_input" == value["_meta"]["title"]:
                    positive_block_id = key
                if "negative_input" == value["_meta"]["title"]:
                    negative_block_id = key

                # if "positive" in value["inputs"]:
                #     positive_block_id = local_workflow[key]["inputs"]["positive"][0]
                # if "negative" in value["inputs"]:
                #     negative_block_id = local_workflow[key]["inputs"]["negative"][0]

                if ("width" in value["inputs"]) and ("height" in value["inputs"]):
                    width, height = random.choice(settings["models"]["sizes_list"]).split("x")
                    local_workflow[key]["inputs"]["width"] = int(width)
                    local_workflow[key]["inputs"]["height"] = int(height)

        if not negative_block_id and not positive_block_id:
            raise Exception(f"Where is text prompt?")

        local_workflow[positive_block_id]["inputs"]["text"] += positive_prompt
        local_workflow[negative_block_id]["inputs"]["text"] += negative_prompt

        return local_workflow

    def change_checkpoint(self):
        if self.current_model_count > 0:
            return
        self.current_model_info = random.choice(self.checkpoint_list)
        self.current_model_count = settings["models.images_per_model"]
        logger.info(f"use model {self.current_model_info.get('name')}")

    def get_progress(self):
        return self.current_status
        pass

    def generate_image(self, prompt: str, negative_prompt: str, artist_prompt: str) -> list[
        AIImage]:
        logger.info("Generate image by comfy api")
        self.change_checkpoint()
        static_positive_tags = settings[f"static_positive_tags.{self.current_model_info.get('tags_type').value}"]

        static_negative_tags = settings[f"static_negative_tags.{self.current_model_info.get('tags_type').value}"]

        current_workflow = self._read_workflow(self.current_model_info.get("name"))

        generate_workflow = self._fill_workflow(current_workflow, f"{static_positive_tags},{prompt},{artist_prompt}",
                                                f"{static_negative_tags},{negative_prompt}",
                                                random.randint(1, 4294967294))

        self.current_status = self.comfy_worker.get_queue()

        while (len(self.current_status['queue_running']) > 0) or (len(self.current_status['queue_pending']) > 0):
            self.current_status = self.comfy_worker.get_queue()
            logger.info(f'Comfy used now. Go to sleep')
            time.sleep(settings["comfy_api_config.time_to_sleep_if_has_usage"])

        queue_result = self.comfy_worker.queue_workflow(generate_workflow)
        prompt_id = queue_result.get("prompt_id")
        images = self.comfy_worker.get_images_from_prompt(prompt_id)
        if len(images) > 1:
            raise Exception(f"Fix comfy workflow {self.current_model_info.name} to many image output")
        images = [image[0] for image in images.values()]
        image_bytes = images[0]
        _, _, ratings, _, general_tags = self.image_tagger.get_image_marks(io.BytesIO(image_bytes))

        image = AIImage(0, "", image_bytes, self.current_model_info.get("name"), ratings, general_tags)
        self.current_model_count -= 1

        return [image]


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
        AIImage]:
        logger.info("Generate image by A1111 api")
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
            result_images.append(AIImage(seed, image_info, image_bytes, self.current_model_name, ratings, general_tags))
            self.current_model_count -= 1

        return result_images
