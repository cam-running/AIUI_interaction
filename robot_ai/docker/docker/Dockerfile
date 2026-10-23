# 多模态智能机器人系统Docker镜像
#FROM python:3.10-slim
FROM --platform=linux/arm64 python:3.10
#ARG http_proxy
#ARG https_proxy

# 设置工作目录
WORKDIR /app
# 配置国内镜像源以提高下载速度
RUN echo "deb https://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ bullseye-backports main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list

# 安装系统依赖和 Git
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    cmake \
    libffi-dev \
    python3-dev \
    pkg-config \
    libopencv-dev \
    python3-opencv \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    git \
    curl \
    vim \
    supervisor \
    sox \
    libsox-fmt-all \
    alsa-utils \
    ffmpeg \
    libavcodec-extra \
    && rm -rf /var/lib/apt/lists/*

# 设置Python环境变量
ENV PYTHONPATH=/app:/home/ict:/home/admin/Redcse
ENV PYTHONUNBUFFERED=1

# 配置 pip 使用阿里云镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

# 设置 Git 默认用户信息
RUN git config --global user.name "zhaoyong" && \
    git config --global user.email "77912776@qq.com"

# 创建必要目录
RUN mkdir -p /home/ict /home/admin/Redcse logs static/images config


# 下载代码仓库
RUN cd /home/ict && \
    git clone -b 2025-06-19-xueyang-dev https://15638557827:7893ac1253a2c37314d95c86674bb9ed@gitee.com/latux/server_tts.git && \
    git clone https://15638557827:7893ac1253a2c37314d95c86674bb9ed@gitee.com/latux/face_voice_0.git face_voice && \
    git clone -b dev-torjean https://15638557827:7893ac1253a2c37314d95c86674bb9ed@gitee.com/latux/robot_ai.git
#    cd /home/admin && \
#    git clone https://15638557827:7893ac1253a2c37314d95c86674bb9ed@gitee.com/latux/Redcse.git

# 复制主应用代码
COPY . /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt || { echo "pip install failed"; exit 1; }


# 拷贝 Redcse 项目到目标目录
RUN cp -r /home/ict/face_voice/Redcse /home/admin/

# 拷贝音频测试文件并赋予权限
RUN cp -r /home/ict/server_tts/server_ziqidong/mp3 /home/ict/
RUN chmod -R 777 /home/ict

# 复制启动脚本和配置文件
COPY docker/docker/start_robot_services.sh /app/start_robot_services.sh
COPY docker/docker/supervisor_robot_services.conf /etc/supervisor/conf.d/robot_services.conf

# 设置权限
#RUN chmod +x scripts/robot.sh || true && \
#    chmod +x /app/start_robot_services.sh
RUN chmod +x /app/start_robot_services.sh

# 环境变量设置完成

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令 - 使用自定义启动脚本
CMD ["/app/start_robot_services.sh"]
#CMD ["bash"]