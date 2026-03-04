# AWS Lambda Python 3.11 base image (Amazon Linux 2023, x86_64)
# This is the same environment Lambda actually runs in, so compiled
# packages like xgboost will have the correct Linux binaries.
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements first so Docker can cache this layer
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install dependencies into the Lambda task root
RUN pip install --no-cache-dir --only-binary=:all: -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy the Lambda handler
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/

# Lambda looks for: <module>.<handler_function>
CMD ["lambda_function.lambda_handler"]
