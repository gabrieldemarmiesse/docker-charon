FROM python:3.9-slim

RUN --mount=source=requirements.txt,destination=/requirements.txt \
    pip install -r requirements.txt && \
    rm -rf /root/.cache/pip


COPY ./ /docker-charon
WORKDIR /docker-charon

RUN pip install -e .

ENTRYPOINT ["docker-charon"]
