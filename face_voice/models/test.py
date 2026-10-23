# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   face_v.PY
# @Time       2025-05-30 23:25

from pydantic import BaseModel


class TestItem(BaseModel):
    name: str
    data: list


if __name__ == "__main__":
    pass
