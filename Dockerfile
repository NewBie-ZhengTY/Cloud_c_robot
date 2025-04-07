# Use official Python slim image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code files into the container
COPY . .

# Set the command to run when the container starts
CMD ["python", "bot.py"]


