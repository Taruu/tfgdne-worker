import time

from config import settings
from utils.image_generator import A1111ApiWorker
from utils.post_image import SzurubooruPoster
from utils.prompt_generator import PromptGen
from workers.random_tags_worker import TagSource, RandomTags

prompt_gen_danbooru = PromptGen(TagSource.danbooru)
prompt_gen_e621 = PromptGen(TagSource.e621)
image_gen = A1111ApiWorker()
imageboard_poster = SzurubooruPoster()

tags_gens = {
    TagSource.danbooru: {
        'general': RandomTags(settings["tags_files.danbooru_file"]),
        'artists': RandomTags(settings["tags_files.danbooru_artist_file"])
    },
    TagSource.e621: {
        'general': RandomTags(settings["tags_files.e621_file"]),
        'artists': RandomTags(settings["tags_files.e621_artist_file"])
    }
}

while True:
    current_type = image_gen.current_model_type
    tags = tags_gens[current_type]['general'].get_random_tags(settings["tags.quantity_random_tags"])
    artist_tags = tags_gens[current_type]['artists'].get_random_tags(
        settings["tags.quantity_random_artists"])

    if current_type is TagSource.danbooru:
        artist_tags = [tag.name for tag in artist_tags]
    elif current_type is TagSource.e621:
        artist_tags = [f"by {tag.name}" for tag in artist_tags]

    tags = [tag.name for tag in tags]

    prompt = f"{', '.join(tags)}"
    artist_prompt = f"{', '.join(artist_tags)}"
    # TODO negative promt generator

    try:
        images = image_gen.generate_image(prompt, "", artist_prompt, 1)
        for image in images:
            imageboard_poster.post_image(image)
        time.sleep(1)
    except Exception:
        time.sleep(1)
