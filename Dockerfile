# 使用官方的 Python 精简镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 拷贝 requirements 文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝所有代码文件到容器中
COPY . .

# 设置容器启动时运行的命令
CMD ["python", "bot.py"]

