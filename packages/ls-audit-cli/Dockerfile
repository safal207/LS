FROM python:3.11-slim

WORKDIR /opt/ls
COPY packages/ls-audit-cli ./packages/ls-audit-cli

RUN python -m pip install --no-cache-dir ./packages/ls-audit-cli

ENTRYPOINT ["ls-audit"]
CMD ["--help"]
