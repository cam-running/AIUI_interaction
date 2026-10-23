# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   face_analysis.PY
# @Time       2025-05-28 23:20

import face_recognition
import numpy as np
import os

def load_face_encodings(image_path):
    known_face_encodings = []
    known_face_names = []
    for filename in os.listdir(image_path):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            image_file = os.path.join(image_path, filename)
            image = face_recognition.load_image_file(image_file)
            face_encoding = face_recognition.face_encodings(image)[0]
            known_face_encodings.append(face_encoding)
            known_face_names.append(filename)
    return known_face_encodings, known_face_names


def calculate_euclidean_distance(embedding1, embedding2):
    return np.linalg.norm(embedding1 - embedding2)


def find_most_similar_face(target_image_path, known_face_encodings, known_face_names):
    target_image = face_recognition.load_image_file(target_image_path)
    target_face_encoding_data = face_recognition.face_encodings(target_image)
    if not target_face_encoding_data:
        return None, None
    target_face_encoding = target_face_encoding_data[0]
    min_distance = float('inf')
    most_similar_name = None
    for i, known_face_encoding in enumerate(known_face_encodings):
        distance = calculate_euclidean_distance(target_face_encoding, known_face_encoding)
        if distance < min_distance:
            min_distance = distance
            most_similar_name = known_face_names[i]
    return most_similar_name, min_distance


if __name__ == "__main__":
    pass
