# Use a small Python base image
FROM python:3.10-slim

# Avoid buffering so logs show live
ENV PYTHONUNBUFFERED=1

# Create app directory
WORKDIR /app

# Install system packages needed for some Python libs (pillow, pandas, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker caching
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code and data files
COPY . /app

# Make port variable available (Hugging Face supplies PORT)
ENV PORT=7860

# Expose the port (optional)
EXPOSE 7860

# Start Streamlit (use bash -c to expand $PORT)
CMD ["bash", "-lc", "streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"]
