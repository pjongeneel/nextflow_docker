FROM phusion/baseimage:0.11

# Install debian dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    default-jre=2:1.11-68ubuntu1~18.04.1 \
    python3-minimal=3.6.7-1~18.04 \
    python3-pip=9.0.1-2.3~ubuntu1.18.04.1 \
    python3-setuptools=39.0.1-2 \
    wget=1.19.4-1ubuntu2.2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install python dependencies 
RUN python3 -m pip install pip --upgrade \
    && python3 -m pip install boto3 --upgrade

# Install Nextflow executable
WORKDIR /home
RUN wget -qO- https://get.nextflow.io | bash \
    && mv nextflow /usr/local/bin

# Copy Nextflow wrapper script
COPY nextflow.py /home/nextflow.py
COPY S3Manager.py /home/S3Manager.py

# Define container entry point
ENTRYPOINT ["python3 /home/nextflow.py"]
CMD ["--help"]
