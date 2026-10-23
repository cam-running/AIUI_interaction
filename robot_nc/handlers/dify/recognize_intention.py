import requests
import time

from config.config.dify_config import difyconfig as dify_config

def chat_with_dify(question='你看到了什么', image_path=''):
    s1_time = time.time()
    headers = {
        "Authorization": f"Bearer {dify_config.get_recognize_api_key()}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {},  # 可以留空，或者传其他上下文
        "query": question,
        "response_mode": "blocking",
        "conversation_id": "",  # 如果是新会话可以留空
        "user": dify_config.get_user(),
    }
    # 发送请求
    try:
        s3_time = time.time()
        resp = requests.post(dify_config.get_recognize_url(), headers=headers, json=payload)
        s4_time = time.time()
        res = resp.json().get("answer", '请求出错')
        print(f"请求完成耗时: {s4_time - s3_time:.2f}秒")
        print(f"总耗时: {s4_time - s1_time:.2f}秒")
        return res
    except Exception as e:
        print(f"请求出错: {e}")
        return ''

if __name__ == '__main__':
    # chat_with_dify(question='请用 30 字以内分析你看到的',image_path='demo_pic.png')
    res = chat_with_dify(question='你看到了什么', image_path='')
    print(11111,res)