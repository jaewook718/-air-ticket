FROM python:3.12-slim
WORKDIR /app
COPY air_ticket /app/air_ticket
RUN chmod -R a+rX /app/air_ticket
ENV HOST=0.0.0.0 PORT=8000
USER 10001
EXPOSE 8000
CMD ["python", "air_ticket/main.py"]
