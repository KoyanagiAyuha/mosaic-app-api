FROM public.ecr.aws/lambda/python:3.9

COPY lambda_function.py /var/task/

COPY requirements.txt .
RUN pip3 install -r requirements.txt --target "/var/task/"

ENV OPENCV_VERSION=4.5.0

CMD [ "lambda_function.lambda_handler" ]