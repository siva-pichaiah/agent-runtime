FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get install -y \
    git curl jq && rm -rf /var/lib/apt/lists/*

# Install OpenAI SDK (or Codex CLI if you're using it)
RUN pip install openai boto3 requests

WORKDIR /app

COPY agent.py /app/agent.py

CMD ["python", "/app/agent.py"]