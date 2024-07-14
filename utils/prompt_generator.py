from config import settings
from workers.random_tags_worker import TagSource, RandomTags


class PromptGen:
    def __init__(self, tags_type: TagSource):
        self.tags_type = tags_type
        if tags_type is TagSource.danbooru:
            self.general_tags = RandomTags(settings["tags_files.danbooru_file"])
            self.artist_tags = RandomTags(settings["tags_files.danbooru_artist_file"])
        elif tags_type is TagSource.e621:
            self.general_tags = RandomTags(settings["tags_files.e621_file"])
            self.artist_tags = RandomTags(settings["tags_files.e621_artist_file"])
        self.quantity_random_artists = settings["tags.quantity_random_artists"]
        self.quantity_random_tags = settings["tags.quantity_random_tags"]

    def generate_artists(self):
        return self.artist_tags.get_random_tags(self.quantity_random_artists)

    def generate_prompt(self):
        return self.general_tags.get_random_tags(self.quantity_random_tags)
