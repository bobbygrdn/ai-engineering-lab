FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime

WORKDIR /code

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

COPY ./app /code/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]