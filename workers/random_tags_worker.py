import pathlib
import random
from time import time
from enum import Enum
from typing import Union
import csv
import sys
from types import ModuleType, FunctionType
from gc import get_referents

# Custom objects know their class.
# Function objects seem to know way too much, including modules.
# Exclude modules as well.
BLACKLIST = type, ModuleType, FunctionType


class TagType(Enum):
    general = 0
    artist = 1
    character = 2
    copyright = 3
    meta = 4


class TagSource(Enum):
    danbooru = "danbooru"
    e621 = "e621"


class Tag:
    def __init__(self, tag_id: int, name: str, type: int, usage_count: int):
        self.tag_id = tag_id
        self.name = name
        self.type = type
        self.usage_count = usage_count

    def __hash__(self):
        return self.name

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Tag({self.tag_id}): {self.name}, {self.type} {self.usage_count}"


class RandomTags:
    def __init__(self, path: Union[str, pathlib.Path]):
        if type(path) is str:
            self.path = pathlib.Path(path)
        else:
            self.path = path

        self.csv_type = None
        if ".e621." in self.path.name:
            self.csv_type = TagSource.e621
            self.header = "id,name,category,post_count".split(',')
            self.type_dict_convert = {0: TagType.general, 1: TagType.artist, 2: None, 3: TagType.copyright,
                                      4: TagType.character, 5: TagType.general, 6: None, 7: TagType.meta}
        elif ".danbooru." in self.path.name:
            self.csv_type = TagSource.danbooru
            self.header = "id,name,type,usage_count".split(',')
            self.type_dict_convert = {0: TagType.general, 1: TagType.artist, 2: TagType.character, 3: TagType.copyright,
                                      4: TagType.meta}
        else:
            raise Exception("Not correct file (ext)")

        self._file = open(self.path)
        self._file.seek(0)
        self.header_skip = len(self._file.readline().encode('utf-8'))

    def __del__(self):
        self._file.close()

    def get_random_tags(self, n=120):
        list_tags = []
        for _ in range(n):
            list_tags.append(self.get_random_tag())
        return list_tags

    def get_random_tag(self):
        text_line = self.get_random_line()
        tag_info_dict = {}
        for colum_name, value in zip(self.header, text_line.split(',')):
            tag_info_dict.update({colum_name: value})
        tag_id = tag_info_dict.pop("id")
        name = tag_info_dict.pop("name")

        if self.csv_type == TagSource.e621:
            e621_type = tag_info_dict.pop("category")
            tag_type = self.type_dict_convert.get(e621_type)
            tag_usage_count = tag_info_dict.pop('post_count')
        elif self.csv_type == TagSource.danbooru:
            tag_type = tag_info_dict.pop("type")
            tag_usage_count = tag_info_dict.pop('usage_count')
        else:
            tag_type = 0
            tag_usage_count = 0

        tag = Tag(tag_id, name, tag_type, tag_usage_count)
        return tag

    def get_random_line(self):
        self._file.seek(self.header_skip)
        random_offset = random.randrange(self.path.stat().st_size)

        self._file.seek(random_offset)
        self._file.readline()
        random_line = self._file.readline()

        if len(random_line) == 0:
            return self.get_random_line()
        return random_line


if __name__ == "__main__":
    rt1 = RandomTags("../tags_files/tags-21-05-2024.e621.csv")
    rt2 = RandomTags("../tags_files/tags-26-05-2023.danbooru.csv")
    start_time = time()
    print(rt1.get_random_tags())
    print(rt2.get_random_tags())
    print(time() - start_time)
