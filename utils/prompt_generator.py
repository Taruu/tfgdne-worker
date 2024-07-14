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

    def generate_artists(self, count=2):
        return self.artist_tags.get_random_tags(count)

    def generate_prompt(self, count=32):
        return self.general_tags.get_random_tags(count)
