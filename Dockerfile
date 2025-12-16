FROM python:3.11-slim

WORKDIR /usr/app

COPY requirement_dbt_slim.txt .

RUN pip install --upgrade pip \
 && pip install --default-timeout=100 --no-cache-dir -r requirement_dbt_slim.txt

COPY . .

CMD ["dbt", "run"]
