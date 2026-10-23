import base64
import requests
import time

# dify 密钥
api_key = "app-wzRAbuWYxm9WiyY6fpQzA7Cu"
user = "howsoGQ@qq.com"
upload_url = "http://robot.yun36.com:8066/v1/files/upload"
chat_url = "http://robot.yun36.com:8066/v1/chat-messages"


def upload_image_to_dify(image_path='demo_pic.png'):
    files = {
        "file": ("demo_pic.png", open("demo_pic.png", "rb"), "image/[png|jpeg|jpg|webp|gif]")
    }
    data = {
        "user": user
    }
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    resp = requests.post(upload_url, headers=headers, files=files, data=data)
    return resp.json().get("id")


def chat_with_dify(question='请用 30 字以内分析你看到的', image_path=''):
    s1_time = time.time()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if image_path != '':
        image_id = upload_image_to_dify(image_path)
        s2_time = time.time()
        print(f"图片上传完成耗时: {s2_time - s1_time:.2f}秒")
        files_val = [
            {
                "type": "image",
                "transfer_method": "local_file",
                "upload_file_id": image_id
                # "url": "https://cloud.dify.ai/logo/logo-site.png"
            }
        ]
    else:
        files_val = []
    payload = {
        "inputs": {},  # 可以留空，或者传其他上下文
        "query": question,
        "response_mode": "blocking",
        "conversation_id": "",  # 如果是新会话可以留空
        "user": user,
        "files": files_val
    }
    # 发送请求
    s3_time = time.time()
    resp = requests.post(chat_url, headers=headers, json=payload)
    s4_time = time.time()
    print(resp.json().get("answer",'请求出错'))
    print(f"请求完成耗时: {s4_time - s3_time:.2f}秒")
    print(f"总耗时: {s4_time - s1_time:.2f}秒")

if __name__ == '__main__':
    # chat_with_dify(question='请用 30 字以内分析你看到的',image_path='demo_pic.png')
    chat_with_dify(question='苏超最近的比赛', image_path='')
