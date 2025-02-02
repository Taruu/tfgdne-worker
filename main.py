import time

from numpy.ma.core import negative

from config import settings
from utils.image_generator import A1111ApiWorker, ComfyApiWorker
from utils.post_image import SzurubooruPoster
from utils.prompt_generator import PromptGen
from workers.random_utils import TagSource, RandomTags, RandomStyle

prompt_gen_danbooru = PromptGen(TagSource.danbooru)
prompt_gen_e621 = PromptGen(TagSource.e621)
image_gen = ComfyApiWorker()
imageboard_poster = SzurubooruPoster()
random_style = RandomStyle(settings["styles.folder"])

tags_generators = {
    TagSource.danbooru: {
        'general': RandomTags(settings["tags_files.danbooru_file"]),
        'artists': RandomTags(settings["tags_files.danbooru_artist_file"])
    },
    TagSource.e621: {
        'general': RandomTags(settings["tags_files.e621_file"]),
        'artists': RandomTags(settings["tags_files.e621_artist_file"])
    },
    TagSource.pony: {
        'general': RandomTags(settings["tags_files.pony_file"]),
        'artists': RandomTags(settings["tags_files.pony_artist_file"])
    },
}

while True:
    # Look into config [models][list]
    current_type = image_gen.current_model_info.get("tags_type")

    tags = tags_generators[current_type]['general'].get_random_tags(settings["tags.quantity_random_tags"])

    artist_tags = tags_generators[current_type]['artists'].get_random_tags(
        settings["tags.quantity_random_artists"])

    if (current_type is TagSource.danbooru) or (current_type is TagSource.pony):
        artist_tags = [tag.name for tag in artist_tags]
    elif current_type is TagSource.e621:
        artist_tags = [f"by {tag.name}" for tag in artist_tags]

    tags = [tag.name for tag in tags]
    pos_style, neg_style = random_style.get_random_style(current_type)

    pos_style.extend(tags)

    prompt = f"{', '.join(pos_style)}"
    artist_prompt = f"{', '.join(artist_tags)}"
    negative_prompt = f"{', '.join(neg_style)}"

    # TODO negative promt generator
    images = image_gen.generate_image(prompt, "", artist_prompt)
    for image in images:
        imageboard_poster.post_image(image)
