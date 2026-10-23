#!/usr/bin/env python3
import socket
import struct
import wave
import time

HOST = "127.0.0.1"
PORT = 7000

def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    print(f"connected to {HOST}:{PORT}")

    out_path = "/tmp/frontend_test_ap.wav"
    wf = wave.open(out_path, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)   # int16
    wf.setframerate(16000)

    duration_sec = 5.0
    start = time.time()
    total_samples = 0

    try:
        while time.time() - start < duration_sec:
            # 1) 读 4 字节长度
            header = read_exact(s, 4)
            (nsamples,) = struct.unpack("<I", header)

            # 2) 读 nsamples * 2 字节 PCM
            data = read_exact(s, nsamples * 2)

            wf.writeframesraw(data)
            total_samples += nsamples

        wf.writeframes(b"")  # finalize
        wf.close()
        print(f"saved {total_samples} samples to {out_path}")
    finally:
        s.close()

if __name__ == "__main__":
    main()
