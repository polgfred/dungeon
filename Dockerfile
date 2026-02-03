FROM python:3.11-slim

WORKDIR /app

# Textual UI runtime dependency.
RUN pip install --no-cache-dir textual==2.1.2

COPY src /app/src

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV TERM=xterm-256color
ENV COLORTERM=truecolor

# Runs the Textual app directly when the container starts.
CMD ["python3", "-m", "dungeon.textual_app"]
