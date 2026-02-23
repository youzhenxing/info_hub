# 微信公众号订阅模块 Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源代码
COPY src/ ./src/
COPY main.py .

# 创建数据目录
RUN mkdir -p /app/data/output

# 设置入口
ENTRYPOINT ["python", "main.py"]
CMD ["scheduler"]
