from config import settings
from utils.image_generator import SDImage
from workers.szurubooru_post_worker import SzurubooruApi


class SzurubooruPoster:
    def __init__(self):
        self.szurubooru_api = SzurubooruApi(settings["szurubooru.url"], settings["szurubooru.login"],
                                            settings["szurubooru.password"])
        pass

    def post_image(self, sd_image: SDImage):
        if not sd_image.is_safe():
            return None

        post_tags = list(sd_image.general_tags.keys())
        post_tags.append(sd_image.model_name)
        safety = "safe"

        post = self.szurubooru_api.upload(content=sd_image.image_bytes, tags=post_tags, safety=safety)
        if not post:
            return None
        self.szurubooru_api.comment(sd_image.info_text, post.get('id'))
        print(post)
