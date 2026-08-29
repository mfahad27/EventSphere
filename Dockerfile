FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FLASK_ENV=production
EXPOSE 5000
CMD ["python", "-m", "flask", "--app", "run:app", "run", "--host=0.0.0.0", "--port=5000"]
