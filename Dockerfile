FROM python:3.9-alpine
RUN apk --update add gcc build-base
WORKDIR /app
ADD requirements.txt /app/
ADD main.py /app/
ADD lets_encrypt_cert_manager_controller /app/lets_encrypt_cert_manager_controller/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD kopf run /app/main.py
