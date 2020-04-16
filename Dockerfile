## First build stage
FROM phusion/baseimage:0.11 as builder

# Define arguments
ARG AWS_HELPER_VERSION

# Set environment variables
ENV AWS_HELPER_VERSION=${AWS_HELPER_VERSION}

# Install debian dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    python3-minimal=3.6.7-1~18.04 \
    python3-pip=9.0.1-2.3~ubuntu1.18.04.1 \
    wget=1.19.4-1ubuntu2.2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install AWS CLI
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install awscli --upgrade

# Install nextflow
RUN wget -qO- https://get.nextflow.io | bash

# Download AWS_HELPER module
RUN aws s3 cp s3://awshelper.module/dist/aws-${AWS_HELPER_VERSION}.tar.gz aws-helper.tar.gz

## Second stage build
FROM phusion/baseimage:0.11 as final

COPY --from=builder nextflow /usr/local/bin/nextflow
COPY --from=builder aws-helper.tar.gz aws-helper.tar.gz

# Install debian dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    default-jre=2:1.11-68ubuntu1~18.04.1 \
    git=1:2.17.1-1ubuntu0.5 \
    python3-minimal=3.6.7-1~18.04 \
    python3-pip=9.0.1-2.3~ubuntu1.18.04.1 \
    python3-setuptools=39.0.1-2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install python dependencies 
RUN python3 -m pip install pip --upgrade \
    && python3 -m pip install boto3 --upgrade \
    && python3 -m pip install GitPython --upgrade \
    && python3 -m pip install aws-helper.tar.gz

# Copy Nextflow wrapper script
COPY nextflow.py /home/nextflow.py
COPY S3Manager.py /home/S3Manager.py

# Define container entry point
ENTRYPOINT ["python3", "/home/nextflow.py"]
CMD ["--help"]
