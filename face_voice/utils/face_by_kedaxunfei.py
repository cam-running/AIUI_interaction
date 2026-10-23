# -*- coding: UTF-8 -*-
# @Author     zyb
# @FileName   face_by_kedaxunfei.PY
# @Time       2025-05-29 23:20

import zlib
import json
import struct
import numpy as np
import cv2
from abc import abstractmethod, ABC
from socket import socket, AF_INET, SOCK_STREAM

class ProcessStrategy(ABC):
    def makepacket(self, sid, type, content):
        size = len(content)
        temp = bytearray()
        temp.append(0xa5)
        temp.append(0x01)
        temp.append(type)
        temp.append(size & 0xff)
        temp.append((size >> 8) & 0xff)
        temp.append((size >> 16) & 0xff)
        temp.append((size >> 24) & 0xff)
        temp.append(sid & 0xff)
        temp.append((sid >> 8) & 0xff)
        temp.extend(content)
        temp.append(0x00)
        return temp

    def checkcode(self, data):
        total = sum(data)
        checkcode = (~total + 1) & 0xFF
        return checkcode

    @abstractmethod
    def process(self, client_socket, data):
        pass


class ConfirmProcess(ProcessStrategy):
    def process(self, client_socket, msg_id):
        temp = bytearray()
        temp.append(0xa5)
        temp.append(0x00)
        temp.append(0x00)
        temp.append(0x00)
        send_data = self.makepacket(msg_id, 0xff, temp)
        client_socket.send(send_data)

class AiuiMessageProcess(ProcessStrategy):
    def process(self, client_socket, data):
        if not data:
            return False, bytearray()
        try:
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            output = decompressor.decompress(data)
            output += decompressor.flush()
            return True, output
        except zlib.error as e:
            return False, bytearray()

class SocketFace:
    def __init__(self, host, queue, logger, show):
        self.client_socket = socket(AF_INET, SOCK_STREAM)
        self.server_ip_port = (host, 9090)
        self.client_socket.connect(self.server_ip_port)
        self.frame_width = 0
        self.frame_height = 0
        self.format = "jpeg"
        self.hasface = False
        self.faceinfo = None
        self.headinfo = None
        self.queue = queue
        self.logger = logger
        self.show = show
        if show:
            cv2.namedWindow("test", cv2.WINDOW_NORMAL)

    def close(self):
        self.client_socket.close()

    def recv_all(self, num_byte):
        data = b''
        while len(data) < num_byte:
            packet = self.client_socket.recv(num_byte - len(data))
            if not packet:
                return None
            data += packet
        return data

    def process(self):
        recv_data = self.recv_all(9)
        sync_head, user_id, msg_type, msg_length, msg_id = struct.unpack('<BBBIH', recv_data)
        if sync_head == 0xa5 and user_id == 0x01:
            recv_data = self.recv_all(msg_length + 1)
            if msg_type == 0x07:
                ConfirmProcess().process(self.client_socket, msg_id)
                res = json.loads(recv_data[:-1])
                self.frame_width = res["width"]
                self.frame_height = res["height"]
                self.format = "jpeg" if res["format"] == 1 else "bgr"

            if msg_type == 0x08:
                ConfirmProcess().process(self.client_socket, msg_id)
                frame = cv2.imdecode(np.frombuffer(recv_data[:-1], dtype=np.uint8), cv2.IMREAD_COLOR)
                frame = cv2.resize(frame, (self.frame_width, self.frame_height))
                if self.hasface:
                    x, y, w, h = self.headinfo['x'], self.headinfo['y'], self.headinfo['w'], self.headinfo['h']
                    face_image = frame[y:y + h, x:x + w]
                    _, face_image_buffer = cv2.imencode('.jpg', face_image)
                    face_image_data = face_image_buffer.tobytes()
                    self.queue.put({"face": face_image_data})
                if self.show and self.faceinfo:
                    x2 = self.faceinfo['x'] + self.faceinfo['w']
                    y2 = self.faceinfo['y'] + self.faceinfo['h']
                    cv2.rectangle(frame, (self.faceinfo['x'], self.faceinfo['y']), (x2, y2), (0, 255, 0), 3)
                if self.show:
                    cv2.imshow("test", frame)

            if msg_type == 0x0B:
                ConfirmProcess().process(self.client_socket, msg_id)
                res = json.loads(recv_data[:-1])
                if res.get("list"):
                    face_data = res["list"][0]
                    if face_data.get("hasFace"):
                        self.hasface = True
                        self.faceinfo = face_data["body"]
                        self.headinfo = face_data["faceInfo"]
                    else:
                        self.hasface = False
                        self.faceinfo = None
                        self.headinfo = None
                else:
                    self.hasface = False
                    self.faceinfo = None
                    self.headinfo = None


if __name__ == "__main__":
    pass
