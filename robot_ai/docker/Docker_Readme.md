<!--
 * @Author: zhaoyong 77912776@qq.com
 * @Date: 2025-07-09 11:08:29
 * @LastEditTime: 2025-07-11 15:27:31
 * @LastEditors: zhaoyong 77912776@qq.com
 * @FilePath: \docker\Docker_Readme.md
 * @Description: 头部注释配置模板
-->
# 机器人系统 Docker 部署指南
## 执行梯子
sudo python /home/ict/robot_ai/docker/shadowsocks/local.py -c /home/ict/robot_ai/docker/shadowsocks/config.json -d start

## 查看梯子是否生效
curl -x http://127.0.0.1:2080 http://ipinfo.io


## 执行镜像并生效
export HTTP_PROXY=http://127.0.0.1:2080
export HTTPS_PROXY=http://127.0.0.1:2080

## 生成镜像
cd /home/ict/robot_ai/docker/docker
docker compose up 

## 重新构建
docker compose up --build -d
## 挂后台
docker compose up -d 


## 创建版本镜像
docker build \
  --build-arg http_proxy= \
  --build-arg https_proxy= \
  -t robot-ai:test-0.0.1 .

docker build -t robot-ai:test-0.0.1 .

docker save rebot-ai:test-0.0.1 rebot-ai-test-0.0.1.tar


docker save -o rebot-ai-test-0.0.1.tar rebot-ai:test-0.0.1
docker load -i rebot-ai-test-0.0.1.tar
docker run -it rebot-ai:test-0.0.1
