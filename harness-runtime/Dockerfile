FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY adapters/__init__.py ./adapters/__init__.py
COPY contracts/__init__.py ./contracts/__init__.py
COPY supervisor/__init__.py ./supervisor/__init__.py
RUN python -m pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    ".[docker,service]"

COPY adapters ./adapters
COPY contracts ./contracts
COPY supervisor ./supervisor
COPY poc ./poc
COPY images ./images
RUN python -m pip install --no-deps .

EXPOSE 8790

CMD ["python", "-m", "supervisor.main"]
