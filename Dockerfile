FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get install -y \
    git curl jq nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @openai/codex

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py /app/agent.py

CMD ["python", "/app/agent.py"]