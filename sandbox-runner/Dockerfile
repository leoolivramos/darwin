FROM maven:3.9-eclipse-temurin-21

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 python3-venv tar \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global --add safe.directory '*' \
    && python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sandbox_runner.py .

RUN mkdir -p /work
EXPOSE 9091
CMD ["uvicorn", "sandbox_runner:app", "--host", "0.0.0.0", "--port", "9091"]
