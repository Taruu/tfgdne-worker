from config import settings
from utils.image_generator import AIImage
from workers.szurubooru_post_worker import SzurubooruApi
from loguru import logger


class DanbooruPoster:
    def __init__(self):
        pass


class SzurubooruPoster:
    def __init__(self):
        self.szurubooru_api = SzurubooruApi(settings["szurubooru.url"], settings["szurubooru.login"],
                                            settings["szurubooru.password"])
        self.max_images = settings["imagebouard_config.max_images"]
        pass

    def _get_total_posts_count(self):
        result = self.szurubooru_api.list_posts(0, 1, "")
        return result.get('total')

    def _remove_posts_out_limits(self):
        total_posts = self._get_total_posts_count()
        posts_to_remove_count = total_posts - self.max_images
        logger.info(f"need remove {posts_to_remove_count} posts")
        while posts_to_remove_count > 0:
            posts_to_remove = self.szurubooru_api.list_posts(self.max_images, 16, "").get("results")
            for post in posts_to_remove:
                post_id = post.get('id')
                version = post.get('version')
                result = self.szurubooru_api.delete_post(post_id, version=version)
                posts_to_remove_count -= 1

    def post_image(self, ai_image: AIImage):
        if not ai_image.is_safe():
            return None

        post_tags = list(ai_image.general_tags.keys())
        post_tags.append(ai_image.model_name)

        safety = "safe" if ai_image.ratings.get("general") > ai_image.ratings.get("sensitive") else "sketchy"

        post = self.szurubooru_api.upload(content=ai_image.image_bytes, tags=post_tags, safety=safety)
        new_post_id = post.get("id")

        if not post:
            return None
        logger.info(f"post image id {new_post_id} with tags {post_tags}, and safety {safety}")

        if len(ai_image.info_text):
            self.szurubooru_api.comment(ai_image.info_text, new_post_id)
        else:
            self.szurubooru_api.comment("Look in source file to get all metadata about generated image", new_post_id)

        if self._get_total_posts_count() > self.max_images:
            self._remove_posts_out_limits()
